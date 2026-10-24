import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
const scenario = process.env.E2E_SCENARIO ?? '';
test.skip(!scenario, 'Запускать с E2E_SCENARIO и сервером соответствующего VITE_DEMO_SCENARIO');
async function startApplication(page: Page) {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Войти в кабинет' }).click();
  await page.getByRole('button', { name: /Мастерская роста/ }).click();
  await page.getByRole('link', { name: 'Подобрать финансирование', exact: true }).click();
  await page.getByRole('button', { name: 'Продолжить', exact: true }).click();
  await page.getByRole('button', { name: 'Подобрать варианты' }).click();
  await page
    .getByRole('article')
    .filter({ has: page.getByRole('heading', { name: 'Оборотный кредит', exact: true }) })
    .getByRole('link', { name: 'Подробнее' })
    .click();
  await page.getByRole('button', { name: 'Перейти к заявке' }).click();
  await page.getByRole('button', { name: 'К финансовым данным' }).click();
  await expect(page.getByRole('checkbox', { name: /Подтвердить:/ })).toHaveCount(8);
  for (const check of await page.getByRole('checkbox', { name: /Подтвердить:/ }).all())
    await check.check();
}
async function submit(page: Page) {
  await page.getByRole('button', { name: 'К документам' }).click();
  await page.getByRole('checkbox', { name: /Подтверждаю полномочия/ }).check();
  await page.getByRole('link', { name: 'Проверить заявку' }).click();
  await page.getByRole('checkbox', { name: /Я проверил сведения/ }).check();
  await page.getByRole('button', { name: 'Отправить на рассмотрение' }).click();
  await expect(page.getByRole('heading', { name: 'Каждый шаг — на виду' })).toBeVisible();
}
test('проверка отдельного демосценария', async ({ page }) => {
  await startApplication(page);
  if (scenario === 'network') {
    await expect(page.getByText('Ошибка сохранения', { exact: true })).toBeVisible();
    await expect(async () => {
      await page.getByRole('button', { name: 'Повторить сохранение' }).click();
      await expect(page.getByText('Сохранено', { exact: true })).toBeVisible({ timeout: 1000 });
    }).toPass({ timeout: 12000, intervals: [600, 1500, 2500] });
  }
  if (scenario === 'conflict') {
    await page.getByRole('button', { name: 'Сопоставить версии' }).click();
    await expect(page.getByRole('heading', { name: /Сервер · версия/ })).toBeVisible();
    await page.getByRole('button', { name: /Сохранить мой ввод поверх/ }).click();
    await expect(page.getByText('Сохранено', { exact: true })).toBeVisible();
  }
  if (scenario === 'ocr-failed') {
    await page.getByRole('button', { name: 'К документам' }).click();
    await page.getByLabel('Загрузить документ').setInputFiles({
      name: 'demo.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Synthetic financial report'),
    });
    await expect(page.getByText('Распознавание не удалось', { exact: true })).toBeVisible({
      timeout: 10000,
    });
    await page.getByRole('checkbox', { name: /Подтверждаю полномочия/ }).check();
    await page.getByRole('link', { name: 'Проверить заявку' }).click();
    await page.getByRole('checkbox', { name: /Я проверил сведения/ }).check();
    await page.getByRole('button', { name: 'Отправить на рассмотрение' }).click();
  } else await submit(page);
  if (scenario === 'rfi') {
    await expect(page.getByRole('heading', { name: 'Нужно уточнение', exact: true })).toBeVisible({
      timeout: 15000,
    });
    await page.getByRole('link', { name: 'Продолжить', exact: true }).click();
    await expect(page.getByLabel('EBIT', { exact: true })).toHaveAttribute('readonly', '');
    await page.getByLabel('Выручка', { exact: true }).fill('13000000');
    await page.getByRole('checkbox', { name: 'Подтверждаю уточнённые сведения' }).check();
    await page.getByLabel('Загрузить документ').setInputFiles({
      name: 'revenue.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Synthetic revenue evidence'),
    });
    await expect(page.getByText('Проверен', { exact: true })).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'Отправить ответ' }).click();
    await expect(
      page.getByRole('heading', { name: 'Предложение готово', exact: true }),
    ).toBeVisible({ timeout: 15000 });
  } else if (scenario === 'manual') {
    await expect(page.getByRole('heading', { name: 'Ручная проверка', exact: true })).toBeVisible({
      timeout: 15000,
    });
    await expect(page.getByText('Это не отказ.', { exact: false })).toBeVisible();
  } else if (scenario === 'declined') {
    await expect(
      page.getByRole('heading', { name: 'Отрицательное решение', exact: true }),
    ).toBeVisible({ timeout: 15000 });
  } else
    await expect(
      page.getByRole('heading', { name: 'Предложение готово', exact: true }),
    ).toBeVisible({ timeout: 15000 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
