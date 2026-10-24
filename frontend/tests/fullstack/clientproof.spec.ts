import { expect, test, type Page } from '@playwright/test';

interface ProjectFixture {
  project_id: string;
  version_id: string;
  grant_id: string;
  name: string;
}
interface Fixture {
  organization_id: string;
  users: Record<
    'owner' | 'client' | 'foreign' | 'workflow_client',
    { id: string; email: string }
  >;
  projects: Record<string, ProjectFixture>;
}
if (
  !process.env.CP_FIXTURE_JSON ||
  !process.env.CP_FRONTEND_URL ||
  !process.env.CP_MAIL_URL ||
  !process.env.CLIENTPROOF_TEST_API_URL ||
  !process.env.CLIENTPROOF_TEST_OWNER_TOKEN
) {
  throw new Error(
    'Run scripts/run_local_acceptance.py --verify; genuine owned runtime is required',
  );
}
const fixture: Fixture = JSON.parse(process.env.CP_FIXTURE_JSON) as Fixture;
const api = process.env.CLIENTPROOF_TEST_API_URL;
const mail = process.env.CP_MAIL_URL;

async function signIn(page: Page, email: string) {
  expect(
    process.env.CP_FRONTEND_URL,
    'Run scripts/run_local_acceptance.py --verify',
  ).toBeTruthy();
  const before = await page.request.get(`${mail}/api/v1/messages`);
  const previous = (await before.json()) as { messages: { ID: string }[] };
  const previousIds = new Set(previous.messages.map((message) => message.ID));
  await page.goto('/login');
  await page.locator('#email').fill(email);
  const continueButton = page.getByRole('button', {
    name: 'Продолжить',
    exact: true,
  });
  await page.locator('#email').press('Tab');
  await expect(continueButton).toBeFocused();
  await continueButton.press('Enter');
  let otp = '';
  await expect
    .poll(
      async () => {
        const response = await page.request.get(`${mail}/api/v1/messages`);
        const listing = (await response.json()) as {
          messages: { ID: string; To: { Address: string }[] }[];
        };
        for (const message of listing.messages) {
          if (previousIds.has(message.ID)) continue;
          if (!message.To.some((recipient) => recipient.Address === email))
            continue;
          const detail = await page.request.get(
            `${mail}/api/v1/message/${message.ID}`,
          );
          const body = (await detail.json()) as { Text: string; HTML: string };
          otp = (body.Text + ' ' + body.HTML).match(/\b\d{6}\b/)?.[0] ?? '';
          if (otp) return true;
        }
        return false;
      },
      {
        timeout: 30_000,
        message: 'Genuine GoTrue OTP delivered to owned SMTP mailbox',
      },
    )
    .toBe(true);
  await page.locator('input[autocomplete="one-time-code"]').fill(otp);
  await page.locator('input[autocomplete="one-time-code"]').press('Tab');
  await expect(continueButton).toBeFocused();
  await continueButton.press('Enter');
  await expect(page).not.toHaveURL(/\/login/);
}

