import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';
test('загрузка → OCR → явное подтверждение → скачивание CLEAN-файла', async ({ page }) => {
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
  await page.getByRole('button', { name: 'К документам' }).click();
  const content = Buffer.from('Synthetic report for frontend tests');
  await page
    .getByLabel('Загрузить документ')
    .setInputFiles({ name: 'demo.txt', mimeType: 'text/plain', buffer: content });
  await page.getByRole('button', { name: 'Сверить показатели' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByLabel('Выручка', { exact: true })).toHaveValue('12500000');
  for (const check of await dialog.getByRole('checkbox', { name: /Проверено по документу:/ }).all())
    await check.check();
  await dialog.getByLabel('Выручка', { exact: true }).fill('12900000');
  await expect(
    dialog.getByRole('checkbox', { name: 'Проверено по документу: Выручка', exact: true }),
  ).not.toBeChecked();
  await dialog
    .getByRole('checkbox', { name: 'Проверено по документу: Выручка', exact: true })
    .check();
  await dialog.getByRole('button', { name: 'Подтвердить проверенные значения' }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole('checkbox', { name: /Подтверждаю полномочия/ }).check();
  await page.getByRole('link', { name: 'Проверить заявку' }).click();
  await expect(page.getByText('12900000 ₽', { exact: false })).toBeVisible();
  await page.getByRole('checkbox', { name: /Я проверил сведения/ }).check();
  await page.getByRole('button', { name: 'Отправить на рассмотрение' }).click();
  await page.getByRole('link', { name: /Документы заявки/ }).click();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Скачать', exact: true }).click();
  const file = await downloaded;
  expect(file.suggestedFilename()).toBe('demo.txt');
  expect(await readFile((await file.path())!)).toEqual(content);
});
