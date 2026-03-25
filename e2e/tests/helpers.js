// @ts-check
const { expect } = require("@playwright/test");

/**
 * Register a new user via the platform auth modal.
 * @param {import('@playwright/test').Page} page
 * @param {string} email
 * @param {string} password
 * @param {string} name
 */
async function registerUser(page, email, password = "testpass123", name = "Test User") {
  await page.goto("/platform.html");
  // Wait for auth modal
  await page.waitForSelector('[data-auth-mode]', { timeout: 5000 }).catch(() => {});

  // Switch to register mode if needed
  const registerLink = page.locator('text=Create an account');
  if (await registerLink.isVisible()) {
    await registerLink.click();
  }

  await page.fill('input[type="email"]', email);
  await page.fill('input[name="name"], input[placeholder*="name"]', name).catch(() => {});
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');

  // Wait for platform to load (map visible or sidebar visible)
  await page.waitForSelector('.sidebar, #map', { timeout: 10000 });
}

/**
 * Log in an existing user via the platform auth modal.
 * @param {import('@playwright/test').Page} page
 * @param {string} email
 * @param {string} password
 */
async function loginUser(page, email, password = "testpass123") {
  await page.goto("/platform.html");
  await page.waitForSelector('input[type="email"]', { timeout: 5000 });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForSelector('.sidebar, #map', { timeout: 10000 });
}

/**
 * Register + set as admin via direct API call.
 * @param {string} baseUrl
 * @param {string} email
 * @param {string} password
 */
async function seedAdminUser(baseUrl, email = "admin@e2e.test", password = "adminpass123") {
  const resp = await fetch(`${baseUrl}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, name: "E2E Admin" }),
  });
  const data = await resp.json();
  return { token: data.token, userId: data.user?.id, email };
}

/**
 * Make an authenticated API call.
 * @param {string} baseUrl
 * @param {string} path
 * @param {string} token
 * @param {object} [options]
 */
async function apiCall(baseUrl, path, token, options = {}) {
  const resp = await fetch(`${baseUrl}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });
  return resp.json();
}

module.exports = { registerUser, loginUser, seedAdminUser, apiCall };
