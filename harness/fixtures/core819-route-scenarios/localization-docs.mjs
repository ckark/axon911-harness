export const targetSelector = "body";

export async function setup() {}

export async function assertDom(page) {
  const heading = page.getByRole("heading", { name: "Localization (i18n)", exact: true });
  const brandedSection = page.getByRole("heading", { name: "LocalizedMessage branding", exact: true });
  return [
    { type: "heading-visible", passed: await heading.isVisible() },
    { type: "migration-copy-visible", passed: await brandedSection.isVisible() },
  ];
}

export async function proveChangedPaths(page) {
  const locator = page.getByText("Formatter return types are tightened in a follow-up change", { exact: false });
  return [
    {
      path: "turbo/apps/docs/mdx/engineering/working-on-features/localization.mdx",
      signal: "rendered-migration-copy",
      passed: await locator.isVisible(),
    },
  ];
}