test('staff creates a client, project, deliverable and published version through the actual UI', async ({
  page,
  request,
}) => {
  const headers = {
    Authorization: `Bearer ${process.env.CLIENTPROOF_TEST_OWNER_TOKEN ?? ''}`,
  };
  const overdueProject = fixture.projects.browser_approved;
  const deadline = await request.patch(
    `${api}/api/v1/clientproof/projects/${overdueProject.project_id}`,
    { headers, data: { response_deadline_at: '2001-01-01T00:00:00Z' } },
  );
  expect(deadline.status()).toBe(200);
  const persisted = await request.get(`${api}/api/v1/clientproof/projects`, {
    headers,
  });
  expect(persisted.status()).toBe(200);
  const dashboardProjects = (await persisted.json()) as {
    name: string;
    status: string;
    response_deadline_at: string | null;
  }[];
  await signIn(page, fixture.users.owner.email);
  await page.goto('/');
  await expect(
    page.getByRole('heading', { name: 'Рабочая панель', exact: true }),
  ).toBeVisible();
  for (const [status, label] of [
    ['in_review', 'Ожидают согласования'],
    ['draft', 'Черновики'],
    ['approved', 'Принятые проекты'],
    ['changes_requested', 'На доработке'],
  ]) {
    const expectedProjects = dashboardProjects.filter(
      (project) => project.status === status,
    );
    expect(expectedProjects.length).toBeGreaterThan(0);
    const region = page.getByRole('region', { name: label, exact: true });
    await expect(
      region.getByRole('link', { name: 'Открыть проект', exact: true }),
    ).toHaveCount(expectedProjects.length);
    for (const project of expectedProjects) {
      await expect(
        region.getByText(project.name, { exact: true }),
      ).toBeVisible();
    }
  }
  const overdue = page.getByRole('region', {
    name: 'Просроченные ответы',
    exact: true,
  });
  const overdueProjects = dashboardProjects.filter(
    (project) =>
      project.status === 'in_review' &&
      project.response_deadline_at !== null &&
      Date.parse(project.response_deadline_at) < Date.now(),
  );
  await expect(
    overdue.getByRole('link', { name: 'Открыть проект', exact: true }),
  ).toHaveCount(overdueProjects.length);
  await expect(
    overdue.getByText(overdueProject.name, { exact: true }),
  ).toBeVisible();
  const projectLink = page
    .getByRole('link', { name: 'Открыть проект', exact: true })
    .first();
  await projectLink.focus();
  await page.keyboard.press('Shift+Tab');
  await page.keyboard.press('Tab');
  await expect(projectLink).toBeFocused();
  expect(
    await projectLink.evaluate((node) => getComputedStyle(node).boxShadow),
  ).not.toBe('none');
  const contrast = await projectLink.evaluate((node) => {
    const context = document.createElement('canvas').getContext('2d')!;
    const luminance = (color: string) => {
      context.clearRect(0, 0, 1, 1);
      context.fillStyle = color;
      context.fillRect(0, 0, 1, 1);
      const rgba = [...context.getImageData(0, 0, 1, 1).data];
      // This primary dashboard action must supply an opaque background.
      if (rgba[3] !== 255) throw new Error('Expected opaque action colors');
      return rgba.slice(0, 3).reduce((sum, value, index) => {
        const channel = value / 255;
        const linear =
          channel <= 0.04045
            ? channel / 12.92
            : ((channel + 0.055) / 1.055) ** 2.4;
        return sum + linear * [0.2126, 0.7152, 0.0722][index];
      }, 0);
    };
    const style = getComputedStyle(node);
    const foreground = luminance(style.color);
    const background = luminance(style.backgroundColor);
    return (
      (Math.max(foreground, background) + 0.05) /
      (Math.min(foreground, background) + 0.05)
    );
  });
  expect(contrast).toBeGreaterThanOrEqual(4.5);
  await projectLink.press('Enter');
  await expect(page).toHaveURL(/\/projects\/[a-f0-9-]+$/);
  await expect(
    page.getByRole('region', { name: 'Работа с результатами' }),
  ).toBeVisible();
  await page.goto('/clients');
  await page
    .getByLabel('Имя клиента', { exact: true })
    .fill('Клиент полного UI цикла');
  await page
    .getByLabel('Электронная почта клиента')
    .fill(fixture.users.workflow_client.email);
  await page
    .getByLabel('Идентификатор клиента в Auth')
    .fill(fixture.users.workflow_client.id);
  await page.getByRole('button', { name: 'Добавить клиента' }).click();
  await expect(
    page.getByText('Клиент добавлен.', { exact: true }),
  ).toBeVisible();
  await page.goto('/projects');
  await page
    .getByLabel('Клиент', { exact: true })
    .selectOption({ label: 'Клиент полного UI цикла' });
  await page
    .getByLabel('Название', { exact: true })
    .fill('Проект полного UI цикла');
  const created = page.waitForResponse(
    (response) =>
      response.url().endsWith('/projects') &&
      response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Создать проект' }).click();
  const response = await created;
  expect(response.status()).toBe(200);
  const project = (await response.json()) as { id: string };
  await page.goto(`/projects/${project.id}`);
  await page
    .getByLabel('Название результата')
    .fill('Результат полного UI цикла');
  await page.getByLabel('Название результата').press('Tab');
  const createDeliverable = page.getByRole('button', {
    name: 'Создать результат',
  });
  await expect(createDeliverable).toBeFocused();
  await createDeliverable.press('Enter');
  await expect(
    page.getByText('Результат создан.', { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel('Результат для версии')
    .selectOption({ label: 'Результат полного UI цикла' });
  await page.getByLabel('Название версии').fill('Версия из настоящего UI');
  await page
    .getByLabel('Содержимое версии')
    .fill('Содержимое сохранено настоящим API в PostgreSQL.');
  await page.getByRole('button', { name: 'Создать черновик' }).click();
  await expect(
    page.getByText('Черновик сохранён.', { exact: true }),
  ).toBeVisible();
  await page.getByLabel('Файл к черновику').setInputFiles({
    name: 'ui-result.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('real private upload from actual browser UI'),
  });
  await page.getByRole('button', { name: 'Загрузить файл' }).click();
  await expect(page.getByText('Файл загружен.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Опубликовать версию' }).click();
  await expect(
    page.getByText('Версия опубликована.', { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole('heading', { name: 'Версия из настоящего UI' }),
  ).toBeVisible();
  await expect(
    page.getByText('Содержимое сохранено настоящим API в PostgreSQL.', {
      exact: true,
    }),
  ).toBeVisible();
});

for (const outcome of ['approved', 'changes_requested'] as const) {
  test(`genuine OTP, persisted ${outcome}, reload and revocation`, async ({
    page,
    request,
  }) => {
    const project = fixture.projects[`browser_${outcome}`];
    // No route interception, no injected localStorage/session, no auth bypass.
    await signIn(page, fixture.users.client.email);
    await page.goto('/projects');
    await expect(page.getByText(project.name, { exact: true })).toBeVisible();
    await page.goto(`/projects/${project.project_id}`);
    await expect(
      page.getByRole('heading', { name: project.name }),
    ).toBeVisible();
    await expect(
      page.getByRole('region', { name: 'Работа с результатами' }),
    ).toHaveCount(0);
    await expect(
      page.getByRole('button', { name: 'Выдать доступ' }),
    ).toHaveCount(0);
    const comment = `Сохранённый браузерный комментарий ${outcome}`;
    await page.getByLabel('Новый комментарий').fill(comment);
    await page.getByRole('button', { name: 'Добавить комментарий' }).click();
    await expect(page.getByText(comment, { exact: true })).toBeVisible();
    if (outcome === 'approved') {
      await page.getByRole('button', { name: 'Принять', exact: true }).click();
      await page.getByRole('button', { name: 'Подтвердить приёмку' }).click();
    } else {
      await page
        .getByRole('button', { name: 'На доработку', exact: true })
        .click();
    }
    const expectedOutcome =
      outcome === 'approved' ? 'Принято • активное' : 'На доработку • активное';
    const escapedOutcome = expectedOutcome.replace(
      /[.*+?^${}()|[\]\\]/g,
      '\\$&',
    );
    // The visible history row includes the persisted creation timestamp.
    const historyRow = page.getByRole('listitem').filter({
      hasText: new RegExp(
        `^${escapedOutcome} • \\d{2}\\.\\d{2}\\.\\d{4},?\\s+\\d{2}:\\d{2}:\\d{2}$`,
      ),
    });
    await expect(historyRow).toBeVisible();
    await page.reload();
    await expect(page.getByText(comment, { exact: true })).toBeVisible();
    await expect(historyRow).toBeVisible();
    const prefix = `${api}/api/v1/clientproof/projects/${project.project_id}`;
    const headers = {
      Authorization: `Bearer ${process.env.CLIENTPROOF_TEST_OWNER_TOKEN ?? ''}`,
    };
    const persisted = await request.get(
      `${prefix}/versions/${project.version_id}/decisions`,
      { headers },
    );
    expect(persisted.status()).toBe(200);
    expect(
      ((await persisted.json()) as { decision: string }[]).map(
        (item) => item.decision,
      ),
    ).toEqual([outcome]);
    const revoked = await request.post(
      `${prefix}/grants/${project.grant_id}/revoke`,
      { headers },
    );
    expect(revoked.status()).toBe(200);
    await page.reload();
    await expect(page.getByRole('alert').first()).toBeVisible();
    await expect(page.getByLabel('Новый комментарий')).toHaveCount(0);
    await page.goto('/projects');
    await expect(page.getByText(project.name, { exact: true })).toHaveCount(0);
  });
}
