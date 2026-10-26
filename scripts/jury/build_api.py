#!/usr/bin/env python3
"""Build the jury contract from the audited runtime route allowlist and shared DTO schemas.

The design contract is a schema library only. Planned routes are never copied.
Run validate.py afterwards to compare all routes with current Java controllers.
"""
import copy
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/jury/api'
OUT.mkdir(parents=True, exist_ok=True)
schemas = copy.deepcopy(json.loads((ROOT / 'docs/architecture/contracts/public.openapi.json').read_text())['components']['schemas'])
schemas['Login'] = {'type': 'object', 'required': ['login', 'password'], 'properties': {
    'login': {'type': 'string', 'minLength': 1, 'maxLength': 128},
    'password': {'type': 'string', 'minLength': 1, 'maxLength': 256, 'format': 'password', 'writeOnly': True}}}
schemas['AssistantMessage'] = {'type': 'object', 'required': ['clientMessageId', 'text'], 'properties': {
    'clientMessageId': {'type': 'string', 'minLength': 1, 'maxLength': 128},
    'text': {'type': 'string', 'minLength': 1, 'maxLength': 2000}}}
# Backend proxies the standalone assistant JSON without a camelCase conversion.
assistant = json.loads((ROOT / 'ml/assistant/openapi.json').read_text())['components']['schemas']
for name, value in assistant.items():
    schemas['Assistant_' + name] = json.loads(json.dumps(value).replace('#/components/schemas/', '#/components/schemas/Assistant_'))
schemas['AssistantHistory'] = {'type': 'object', 'additionalProperties': True,
    'description': 'Серверный JSON истории standalone assistant; динамические сообщения/hidden entries, см. ml/assistant API.'}
schemas['AssistantSource'] = {'type': 'object', 'additionalProperties': True,
    'description': 'Разрешённый источник конкретного диалога. Точная версия и права проверяются assistant.'}
schemas['InformationDraft']['properties'] = {k: v for k, v in schemas['InformationDraft']['properties'].items()
    if k in ('requestVersion', 'draftVersion', 'documentReferences', 'requirementsVersion', 'financialStatementVersion')}
schemas['InformationDraft']['required'] = ['requestVersion', 'draftVersion', 'documentReferences', 'requirementsVersion']

