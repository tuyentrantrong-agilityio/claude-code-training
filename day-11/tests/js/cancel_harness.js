// Runs the <script> of webapp/index.html in Node with a fake DOM and a fake fetch,
// plays the cancel scenarios and prints one JSON object of results.
// Usage: node cancel_harness.js <path to index.html>
"use strict";
const fs = require("fs");
const vm = require("vm");

const html = fs.readFileSync(process.argv[2], "utf8");
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];

function response(status, body) {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return { ok: status >= 200 && status < 300, status, text: async () => text, json: async () => JSON.parse(text) };
}

function node(tag) {
  return {
    tag, style: {}, children: [], listeners: {}, textContent: "", disabled: false,
    appendChild(child) { this.children.push(child); },
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
  };
}

// Fake server. `items` is what GET /api/bids lists (the user's bids, newest first); `others` are bids
// of other users, used only for the price lookups and the standings. `cancel` answers
// POST /api/bids/<id>/cancel: [status, body], "defer" (pending until page.answer()) or "network".
// `after`, when set, replaces `items` once a non-200 answer was given (a change made elsewhere).
// `storage` is the browser's localStorage; pass the same object to a second page to reload the browser.
function makePage({ items, others = [], cancel = null, confirmAnswer = true, after = null,
                    auctionId = "", amount = "", storage = {}, pageSize = "2", listFailsAfterPost = false }) {
  const state = { items, others, cancel, listDown: false };
  const els = {};
  const el = (id) => {
    if (!els[id]) {
      const value = id === "limit" ? pageSize : id === "auction_id" ? auctionId : id === "amount" ? amount : "";
      els[id] = Object.assign(node("el"), { id, value, hidden: false });
      if (id === "rows") Object.defineProperty(els[id], "innerHTML", { set() { this.children = []; }, get() { return ""; } });
    }
    return els[id];
  };
  const requests = [];
  const confirms = [];
  const pending = [];

  const restand = () => {
    const active = state.items.concat(state.others).filter((b) => b.status === "active");
    const top = (auction) => active.filter((b) => b.auction_id === auction)
      .sort((a, b) => b.amount - a.amount || a.id - b.id)[0];
    state.items = state.items.map((b) => ({
      ...b, standing: b.status !== "active" ? null : top(b.auction_id).id === b.id ? "winning" : "outbid",
    }));
  };
  const apply = (status, body) => {
    if (listFailsAfterPost) state.listDown = true;
    if (status === 200) {
      state.items = state.items.map((b) => (b.id === body.id ? { ...b, status: "cancelled" } : b));
      restand();
    } else if (after) state.items = after;
    return response(status, body);
  };
  const lookup = (id) => {
    const active = state.items.concat(state.others).filter((b) => b.auction_id === Number(id) && b.status === "active");
    if (!active.length) return `{"auction_id": ${id}, "highest": null, "step": null, "minimum_bid": 1}`;
    const highest = Math.max(...active.map((b) => b.amount));
    const step = highest < 1000 ? 10 : 50;
    return `{"auction_id": ${id}, "highest": ${highest}, "step": ${step}, "minimum_bid": ${highest + step}}`;
  };
  const fetch = (url, opts = {}) => {
    const method = opts.method || "GET";
    requests.push({ method, url });
    if (method === "POST" && url === "/api/bids") return Promise.resolve(response(201, { id: 9 }));
    if (method === "POST") {
      if (state.cancel === "network") return Promise.reject(new TypeError("Failed to fetch"));
      if (state.cancel === "defer") return new Promise((resolve) => pending.push(resolve));
      return Promise.resolve(apply(...state.cancel));
    }
    if (url.includes("/minimum-bid")) return Promise.resolve(response(200, lookup(url.split("/")[3])));
    if (state.listDown) return Promise.reject(new TypeError("Failed to fetch"));
    const query = new URLSearchParams(url.split("?")[1]);
    const limit = Number(query.get("limit"));
    const from = Number(query.get("cursor") || 0);
    const next = from + limit < state.items.length ? String(from + limit) : null;
    return Promise.resolve(response(200, { items: state.items.slice(from, from + limit), next_cursor: next }));
  };
  const ctx = {
    document: { getElementById: el, createElement: node },
    localStorage: { getItem: (k) => (k in storage ? storage[k] : null), setItem: (k, v) => { storage[k] = String(v); } },
    console: { log() {}, error() {} },
    confirm: (text) => { confirms.push(text); return confirmAnswer; },
    fetch, JSON, BigInt, Promise, URLSearchParams, setTimeout,
  };
  vm.createContext(ctx);
  vm.runInContext(script, ctx);
  return {
    el, requests, confirms, state, storage,
    posts: () => requests.filter((r) => r.method === "POST").map((r) => r.url),
    loads: () => requests.filter((r) => r.method === "GET" && r.url.startsWith("/api/bids?limit=2")).length,
    lookups: (from = 0) => requests.slice(from).filter((r) => r.url.includes("/minimum-bid")).map((r) => r.url),
    rows: () => el("rows").children.map((tr) => tr.children.map((td) => td.textContent)),
    buttons: () => el("rows").children.map((tr) => {
      const cell = tr.children[5];
      return cell && cell.children.length ? cell.children[0] : null;
    }),
    hint: () => el("min-bid-hint").textContent,
    banner: () => el("outbid-banner").textContent,
    answer: (status, body) => pending.shift()(apply(status, body)),
    click: async (button) => { button.listeners.click.forEach((f) => f()); await settle(); },
  };
}

