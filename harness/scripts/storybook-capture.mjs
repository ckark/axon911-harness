#!/usr/bin/env node
/** Batch Storybook iframe captures with render-health facts. */

import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

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

const CAPTURE_PADDING_PX = 16;

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
  const chosen = narrowed[0] || matches[0];
  if (!chosen) {
    throw new Error(`story not found in index: ${needle}`);
  }
  return chosen.id;
}

function globalsQuery(theme, brand) {
  const parts = [];
  if (theme) parts.push(`theme:${theme}`);
  if (brand) parts.push(`uiBrand:${brand}`);
  if (theme === "dark") {
    parts.push("backgrounds.value:#111");
  }
  return parts.length ? `&globals=${encodeURIComponent(parts.join(";"))}` : "";
}

function parseViewport(raw) {
  const match = String(raw || "1280x720").match(/^(\d+)x(\d+)$/);
  return {
    width: match ? Number(match[1]) : 1280,
    height: match ? Number(match[2]) : 720,
  };
}

async function cssTokensReady(page) {
  return page.evaluate(() => {
    const style = getComputedStyle(document.documentElement);
    return Boolean(
      style.getPropertyValue("--color-background-base").trim() ||
        style.getPropertyValue("--color-background").trim(),
    );
  });
}

async function themeApplied(page, theme) {
  return page.evaluate((expectedTheme) => {
    const html = document.documentElement;
    const bodyStyle = getComputedStyle(document.body);
    const bg = bodyStyle.backgroundColor || "";
    const hasBrandClass = Array.from(html.classList).some((name) => name.startsWith("brand-"));
    const darkish =
      bg.includes("rgb(") &&
      bg
        .replace(/[^\d,]/g, "")
        .split(",")
        .slice(0, 3)
        .every((part) => Number(part) <= 40);
    const lightish =
      bg.includes("rgb(") &&
      bg
        .replace(/[^\d,]/g, "")
        .split(",")
        .slice(0, 3)
        .every((part) => Number(part) >= 210);
    const themeLooksCorrect = (expectedTheme === "light" ? lightish : darkish) && hasBrandClass;
    return {
      hasBrandClass,
      themeLooksCorrect,
      bodyBackground: bg,
    };
  }, theme);
}

async function bootstrapBrandClass(page, brand) {
  const normalized = String(brand || "prepared").trim() || "prepared";
  await page.evaluate((value) => {
    const html = document.documentElement;
    for (const className of Array.from(html.classList)) {
      if (className.startsWith("brand-")) {
        html.classList.remove(className);
      }
    }
    html.classList.add(`brand-${value}`);
  }, normalized);
}

async function resolveCaptureClip(page, selector) {
  const clip = await page.evaluate(
    ({ rootSelector, padding }) => {
      const root = document.querySelector(rootSelector);
      if (!root) {
        return null;
      }
      const preferred =
        root.querySelector(".rt-CalloutRoot") ||
        root.querySelector("[role='status']") ||
        root.querySelector(".pr-callout") ||
        root.firstElementChild ||
        root;
      const rect = preferred.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) {
        return null;
      }
      return {
        x: Math.max(0, rect.x - padding),
        y: Math.max(0, rect.y - padding),
        width: rect.width + padding * 2,
        height: rect.height + padding * 2,
      };
    },
    { rootSelector: selector, padding: CAPTURE_PADDING_PX },
  );
  return clip;
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

  for (let attempt = 0; attempt < 3; attempt += 1) {
    consoleErrors.length = 0;
    failedRequests.length = 0;
    await page.goto(url, { waitUntil: "networkidle", timeout: 120000 });
    await page.waitForFunction(
      () => document.body.classList.contains("sb-show-main"),
      undefined,
      { timeout: 120000 },
    );
    await bootstrapBrandClass(page, capture.brand || "prepared");
    if ((await cssTokensReady(page)) && (await themeApplied(page, capture.theme || "dark")).themeLooksCorrect) {
      break;
    }
    const staleDeps = failedRequests.some((entry) => entry.includes("Outdated Optimize Dep"));
    if (staleDeps && attempt < 2) {
      await page.reload({ waitUntil: "networkidle", timeout: 120000 });
      continue;
    }
    if (attempt < 2) {
      await page.waitForTimeout(1000);
      continue;
    }
  }
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
  const clip = await resolveCaptureClip(page, selector);
  const box = clip || (await target.boundingBox());
  const stylesheetsPresent = await page.evaluate(() => document.styleSheets.length > 0);
  const cssTokensReadyValue = await cssTokensReady(page);
  const themeState = await themeApplied(page, capture.theme || "dark");
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
  if (clip) {
    await page.screenshot({
      path: capture.output_path,
      animations: "disabled",
      caret: "hide",
      scale: "css",
      clip,
    });
  } else {
    await target.screenshot({
      path: capture.output_path,
      animations: "disabled",
      caret: "hide",
      scale: "css",
    });
  }

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
      css_tokens_ready: cssTokensReadyValue,
      theme_applied: themeState.themeLooksCorrect,
      target_visible: (box?.width || 0) > 0 && (box?.height || 0) > 0,
      target_bounds_nonzero: (box?.width || 0) > 0 && (box?.height || 0) > 0,
      stylesheets_present: stylesheetsPresent,
      console_errors: consoleErrors,
      failed_requests: failedRequests,
    },
  };
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  colorScheme: "dark",
});
const page = await context.newPage();
const entries = await loadStoryIndex(spec.baseUrl);
const results = [];

for (const capture of spec.captures || []) {
  results.push(await captureOne(page, capture, spec.baseUrl, entries));
}

await browser.close();
process.stdout.write(JSON.stringify({ ok: true, results }) + "\n");
