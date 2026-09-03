#!/usr/bin/env node
/** Batch Storybook iframe captures with render-health facts. */

import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const specPath = process.argv[2];
if (!specPath) {
  console.error("usage: storybook-capture.mjs <spec.json>");
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

async function loadStoryIndex(baseUrl) {
  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/index.json`);
  if (!response.ok) {
    throw new Error(`failed to load story index: ${response.status}`);
  }
  const payload = await response.json();
  return payload.entries || {};
}

function resolveStoryId(entries, storyRef, exportName = "Default") {
  const needle = String(storyRef || "").trim();
  if (!needle) {
    throw new Error("missing story_id");
  }
  if (entries[needle]) {
    return needle;
  }
  const matches = Object.values(entries).filter((entry) => {
    if (entry.type !== "story") return false;
    if (entry.title === needle) return true;
    if (String(entry.title || "").endsWith(`/${needle}`)) return true;
    if (String(entry.title || "").endsWith(needle)) return true;
    return false;
  });
  const narrowed = matches.filter((entry) => String(entry.name || entry.exportName || "") === exportName);
  const chosen = (narrowed[0] || matches[0]);
  if (!chosen) {
    throw new Error(`story not found in index: ${needle}`);
  }
  return chosen.id;
}

function globalsQuery(theme, brand) {
  const parts = [];
  if (theme) parts.push(`theme:${theme}`);
  if (brand) parts.push(`brand:${brand}`);
  return parts.length ? `&globals=${encodeURIComponent(parts.join(";"))}` : "";
}

function parseViewport(raw) {
  const match = String(raw || "1280x720").match(/^(\d+)x(\d+)$/);
  return {
    width: match ? Number(match[1]) : 1280,
    height: match ? Number(match[2]) : 720,
  };
}

async function captureOne(page, capture, baseUrl, entries) {
  const viewport = parseViewport(capture.viewport);
  await page.setViewportSize(viewport);
  const slug = resolveStoryId(entries, capture.story_id, capture.export_name || "Default");
  const url =
    `${baseUrl.replace(/\/$/, "")}/iframe.html?id=${encodeURIComponent(slug)}` +
    `&viewMode=story${globalsQuery(capture.theme, capture.brand)}`;
  const consoleErrors = [];
  const failedRequests = [];
  page.removeAllListeners("console");
  page.removeAllListeners("requestfailed");
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("requestfailed", (req) => failedRequests.push(req.url()));

  await page.goto(url, { waitUntil: "networkidle", timeout: 120000 });
  await page.waitForFunction(
    () => document.body.classList.contains("sb-show-main"),
    undefined,
    { timeout: 120000 },
  );
  await page.waitForTimeout(500);

  for (const action of capture.actions || []) {
    if (action.type === "click" && action.selector) {
      await page.locator(action.selector).first().click({ timeout: 30000 });
      await page.waitForTimeout(300);
    }
  }

  const selector = capture.target_selector || "#storybook-root";
  const target = page.locator(selector).first();
  await target.waitFor({ state: "visible", timeout: 30000 });
  const box = await target.boundingBox();
  const stylesheetsPresent = await page.evaluate(() => document.styleSheets.length > 0);
  const cssTokensReady = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement);
    return Boolean(style.getPropertyValue("--color-background-primary").trim());
  });
  const fontsReady = await page.evaluate(async () => {
    if (!document.fonts) return true;
    try {
      await document.fonts.ready;
      return true;
    } catch {
      return false;
    }
  });

  fs.mkdirSync(path.dirname(capture.output_path), { recursive: true });
  await target.screenshot({
    path: capture.output_path,
    animations: "disabled",
    caret: "hide",
    scale: "css",
  });

  return {
    story_id: capture.story_id,
    resolved_story_id: slug,
    story_url: url,
    target_selector: selector,
    width: box?.width || 0,
    height: box?.height || 0,
    health: {
      storybook_ready: true,
      fonts_ready: fontsReady,
      css_tokens_ready: cssTokensReady,
      target_visible: (box?.width || 0) > 0 && (box?.height || 0) > 0,
      target_bounds_nonzero: (box?.width || 0) > 0 && (box?.height || 0) > 0,
      stylesheets_present: stylesheetsPresent,
      console_errors: consoleErrors,
      failed_requests: failedRequests,
    },
  };
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext();
const page = await context.newPage();
const entries = await loadStoryIndex(spec.baseUrl);
const results = [];

for (const capture of spec.captures || []) {
  results.push(await captureOne(page, capture, spec.baseUrl, entries));
}

await browser.close();
process.stdout.write(JSON.stringify({ ok: true, results }) + "\n");
