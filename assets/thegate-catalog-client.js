(function (root) {
  "use strict";

  var memoryCatalog = null;

  function emit(name, detail) {
    if (typeof root.dispatchEvent === "function" && typeof root.CustomEvent === "function") {
      root.dispatchEvent(new root.CustomEvent("thegate:catalog-" + name, { detail: detail }));
    }
  }

  function safeImage(value) {
    if (typeof value !== "string" || value.trim() !== value) return false;
    try {
      var url = new URL(value);
      return url.protocol === "https:" && !url.username && !url.password && !url.hash;
    } catch (_error) {
      return false;
    }
  }

  function validate(payload) {
    if (!payload || payload.schema_version !== "the_gate_website_catalog.v1") {
      throw new Error("CATALOG_SCHEMA_INVALID");
    }
    if (!Array.isArray(payload.items) || payload.total !== payload.items.length || payload.total > 1000) {
      throw new Error("CATALOG_COUNT_INVALID");
    }
    payload.items.forEach(function (item) {
      if (!item || typeof item.code !== "string" || !item.code || typeof item.name !== "string") {
        throw new Error("CATALOG_ITEM_INVALID");
      }
      if (typeof item.sale_price !== "number" || !(item.sale_price > 0) || item.price_status !== "available") {
        throw new Error("CATALOG_PRICE_INVALID");
      }
      if (!Array.isArray(item.images) || item.images.length !== 1 || !safeImage(item.images[0])) {
        throw new Error("CATALOG_IMAGE_INVALID");
      }
      if (Object.prototype.hasOwnProperty.call(item, "inventory") || Object.prototype.hasOwnProperty.call(item, "generation_id")) {
        throw new Error("CATALOG_INTERNAL_FIELD_REJECTED");
      }
    });
    return payload;
  }

  function delay(milliseconds) {
    return new Promise(function (resolve) { root.setTimeout(resolve, milliseconds); });
  }

  async function requestOnce(endpoint, timeoutMs) {
    var controller = new AbortController();
    var timer = root.setTimeout(function () { controller.abort(); }, timeoutMs);
    try {
      var response = await root.fetch(endpoint, {
        method: "GET",
        credentials: "same-origin",
        headers: { "Accept": "application/json" },
        signal: controller.signal
      });
      if (response.status === 304 && memoryCatalog) return memoryCatalog;
      if (response.status === 304) throw new Error("CATALOG_304_WITHOUT_MEMORY_CACHE");
      if (!response.ok) {
        var error = new Error("CATALOG_HTTP_" + response.status);
        error.retryable = response.status === 429 || response.status === 503;
        throw error;
      }
      var payload = validate(await response.json());
      memoryCatalog = payload;
      return payload;
    } finally {
      root.clearTimeout(timer);
    }
  }

  async function load(options) {
    options = options || {};
    var endpoint = options.endpoint || "/api/catalog";
    var timeoutMs = Number.isFinite(options.timeoutMs) ? options.timeoutMs : 8000;
    var attempts = Number.isInteger(options.attempts) ? options.attempts : 2;
    if (attempts < 1 || attempts > 3 || timeoutMs < 500 || timeoutMs > 30000) {
      throw new Error("CATALOG_CLIENT_CONFIG_INVALID");
    }
    emit("loading", { endpoint: endpoint });
    var lastError;
    for (var attempt = 1; attempt <= attempts; attempt += 1) {
      try {
        var catalog = await requestOnce(endpoint, timeoutMs);
        emit("ready", { catalog: catalog });
        return catalog;
      } catch (error) {
        lastError = error;
        var retryable = error.name === "AbortError" || error.retryable === true || error instanceof TypeError;
        if (!retryable || attempt === attempts) break;
        await delay(250 * attempt);
      }
    }
    var code = lastError && lastError.message ? lastError.message : "CATALOG_UNAVAILABLE";
    emit("error", { code: code });
    throw lastError || new Error(code);
  }

  root.TheGateCatalog = Object.freeze({ load: load, validate: validate });
})(typeof window !== "undefined" ? window : globalThis);
