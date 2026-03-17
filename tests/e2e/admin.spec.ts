import { test, expect } from '@playwright/test';

test.describe('Admin Dashboard', () => {

  test('admin page loads and has responsive table markup', async ({ page }) => {
    await page.goto('/admin.html');
    await page.waitForLoadState('domcontentloaded');

    // Page should load (even if showing auth gate)
    await expect(page).toHaveTitle(/Admin/);

    // Verify responsive-table class exists on tables in the HTML
    const tables = page.locator('table.responsive-table');
    const count = await tables.count();
    expect(count).toBe(5);
  });

  test('admin page has mobile-responsive CSS', async ({ page }) => {
    await page.goto('/admin.html');
    await page.waitForLoadState('domcontentloaded');

    // Check that responsive CSS media queries exist
    const hasResponsiveCSS = await page.evaluate(() => {
      for (const sheet of document.styleSheets) {
        try {
          for (const rule of sheet.cssRules) {
            if (rule instanceof CSSMediaRule && rule.conditionText?.includes('768px')) {
              return true;
            }
          }
        } catch (e) { /* cross-origin */ }
      }
      return false;
    });
    expect(hasResponsiveCSS).toBe(true);
  });

  test('non-admin user sees access denied', async ({ page, request }) => {
    // Register a regular user
    const email = `e2e_nonadmin_${Date.now()}@test.com`;
    const reg = await request.post('/api/auth/register', {
      data: { email, password: 'TestPass123!' },
    });
    const token = (await reg.json()).token;

    // Set token in localStorage and visit admin page
    await page.goto('/admin.html');
    await page.evaluate((t) => localStorage.setItem('strype_token', t), token);
    await page.reload();
    await page.waitForLoadState('domcontentloaded');

    // Auth gate should show (admin stats check will fail for non-admin)
    await expect(page.locator('#authGate')).toBeVisible({ timeout: 10000 });
  });
});
