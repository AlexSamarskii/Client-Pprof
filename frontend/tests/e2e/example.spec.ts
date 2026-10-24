import { test, expect, type Locator } from '@playwright/test';

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

// Original BF05 counter reproduction is preserved in the baseline artifacts.
for (const path of ['/', '/projects']) {
  test(`unauthenticated entry to ${path} requires sign-in`, async ({
    page,
    browserName,
  }) => {
    await page.route(`${AUTH_URL}/auth/v1/otp**`, (route) =>
      route.fulfill({ status: 200, json: {} }),
    );
    await page.goto(`${APP_URL}${path}`);

    await expect(page).toHaveURL(
      (url) =>
        url.origin === APP_URL &&
        url.pathname === '/login' &&
        url.searchParams.get('redirect') === path,
    );
    await expect(
      page.getByRole('link', { name: 'Рабочая панель', exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByRole('link', { name: 'Проекты', exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByRole('heading', { name: 'Проекты', exact: true }),
    ).toHaveCount(0);

    const email = page.getByLabel('Электронная почта', { exact: true });
    const continueButton = page.getByRole('button', {
      name: 'Продолжить',
      exact: true,
    });
    await expectReadableText(
      page.locator('label').filter({ hasText: 'Электронная почта' }),
    );
    await expect(email).toBeVisible();
    await expect(email).toBeEditable();
    // Safari on macOS uses Option+Tab to include buttons in keyboard navigation.
    await page.keyboard.press(browserName === 'webkit' ? 'Alt+Tab' : 'Tab');
    await expect(email).toBeFocused();
    await expect(continueButton).toBeVisible();
    await email.fill('protected-entry@example.test');
    await expect(continueButton).toBeEnabled();
    // Safari on macOS uses Option+Tab to include buttons in keyboard navigation.
    await page.keyboard.press(browserName === 'webkit' ? 'Alt+Tab' : 'Tab');
    await expect(continueButton).toBeFocused();
    expect(
      await continueButton.evaluate((node) => getComputedStyle(node).boxShadow),
    ).not.toBe('none');
    const contrast = await continueButton.evaluate((node) => {
      const canvas = document.createElement('canvas');
      canvas.width = 1;
      canvas.height = 1;
      const context = canvas.getContext('2d')!;
      const rgba = (value: string) => {
        context.clearRect(0, 0, 1, 1);
        context.fillStyle = value;
        context.fillRect(0, 0, 1, 1);
        return [...context.getImageData(0, 0, 1, 1).data];
      };
      const style = getComputedStyle(node);
      const foreground = rgba(style.color),
        background = rgba(style.backgroundColor);
      const light = (rgb: number[]) =>
        rgb
          .slice(0, 3)
          .map((v) => {
            const c = v / 255;
            return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
          })
          .reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);
      const first = light(foreground),
        second = light(background);
      return (
        (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05)
      );
    });
    expect(contrast).toBeGreaterThanOrEqual(4.5);

    const [request] = await Promise.all([
      page.waitForRequest(
        (request) =>
          request.url().startsWith(`${AUTH_URL}/auth/v1/otp`) &&
          request.method() === 'POST',
      ),
      page.keyboard.press('Enter'),
    ]);
    expect(request.postDataJSON()).toMatchObject({
      email: 'protected-entry@example.test',
    });
    await expect(
      page.getByText('Проверьте почту: мы отправили ссылку и код для входа.', {
        exact: true,
      }),
    ).toBeVisible();
    await expectReadableText(
      page.getByText('Проверьте почту: мы отправили ссылку и код для входа.', {
        exact: true,
      }),
    );
    await expectReadableText(
      page.locator('label').filter({ hasText: 'Код из письма' }),
    );
    await expect(page.getByLabel('Код из письма')).toBeVisible();
    await expect(page).toHaveURL((url) => url.pathname === '/login');
  });
}
