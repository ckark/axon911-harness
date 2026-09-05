export const targetSelector = "[data-testid='anet-disabled-banner'], .anet-disabled-banner, [role='alert']";

export async function setup(page, { baseUrl }) {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });
}

export async function assertDom(page) {
  const banner = page.locator(targetSelector).first();
  const visible = await banner.isVisible();
  const box = await banner.boundingBox();
  const cta = page.getByRole("button", { name: /configure|enable|anet/i }).first();
  const ctaVisible = await cta.isVisible().catch(() => false);
  const ctaBox = ctaVisible ? await cta.boundingBox() : null;
  return [
    { type: "banner-visible", passed: visible },
    { type: "banner-unclipped", passed: Boolean(box && box.width > 0 && box.height > 0) },
    { type: "cta-visible", passed: ctaVisible },
    { type: "cta-unclipped", passed: Boolean(ctaBox && ctaBox.width > 0 && ctaBox.height > 0) },
  ];
}

export async function proveChangedPaths(page) {
  const moduleLoaded = await page.evaluate(() => Boolean(document.querySelector(targetSelector)));
  return [{ path: "turbo/apps/dispatch/src/modules/triage/components/AnetDisabledBanner.tsx", loaded: moduleLoaded }];
}
