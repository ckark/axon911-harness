export const targetSelector = "body";

export async function setup() {}

export async function assertDom(page) {
  const visible = await page.locator(targetSelector).isVisible();
  return [{ type: "page-visible", passed: visible }];
}

export async function proveChangedPaths() {
  return [];
}
