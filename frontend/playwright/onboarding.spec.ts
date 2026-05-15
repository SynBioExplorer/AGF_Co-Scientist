import { test, expect, type Page, type Route } from '@playwright/test';

async function mockBackend(page: Page): Promise<void> {
  await page.route('**/api/setup/status', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ completed: false, missing_steps: ['providers'] }),
    }),
  );
  await page.route('**/api/setup/validate-key', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ valid: true, available_models: ['gemini-2.5-flash'] }),
    }),
  );
  await page.route('**/api/setup/complete', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true }),
    }),
  );
  await page.route('**/api/runs', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    }),
  );
}

test('full onboarding flow', async ({ page }) => {
  await mockBackend(page);
  await page.goto('/');
  await expect(page).toHaveURL(/\/onboarding/);

  // Step 1
  await expect(page.getByText(/Welcome to AGF Co-Scientist/)).toBeVisible();
  await page.getByTestId('wizard-next').click();

  // Step 2 — providers
  await expect(page.getByText(/Connect a model provider/)).toBeVisible();
  await expect(page.getByTestId('wizard-next')).toBeDisabled();
  await page.getByTestId('provider-key-gemini').fill('sk-gemini');
  await expect(page.getByTestId('wizard-next')).toBeEnabled();
  await page.getByTestId('provider-test-gemini').click();
  await expect(page.getByText(/Validated successfully/i).first()).toBeVisible();
  await page.getByTestId('wizard-next').click();

  // Step 3 — optional
  await expect(page.getByText(/Optional services/)).toBeVisible();
  await page.getByTestId('wizard-next').click();

  // Step 4 — folder
  await expect(page.getByText(/Where should we save reports/)).toBeVisible();
  await page.getByTestId('export-folder-input').fill('/home/test/reports');
  await page.getByTestId('wizard-next').click();

  // Step 5 — email + finish
  await expect(page.getByText(/Email reports/)).toBeVisible();
  await page.getByTestId('wizard-finish').click();

  await expect(page).toHaveURL('/');
});
