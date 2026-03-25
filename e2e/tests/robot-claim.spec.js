// @ts-check
const { test, expect } = require("@playwright/test");

test.describe("Robot Claim Flow", () => {
  test("claim page loads and validates code input", async ({ page }) => {
    // Set a token in localStorage (claim page requires auth)
    await page.goto("/platform.html");
    // Register
    await page.waitForSelector('input[type="email"]', { timeout: 5000 }).catch(() => {});
    const emailInput = page.locator('input[type="email"]');
    if (await emailInput.isVisible()) {
      const email = `claim-${Date.now()}@e2e.test`;
      // Try register flow
      const registerLink = page.locator('text=Create an account');
      if (await registerLink.isVisible()) await registerLink.click();
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]', "testpass123");
      const nameInput = page.locator('input[name="name"], input[placeholder*="name"]').first();
      if (await nameInput.isVisible().catch(() => false)) await nameInput.fill("Claim Tester");
      await page.click('button[type="submit"]');
      await page.waitForTimeout(2000);
    }

    // Navigate to claim page
    await page.goto("/claim.html");
    await expect(page.locator("h1")).toContainText("Claim");

    // Verify form elements exist
    await expect(page.locator("#claimCode")).toBeVisible();
    await expect(page.locator('#validateForm button[type="submit"]')).toBeVisible();
  });

  test("invalid claim code shows error", async ({ page }) => {
    // Setup auth first
    await page.goto("/platform.html");
    const emailInput = page.locator('input[type="email"]');
    if (await emailInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      const email = `claim-err-${Date.now()}@e2e.test`;
      const registerLink = page.locator('text=Create an account');
      if (await registerLink.isVisible()) await registerLink.click();
      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]', "testpass123");
      await page.click('button[type="submit"]');
      await page.waitForTimeout(2000);
    }

    await page.goto("/claim.html");
    await page.fill("#claimCode", "invalid_code_12345");
    await page.click('#validateForm button[type="submit"]');

    // Should show error flash
    await expect(page.locator(".flash.show")).toBeVisible({ timeout: 5000 });
  });

  test("claim page accepts code from URL param", async ({ page }) => {
    await page.goto("/claim.html?code=test_code_from_url");
    const codeInput = page.locator("#claimCode");
    await expect(codeInput).toHaveValue("test_code_from_url");
  });
});
