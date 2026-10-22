import { test, expect, type Page } from '@playwright/test';
const finance={totalAssets:'1000000',totalLiabilities:'400000',currentAssets:'500000',currentLiabilities:'200000',equity:'600000',revenue:'3000000',netProfit:'100000',ebit:'150000'};
async function login(page:Page,account='representative-a'){
 await page.goto('/login');await page.locator('#name').selectOption(account);await page.getByRole('button',{name:'Войти в кабинет'}).click();await expect(page.getByRole('heading',{name:'От имени какой компании работаем?'})).toBeVisible();await page.getByRole('button',{name:/Перейти в кабинет|Активная компания/}).first().click();await expect(page.getByRole('heading',{name:/Добрый день/})).toBeVisible();
}
async function create(page:Page,preliminary?:string){
 await page.goto('/needs');await page.getByRole('button',{name:'Продолжить',exact:true}).click();await page.locator('#amount').fill('500000');await page.getByRole('button',{name:'Подобрать варианты'}).click();await page.getByRole('link',{name:'Подробнее'}).first().click();await page.getByRole('button',{name:/Перейти к заявке/}).click();await expect(page.locator('#businessAgeMonths')).toBeVisible();
 const id=page.url().split('/applications/')[1].split('/')[0];
 await page.locator('#activity').fill('Торговля');await page.locator('#businessAgeMonths').fill('40');if(preliminary)await page.locator('#preliminaryRevenue').fill(preliminary);
 await page.getByRole('button',{name:/К финансовым данным/}).click();
 for(const [key,value] of Object.entries(finance))await page.locator('#'+key).fill(value);
 for(const box of await page.getByRole('checkbox',{name:/Подтвердить:/}).all())await box.check();
 await page.getByRole('button',{name:/К документам/}).click();
 await page.getByRole('checkbox',{name:/Подтверждаю использование/}).check();await page.getByRole('link',{name:/Проверить заявку/}).click();await page.getByRole('checkbox',{name:/Я проверил сведения/}).check();await page.getByRole('button',{name:/Отправить на рассмотрение/}).click();await expect(page).toHaveURL(new RegExp(`/applications/${id}/status`));return id;
}
test('existing UI → real backend → real Risk → offer acceptance and demo completion',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await login(page);const id=await create(page);
 await expect(page.getByRole('heading',{name:'Предложение готово'})).toBeVisible({timeout:30000});await page.getByRole('link',{name:'Посмотреть предложение'}).click();
 await page.getByRole('checkbox',{name:/Я ознакомился/}).check();await page.getByRole('button',{name:/Принять предложение/}).click();await page.getByRole('button',{name:'Подтвердить',exact:true}).click();await expect(page.getByText('Условия уже приняты.')).toBeVisible();
 await page.getByRole('checkbox',{name:/Я ознакомился/}).check();await page.getByRole('button',{name:/Завершить демооформление/}).click();await page.getByRole('button',{name:'Подтвердить',exact:true}).click();await expect(page.getByRole('heading',{name:'Демонстрация, деньги не перечисляются'})).toBeVisible();await page.goto(`/applications/${id}/status`);await page.reload();await expect(page.getByRole('heading',{name:'Оформление завершено'})).toBeVisible();expect(errors).toEqual([]);
});
test('RFI correction follows server-requested field and re-evaluates the same application',async({page})=>{
 await login(page);const id=await create(page,'100000');await expect(page.getByRole('heading',{name:'Нужно уточнение'})).toBeVisible({timeout:30000});await page.getByRole('link',{name:'Дополнить сведения'}).click();await expect(page.locator('#rfi-revenue')).toBeEditable();await expect(page.locator('#rfi-totalAssets')).not.toBeEditable();await page.locator('#rfi-revenue').fill('3000000,01');await page.getByRole('checkbox',{name:'Подтверждаю уточнённые сведения'}).check();await page.getByRole('button',{name:'Отправить ответ'}).click();await expect(page).toHaveURL(new RegExp(`/applications/${id}/status`));await expect(page.getByRole('heading',{name:'Предложение готово'})).toBeVisible({timeout:30000});
});
test('feed preferences, stable feedback retry and saved materials use public operations',async({page})=>{
 await login(page);await page.getByLabel('task',{exact:true}).selectOption('EQUIPMENT');await page.getByRole('button',{name:'Сохранить предпочтения'}).click();await expect(page.getByTestId('feed-card').first()).toBeVisible();
 const card=page.getByTestId('feed-card').first(), title=await card.locator('h3').innerText();await card.getByRole('button',{name:/^(Полезно|✓ В полезном)$/}).click();await expect(card.getByRole('button',{name:'✓ В полезном'})).toBeVisible();await page.getByRole('button',{name:'Полезные материалы'}).click();await expect(page.getByTestId('feed-card').filter({hasText:title})).toBeVisible();
});
test('VIEW requires continuous visibility; lost feedback response reuses event and command key',async({page})=>{
 await login(page);
 const card=page.getByTestId('feed-card').first();await expect(card).toBeVisible();const id=await card.getAttribute('data-content-id');
 const views:string[]=[],helpful:{body:string;key:string}[]=[];
 page.on('request',r=>{if(r.url().endsWith('/api/v1/recommendation-feedback')){const data=r.postDataJSON();if(data.itemId===id&&data.action==='VIEW')views.push(data.clientEventId);if(data.itemId===id&&data.action==='HELPFUL')helpful.push({body:r.postData()!,key:r.headers()['idempotency-key']});}});
 await card.scrollIntoViewIfNeeded();await page.waitForTimeout(400);expect(views).toHaveLength(0);
 await page.getByRole('heading',{name:/Добрый день/}).scrollIntoViewIfNeeded();await page.waitForTimeout(300);
 await card.scrollIntoViewIfNeeded();await page.waitForTimeout(400);expect(views).toHaveLength(0);
 await expect.poll(()=>views.length).toBe(1);
 let dropped=false;
 await page.route('**/api/v1/recommendation-feedback',async route=>{const e=route.request().postDataJSON();if(e.itemId===id&&e.action==='HELPFUL'&&!dropped){dropped=true;await route.fetch();await route.abort('failed');}else await route.continue();});
 await card.getByRole('button',{name:/^(Полезно|✓ В полезном)$/}).click();await card.getByRole('button',{name:/Повторить/}).click();await expect(card.getByRole('button',{name:'✓ В полезном'})).toBeVisible();
 expect(helpful).toHaveLength(2);expect(helpful[1]).toEqual(helpful[0]);
 await page.screenshot({path:new URL('../../reports/ui-feed-antifraud/ui-workspace.png',import.meta.url).pathname,fullPage:false});
});
