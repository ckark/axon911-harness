export const targetSelector = "body";

export async function setup() {}

export async function assertDom(page) {
  const overview = page.getByRole("heading", { name: "Overview", exact: true });
  const composition = page.getByRole("heading", { name: "Composition", exact: true });
  return [
    { type: "overview-visible", passed: await overview.isVisible() },
    { type: "composition-visible", passed: await composition.isVisible() },
  ];
}

export async function proveChangedPaths(page) {
  const locator = page.getByText("Callout is a single row with predictable structure", { exact: false });
  return [
    {
      path: "apps/docs/mdx/design/components/callout/usage.mdx",
      signal: "rendered-product-docs-copy",
      passed: await locator.isVisible(),
    },
  ];
}
