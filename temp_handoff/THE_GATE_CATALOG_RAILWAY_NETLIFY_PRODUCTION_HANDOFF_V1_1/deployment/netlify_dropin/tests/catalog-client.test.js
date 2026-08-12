"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const clientSource = fs.readFileSync(
  path.join(__dirname, "..", "assets", "thegate-catalog-client.js"),
  "utf8"
);

function payload() {
  return {
    schema_version: "the_gate_website_catalog.v1",
    generated_at: "2042-03-14T03:00:00+00:00",
    source_data_as_of: "2042-03-14T02:00:00+00:00",
    total: 1,
    items: [{
      code: "SYNTHETIC-001",
      name: "Synthetic",
      sale_price: 299000,
      price_status: "available",
      images: ["https://example.invalid/item.jpg"]
    }]
  };
}

function response(status, body) {
  return { status, ok: status >= 200 && status < 300, json: async () => body };
}

function context(fetchImpl) {
  const events = [];
  const target = {
    fetch: fetchImpl,
    setTimeout,
    clearTimeout,
    AbortController,
    URL,
    TypeError,
    CustomEvent: class {
      constructor(type, options) { this.type = type; this.detail = options.detail; }
    },
    dispatchEvent: (event) => events.push(event)
  };
  target.globalThis = target;
  vm.runInNewContext(clientSource, target, { filename: "thegate-catalog-client.js" });
  return { api: target.TheGateCatalog, events };
}

async function expectReject(promise, pattern) {
  try {
    await promise;
  } catch (error) {
    if (!pattern.test(error.message)) throw error;
    return;
  }
  throw new Error("EXPECTED_REJECTION");
}

(async function main() {
  let calls = 0;
  let c = context(async () => { calls += 1; return response(200, payload()); });
  const loaded = await c.api.load({ attempts: 1 });
  if (loaded.total !== 1 || calls !== 1) throw new Error("HTTP_200_FAILED");

  c = context((() => {
    let index = 0;
    return async () => (++index === 1 ? response(200, payload()) : response(304, null));
  })());
  await c.api.load({ attempts: 1 });
  if ((await c.api.load({ attempts: 1 })).total !== 1) throw new Error("HTTP_304_FAILED");

  c = context((() => {
    let index = 0;
    return async () => (++index === 1 ? response(429, {}) : response(200, payload()));
  })());
  if ((await c.api.load({ attempts: 2 })).total !== 1) throw new Error("HTTP_429_RETRY_FAILED");

  c = context(async () => response(503, {}));
  await expectReject(c.api.load({ attempts: 2 }), /CATALOG_HTTP_503/);

  c = context(async () => response(200, { schema_version: "wrong", total: 0, items: [] }));
  await expectReject(c.api.load({ attempts: 1 }), /CATALOG_SCHEMA_INVALID/);

  c = context((_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener("abort", () => {
      const error = new Error("aborted");
      error.name = "AbortError";
      reject(error);
    });
  }));
  await expectReject(c.api.load({ attempts: 1, timeoutMs: 500 }), /aborted/);

  process.stdout.write("netlify_client_tests=6 pass=6 fail=0\n");
})().catch((error) => {
  process.stderr.write("netlify_client_tests_failed=" + error.message + "\n");
  process.exitCode = 1;
});
