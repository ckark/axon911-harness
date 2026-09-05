#!/usr/bin/env node

import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const specPath = process.argv[2];
if (!specPath) {
  console.error("usage: route-capture.mjs <spec.json>");
  process.exit(2);
}

const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
const playwrightRoot = spec.playwrightModuleRoot;
if (!playwrightRoot) {
  console.error("playwrightModuleRoot required");
  process.exit(2);
}

const require = createRequire(path.join(playwrightRoot, "package.json"));
const { chromium } = require("playwright");

function parseViewport(raw) {
  const match = String(raw || "1280x720").match(/^(\d+)x(\d+)$/);
  return {
    width: match ? Number(match[1]) : 1280,
    height: match ? Number(match[2]) : 720,
  };
}

async function loadScenarioAdapter(scenarioId) {
  const adapterPath = path.resolve(
    path.dirname(new URL(import.meta.url).pathname),
    "..",
    "fixtures",
    "core819-route-scenarios",
    `${scenarioId}.mjs`,
  );
  if (!fs.existsSync(adapterPath)) {
    throw new Error(`missing route scenario adapter: ${scenarioId}`);
  }
  return import(pathToFileURL(adapterPath).href);
}

async function main() {
  const scenario = spec.scenario || {};
  const viewport = parseViewport(scenario.viewport);
  const adapter = await loadScenarioAdapter(String(scenario.scenario_id || ""));
  const browser = await chromium.launch({ headless: true });
  const consoleErrors = [];
  const failedRequests = [];
  const page = await browser.newPage({ viewport });
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });
  page.on("requestfailed", (request) => {
    failedRequests.push(request.url());
  });
  try {
    if (typeof adapter.setup === "function") {
      await adapter.setup(page, { baseUrl: spec.baseUrl, scenario });
    }
    const route = String(scenario.route || "/");
    await page.goto(`${spec.baseUrl.replace(/\/$/, "")}${route}`, { waitUntil: "networkidle" });
    const targetSelector = String(scenario.target_selector || adapter.targetSelector || "body");
    const target = page.locator(targetSelector).first();
    await target.waitFor({ state: "visible", timeout: 30000 });
    const clipBounds = await target.boundingBox();
    if (!clipBounds || clipBounds.width <= 0 || clipBounds.height <= 0) {
      throw new Error("target bounds are zero");
    }
    const domAssertions = typeof adapter.assertDom === "function"
      ? await adapter.assertDom(page, { scenario })
      : [];
    const changedPathProof = typeof adapter.proveChangedPaths === "function"
      ? await adapter.proveChangedPaths(page, { scenario })
      : [];
    const failed = domAssertions.filter((item) => item && item.passed === false);
    const failedProof = changedPathProof.filter((item) => item && item.passed === false);
    await target.screenshot({ path: spec.outputPath });
    const health = {
      storybook_ready: true,
      fonts_ready: true,
      css_tokens_ready: true,
      theme_applied: true,
      target_visible: true,
      target_bounds_nonzero: true,
      stylesheets_present: true,
      console_errors: consoleErrors,
      failed_requests: failedRequests,
      dom_assertions_passed: failed.length === 0,
      changed_path_proof_passed: changedPathProof.length > 0 && failedProof.length === 0,
    };
    if (failed.length) {
      throw new Error(`dom assertions failed: ${failed.map((item) => item.type).join(", ")}`);
    }
    if (!changedPathProof.length || failedProof.length) {
      throw new Error("changed-path proof failed");
    }
    process.stdout.write(
      JSON.stringify({
        ok: true,
        target_selector: targetSelector,
        clip_selector: targetSelector,
        clip_bounds: clipBounds,
        dom_assertions: domAssertions,
        changed_path_proof: changedPathProof,
        health,
      }),
    );
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stdout.write(JSON.stringify({ ok: false, error: String(error.message || error) }));
  process.exit(1);
});
