import { expect, test } from '@playwright/test';
test('полный путь: вход → заявка → предложение → оформление', async ({ page }, info) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/login');
  await expect(page.getByRole('heading', { name: 'Рады вас видеть' })).toBeVisible();
  await page.getByLabel('Как к вам обращаться?').fill('Александр');
  await page.getByRole('button', { name: 'Войти в кабинет' }).click();
  await page.getByRole('button', { name: /Мастерская роста/ }).click();
  await expect(page.getByRole('heading', { name: 'Добрый день, Александр' })).toBeVisible();
  await expect(page.getByText('Здесь появится ваша первая заявка')).toBeVisible();
  await expect(page.locator('body')).not.toHaveJSProperty('scrollWidth', 0);
  await page.screenshot({
    path: `test-results/workspace-${info.project.name}.png`,
    fullPage: true,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('link', { name: 'Подобрать финансирование', exact: true }).click();
  await page.getByRole('button', { name: 'Продолжить', exact: true }).click();
  await page.getByRole('button', { name: 'Подобрать варианты' }).click();
  await page
    .getByRole('article')
    .filter({ has: page.getByRole('heading', { name: 'Оборотный кредит', exact: true }) })
    .getByRole('link', { name: 'Подробнее' })
    .click();
  await page.getByRole('button', { name: 'Перейти к заявке' }).click();
  await expect(page.getByLabel('Название компании')).toHaveValue('ООО «Мастерская роста»');
  await page.getByRole('button', { name: 'К финансовым данным' }).click();
  const checks = page.getByRole('checkbox', { name: /Подтвердить:/ });
  await expect(checks).toHaveCount(8);
  for (const c of await checks.all()) await c.check();
  await page.getByRole('button', { name: 'К документам' }).click();
  await page.getByRole('checkbox', { name: /Подтверждаю полномочия/ }).check();
  await page.getByRole('link', { name: 'Проверить заявку' }).click();
  await page.getByRole('checkbox', { name: /Я проверил сведения/ }).check();
  await page.getByRole('button', { name: 'Отправить на рассмотрение' }).click();
  await expect(page.getByRole('heading', { name: 'Каждый шаг — на виду' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Предложение готово', exact: true })).toBeVisible({
    timeout: 15000,
  });
  await page.getByRole('link', { name: 'Продолжить', exact: true }).click();
  await page.getByRole('checkbox', { name: /Я ознакомился/ }).check();
  await page.getByRole('button', { name: 'Принять предложение', exact: true }).click();
  await page.getByRole('button', { name: 'Подтвердить', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Остался последний шаг' })).toBeVisible();
  await page.getByRole('checkbox', { name: /Я ознакомился/ }).check();
  await page.getByRole('button', { name: 'Завершить оформление' }).click();
  await page.getByRole('button', { name: 'Подтвердить', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Оформление завершено' }),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/completed-${info.project.name}.png`,
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
test('вход с клавиатуры и безопасный помощник', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Как к вам обращаться?').focus();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Войти в кабинет' })).toBeFocused();
  await page.keyboard.press('Enter');
  await page.getByRole('button', { name: /Мастерская роста/ }).click();
  await page.getByRole('link', { name: 'Спросить помощника' }).click();
  await page.getByLabel('Ваш вопрос').fill('Обещаешь одобрение?');
  await page.getByRole('button', { name: 'Отправить вопрос' }).click();
  await expect(page.getByText(/Я не могу оценить вероятность одобрения/)).toBeVisible();
  await page.getByRole('heading', { level: 1 }).focus();
  await expect(page.locator('h1')).toBeFocused();
});