A = '/api/v1/applications'
F = A + '/{applicationId}/financial-statement'
I = A + '/{applicationId}/information-requests'
D = I + '/{requestId}/draft'
C = '/api/v1/assistant/conversations/{conversationId}'
# method, path, body schema, response schema, success status, source controller
routes = [
 ('post','/api/v1/auth/login','Login','Session',200,'PasswordAccessController'),
 ('get','/api/v1/session',None,'Session',200,'SessionController'),
 ('post','/api/v1/session/logout',None,None,204,'SessionController'),
 ('post','/api/v1/session/company','SelectCompany','Session',200,'SessionController'),
 ('get','/api/v1/companies',None,'CompanyList',200,'CompanyController'),
 ('get','/api/v1/companies/{companyId}',None,'Company',200,'CompanyController'),
 ('get','/api/v1/products',None,'ProductList',200,'ProductController'),
 ('post',A,'CreateApplication','Application',201,'ApplicationController'),
 ('get',A,None,'ApplicationList',200,'ApplicationController'),
 ('get',A+'/{applicationId}',None,'Application',200,'ApplicationController'),
 ('patch',A+'/{applicationId}','DraftPatch','Application',200,'ApplicationController'),
 ('post',A+'/{applicationId}/submit','Submit','CommandReceipt',202,'ApplicationController'),
 ('get',F,None,'MLFinancialStatement',200,'FinancialStatementController'),
 ('put',F,'MLFinancialInput','MLFinancialStatement',200,'FinancialStatementController'),
 ('post',F+'/confirm','MLFinancialConfirmation','MLFinancialStatement',200,'FinancialStatementController'),
 ('get',I,None,'InformationRequestList',200,'InformationRequestController'),
 ('get',D,None,'InformationDraft',200,'InformationRequestController'),
 ('patch',D,'InformationDraftPatch','InformationDraft',200,'InformationRequestController'),
 ('get',D+'/financial-statement',None,'MLFinancialStatement',200,'InformationRequestController'),
 ('put',D+'/financial-statement','MLFinancialInput','MLFinancialStatement',200,'InformationRequestController'),
 ('post',D+'/financial-statement/confirm','MLFinancialConfirmation','MLFinancialStatement',200,'InformationRequestController'),
 ('post',I+'/{requestId}/responses','InformationResponse','CommandReceipt',202,'InformationRequestController'),
 ('get',A+'/{applicationId}/status',None,'StatusView',200,'StatusController'),
 ('get','/api/v1/operations/{operationId}',None,'Operation',200,'OperationController'),
 ('get',A+'/{applicationId}/document-requirements',None,'DocumentRequirements',200,'DocumentController'),
 ('post',A+'/{applicationId}/documents/upload-intents','UploadInput','UploadIntent',201,'DocumentController'),
 ('delete','/api/v1/uploads/{uploadId}',None,None,204,'DocumentController'),
 ('get',A+'/{applicationId}/documents',None,'DocumentList',200,'DocumentController'),
 ('get','/api/v1/documents/{documentId}',None,'Document',200,'DocumentController'),
 ('get','/api/v1/documents/{documentId}/extraction',None,'Extraction',200,'DocumentController'),
 ('post','/api/v1/documents/{documentId}/download-intents',None,'DownloadIntent',201,'DocumentController'),
 ('put','/api/v1/files/uploads/{transferId}',None,None,204,'FileTransferController'),
 ('get','/api/v1/files/downloads/{transferId}',None,None,200,'FileTransferController'),
 ('get',A+'/{applicationId}/decision',None,'Decision',200,'DecisionController'),
 ('get','/api/v1/offers/{offerId}',None,'Offer',200,'DecisionController'),
 ('post','/api/v1/offers/{offerId}/accept','OfferCommand','Offer',200,'OfferCommandController'),
 ('post','/api/v1/offers/{offerId}/complete','OfferCommand','Offer',200,'OfferCommandController'),
 ('get','/api/v1/feed/preferences',None,'FeedPreferences',200,'FeedController'),
 ('put','/api/v1/feed/preferences','FeedPreferences','FeedPreferences',200,'FeedController'),
 ('get','/api/v1/feed',None,'Feed',200,'FeedController'),
 ('get','/api/v1/feed/saved',None,'SavedFeed',200,'FeedController'),
 ('post','/api/v1/recommendation-feedback','MLRecommendationFeedback','MLReceipt',200,'FeedController'),
 ('get',C+'/messages',None,'AssistantHistory',200,'AssistantController'),
 ('post',C+'/messages','AssistantMessage','Assistant_ChatResponse',200,'AssistantController'),
 ('get',C+'/sources/{documentId}/{version}',None,'AssistantSource',200,'AssistantController'),
]

def ref(name): return {'$ref': '#/components/schemas/' + name}
def parameter(name, where='header', required=True, schema=None, description=None):
    p = {'name': name, 'in': where, 'required': required, 'schema': schema or {'type': 'string'}}
    if description: p['description'] = description
    return p

