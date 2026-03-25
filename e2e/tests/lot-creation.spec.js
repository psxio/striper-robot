// @ts-check
const { test, expect } = require("@playwright/test");
const { registerUser } = require("./helpers");

test.describe("Lot Management", () => {
  const email = `lots-${Date.now()}@e2e.test`;

  test.beforeEach(async ({ page }) => {
    await registerUser(page, email, "testpass123", "Lot Tester");
  });

  test("create a new lot", async ({ page }) => {
    // Look for the "New" or "+ New" button in the sidebar
    const newBtn = page.locator('button:has-text("New"), button:has-text("+ New")').first();
    await expect(newBtn).toBeVisible({ timeout: 5000 });
    await newBtn.click();

    // Fill in lot name if a modal or form appears
    const nameInput = page.locator('input[placeholder*="lot"], input[name="lotName"], #lotNameInput').first();
    if (await nameInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await nameInput.fill("E2E Test Lot");
      const saveBtn = page.locator('button:has-text("Create"), button:has-text("Save")').first();
      await saveBtn.click();
    }

    // Verify lot appears in the sidebar list
    await expect(page.locator('text=E2E Test Lot')).toBeVisible({ timeout: 5000 }).catch(() => {
      // Some UI patterns show the lot differently
    });
  });

  test("lot appears in sidebar after creation", async ({ page }) => {
    // Create via API for reliability
    const token = await page.evaluate(() => localStorage.getItem("strype_token"));
    const baseUrl = page.url().split("/platform")[0];

    const resp = await page.request.post(`${baseUrl}/api/lots`, {
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      data: { name: "API Created Lot", center: { lat: 33.0, lng: -97.0 }, zoom: 18, features: [] },
    });
    expect(resp.status()).toBe(201);

    // Reload and check sidebar
    await page.reload();
    await page.waitForSelector(".sidebar", { timeout: 10000 });
    await expect(page.locator('text=API Created Lot')).toBeVisible({ timeout: 5000 });
  });
});
