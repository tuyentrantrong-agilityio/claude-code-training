// Runs the <script> of webapp/index.html in Node with a fake DOM and a fake fetch,
// plays the T-03 hint scenarios and prints one JSON object of results.
// Usage: node hint_harness.js <path to index.html>
"use strict";
const fs = require("fs");
const vm = require("vm");

const html = fs.readFileSync(process.argv[2], "utf8");
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];

function response(status, body) {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return { ok: status >= 200 && status < 300, status, text: async () => text, json: async () => JSON.parse(text) };
}

// Fake server: lookups come from `minimums` (raw JSON text or a status number),
// `post` answers the POST /api/bids. A value of "defer" leaves the request pending.
function makePage({ minimums = {}, post = null, auctionId = "" } = {}) {
  const server = { minimums, post };
  const els = {};
  const el = (id) => els[id] || (els[id] = {
    id, value: id === "limit" ? "2" : id === "auction_id" ? auctionId : "",
    textContent: "", hidden: false, innerHTML: "", style: {}, listeners: {},
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    appendChild() {},
  });
  const requests = [];
  const pending = [];
  const fetch = (url, opts = {}) => {
    const method = opts.method || "GET";
    requests.push({ method, url, hintAtSend: el("min-bid-hint").textContent });
    if (url.startsWith("/api/bids?")) return Promise.resolve(response(200, { items: [], next_cursor: null }));
    if (method === "POST") {
      if (server.post === "network") return Promise.reject(new TypeError("Failed to fetch"));
      return Promise.resolve(response(server.post[0], server.post[1]));
    }
    const id = url.split("/")[3];
    const answer = server.minimums[id];
    if (answer === "defer") return new Promise((resolve) => pending.push({ id, resolve }));
    if (answer === "network") return Promise.reject(new TypeError("Failed to fetch"));
    if (typeof answer === "number") return Promise.resolve(response(answer, { error: "server error" }));
    return Promise.resolve(response(200, answer));
  };
  const ctx = {
    document: { getElementById: el, createElement: () => ({ style: {}, appendChild() {}, textContent: "" }) },
    localStorage: { getItem: () => null, setItem() {} },
    console: { log() {}, error() {} },
    fetch, JSON, BigInt, Promise, URLSearchParams, setTimeout,
  };
  vm.createContext(ctx);
  vm.runInContext(script, ctx);
  const page = {
    el, requests, pending, server,
    hint: () => el("min-bid-hint").textContent,
    lookups: () => requests.filter((r) => r.url.includes("/minimum-bid")).map((r) => r.url),
    type: async (value) => { el("auction_id").value = value; el("auction_id").listeners.input.forEach((f) => f({})); await settle(); },
    submit: async () => { el("bid-form").listeners.submit.forEach((f) => f({ preventDefault() {} })); await settle(); },
  };
  return page;
}

// A page error inside an event handler must fail one scenario, not stop the run.
const unhandled = [];
process.on("unhandledRejection", (e) => unhandled.push(String(e)));
process.on("uncaughtException", (e) => unhandled.push(String(e)));

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
const body = (highest, step, min) => `{"auction_id": 7, "highest": ${highest}, "step": ${step}, "minimum_bid": ${min}}`;

