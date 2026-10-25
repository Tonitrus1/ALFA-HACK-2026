import { test, expect, type Page } from '@playwright/test';
const finance={totalAssets:'1000000',totalLiabilities:'400000',currentAssets:'500000',currentLiabilities:'200000',equity:'600000',revenue:'3000000',netProfit:'100000',ebit:'150000'};
async function login(page:Page,account='representative-a'){
 await page.goto('/login');await page.locator('#name').selectOption(account);await page.getByRole('button',{name:'Войти в кабинет'}).click();await expect(page.getByRole('heading',{name:'От имени какой компании работаем?'})).toBeVisible();await page.getByRole('button',{name:/Перейти в кабинет|Активная компания/}).first().click();await expect(page.getByRole('heading',{name:/Добрый день/})).toBeVisible();
}
async function create(page:Page,preliminary?:string){
 await page.goto('/needs');await page.getByRole('button',{name:'Продолжить',exact:true}).click();await page.locator('#amount').fill('500000');await page.getByRole('button',{name:'Подобрать варианты'}).click();await page.getByRole('link',{name:'Подробнее'}).first().click();await page.getByRole('button',{name:/Перейти к заявке/}).click();await expect(page.locator('#businessAgeMonths')).toBeVisible();
 const id=page.url().split('/applications/')[1].split('/')[0];
 await page.locator('#activity').fill('Торговля');await page.locator('#businessAgeMonths').fill('40');if(preliminary)await page.locator('#preliminaryRevenue').fill(preliminary);
 await page.getByRole('button',{name:/К документам/}).click();
 await expect(page.getByRole('heading',{name:'Документы для заполнения анкеты'})).toBeVisible();
 await page.getByRole('checkbox',{name:/Подтверждаю корректность/}).check();
 await page.getByRole('button',{name:/К финансовым данным/}).click();
 for(const [key,value] of Object.entries(finance))await page.locator('#'+key).fill(value);
 for(const box of await page.getByRole('checkbox',{name:/Подтвердить:/}).all())await box.check();
 await page.getByRole('button',{name:/Проверить заявку/}).click();
 await page.getByRole('checkbox',{name:/Я проверил сведения/}).check();await page.getByRole('button',{name:/Отправить на рассмотрение/}).click();await expect(page).toHaveURL(new RegExp(`/applications/${id}/status`));return id;
}
test('existing UI → real backend → real Risk → offer acceptance and completion',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await login(page);const id=await create(page);
 await expect(page.getByRole('heading',{name:'Предложение готово'})).toBeVisible({timeout:30000});await page.getByRole('link',{name:'Посмотреть предложение'}).click();
 await page.getByRole('checkbox',{name:/Я ознакомился/}).check();await page.getByRole('button',{name:/Принять предложение/}).click();await page.getByRole('button',{name:'Подтвердить',exact:true}).click();await expect(page.getByText('Условия уже приняты.')).toBeVisible();
 await page.getByRole('checkbox',{name:/Я ознакомился/}).check();await page.getByRole('button',{name:/Завершить оформление/}).click();await page.getByRole('button',{name:'Подтвердить',exact:true}).click();await expect(page.getByRole('heading',{name:'Оформление завершено'})).toBeVisible();await page.goto(`/applications/${id}/status`);await page.reload();await expect(page.getByRole('heading',{name:'Оформление завершено'})).toBeVisible();expect(errors).toEqual([]);
 await page.getByRole('link',{name:'Посмотреть результат',exact:true}).click();
 await expect(page).toHaveURL(new RegExp(`/applications/${id}/result$`));
 await expect(page.getByRole('heading',{name:'Результат заявки'})).toBeVisible();
 await expect(page.getByText('Согласованная сумма',{exact:true})).toBeVisible();
 await expect(page.locator('strong.amount')).toHaveText(/500\s*000/);
});

test('assistant sends with Enter, preserves Shift+Enter and prevents duplicate pending sends',async({page})=>{
 await login(page);
 const sent:string[]=[];let release:()=>void=()=>{};
 const responseGate=new Promise<void>(resolve=>{release=resolve;});
 await page.route('**/api/v1/assistant/conversations/*/messages',async route=>{
   if(route.request().method()==='GET'){await route.fulfill({json:{messages:[]}});return;}
   sent.push(route.request().postDataJSON().text);await responseGate;
   await route.fulfill({json:{message_id:'keyboard-response',status:'ANSWER',answer:'Сообщение получено.',citations:[]}});
 });
 await page.goto('/assistant/keyboard-check');
 const input=page.getByLabel('Ваш вопрос',{exact:true});
 await input.fill('Первая строка');await input.press('Shift+Enter');await input.pressSequentially('Вторая строка');
 await expect(input).toHaveValue('Первая строка\nВторая строка');expect(sent).toEqual([]);
 await input.press('Enter');await expect.poll(()=>sent.length).toBe(1);
 expect(sent[0]).toBe('Первая строка\nВторая строка');await expect(input).toHaveValue('');
 await input.fill('Следующий вопрос');await input.press('Enter');expect(sent).toHaveLength(1);
 release();await expect(page.getByText('Сообщение получено.',{exact:true})).toBeVisible();
 await input.fill('   ');await input.press('Enter');expect(sent).toHaveLength(1);
});

