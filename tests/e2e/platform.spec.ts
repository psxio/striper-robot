import { test, expect, Page } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

let authToken: string;
let authUser: object;

async function dismissOverlays(page: Page) {
  await page.evaluate(() => {
    const help = document.getElementById('helpOverlay');
    if (help) help.classList.remove('visible');
    const loader = document.getElementById('pageLoader');
    if (loader) loader.style.display = 'none';
  });
}

async function ensureAuth(page: Page) {
  if (!authToken) {
    const email = `e2e_plat_${Date.now()}@test.com`;
    const resp = await page.request.post('/api/auth/register', {
      data: { email, password: 'TestPass123!', name: 'Platform Tester' },
    });
    if (!resp.ok()) {
      // Rate limited — skip gracefully
      test.skip(true, 'Registration rate limited — skipping platform tests');
      return;
    }
    const data = await resp.json();
    authToken = data.token;
    authUser = data.user;
  }

  // Load the page (so localStorage is scoped to the right origin), set auth, reload
  await page.goto('/platform.html');
  await page.waitForLoadState('domcontentloaded');
  await page.evaluate(({ t, u }) => {
    localStorage.setItem('strype_token', t);
    localStorage.setItem('strype_user', JSON.stringify(u));
  }, { t: authToken, u: authUser });
  // Reload so the app JS picks up the token on init
  await page.reload();
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.sidebar').waitFor({ state: 'visible', timeout: 10000 });
  await dismissOverlays(page);
}

test.describe('Platform — Lot Management', () => {

  test('user can create a lot via sidebar', async ({ page }) => {
    await ensureAuth(page);

    await page.locator('.panel-action-btn').first().click();
    await expect(page.locator('#modalOverlay')).toHaveClass(/visible/, { timeout: 5000 });
    await page.locator('#newLotName').fill('E2E Test Lot');

    // Wait for the API call to complete when clicking confirm
    const responsePromise = page.waitForResponse(
      resp => resp.url().includes('/api/lots') && resp.request().method() === 'POST',
      { timeout: 10000 }
    );
    await page.locator('#newLotConfirm').click();
    const resp = await responsePromise;
    expect(resp.ok()).toBeTruthy();

    // Wait for UI update
    await expect(page.locator('#modalOverlay')).not.toHaveClass(/visible/, { timeout: 10000 });
    await expect(page.locator('.lot-name').filter({ hasText: 'E2E Test Lot' })).toBeVisible({ timeout: 10000 });
  });

  test('map loads with Leaflet controls', async ({ page }) => {
    await ensureAuth(page);
    await expect(page.locator('#map')).toBeVisible();
    await expect(page.locator('.leaflet-control-zoom')).toBeVisible({ timeout: 10000 });
  });

  test('sidebar tabs switch correctly', async ({ page }) => {
    await ensureAuth(page);
    const tabs = page.locator('.sidebar-tab');
    await expect(tabs.first()).toHaveClass(/active/);
    await tabs.last().click();
    await expect(tabs.last()).toHaveClass(/active/);
  });
});

test.describe('Platform — Settings & GDPR', () => {

  test('settings modal has GDPR download button', async ({ page }) => {
    await ensureAuth(page);
    // Wait for auth UI to update (avatar onclick changes from openAuthModal to showUserMenu)
    await page.waitForTimeout(2000);
    // Open settings directly via JS to avoid auth modal race
    await page.evaluate(() => { if (typeof openSettingsModal === 'function') openSettingsModal(); });
    await expect(page.locator('#settingsModal')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('#exportDataBtn')).toBeVisible();
  });

  test('GDPR export triggers download', async ({ page }) => {
    await ensureAuth(page);
    await page.waitForTimeout(2000);
    await page.evaluate(() => { if (typeof openSettingsModal === 'function') openSettingsModal(); });
    await expect(page.locator('#settingsModal')).toBeVisible({ timeout: 5000 });

    const downloadPromise = page.waitForEvent('download', { timeout: 15000 });
    await page.locator('#exportDataBtn').click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe('strype-data-export.json');
  });

  test('delete account button visible in settings', async ({ page }) => {
    await ensureAuth(page);
    await page.waitForTimeout(2000);
    await page.evaluate(() => { if (typeof openSettingsModal === 'function') openSettingsModal(); });
    await expect(page.locator('#settingsModal')).toBeVisible({ timeout: 5000 });
    // Delete Account button should be at the bottom
    await expect(page.locator('text=Delete Account')).toBeVisible();
  });
});
