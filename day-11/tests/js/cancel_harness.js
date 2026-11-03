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

// `items` is what GET /api/bids returns. `cancel` answers POST /api/bids/<id>/cancel:
// [status, body], or "defer" to leave the request pending until page.answer().
// `after`, when set, replaces `items` once a non-200 answer was given (a change made elsewhere).
function makePage({ items, cancel = null, confirmAnswer = true, after = null }) {
  const state = { items, cancel };
  const els = {};
  const el = (id) => {
    if (!els[id]) {
      els[id] = Object.assign(node("el"), { id, value: id === "limit" ? "2" : "", hidden: false });
      if (id === "rows") Object.defineProperty(els[id], "innerHTML", { set() { this.children = []; }, get() { return ""; } });
    }
    return els[id];
  };
  const requests = [];
  const confirms = [];
  const pending = [];
  const apply = (status, body) => {
    if (status === 200) state.items = state.items.map((b) => (b.id === body.id ? { ...b, status: "cancelled", standing: null } : b));
    else if (after) state.items = after;
    return response(status, body);
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
    return Promise.resolve(response(200, { items: state.items, next_cursor: null }));
  };
  const ctx = {
    document: { getElementById: el, createElement: node },
    localStorage: { getItem: () => null, setItem() {} },
    console: { log() {}, error() {} },
    confirm: (text) => { confirms.push(text); return confirmAnswer; },
    fetch, JSON, BigInt, Promise, URLSearchParams, setTimeout,
  };
  vm.createContext(ctx);
  vm.runInContext(script, ctx);
  return {
    el, requests, confirms,
    posts: () => requests.filter((r) => r.method === "POST").map((r) => r.url),
    loads: () => requests.filter((r) => r.method === "GET" && r.url.startsWith("/api/bids?limit=2")).length,
    rows: () => el("rows").children.map((tr) => tr.children.map((td) => td.textContent)),
    buttons: () => el("rows").children.map((tr) => {
      const cell = tr.children[5];
      return cell && cell.children.length ? cell.children[0] : null;
    }),
    answer: (status, body) => pending.shift()(apply(status, body)),
    click: async (button) => { button.listeners.click.forEach((f) => f()); await settle(); },
  };
}

const unhandled = [];
process.on("unhandledRejection", (e) => unhandled.push(String(e)));
process.on("uncaughtException", (e) => unhandled.push(String(e)));

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
const ACTIVE = { id: 31, auction_id: 7, amount: 500, status: "active", standing: "winning" };

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
    const p = makePage({ items: [ACTIVE], cancel: [409, { error: "bid is not active" }], after: [cancelled] });
    await settle();
    const button = p.buttons()[0];
    await p.click(button);
    return {
      posts: p.posts(), loads: p.loads(), notice: p.el("cancel-notice").textContent,
      error: p.el("error").textContent, rows: p.rows(), hasButton: p.buttons().map((b) => b !== null),
    };
  },
  async notFound() {
    const p = makePage({ items: [ACTIVE], cancel: [404, { error: "bid not found" }] });
    await settle();
    await p.click(p.buttons()[0]);
    return {
      posts: p.posts(), loads: p.loads(), notice: p.el("cancel-notice").textContent,
      error: p.el("error").textContent, rows: p.rows(),
    };
  },
  async networkFailure() {
    const p = makePage({ items: [ACTIVE], cancel: "network" });
    await settle();
    const button = p.buttons()[0];
    await p.click(button);
    return {
      posts: p.posts(), loads: p.loads(), disabled: button.disabled, notice: p.el("cancel-notice").textContent,
      error: p.el("error").textContent, rows: p.rows(),
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
  async buttonsPerRow() {
    const p = makePage({
      items: [
        ACTIVE,
        { id: 32, auction_id: 8, amount: 90, status: "cancelled", standing: null },
        { id: 33, auction_id: 9, amount: 70, status: "active", standing: "outbid" },
      ],
    });
    await settle();
    return { rows: p.rows(), buttons: p.buttons().map((b) => (b === null ? null : b.textContent)) };
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
