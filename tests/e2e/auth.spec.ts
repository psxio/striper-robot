import { test, expect } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

async function dismissHelpOverlay(page: import('@playwright/test').Page) {
  // The Quick Start help overlay blocks all interaction on first visit
  try {
    const closeBtn = page.locator('.help-close, .help-modal .help-close');
    if (await closeBtn.isVisible({ timeout: 2000 })) {
      await closeBtn.click();
      await page.waitForTimeout(300);
    }
  } catch { /* no overlay */ }
  // Force-hide via JS as fallback
  await page.evaluate(() => {
    const el = document.getElementById('helpOverlay');
    if (el) el.classList.remove('visible');
    const loader = document.getElementById('pageLoader');
    if (loader) loader.style.display = 'none';
  });
}

test.describe('Landing Page', () => {

  test('loads with correct title and specs', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Strype/);
    const body = await page.textContent('body');
    expect(body).toContain('UM982');
    expect(body).toContain('18Ah');
    expect(body).toContain('$1,011');
  });

  test('pricing section shows three tiers', async ({ page }) => {
    await page.goto('/#pricing');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('.price-card')).toHaveCount(3);
  });

  test('ROI calculator updates on input', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    // Scroll to ROI section
    await page.locator('#roi').scrollIntoViewIfNeeded();
    const spacesSlider = page.locator('#spaces');
    await expect(spacesSlider).toBeVisible({ timeout: 10000 });
    await spacesSlider.fill('200');
    await expect(page.locator('#annualCrew')).not.toHaveText('$0');
  });
});

test.describe('Platform Authentication UI', () => {

  test('platform page loads and shows map', async ({ page }) => {
    await page.goto('/platform.html');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('#map')).toBeVisible();
  });

  test('user avatar opens auth modal', async ({ page }) => {
    await page.goto('/platform.html');
    await page.evaluate(() => localStorage.clear());
    await page.waitForLoadState('domcontentloaded');
    await dismissHelpOverlay(page);

    await page.locator('#userAvatar').click();
    await expect(page.locator('#authModal')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('#authEmail')).toBeVisible();
    await expect(page.locator('#authPassword')).toBeVisible();
  });

  test('can switch between login and register tabs', async ({ page }) => {
    await page.goto('/platform.html');
    await page.evaluate(() => localStorage.clear());
    await page.waitForLoadState('domcontentloaded');
    await dismissHelpOverlay(page);

    await page.locator('#userAvatar').click();
    await expect(page.locator('#authModal')).toBeVisible({ timeout: 5000 });

    await page.locator('#authTabRegister').click();
    await expect(page.locator('#nameField')).toBeVisible();

    await page.locator('#authTabLogin').click();
    await expect(page.locator('#nameField')).not.toBeVisible();
  });

  test.skip('register via API and access settings with GDPR button — covered in platform.spec.ts', async ({ page }) => {
    const email = `e2e_ui_${Date.now()}@test.com`;

    // Register via API to avoid rate limit on UI
    const resp = await page.request.post('/api/auth/register', {
      data: { email, password: 'TestPass123!', name: 'E2E User' },
    });
    const { token, user } = await resp.json();

    await page.goto('/platform.html');
    await page.evaluate(({ t, u }) => {
      localStorage.setItem('strype_token', t);
      localStorage.setItem('strype_user', JSON.stringify(u));
    }, { t: token, u: user });
    await page.reload();
    await page.waitForLoadState('domcontentloaded');
    await dismissHelpOverlay(page);

    await page.locator('#userAvatar').click();
    await page.locator('text=Settings').click();
    await expect(page.locator('#settingsModal')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('#exportDataBtn')).toBeVisible();
  });
});
