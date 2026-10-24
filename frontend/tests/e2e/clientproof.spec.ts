import { expect, test, type Locator, type Page } from '@playwright/test';

async function expectReadableText(locator: Locator) {
  await expect(locator).toBeVisible();
  const contrast = await locator.evaluate((node) => {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 1;
    const context = canvas.getContext('2d')!;
    const rgba = (value: string) => {
      context.clearRect(0, 0, 1, 1);
      context.fillStyle = value;
      context.fillRect(0, 0, 1, 1);
      return [...context.getImageData(0, 0, 1, 1).data].map((n) => n / 255);
    };
    const over = (front: number[], back: number[]) =>
      front
        .slice(0, 3)
        .map((n, i) => n * front[3] + back[i] * (1 - front[3]))
        .concat(1);
    const layers: number[][] = [];
    for (
      let element: Element | null = node;
      element;
      element = element.parentElement
    ) {
      layers.push(rgba(getComputedStyle(element).backgroundColor));
    }
    const background = layers
      .reverse()
      .reduce((back, front) => over(front, back), [1, 1, 1, 1]);
    const foreground = over(rgba(getComputedStyle(node).color), background);
    const light = (rgb: number[]) =>
      rgb
        .slice(0, 3)
        .map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
        .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);
    return (
      (Math.max(light(foreground), light(background)) + 0.05) /
      (Math.min(light(foreground), light(background)) + 0.05)
    );
  });
  expect(
    contrast,
    `Rendered text contrast: ${await locator.textContent()}`,
  ).toBeGreaterThanOrEqual(4.5);
}

const APP_URL = 'http://127.0.0.1:5173';
const AUTH_URL = 'http://127.0.0.1:54321';
const BACKEND_URL = 'http://127.0.0.1:8000';
const ORGANIZATION_ID = '11111111-1111-4111-8111-111111111111';
const PROJECT_ID = '22222222-2222-4222-8222-222222222222';
const VERSION_ID = '55555555-5555-4555-8555-555555555555';

function authResponse() {
  return {
    access_token: 'e2e-access-token',
    token_type: 'bearer',
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    refresh_token: 'e2e-refresh-token',
    user: {
      id: '33333333-3333-4333-8333-333333333333',
      aud: 'authenticated',
      role: 'authenticated',
      email: 'client@example.test',
      app_metadata: {},
      user_metadata: {},
      created_at: '2026-03-20T10:00:00Z',
    },
  };
}

async function installMocks(page: Page) {
  await page.route(`${AUTH_URL}/auth/v1/otp**`, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
  );
  await page.route(`${AUTH_URL}/auth/v1/verify`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(authResponse()),
    }),
  );
  await page.route(`${BACKEND_URL}/api/v1/org`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: ORGANIZATION_ID,
          name: 'Agency',
          created_at: '2026-03-20T10:00:00Z',
          updated_at: null,
          deleted_at: null,
          additional_data: {},
          billing_is_paid: true,
          billing_cancel_at_period_end: false,
        },
      ]),
    }),
  );
  await page.route(
    `${BACKEND_URL}/api/v1/org/${ORGANIZATION_ID}/users/33333333-3333-4333-8333-333333333333`,
    (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: '33333333-3333-4333-8333-333333333333',
          created_at: '2026-03-20T10:00:00Z',
          username: 'external-client',
          email: 'client@example.test',
          additional_data: {},
        }),
      }),
  );
  await page.route(
    `${BACKEND_URL}/api/v1/org/${ORGANIZATION_ID}/membership`,
    (route) =>
      route.fulfill({
        status: 403,
        contentType: 'application/json',
        body: '"Forbidden"',
      }),
  );
  await page.route(`${BACKEND_URL}/api/v1/clientproof/projects`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: PROJECT_ID,
          organization_id: ORGANIZATION_ID,
          client_id: '44444444-4444-4444-8444-444444444444',
          name: 'Granted project',
          description: null,
          status: 'in_review',
          response_deadline_at: '2026-03-25T10:00:00Z',
          archived_at: null,
          created_at: '2026-03-20T10:00:00Z',
        },
      ]),
    }),
  );
  await page.route(
    `${BACKEND_URL}/api/v1/clientproof/projects/${PROJECT_ID}`,
    (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: PROJECT_ID,
          organization_id: ORGANIZATION_ID,
          client_id: '44444444-4444-4444-8444-444444444444',
          name: 'Granted project',
          description: null,
          status: 'in_review',
          response_deadline_at: '2026-03-25T10:00:00Z',
          archived_at: null,
          created_at: '2026-03-20T10:00:00Z',
        }),
      }),
  );
  await page.route(
    `${BACKEND_URL}/api/v1/clientproof/projects/${PROJECT_ID}/deliverables`,
    (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '[]',
      }),
  );
  await page.route(
    `${BACKEND_URL}/api/v1/clientproof/projects/${PROJECT_ID}/versions`,
    (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: VERSION_ID,
            deliverable_id: '00000000-0000-4000-8000-000000000000',
            version_number: 1,
            title: 'Первый вариант',
            content: 'Содержимое версии',
            review_seq: 1,
            published_at: '2026-03-20T11:00:00Z',
            created_at: '2026-03-20T10:30:00Z',
          },
        ]),
      }),
  );
}

