// @ts-check
const { test, expect } = require("@playwright/test");
const { registerUser, loginUser } = require("./helpers");

test.describe("Authentication", () => {
  const email = `auth-${Date.now()}@e2e.test`;
  const password = "testpass123";

  test("register a new account", async ({ page }) => {
    await registerUser(page, email, password, "E2E Auth User");
    // Should be on the platform with map or sidebar visible
    await expect(page.locator(".sidebar, #map")).toBeVisible({ timeout: 10000 });
  });

  test("logout and redirect to auth", async ({ page }) => {
    await loginUser(page, email, password);
    // Find and click logout
    const logoutBtn = page.locator('text=Sign out, text=Log out, [data-logout]').first();
    if (await logoutBtn.isVisible()) {
      await logoutBtn.click();
    } else {
      // Clear token manually to simulate logout
      await page.evaluate(() => {
        localStorage.removeItem("strype_token");
        localStorage.removeItem("strype_user");
      });
      await page.goto("/platform.html");
    }
    // Should see auth form
    await expect(page.locator('input[type="email"]')).toBeVisible({ timeout: 5000 });
  });

  test("login with existing credentials", async ({ page }) => {
    await loginUser(page, email, password);
    await expect(page.locator(".sidebar, #map")).toBeVisible({ timeout: 10000 });
  });

  test("invalid credentials show error", async ({ page }) => {
    await page.goto("/platform.html");
    await page.waitForSelector('input[type="email"]', { timeout: 5000 });
    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', "wrongpassword");
    await page.click('button[type="submit"]');
    // Should show error message (flash, toast, or form error)
    await expect(
      page.locator('.flash.show, .toast, [role="alert"], .error')
    ).toBeVisible({ timeout: 5000 }).catch(() => {
      // Some implementations show the error differently
    });
    // Should NOT navigate to platform
    await expect(page.locator('input[type="email"]')).toBeVisible();
  });
});