const scenarios = {
  async typed() {
    const p = makePage({ minimums: { 7: body(100, 10, 110) } });
    await p.type("7");
    return { hint: p.hint(), lookups: p.lookups() };
  },
  async noBids() {
    const p = makePage({ minimums: { 20: body(null, null, 1) } });
    await p.type("20");
    return { hint: p.hint() };
  },
  async invalid() {
    const out = {};
    for (const value of ["", "0", "abc", "1e3", "+7", "7.0", "-5", "7.5", "9223372036854775808"]) {
      const p = makePage();
      p.el("min-bid-hint").textContent = "Minimum next bid: 110";
      await p.type(value);
      out[value] = { hint: p.hint(), lookups: p.lookups().length };
    }
    return out;
  },
  async trimmed() {
    const out = {};
    for (const value of [" 007 ", "\t7\t", "9223372036854775807"]) {
      const p = makePage({ minimums: { 7: body(100, 10, 110), "9223372036854775807": body(null, null, 1) } });
      await p.type(value);
      out[value] = { hint: p.hint(), lookups: p.lookups() };
    }
    return out;
  },
  async failedLookup() {
    const out = {};
    for (const answer of [500, "network"]) {
      const p = makePage({ minimums: { 7: answer } });
      await p.type("7");
      out[answer] = p.hint();
    }
    return out;
  },
  async stale() {
    const p = makePage({ minimums: { 7: "defer", 8: "defer" } });
    await p.type("7");
    await p.type("8");
    const hintWhilePending = p.hint();
    p.pending.find((r) => r.id === "8").resolve(response(200, body(999, 10, 1009)));
    await settle();
    p.pending.find((r) => r.id === "7").resolve(response(200, body(100, 10, 110)));
    await settle();
    return { hintWhilePending, hint: p.hint() };
  },
  async cleared() {
    const p = makePage({ minimums: { 7: body(100, 10, 110) } });
    await p.type("7");
    const before = p.hint();
    await p.type("");
    return { before, after: p.hint(), lookups: p.lookups().length };
  },
  async rejected() {
    const p = makePage({ minimums: { 7: body(100, 10, 110) }, post: [409, { error: "bid must be at least 130" }] });
    await p.type("7");
    const before = p.hint();
    p.el("amount").value = "110";
    p.server.minimums[7] = body(120, 10, 130); // user 5 bid 120 meanwhile
    p.requests.length = 0;
    await p.submit();
    const refresh = p.requests.find((r) => r.url.includes("/minimum-bid"));
    return {
      before, error: p.el("error").textContent, hint: p.hint(), hintAtRefresh: refresh && refresh.hintAtSend,
      lookups: p.lookups(), amount: p.el("amount").value, auctionId: p.el("auction_id").value,
    };
  },
  async rejectedLookupFails() {
    const p = makePage({ minimums: { 7: 500 }, post: [409, { error: "bid must be at least 130" }], auctionId: "7" });
    p.el("min-bid-hint").textContent = "Minimum next bid: 110";
    await p.submit();
    return { error: p.el("error").textContent, hint: p.hint() };
  },
  async accepted() {
    const p = makePage({ minimums: { 7: body(1000, 50, 1050) }, post: [201, { id: 9 }], auctionId: "7" });
    p.el("amount").value = "1000";
    p.el("min-bid-hint").textContent = "Minimum next bid: 1000";
    await p.submit();
    return { hint: p.hint(), lookups: p.lookups(), amount: p.el("amount").value, auctionId: p.el("auction_id").value };
  },
  async otherResults() {
    const out = {};
    for (const [name, post] of [["400", [400, { error: "auction_id and amount must be integers" }]], ["500", [500, { error: "boom" }]], ["network", "network"]]) {
      const p = makePage({ minimums: { 7: body(100, 10, 110) }, post, auctionId: "7" });
      await p.submit();
      out[name] = { hint: p.hint(), lookups: p.lookups() };
    }
    return out;
  },
  async invalidIdAfterBid() {
    const p = makePage({ post: [400, { error: "auction_id and amount must be positive" }], auctionId: "0" });
    p.el("min-bid-hint").textContent = "Minimum next bid: 110";
    await p.submit();
    return { hint: p.hint(), lookups: p.lookups().length };
  },
  async onLoad() {
    const withValue = makePage({ minimums: { 7: body(100, 10, 110) }, auctionId: "7" });
    await settle();
    const empty = makePage();
    await settle();
    return { hint: withValue.hint(), lookups: withValue.lookups(), emptyLookups: empty.lookups().length };
  },
  async largeAmount() {
    const p = makePage({ minimums: { 10: body("9223372036854775800", 50, "9223372036854775850") } });
    await p.type("10");
    return { hint: p.hint() };
  },
};

(async () => {
  const results = {};
  for (const [name, run] of Object.entries(scenarios)) {
    unhandled.length = 0;
    try { results[name] = await run(); } catch (e) { results[name] = { crash: String(e && e.stack || e) }; }
    if (unhandled.length) results[name] = { crash: unhandled.join("; ") };
  }
  process.stdout.write(JSON.stringify(results));
})();