test('external client signs in with email OTP and sees a granted project', async ({
  page,
}) => {
  await installMocks(page);
  await page.goto(`${APP_URL}/login`);
  await page.getByLabel('Электронная почта').fill('client@example.test');
  await page.getByRole('button', { name: 'Продолжить' }).click();
  await expect(
    page.getByText('Проверьте почту: мы отправили ссылку и код для входа.'),
  ).toBeVisible();
  await page.getByLabel('Код из письма').fill('123456');
  await page.getByRole('button', { name: 'Продолжить' }).click();
  await expect(page).toHaveURL(`${APP_URL}/`);
  await expectReadableText(
    page.getByRole('heading', { name: 'Рабочая панель', exact: true }),
  );
  await expectReadableText(
    page.getByRole('heading', { name: 'Ожидают согласования', exact: true }),
  );
  await expectReadableText(
    page.getByRole('link', { name: 'Открыть проект', exact: true }).first(),
  );
  await expectReadableText(page.getByText('Статус:', { exact: false }).first());

  await page.goto(`${APP_URL}/projects`);
  await expect(page.getByRole('heading', { name: 'Проекты' })).toBeVisible();
  await expect(page.getByText('Granted project')).toBeVisible();
});

for (const outcome of ['approved', 'changes_requested'] as const) {
  test(`external client comments and records ${outcome} for a granted version`, async ({
    page,
    browserName,
  }) => {
    await installMocks(page);
    await page.addInitScript((auth) => {
      globalThis.localStorage.setItem(
        'sb-127-auth-token',
        JSON.stringify(auth),
      );
    }, authResponse());
    const comments: unknown[] = [];
    const decisions: unknown[] = [];
    await page.route(
      `${BACKEND_URL}/api/v1/clientproof/projects/${PROJECT_ID}/versions/${VERSION_ID}/comments`,
      async (route) => {
        if (route.request().method() === 'GET') {
          await route.fulfill({ json: comments });
          return;
        }
        const body = route.request().postDataJSON() as { body: string };
        const comment = {
          id: '66666666-6666-4666-8666-666666666666',
          version_id: VERSION_ID,
          author_user_id: null,
          author_client_id: '44444444-4444-4444-8444-444444444444',
          body: body.body,
          created_at: '2026-03-20T11:00:00Z',
        };
        comments.push(comment);
        await route.fulfill({ json: comment });
      },
    );
    await page.route(
      `${BACKEND_URL}/api/v1/clientproof/projects/${PROJECT_ID}/versions/${VERSION_ID}/decisions`,
      (route) => route.fulfill({ json: decisions }),
    );
    await page.route(
      `${BACKEND_URL}/api/v1/clientproof/projects/${PROJECT_ID}/versions/${VERSION_ID}/decision`,
      async (route) => {
        if (decisions.length > 0) {
          await route.fulfill({
            status: 409,
            json: { detail: { kind: 'decision_conflict' } },
          });
          return;
        }
        const body = route.request().postDataJSON() as { decision: string };
        const decision = {
          id: '77777777-7777-4777-8777-777777777777',
          version_id: VERSION_ID,
          client_id: '44444444-4444-4444-8444-444444444444',
          decision: body.decision,
          active: true,
          created_at: '2026-03-20T11:00:00Z',
        };
        decisions.push(decision);
        await route.fulfill({ json: decision });
      },
    );
    await page.route(
      `${BACKEND_URL}/api/v1/clientproof/projects/${PROJECT_ID}/versions/${VERSION_ID}/files`,
      (route) => route.fulfill({ json: [] }),
    );
    await page.goto(`${APP_URL}/projects/${PROJECT_ID}`);
    await expectReadableText(
      page.getByRole('heading', { name: 'Granted project', exact: true }),
    );
    await expectReadableText(
      page.getByText('Комментарии и решения привязаны к версии.', {
        exact: true,
      }),
    );
    await expectReadableText(
      page.getByText('Содержимое версии', { exact: true }),
    );
    await expectReadableText(
      page.locator('label').filter({ hasText: 'Новый комментарий' }),
    );
    await expectReadableText(
      page.getByRole('button', { name: 'Добавить комментарий', exact: true }),
    );
    // Wait for the real membership query's retry policy to settle its 403.
    await expect(
      page.getByRole('button', { name: 'Принять', exact: true }),
    ).toBeVisible({ timeout: 15_000 });
    await expectReadableText(
      page.getByRole('button', { name: 'Принять', exact: true }),
    );
    await expectReadableText(
      page.getByRole('button', { name: 'На доработку', exact: true }),
    );
    await page.getByLabel('Новый комментарий').focus();
    await page.keyboard.type('Нужны правки');
    // Safari on macOS uses Option+Tab to include buttons in keyboard navigation.
    await page.keyboard.press(browserName === 'webkit' ? 'Alt+Tab' : 'Tab');
    await expect(
      page.getByRole('button', { name: 'Добавить комментарий' }),
    ).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.getByText('Нужны правки')).toBeVisible();
    await expectReadableText(page.getByText('Нужны правки', { exact: true }));
    if (outcome === 'approved') {
      await page.getByRole('button', { name: 'Принять', exact: true }).focus();
      await page.keyboard.press('Enter');
      await expectReadableText(
        page.getByRole('button', { name: 'Подтвердить приёмку' }),
      );
      await expectReadableText(
        page.getByRole('button', { name: 'Отмена', exact: true }),
      );
      await page.getByRole('button', { name: 'Подтвердить приёмку' }).focus();
      await page.keyboard.press('Enter');
    } else {
      await page.getByRole('button', { name: 'На доработку' }).focus();
      await page.keyboard.press('Enter');
    }
    await expect(
      page.getByText(
        `${outcome === 'approved' ? 'Принято' : 'На доработку'} • активное`,
        { exact: false },
      ),
    ).toBeVisible();
    await page.reload();
    await expect(page.getByText('Нужны правки')).toBeVisible();
    await expect(
      page.getByText(
        `${outcome === 'approved' ? 'Принято' : 'На доработку'} • активное`,
        { exact: false },
      ),
    ).toBeVisible();
    if (outcome === 'approved') {
      await page.getByRole('button', { name: 'На доработку' }).focus();
      await page.keyboard.press('Enter');
    } else {
      await page.getByRole('button', { name: 'Принять', exact: true }).focus();
      await page.keyboard.press('Enter');
      await page.getByRole('button', { name: 'Подтвердить приёмку' }).focus();
      await page.keyboard.press('Enter');
    }
    await expect(page.getByRole('alert')).toHaveText(
      'Решение уже зафиксировано. Обновите статус версии.',
    );
    expect(decisions).toHaveLength(1);
    await expect(
      page.getByText(
        `${outcome === 'approved' ? 'Принято' : 'На доработку'} • активное`,
        { exact: false },
      ),
    ).toBeVisible();
  });
}