paths = {}
sources = {p.stem: str(p.relative_to(ROOT)) for p in (ROOT/'backend/app/src/main/java').rglob('*.java')}
for method, path, body, response, status, controller in routes:
    auth = path == '/api/v1/auth/login'
    op = {'operationId': method + '_' + re.sub(r'[^a-zA-Z0-9]+', '_', path).strip('_'),
          'summary': method.upper() + ' ' + path, 'tags': [controller.removesuffix('Controller')],
          'x-source': sources[controller], 'parameters': [], 'responses': {str(status): {'description': 'Успешный ответ runtime'}}}
    if auth:
        op['security'] = []
        op['parameters'].append(parameter('Origin', description='Должен точно входить в server allowlist.'))
    else:
        if controller not in ('CompanyController', 'AssistantController') and path != '/api/v1/session':
            op['parameters'].append(parameter('X-Company-Context', schema={'type':'integer','minimum':1}, description='contextVersion из текущей сессии, не companyId.'))
        if method != 'get': op['parameters'].append(parameter('X-CSRF-Token', description='csrfToken из текущей сессии.'))
    for name in re.findall(r'{([^}]+)}', path): op['parameters'].append(parameter(name, 'path'))
    if path in ('/api/v1/products', A, '/api/v1/feed', '/api/v1/feed/preferences', '/api/v1/feed/saved') and method == 'get':
        op['parameters'].append(parameter('companyId','query'))
    if path == '/api/v1/feed/preferences' and method == 'put': op['parameters'].append(parameter('companyId','query'))
    if method == 'get' and (path in ('/api/v1/companies','/api/v1/products',A,'/api/v1/feed','/api/v1/feed/saved') or path == A+'/{applicationId}/documents'):
        op['parameters'].append(parameter('cursor','query',False))
        if not path.startswith('/api/v1/feed'): op['parameters'].append(parameter('limit','query',False,{'type':'integer','minimum':1,'maximum':100,'default':20}))
    idempotent = (method, path) in {('post',A),('post',A+'/{applicationId}/submit'),('post',A+'/{applicationId}/documents/upload-intents'),('post',I+'/{requestId}/responses'),('post','/api/v1/recommendation-feedback')} or body in ('MLFinancialInput','MLFinancialConfirmation','OfferCommand')
    if idempotent: op['parameters'].append(parameter('Idempotency-Key', description='Один ключ для повтора одного и того же тела в его actor/company/scope.'))
    if method == 'patch' or body in ('MLFinancialInput','MLFinancialConfirmation','OfferCommand'):
        op['parameters'].append(parameter('If-Match', description='ETag ресурса, например "v2". Для финансов — containerVersion; для оферты — version.'))
    if body: op['requestBody'] = {'required':True,'content':{'application/json':{'schema':ref(body)}}}
    if response:
        op['responses'][str(status)]['content'] = {'application/json': {'schema': ref(response)}}
    if controller == 'FileTransferController':
        op['parameters'].append(parameter('X-Upload-Grant' if method == 'put' else 'X-Download-Grant'))
        if method == 'put': op['requestBody'] = {'required':True,'content': {mime:{'schema':{'type':'string','format':'binary'}} for mime in ('application/pdf','image/jpeg','image/png')}}
        else: op['responses']['200']['content'] = {'application/octet-stream':{'schema':{'type':'string','format':'binary'}}}
    for code in ('400','401','403','404','409','422','503'):
        op['responses'][code] = {'description': 'При соответствующей ошибке валидации, доступа, версии или зависимости', 'content':{'application/json':{'schema':ref('Error')}}}
    if status in (201,202): op['responses'][str(status)]['headers'] = {'Location':{'description':'Для команды — statusUrl, для создания заявки — URI заявки. Не все intent-ответы устанавливают Location.','schema':{'type':'string'}}} if controller == 'ApplicationController' or status == 202 else {}
    paths.setdefault(path,{})[method] = op

used = set()
def visit(node):
    if isinstance(node, dict):
        if '$ref' in node and node['$ref'].startswith('#/components/schemas/'):
            name = node['$ref'].split('/')[-1]
            if name not in used: used.add(name); visit(schemas[name])
        for v in node.values(): visit(v)
    elif isinstance(node,list):
        for v in node:visit(v)
visit(paths)
spec = {'openapi':'3.1.0','info':{'title':'Поток: реализованный клиентский API','version':'submission-2026-10-26',
    'description':'Контракт интеграционного MVP. Route allowlist сверяется с текущими Java-контроллерами. Проектные, demo-operator, SSE, withdraw и consent endpoint не включены. Assistant сохраняет свой snake_case JSON. Версия приложения определяется Git tag.'},
    'servers':[{'url':'http://127.0.0.1:8080','description':'Локальный запуск'},{'url':'https://president-diameter-endearing.ngrok-free.dev','description':'Серверный синтетический демо-стенд'}],
    'security':[{'SessionCookie':[]}], 'paths':paths,
    'components':{'securitySchemes':{'SessionCookie':{'type':'apiKey','in':'cookie','name':'credit_session'}},'schemas':{n:schemas[n] for n in sorted(used)}}}