const unhandled = [];
process.on("unhandledRejection", (e) => unhandled.push(String(e)));
process.on("uncaughtException", (e) => unhandled.push(String(e)));

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
const ACTIVE = { id: 31, auction_id: 7, amount: 500, status: "active", standing: "winning" };
const TOO_LATE = "too late to cancel: bids can only be cancelled within 5 minutes";
const bid = (id, auction_id, amount, status = "active", standing = null) => ({ id, auction_id, amount, status, standing });
const states = (p) => ({
  notice: p.el("cancel-notice").textContent, error: p.el("error").textContent, hint: p.hint(), banner: p.banner(),
});

const scenarios = {
  async accepted() {
    const p = makePage({ items: [ACTIVE], cancel: "defer" });
    await settle();
    const rowsBefore = p.rows();
    const button = p.buttons()[0];
    await p.click(button);
    const during = { disabled: button.disabled, posts: p.posts(), notice: p.el("cancel-notice").textContent };
    p.answer(200, { id: 31, auction_id: 7, status: "cancelled" });
    await settle();
    return {
      confirms: p.confirms, rowsBefore, during, posts: p.posts(), loads: p.loads(),
      notice: p.el("cancel-notice").textContent, error: p.el("error").textContent,
      rowsAfter: p.rows(), buttonsAfter: p.buttons().map((b) => b !== null),
    };
  },
  async dismissed() {
    const p = makePage({ items: [ACTIVE], confirmAnswer: false });
    await settle();
    const button = p.buttons()[0];
    await p.click(button);
    return {
      confirms: p.confirms, posts: p.posts(), loads: p.loads(), disabled: button.disabled,
      notice: p.el("cancel-notice").textContent, rows: p.rows(), hasButton: p.buttons().map((b) => b !== null),
    };
  },
  async notActive() {
    const cancelled = { ...ACTIVE, status: "cancelled", standing: null };
    const p = makePage({
      items: [ACTIVE], others: [bid(30, 7, 100, "active", "winning")],
      cancel: [409, { error: "bid is not active" }], after: [cancelled], auctionId: "7",
    });
    await settle();
    const button = p.buttons()[0];
    await p.click(button);
    return {
      posts: p.posts(), loads: p.loads(), notice: p.el("cancel-notice").textContent,
      error: p.el("error").textContent, rows: p.rows(), hasButton: p.buttons().map((b) => b !== null), hint: p.hint(),
    };
  },
  async notFound() {
    const p = makePage({ items: [ACTIVE], cancel: [404, { error: "bid not found" }], auctionId: "7" });
    await settle();
    await p.click(p.buttons()[0]);
    return {
      posts: p.posts(), loads: p.loads(), notice: p.el("cancel-notice").textContent,
      error: p.el("error").textContent, rows: p.rows(), hint: p.hint(),
    };
  },
  async networkFailure() {
    const p = makePage({ items: [ACTIVE], cancel: "network", auctionId: "7" });
    await settle();
    const hintBefore = p.hint();
    const button = p.buttons()[0];
    const from = p.requests.length;
    await p.click(button);
    return {
      posts: p.posts(), loads: p.loads(), disabled: button.disabled, notice: p.el("cancel-notice").textContent,
      error: p.el("error").textContent, rows: p.rows(), hintBefore, hintAfter: p.hint(), lookups: p.lookups(from),
    };
  },
  async otherStatus() {
    const out = {};
    const cases = { "500": [500, { error: "boom" }], "400": [400, { error: "bad" }], "notJson": [200, "<html>oops</html>"] };
    for (const [name, answer] of Object.entries(cases)) {
      const p = makePage({ items: [ACTIVE], cancel: answer });
      await settle();
      const button = p.buttons()[0];
      await p.click(button);
      out[name] = {
        posts: p.posts(), loads: p.loads(), disabled: button.disabled, notice: p.el("cancel-notice").textContent,
        error: p.el("error").textContent, rows: p.rows(),
      };
    }
    return out;
  },
  async noticeCleared() {
    const other = { id: 32, auction_id: 8, amount: 90, status: "active", standing: "outbid" };
    const p = makePage({ items: [ACTIVE, other], cancel: "defer" });
    await settle();
    await p.click(p.buttons()[0]);
    p.answer(200, { id: 31, auction_id: 7, status: "cancelled" });
    await settle();
    const afterFirst = p.el("cancel-notice").textContent;
    p.el("error").textContent = "old error";
    await p.click(p.buttons().find((b) => b !== null));
    const duringSecond = { notice: p.el("cancel-notice").textContent, error: p.el("error").textContent };
    p.answer(200, { id: 32, auction_id: 8, status: "cancelled" });
    await settle();
    const afterSecond = p.el("cancel-notice").textContent;
    p.el("bid-form").listeners.submit.forEach((f) => f({ preventDefault() {} }));
    await settle();
    return { afterFirst, duringSecond, afterSecond, afterBidPost: p.el("cancel-notice").textContent };
  },
  async tooLate() {
    const old = { id: 42, auction_id: 9, amount: 300, status: "active", standing: "winning", created_at: 1 };
    const p = makePage({ items: [old], cancel: [409, { error: TOO_LATE }] });
    await settle();
    await p.click(p.buttons()[0]);
    return {
      posts: p.posts(), loads: p.loads(), notice: p.el("cancel-notice").textContent,
      error: p.el("error").textContent, rows: p.rows(), hasButton: p.buttons().map((b) => b !== null),
      disabled: p.buttons().map((b) => (b === null ? null : b.disabled)),
    };
  },
  async oldActiveRows() {
    const p = makePage({
      items: [
        { id: 42, auction_id: 9, amount: 300, status: "active", standing: "winning", created_at: 1 },
        { id: 43, auction_id: 9, amount: 200, status: "active", standing: "outbid", created_at: 1793613600000 },
      ],
    });
    await settle();
    return { buttons: p.buttons().map((b) => (b === null ? null : b.textContent)) };
  },
  // The reload after the answer fails: the error line and the hint refresh still run.
  async reloadFails() {
    const cancelled = { ...ACTIVE, status: "cancelled", standing: null };
    const p = makePage({
      items: [ACTIVE], others: [bid(30, 7, 100, "active", "outbid")], cancel: [409, { error: "bid is not active" }],
      after: [cancelled], auctionId: "7", listFailsAfterPost: true,
    });
    await settle();
    await p.click(p.buttons()[0]);
    return states(p);
  },
  async buttonsPerRow() {
    const p = makePage({
      items: [
        ACTIVE,
        { id: 32, auction_id: 8, amount: 90, status: "cancelled", standing: null },
        { id: 33, auction_id: 9, amount: 70, status: "active", standing: "outbid" },
      ],
      pageSize: "10",
    });
    await settle();
    return { rows: p.rows(), buttons: p.buttons().map((b) => (b === null ? null : b.textContent)) };
  },
  // T-04 S1: page size 2 and one "Load more", then a cancel reloads the first page only.
  async reloadsFirstPage() {
    const items = [bid(61, 9, 150, "active", "winning"), bid(60, 9, 100, "active", "outbid"), bid(50, 5, 40, "active", "winning"), bid(40, 4, 30, "active", "winning")];
    const p = makePage({ items, cancel: [200, { id: 61, auction_id: 9, status: "cancelled" }] });
    await settle();
    p.el("more").listeners.click.forEach((f) => f());
    await settle();
    const rowsBefore = p.rows().map((r) => r[0]);
    const from = p.requests.length;
    await p.click(p.buttons()[0]);
    const lists = p.requests.slice(from).filter((r) => r.method === "GET" && r.url.startsWith("/api/bids?limit=2")).map((r) => r.url);
    return { rowsBefore, lists, rowsAfter: p.rows() };
  },
  // T-04 S2: the hint is requested again after the reload; the form keeps its values.
  async hintRefreshes() {
    const p = makePage({ items: [ACTIVE], others: [bid(30, 7, 100, "active", "outbid")], cancel: [200, { id: 31, auction_id: 7, status: "cancelled" }], auctionId: "7", amount: "120" });
    await settle();
    const hintBefore = p.hint();
    await p.click(p.buttons()[0]);
    return { hintBefore, hintAfter: p.hint(), auctionId: p.el("auction_id").value, amount: p.el("amount").value };
  },
  async hintInvalidId() {
    const p = makePage({ items: [ACTIVE], cancel: [200, { id: 31, auction_id: 7, status: "cancelled" }], auctionId: "abc" });
    await settle();
    const from = p.requests.length;
    await p.click(p.buttons()[0]);
    return { hint: p.hint(), lookups: p.lookups(from) };
  },
  // The Auction ID field is read when the hint is refreshed, not when the button was clicked.
  async hintCurrentField() {
    const p = makePage({ items: [ACTIVE], cancel: "defer", auctionId: "7" });
    await settle();
    const from = p.requests.length;
    await p.click(p.buttons()[0]);
    p.el("auction_id").value = "8";
    p.answer(200, { id: 31, auction_id: 7, status: "cancelled" });
    await settle();
    return { lookups: p.lookups(from) };
  },
  // T-04 S3: auction 20 was stored as winning; a cancel must not turn into an outbid banner.
  async neverShowsBanner() {
    const mine = [bid(82, 20, 120, "active", "winning"), bid(80, 20, 100, "active", "outbid")];
    const p = makePage({ items: mine, others: [bid(81, 20, 110, "active", "outbid")], cancel: [200, { id: 82, auction_id: 20, status: "cancelled" }], storage: { standing: JSON.stringify({ 20: "winning" }) } });
    await settle();
    const bannerBefore = p.banner();
    await p.click(p.buttons()[0]);
    await settle();
    const afterCancel = { banner: p.banner(), rows: p.rows(), stored: JSON.parse(p.storage.standing) };
    const again = makePage({ items: p.state.items, others: p.state.others, storage: p.storage });
    await settle();
    return { bannerBefore, afterCancel, afterBrowserReload: again.banner() };
  },
  // T-04 S4: a real outbid on auction 21 still shows its banner, and none for auction 20.
  async realOutbid() {
    const mine = [bid(83, 21, 130, "active", "outbid"), bid(82, 20, 120, "cancelled", null), bid(80, 20, 100, "active", "outbid")];
    const p = makePage({ items: mine, others: [bid(81, 20, 110, "active", "winning"), bid(90, 21, 140, "active", "winning")], storage: { standing: JSON.stringify({ 20: "outbid", 21: "winning" }) } });
    await settle();
    return { banner: p.banner() };
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
