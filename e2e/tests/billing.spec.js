// @ts-check
const { test, expect } = require("@playwright/test");

test.describe("Billing Page", () => {
  test.beforeEach(async ({ page }) => {
    // Register and navigate to billing
    await page.goto("/platform.html");
    const emailInput = page.locator('input[type="email"]');
    if (await emailInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      const email = `billing-${Date.now()}@e2e.test`;
      const registerLink = page.locator('text=Create an account');
      if (await registerLink.isVisible()) await registerLink.click();
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]', "testpass123");
      const nameInput = page.locator('input[name="name"], input[placeholder*="name"]').first();
      if (await nameInput.isVisible().catch(() => false)) await nameInput.fill("Billing Tester");
      await page.click('button[type="submit"]');
      await page.waitForTimeout(2000);
    }
  });

  test("billing page renders plan grid", async ({ page }) => {
    await page.goto("/billing.html");
    // Wait for content to load
    await page.waitForSelector("#billingContent", { state: "visible", timeout: 10000 }).catch(() => {});
    await page.waitForSelector("#planGrid", { timeout: 5000 });

    // Should show plan cards
    const planCards = page.locator(".plan-card");
    const count = await planCards.count();
    expect(count).toBeGreaterThanOrEqual(2); // At least Free and Pro
  });

  test("free plan shows as current", async ({ page }) => {
    await page.goto("/billing.html");
    await page.waitForSelector("#planGrid", { timeout: 5000 });

    // Free plan card should have "current" indicator
    const currentBadge = page.locator('text=Current plan').first();
    await expect(currentBadge).toBeVisible({ timeout: 5000 });
  });

  test("settings page loads", async ({ page }) => {
    await page.goto("/settings.html");
    await page.waitForSelector("#settingsContent", { state: "visible", timeout: 10000 }).catch(() => {});

    // Should show profile form
    await expect(page.locator("#profileForm, #fieldEmail")).toBeVisible({ timeout: 5000 });
  });
});
