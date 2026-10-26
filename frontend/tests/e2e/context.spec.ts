import { expect, test } from '@playwright/test';
test('смена компании изолирует заявки, возврат сохраняет ввод, выход завершает сессию', async ({
  page,
}) => {
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
  await page.getByLabel('Название компании').fill('Демонстрационная мастерская');
  await page
    .locator('header')
    .getByRole('link', { name: /Мастерская роста/ })
    .click();
  await page.getByRole('button', { name: /Кофе и дело/ }).click();
  await expect(page.getByText('Здесь появится ваша первая заявка')).toBeVisible();
  await page
    .locator('header')
    .getByRole('link', { name: /Кофе и дело/ })
    .click();
  await page.getByRole('button', { name: /Мастерская роста/ }).click();
  await page.getByRole('link', { name: 'Открыть', exact: true }).click();
  await expect(page.getByLabel('Название компании')).toHaveValue('Демонстрационная мастерская');
  const menu = page.getByRole('button', { name: 'Открыть меню' });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole('button', { name: 'Выйти', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Рады вас видеть' })).toBeVisible();
});
