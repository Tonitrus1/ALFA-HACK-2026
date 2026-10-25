import { test, expect } from '@playwright/test';

test('money input groups rubles and preserves editing and kopecks', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/session')
      return route.fulfill({
        json: {
          userId: 'money-user',
          companyId: 'company-a',
          contextVersion: 1,
          csrfToken: 'test',
          expiresAt: '2099-01-01T00:00:00Z',
        },
      });
    if (path === '/api/v1/companies')
      return route.fulfill({
        json: {
          items: [
            {
              companyId: 'company-a',
              displayName: 'Компания А',
              taxId: '7701234567',
            },
          ],
        },
      });
    if (path === '/api/v1/products')
      return route.fulfill({
        json: {
          items: [
            {
              productId: 'working-capital',
              version: 1,
              name: 'Оборотный кредит',
              purpose: 'Развитие бизнеса',
              minAmount: { amountMinor: 10000000 },
              maxAmount: { amountMinor: 5000000000 },
              maxMonths: 36,
              preliminaryDisclosure: 'Предварительные условия',
            },
          ],
        },
      });
    throw new Error('Unexpected request: ' + path);
  });
  await page.goto('/needs');
  await page.getByRole('button', { name: 'Продолжить', exact: true }).click();
  const amount = page.locator('#amount');
  await expect(amount).toHaveValue('3 000 000');
  await amount.fill('');
  await amount.pressSequentially('3000000,01');
  await expect(amount).toHaveValue('3 000 000,01');
  await amount.fill('1234567');
  await amount.evaluate((element: HTMLInputElement) => element.setSelectionRange(2, 2));
  await amount.press('Backspace');
  await expect(amount).toHaveValue('234 567');
  await amount.fill('1234567');
  await amount.evaluate((element: HTMLInputElement) => element.setSelectionRange(1, 1));
  await amount.press('Delete');
  await expect(amount).toHaveValue('134 567');
  await amount.fill('1234567');
  await amount.evaluate((element: HTMLInputElement) => element.setSelectionRange(3, 3));
  await amount.pressSequentially('9');
  await expect(amount).toHaveValue('12 934 567');
  expect(await amount.evaluate((element: HTMLInputElement) => element.selectionStart)).toBe(4);
  await amount.fill('-1234567,89');
  await expect(amount).toHaveValue('-1 234 567,89');
  await amount.fill('3\u00a0000\u202f000,01');
  await expect(amount).toHaveValue('3 000 000,01');
  await page.getByRole('button', { name: 'Подобрать варианты' }).click();
  await expect(page).toHaveURL(/\/products$/);
  await page.getByRole('link', { name: 'Подробнее' }).first().click();
  await expect(page.getByText('Введено: 3 000 000,01 ₽')).toBeVisible();
  expect(errors).toEqual([]);
});
