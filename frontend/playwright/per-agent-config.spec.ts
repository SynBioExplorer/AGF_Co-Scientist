import { test, expect, type Page, type Route } from '@playwright/test';

let saved: unknown = null;

async function mockBackend(page: Page): Promise<void> {
  await page.route('**/api/setup/status', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ completed: true, missing_steps: [] }),
    }),
  );
  await page.route('**/api/runs', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    }),
  );

  await page.route('**/api/settings/agent-models', async (route: Route) => {
    if (route.request().method() === 'PUT') {
      saved = JSON.parse(route.request().postData() ?? '{}');
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        saved ?? {
          default: { provider: 'gemini', model: 'gemini-2.5-flash', temperature: 0.7 },
          agents: {
            generation: null,
            reflection: null,
            ranking: null,
            evolution: null,
            proximity: null,
            meta_review: null,
            supervisor: null,
            safety: null,
          },
        },
      ),
    });
  });

  await page.route('**/api/settings/available-models**', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ models: ['gpt-4o', 'gpt-4o-mini'] }),
    }),
  );

  await page.route('**/api/settings/secrets', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        providers: {
          gemini: { set: true, masked: '••••1234' },
          openai: { set: false, masked: '' },
          deepseek: { set: false, masked: '' },
          anthropic: { set: false, masked: '' },
        },
        optional: {
          tavily: { set: false, masked: '' },
          semantic_scholar: { enabled: true },
          pubmed: { set: false, masked: '' },
        },
        email: { enabled: false, recipient: '' },
        export_folder: '/tmp',
      }),
    }),
  );
}

test('per-agent model override persists across reload', async ({ page }) => {
  await mockBackend(page);
  await page.goto('/settings');

  await page.getByTestId('tab-models').click();
  await expect(page.getByTestId('agent-row-generation')).toBeVisible();

  await page.getByTestId('provider-select-generation').selectOption('openai');
  await page.getByTestId('save-models').click();

  await page.waitForTimeout(200);
  expect(saved).toBeTruthy();

  // Reload and verify the agent override was kept.
  await page.reload();
  await page.getByTestId('tab-models').click();
  await expect(page.getByTestId('provider-select-generation')).toHaveValue('openai');
});