(OUT/'openapi.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
(OUT/'route-inventory.json').write_text(json.dumps([{'method':m.upper(),'path':p,'source':sources[c]} for m,p,_,_,_,c in routes],ensure_ascii=False,indent=2)+'\n')

accounts = json.loads((ROOT/'docs/jury/demo-access.json').read_text())
values = dict(totalAssetsMinor=100000000,totalLiabilitiesMinor=40000000,currentAssetsMinor=50000000,currentLiabilitiesMinor=20000000,equityMinor=60000000,revenueMinor=300000000,netProfitMinor=10000000,ebitMinor=15000000)
form = dict(periodStart='2025-01-01',periodEnd='2025-12-31',reportingStandard='DEMO',currency='RUB',values=values,sourceDocumentReferences=[])
post_tests = ["pm.test('Ожидаемый успешный HTTP-статус', () => pm.expect(pm.response.code).to.be.within(200, 299));",
 "let b; try { b=pm.response.json(); } catch(e) { b={}; }",
 "if (b.csrfToken) {pm.collectionVariables.set('csrfToken',b.csrfToken);pm.collectionVariables.set('contextVersion',b.contextVersion);if(b.companyId)pm.collectionVariables.set('companyId',b.companyId);}",
 "if(b.applicationId && b.version && !b.offerId) {pm.collectionVariables.set('applicationId',b.applicationId);pm.collectionVariables.set('applicationVersion',b.version);}",
 "if(b.containerVersion)pm.collectionVariables.set('applicationVersion',b.containerVersion);if(b.statementVersion)pm.collectionVariables.set('statementVersion',b.statementVersion);",
 "if(b.operationId)pm.collectionVariables.set('operationId',b.operationId);if(b.offerIds && b.offerIds.length)pm.collectionVariables.set('offerId',b.offerIds[0]);",
 "if(b.offerId){pm.collectionVariables.set('offerId',b.offerId);pm.collectionVariables.set('offerVersion',b.version);}",
 "if(b.cards && b.cards.length){pm.collectionVariables.set('itemId',b.cards[0].contentId);if(b.rankingMetadata)pm.collectionVariables.set('exposureId',b.rankingMetadata.exposureId);}"]
variables = {'baseUrl':'http://127.0.0.1:8080','login':'company-a','password':'','companyId':'company-a','contextVersion':'1','csrfToken':'',
 'applicationId':'','applicationVersion':'1','statementVersion':'1','operationId':'','offerId':'','offerVersion':'1','conversationId':'jury-demo','itemId':'','exposureId':''}
collection = {'info':{'name':'Поток · проверка MVP','schema':'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
    'description':'Сначала выбрать local/server environment. Основная папка создаёт синтетическую заявку. Статус опрашивается автоматически в Runner; рекомендуемый delay 1000 ms. Дополнительные папки запускать отдельно. Сначала см. ../api.md.'},
    'variable':[{'key':k,'value':v} for k,v in variables.items()], 'item':[]}
def request(name,method,path,body=None,etag=False,idem=False):
    headers=[{'key':'Origin','value':'{{baseUrl}}'},{'key':'ngrok-skip-browser-warning','value':'jury-demo'}]
    if path!='/api/v1/auth/login':headers += [{'key':'X-Company-Context','value':'{{contextVersion}}'},{'key':'X-CSRF-Token','value':'{{csrfToken}}'}]
    if idem: headers.append({'key':'Idempotency-Key','value':'{{$guid}}'})
    if etag: headers.append({'key':'If-Match','value':'"v{{'+('offerVersion' if '/offers/' in path else 'applicationVersion')+'}}"'})
    item={'name':name,'request':{'method':method,'header':headers,'url':'{{baseUrl}}'+path},'event':[{'listen':'test','script':{'type':'text/javascript','exec':list(post_tests)}}]}
    if body is not None:
        raw=body if isinstance(body,str) else json.dumps(body,ensure_ascii=False,indent=2)
        item['request']['body']={'mode':'raw','raw':raw,'options':{'raw':{'language':'json'}}};headers.append({'key':'Content-Type','value':'application/json'})
    return item
core=[request('01 Вход','POST','/api/v1/auth/login',{'login':'{{login}}','password':'{{password}}'}),
 request('02 Текущая сессия','GET','/api/v1/session'),request('03 Продукты','GET','/api/v1/products?companyId={{companyId}}'),
 request('04 Создать заявку','POST',A,{'companyId':'{{companyId}}','productId':'working-capital','productVersion':1,'need':{'purpose':'Закупка товара','amount':{'amountMinor':50000000,'currency':'RUB'},'termMonths':12}},idem=True),
 request('05 Сведения о компании','PATCH',A+'/{{applicationId}}',{'business':{'businessAgeMonths':40}},etag=True),
 request('06 Сохранить финансы','PUT',A+'/{{applicationId}}/financial-statement',form,etag=True,idem=True),
 request('07 Подтвердить финансы','POST',A+'/{{applicationId}}/financial-statement/confirm','{"expectedStatementVersion":{{statementVersion}},"confirmedFieldNames":'+json.dumps(list(values))+',"documentReferences":[]}',etag=True,idem=True),
 request('08 Отправить','POST',A+'/{{applicationId}}/submit','{"expectedVersion":{{applicationVersion}},"consentRecordIds":[],"documentIds":[],"documentReferences":[],"requirementsVersion":1,"financialStatementVersion":{{statementVersion}}}',idem=True),
 request('09 Статус','GET',A+'/{{applicationId}}/status'),request('10 Решение','GET',A+'/{{applicationId}}/decision'),
 request('11 Предложение','GET','/api/v1/offers/{{offerId}}'),request('12 Принять','POST','/api/v1/offers/{{offerId}}/accept','{"expectedVersion":{{offerVersion}}}',etag=True,idem=True),
 request('13 Демооформление','POST','/api/v1/offers/{{offerId}}/complete','{"expectedVersion":{{offerVersion}}}',etag=True,idem=True),
 request('14 Итоговый статус','GET',A+'/{{applicationId}}/status')]
core[8]['event'][0]['script']['exec'] += ["if(['SUBMITTED','REVIEW'].includes(b.status)){let n=Number(pm.collectionVariables.get('pollCount')||0)+1;pm.collectionVariables.set('pollCount',n);if(n<60)pm.execution.setNextRequest('09 Статус');else {pm.test('Рассмотрение завершилось',()=>{throw new Error('Повторите чтение статуса после диагностики worker');});pm.execution.setNextRequest(null);}}else{pm.collectionVariables.set('pollCount',0);if(!['APPROVED','ALTERNATIVE'].includes(b.status))pm.execution.setNextRequest(null);}"]
collection['item'].append({'name':'Основной сценарий · создаёт синтетическую заявку','item':core})
collection['item'].append({'name':'Лента · запускать отдельно','item':[
 request('Профиль ленты','GET','/api/v1/feed/preferences?companyId={{companyId}}'),
 request('Изменить профиль','PUT','/api/v1/feed/preferences?companyId={{companyId}}',{'task':'PURCHASE','help':'COST','depth':'EXPLAINED'}),
 request('Подборка','GET','/api/v1/feed?companyId={{companyId}}'),
 request('Сохранить материал','POST','/api/v1/recommendation-feedback','{"clientEventId":"{{$guid}}","exposureId":"{{exposureId}}","itemId":"{{itemId}}","action":"HELPFUL","occurredAt":"{{$isoTimestamp}}"}',idem=True),
 request('Сохранённое','GET','/api/v1/feed/saved?companyId={{companyId}}')]})
collection['item'].append({'name':'Ассистент · запускать отдельно','item':[
 request('Вопрос по документам','POST','/api/v1/assistant/conversations/{{conversationId}}/messages',{'clientMessageId':'{{$guid}}','text':'Какие документы нужны для заявки на оборотный кредит?'}),
 request('История','GET','/api/v1/assistant/conversations/{{conversationId}}/messages')]})
(OUT/'potok.postman_collection.json').write_text(json.dumps(collection,ensure_ascii=False,indent=2)+'\n')
for name,base,password in [('local','http://127.0.0.1:8080',''),('demo',accounts['baseUrl'],accounts['accounts'][0]['password'])]:
    environment={'name':'Поток · '+name,'values':[{'key':k,'value':v,'enabled':True} for k,v in {'baseUrl':base,'login':'company-a','password':password}.items()], '_postman_variable_scope':'environment'}
    (OUT/(name+'.postman_environment.json')).write_text(json.dumps(environment,ensure_ascii=False,indent=2)+'\n')
print(f'Generated {sum(len(v) for v in paths.values())} public operations and {len(used)} reachable schemas')