test('business autosave and manual finances work after a document was uploaded',async({page})=>{
 await login(page);
 const session=await (await page.request.get('/api/v1/session')).json();
 const headers={'Origin':new URL(page.url()).origin,'X-CSRF-Token':session.csrfToken,'X-Company-Context':String(session.contextVersion)};
 const created=await page.request.post('/api/v1/applications',{headers:{...headers,'Idempotency-Key':crypto.randomUUID()},data:{companyId:'company-a',productId:'working-capital',productVersion:1,need:{purpose:'Document autosave regression',amount:{amountMinor:50000000,currency:'RUB'},termMonths:12}}});
 expect(created.ok()).toBe(true); const app=(await created.json()).applicationId;
 const requirements=await (await page.request.get(`/api/v1/applications/${app}/document-requirements`,{headers})).json();
 const requirement=requirements.items.find((r:{allowedContentTypes:string[]})=>r.allowedContentTypes.includes('image/png'));
 const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAIAAAACUFjqAAAAFUlEQVR4nGP8//8/A27AhEduBEsDAKXjAxF9kqZqAAAAAElFTkSuQmCC','base64');
 const intent=await (await page.request.post(`/api/v1/applications/${app}/documents/upload-intents`,{headers:{...headers,'Idempotency-Key':crypto.randomUUID()},data:{fileName:'autosave-regression.png',declaredMimeType:'image/png',sizeBytes:png.length,documentType:'FINANCIAL_STATEMENT',requirementId:requirement.requirementId,requirementsVersion:requirements.requirementsVersion}})).json();
 const uploaded=await page.request.put(intent.uploadUrl,{headers:{...headers,'Content-Type':'image/png','X-Upload-Grant':intent.grant},data:png});expect(uploaded.status()).toBe(204);
 await expect.poll(async()=>{const d=await (await page.request.get(`/api/v1/documents/${intent.documentId}`,{headers})).json();return d.scanState;},{timeout:30000}).toBe('CLEAN');
 await page.goto(`/applications/${app}/company`);
 await page.locator('#activity').fill('Продажи');await page.locator('#businessAgeMonths').fill('36');await page.locator('#preliminaryRevenue').fill('5000000');
 await page.getByRole('button',{name:/К документам/}).click();
 await page.getByRole('checkbox',{name:/Подтверждаю корректность/}).check();
 await page.getByRole('button',{name:/К финансовым данным/}).click();
 await expect(page.locator('#totalAssets')).toBeVisible();
 const stored=await (await page.request.get(`/api/v1/applications/${app}`,{headers})).json();
 expect(stored.terms.business).toMatchObject({activityDescription:'Продажи',businessAgeMonths:36,annualRevenue:{amountMinor:500000000}});
 const financial=await page.request.get(`/api/v1/applications/${app}/financial-statement`,{headers});expect(financial.status()).toBe(404);
 for(const [key,value] of Object.entries(finance))await page.locator('#'+key).fill(value);
 for(const box of await page.getByRole('checkbox',{name:/Подтвердить:/}).all())await box.check();
 await page.getByRole('button',{name:/Проверить заявку/}).click();
 await expect(page).toHaveURL(new RegExp(`/applications/${app}/review$`));
 const saved=await (await page.request.get(`/api/v1/applications/${app}/financial-statement`,{headers})).json();
 expect(saved.confirmed).toBe(true);expect(saved.statement.sourceDocumentReferences).toEqual([]);
 await expect(page.getByText('Ссылки на документы не совпадают')).toHaveCount(0);
});
test('document page exposes OCR review and leaves missing values for manual input',async({page})=>{
 await login(page);
 const session=await (await page.request.get('/api/v1/session')).json();
 const headers={'Origin':new URL(page.url()).origin,'X-CSRF-Token':session.csrfToken,'X-Company-Context':String(session.contextVersion),'Idempotency-Key':crypto.randomUUID()};
 const created=await page.request.post('/api/v1/applications',{headers,data:{companyId:'company-a',productId:'working-capital',productVersion:1,need:{purpose:'Document review check',amount:{amountMinor:50000000,currency:'RUB'},termMonths:12}}});
 expect(created.ok()).toBe(true);const app=(await created.json()).applicationId;
 let partial:{statementVersion:number;containerVersion:number;confirmed:boolean;statement:{values:Record<string,number>;sourceDocumentReferences:unknown[]}}|undefined;
 await page.route(`**/api/v1/applications/${app}/financial-statement`,async route=>{
   if(route.request().method()==='PUT'){
     partial={statementVersion:1,containerVersion:3,confirmed:false,statement:route.request().postDataJSON()};
     await route.fulfill({json:partial});return;
   }
   if(partial)await route.fulfill({json:partial});
   else await route.fulfill({status:404,json:{message:'Финансовые показатели ещё не заполнены'}});
 });
 await page.route(`**/api/v1/applications/${app}/documents`,route=>route.fulfill({json:{items:[{documentId:'review-document',version:4,fileName:'Демонстрационный отчёт',scanState:'CLEAN',extractionState:'READY',extractionId:'review-extraction',objectVersion:'review-object',sizeBytes:100,contentType:'image/png'}]}}));
 await page.route('**/api/v1/documents/review-document/extraction',route=>route.fulfill({json:{extractionId:'review-extraction',documentVersion:4,objectVersion:'review-object',fields:[{name:'revenue',value:'3000000'},{name:'period',value:'2025'}]}}));
 await page.goto(`/applications/${app}/documents`);
 await expect(page.getByText('Распознавание готово',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Сверить показатели'}).click();
 await expect(page.getByRole('dialog',{name:'Сверка финансовых показателей'})).toBeVisible();
 await expect(page.locator('#ocr-revenue')).toHaveValue('3000000');
 await expect(page.locator('#ocr-totalLiabilities')).toHaveCount(0);
 await expect(page.getByText('Найдено показателей: 1 из 8.',{exact:false})).toBeVisible();
 await expect(page.getByRole('checkbox',{name:'Проверено по документу: Выручка'})).not.toBeChecked();
 await page.getByRole('checkbox',{name:'Проверено по документу: Выручка'}).check();
 await page.getByRole('button',{name:'Применить выбранные показатели'}).click();
 await expect(page.getByRole('dialog',{name:'Сверка финансовых показателей'})).toBeHidden();
 expect(partial!.statement.values).toEqual({revenueMinor:300000000});
 expect(partial!.confirmed).toBe(false);
 await page.getByRole('checkbox',{name:/Подтверждаю корректность/}).check();
 await page.getByRole('button',{name:/К финансовым данным/}).click();
 await expect(page.locator('#revenue')).toHaveValue(/^3000000(?:,00)?$/);
 await expect(page.locator('#totalLiabilities')).toHaveValue('');
});

test('financial warnings explain the problem without internal field names',async({page})=>{
 await login(page);
 await page.goto('/needs');await page.getByRole('button',{name:'Продолжить',exact:true}).click();await page.locator('#amount').fill('500000');await page.getByRole('button',{name:'Подобрать варианты'}).click();await page.getByRole('link',{name:'Подробнее'}).first().click();await page.getByRole('button',{name:/Перейти к заявке/}).click();
 await page.locator('#activity').fill('Продажи');await page.locator('#businessAgeMonths').fill('36');await page.getByRole('button',{name:/К документам/}).click();await page.getByRole('checkbox',{name:/Подтверждаю корректность/}).check();await page.getByRole('button',{name:/К финансовым данным/}).click();
 for(const [key,value] of Object.entries({...finance,totalAssets:'0'}))await page.locator('#'+key).fill(value);
 for(const box of await page.getByRole('checkbox',{name:/Подтвердить:/}).all())await box.check();
 await page.getByRole('button',{name:/Проверить заявку/}).click();
 const warning=page.getByRole('alert').filter({hasText:'Сумма активов должна быть больше нуля'}).first();
 await expect(warning).toBeVisible();
 await expect(warning).toContainText('суммой всех обязательств и собственного капитала');
 expect(await warning.innerText()).not.toMatch(/Minor|totalAssets|totalLiabilities|equityMinor|[<>=]/);
});

test('RFI correction follows server-requested field and re-evaluates the same application',async({page})=>{
 await login(page);const id=await create(page,'100000');await expect(page.getByRole('heading',{name:'Нужно уточнение'})).toBeVisible({timeout:30000});await page.getByRole('link',{name:'Дополнить сведения'}).click();await expect(page.locator('#rfi-revenue')).toBeEditable();await expect(page.locator('#rfi-totalAssets')).not.toBeEditable();await page.locator('#rfi-revenue').fill('3000000,01');await page.getByRole('checkbox',{name:'Подтверждаю уточнённые сведения'}).check();await page.getByRole('button',{name:'Отправить ответ'}).click();await expect(page).toHaveURL(new RegExp(`/applications/${id}/status`));await expect(page.getByRole('heading',{name:'Предложение готово'})).toBeVisible({timeout:30000});
});
test('feed preferences, stable feedback retry and saved materials use public operations',async({page})=>{
 await login(page);await page.getByText('Настроить подборку',{exact:true}).click();await page.getByLabel('task',{exact:true}).selectOption('EQUIPMENT');await page.getByRole('button',{name:'Сохранить предпочтения'}).click();await expect(page.getByTestId('feed-card').first()).toBeVisible();
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
