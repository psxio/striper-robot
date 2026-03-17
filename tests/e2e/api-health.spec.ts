import { test, expect } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

// Share a single registration across tests to stay within rate limits
let sharedToken: string;
let sharedEmail: string;

test.describe('API Health & Backend Integration', () => {

  test('health endpoint returns ok', async ({ request }) => {
    const resp = await request.get('/api/health');
    expect(resp.ok()).toBeTruthy();
    const data = await resp.json();
    expect(data.status).toBe('ok');
  });

  test('unauthenticated API calls are rejected', async ({ request }) => {
    const resp = await request.get('/api/auth/me');
    expect([401, 403]).toContain(resp.status());
  });

  test('register and login flow via API', async ({ request }) => {
    sharedEmail = `e2e_api_${Date.now()}@test.com`;

    // Register
    const registerResp = await request.post('/api/auth/register', {
      data: { email: sharedEmail, password: 'TestPass123!', name: 'API Test' },
    });
    expect(registerResp.ok()).toBeTruthy();
    const registerData = await registerResp.json();
    expect(registerData.token).toBeTruthy();
    expect(registerData.user.email).toBe(sharedEmail);
    sharedToken = registerData.token;

    // Login
    const loginResp = await request.post('/api/auth/login', {
      data: { email: sharedEmail, password: 'TestPass123!' },
    });
    expect(loginResp.ok()).toBeTruthy();
    const loginData = await loginResp.json();
    expect(loginData.token).toBeTruthy();
    sharedToken = loginData.token;

    // Authenticated request
    const meResp = await request.get('/api/auth/me', {
      headers: { Authorization: `Bearer ${sharedToken}` },
    });
    expect(meResp.ok()).toBeTruthy();
    const me = await meResp.json();
    expect(me.email).toBe(sharedEmail);
  });

  test('GDPR export returns JSON with all data sections', async ({ request }) => {
    const headers = { Authorization: `Bearer ${sharedToken}` };

    // Create a lot using the shared user
    await request.post('/api/lots', {
      headers,
      data: { name: 'GDPR Test Lot', center: { lat: 40, lng: -74 }, features: [] },
    });

    // Export
    const exportResp = await request.get('/api/user/export', { headers });
    expect(exportResp.ok()).toBeTruthy();

    const data = await exportResp.json();
    expect(data).toHaveProperty('user');
    expect(data).toHaveProperty('lots');
    expect(data).toHaveProperty('jobs');
    expect(data).toHaveProperty('subscriptions');
    expect(data).toHaveProperty('schedules');
    expect(data.user.email).toBe(sharedEmail);
    expect(data.lots.length).toBeGreaterThanOrEqual(1);
  });

  test('free plan cannot access cost estimation', async ({ request }) => {
    const headers = { Authorization: `Bearer ${sharedToken}` };

    const resp = await request.post('/api/estimates/calculate', {
      headers,
      data: { features: [] },
    });
    expect(resp.status()).toBe(403);
  });

  test('duplicate lot blocked for free plan at limit', async ({ request }) => {
    const headers = { Authorization: `Bearer ${sharedToken}` };

    // List lots to find existing one (created in GDPR test above)
    const listResp = await request.get('/api/lots', { headers });
    const lots = (await listResp.json()).items;
    expect(lots.length).toBeGreaterThan(0);
    const lotId = lots[0].id;

    // Duplicate should be blocked (free plan already at 1 lot)
    const dup = await request.post(`/api/lots/${lotId}/duplicate`, { headers });
    expect(dup.status()).toBe(403);
  });

  test('login with wrong password fails', async ({ request }) => {
    const resp = await request.post('/api/auth/login', {
      data: { email: sharedEmail, password: 'WrongPassword!' },
    });
    expect(resp.ok()).toBeFalsy();
  });
});
