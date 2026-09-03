import { createRequire } from "node:module";
import path from "node:path";

const root = process.argv[2];
const require = createRequire(path.join(root, "package.json"));
const { chromium } = require("playwright");

const storyRef = process.argv[3] || "Dispatch App/Core819 Evidence/DownloadListenerApplication";
const baseUrl = "http://127.0.0.1:3013";
const entries = await (await fetch(`${baseUrl}/index.json`)).json().then((p) => p.entries);
const slug = Object.values(entries).find((e) => e.title === storyRef)?.id;
console.log("slug", slug);
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(`${baseUrl}/iframe.html?id=${slug}&viewMode=story&globals=theme:dark;brand:prepared`, {waitUntil:'networkidle', timeout:120000});
await page.waitForTimeout(8000);
const info = await page.evaluate(() => ({
  bodyClass: document.body.className,
  text: document.body.innerText.slice(0,300),
  childCount: document.getElementById('storybook-root')?.childElementCount,
}));
console.log(JSON.stringify(info,null,2));
await browser.close();
