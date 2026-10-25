/** Public backend adapter. Business state is always read back from the server. */
import type { Application, AssistantMessage, Company, DocumentItem, Draft, Finance, FinanceKey, InformationRequest, Need, Notice, Offer, Product, Session, Status } from '../types/domain';
import { financeFields, signedFields } from '../types/domain';
import { fromKopecks, toKopecks } from '../lib/money';
import { referenceText } from '../lib/referenceText';
import { ApiError, context, request } from './http';
import type { Card, Feed, Preferences, SavedFeed } from '../../../integration/api';
export type { Card, Feed, Preferences, SavedFeed };
const json = JSON.stringify;
const enc = encodeURIComponent;
const path = (id: string) => `/api/v1/applications/${enc(id)}`;
const companyQuery = () => { const id = context.get()?.companyId; if (!id) throw new Error('Выберите компанию'); return 'companyId=' + enc(id); };
const unsupported = async <T>(): Promise<T> => { throw new ApiError(503, 'Функция скоро появится. Сейчас используйте ручной ввод и историю заявки.'); };
export function minor(value: string, signed = false): number {
  const result = BigInt(toKopecks(value, signed));
  if (result > BigInt(Number.MAX_SAFE_INTEGER) || result < -BigInt(Number.MAX_SAFE_INTEGER)) throw new Error('Указана слишком большая сумма. Уменьшите её и попробуйте снова.');
  return Number(result);
}
const financeMap: Record<FinanceKey, string> = { revenue:'revenueMinor', netProfit:'netProfitMinor', ebit:'ebitMinor', equity:'equityMinor', totalAssets:'totalAssetsMinor', currentAssets:'currentAssetsMinor', currentLiabilities:'currentLiabilitiesMinor', totalLiabilities:'totalLiabilitiesMinor' };
type Statement = { statementVersion: number; containerVersion: number; confirmed: boolean; statement: {periodStart: string; periodEnd: string; reportingStandard: 'DEMO'; currency: 'RUB'; values: Record<string, number>; sourceDocumentReferences: ReturnType<typeof references> } };
type WireApp = { applicationId: string; companyId: string; productId: string; version: number; status: Status; updatedAt: string; terms: {purpose: string; amount: {amountMinor: number}; termMonths: number; business?: {activityDescription?: string; businessAgeMonths?: number; annualRevenue?: {amountMinor: number}}} };
type WireSession = { userId: string; displayName?: string; companyId?: string; contextVersion: number; csrfToken: string; expiresAt: string };
type WireStatus = { status: Status; nextAction: {type: string; label: string; targetPath: string}; history: {eventId:string; occurredAt:string; label:string}[] };
const mutations = new Map<string, {key: string; payload: string}>();
// Cache the exact payload/key for retries, including after a lost response. Never silently retry CAS.
function stable<T>(url: string, method: string, body: unknown, version?: number): Promise<T> {
  const payload = json(body), identity = [context.get()?.actor,context.get()?.companyId,url,method,version,payload].join('|');
  let entry = mutations.get(identity); if (!entry) { entry = {key:crypto.randomUUID(),payload}; mutations.set(identity,entry); }
  return request<T>(url,{method, body:entry.payload, headers:{'Idempotency-Key':entry.key, ...(version !== undefined ? {'If-Match':`"v${version}"`} : {})}});
}
function command<T>(send: () => Promise<T>) { let active: Promise<T> | undefined; return { send: () => active ?? (active = send().finally(() => {active=undefined;})) }; }
async function list<T>(url: string): Promise<T[]> {
  const all:T[]=[]; let cursor:string|undefined;
  do { const page = await request<{items:T[];nextCursor?:string}>(url+(cursor ? (url.includes('?')?'&':'?')+'cursor='+enc(cursor):'')); all.push(...page.items); cursor=page.nextCursor; } while(cursor);
  return all;
}
async function companies(): Promise<Company[]> { return (await list<{companyId:string;displayName:string;taxId:string}>('/api/v1/companies')).map(c=>({id:c.companyId,name:referenceText(c.displayName),inn:c.taxId,industry:'',address:''})); }
async function session(s?: WireSession): Promise<Session> {
  const wire=s ?? await request<WireSession>('/api/v1/session');
  const mapped:Session={actor:wire.userId,companyId:wire.companyId??null,contextVersion:wire.contextVersion,csrfToken:wire.csrfToken,expiresAt:wire.expiresAt,companies:[]};
  context.set(mapped); mapped.companies=await companies(); return mapped;
}
function statementInput(draft: Draft, refs: ReturnType<typeof references>) {
  if (!/^\d{4}$/.test(draft.period)) throw new Error('Укажите отчётный год');
  const values:Record<string,number>={};
  for(const k of Object.keys(financeFields) as FinanceKey[]) if(draft.finance[k].trim()!=='') values[financeMap[k]]=minor(draft.finance[k],signedFields.includes(k));
  return {periodStart:`${draft.period}-01-01`,periodEnd:`${draft.period}-12-31`,reportingStandard:'DEMO',currency:'RUB',values,sourceDocumentReferences:refs};
}
function finance(s?: Statement): Finance { return Object.fromEntries((Object.keys(financeFields) as FinanceKey[]).map(k=>[k,s?.statement.values[financeMap[k]] === undefined ? '' : fromKopecks(String(s.statement.values[financeMap[k]]))])) as Finance; }
async function optionalStatement(url:string):Promise<Statement|undefined> { try{return await request<Statement>(url);}catch(e){if(e instanceof ApiError && e.status===404)return undefined;throw e;} }
async function application(id:string):Promise<Application> {
  const wire=await request<WireApp>(path(id));
  const [state,s]=await Promise.all([request<WireStatus>(path(id)+'/status'),optionalStatement(path(id)+'/financial-statement')]);
  const c=context.get()?.companies.find(c=>c.id===wire.companyId);
  const action=state.nextAction;
  let href=action.targetPath;
  if(action.type==='CONTINUE')href=path(id).replace('/api/v1','')+'/company';
  else if(action.type==='VIEW_RESULT')href=`/applications/${id}/result`;
  else if(!['PROVIDE_INFORMATION','VIEW_OFFER'].includes(action.type))href=`/applications/${id}/status`;
  return {id,companyId:wire.companyId,productId:wire.productId,version:wire.version,status:state.status,
    financialVersion:s?.statementVersion??0,createdAt:wire.updatedAt,need:{purpose:wire.terms.purpose,amount:String(wire.terms.amount.amountMinor),months:wire.terms.termMonths},
    draft:{companyName:c?.name??'',inn:c?.inn??'',address:'',activity:wire.terms.business?.activityDescription??'',businessAgeMonths:wire.terms.business?.businessAgeMonths?.toString()??'',preliminaryRevenue:wire.terms.business?.annualRevenue ? fromKopecks(String(wire.terms.business.annualRevenue.amountMinor)):'',period:s?.statement.periodStart.slice(0,4)??'2025',currency:'RUB',unit:'RUB',finance:finance(s),confirmed:Object.fromEntries(Object.keys(financeFields).map(k=>[k,!!s?.confirmed])) as Draft['confirmed'],consents:false},
    history:state.history.map(h=>({id:h.eventId,title:referenceText(h.label),at:h.occurredAt})),nextAction:action.type==='WAIT'?null:{label:referenceText(action.label),href}};
}
function references(documents:DocumentItem[]) { if(documents.some(d=>['QUARANTINE','SCANNING'].includes(d.status)))throw new Error('Дождитесь проверки документов'); return documents.filter(d=>d.status==='CLEAN').map(d=>({documentId:d.id,documentVersion:d.documentVersion!,objectVersion:String(d.objectVersion)})); }
async function save(id:string,draft:Draft,version:number,sourceDocument?:DocumentItem):Promise<Application> {
  const age=draft.businessAgeMonths?.trim(); if(age && (!/^\d+$/.test(age)||!Number.isSafeInteger(Number(age))))throw new Error('Срок работы — целое число месяцев');
  const business={activityDescription:draft.activity,...(age ? {businessAgeMonths:Number(age)}:{}),...(draft.preliminaryRevenue?.trim()?{annualRevenue:{amountMinor:minor(draft.preliminaryRevenue),currency:'RUB'}}:{})};
  const clearFields=[...(!age?['business.businessAgeMonths']:[]),...(!draft.preliminaryRevenue?.trim()?['business.annualRevenue']:[])];
  const url=path(id)+'/financial-statement';
  const original=await optionalStatement(url);
  const input=statementInput(draft,original?.statement.sourceDocumentReferences??[]);
  const financialChanged=sourceDocument!==undefined || (original
    ? input.periodStart!==original.statement.periodStart || input.periodEnd!==original.statement.periodEnd || Object.values(financeMap).some(k=>input.values[k]!==original.statement.values[k])
    : Object.keys(input.values).length>0 || draft.period!=='2025');
  const shouldConfirm=Object.values(draft.confirmed).every(Boolean) && Object.values(draft.finance).every(v=>v.trim()!=='');
  if(financialChanged){
    // A manual edit is not evidence that every uploaded file supplied these values.
    // Only explicitly selected OCR sources and existing provenance belong in the statement.
    const sources=sourceDocument ? [...input.sourceDocumentReferences.filter(ref=>ref.documentId!==sourceDocument.id),...references([sourceDocument])] : input.sourceDocumentReferences;
    if(sources.length){
      const docs=await api.documents(id);
      input.sourceDocumentReferences=sources.map(ref=>{
        const current=docs.find(d=>d.id===ref.documentId && d.objectVersion===ref.objectVersion && d.status==='CLEAN');
        if(!current)throw new ApiError(409,'Документ изменился. Откройте сверку заново.');
        return references([current])[0];
      });
    }
  }
  const updated=await request<WireApp>(path(id),{method:'PATCH',headers:{'If-Match':`"v${version}"`},body:json({business,...(clearFields.length?{clearFields}:{})})});
  let s=original;
  if(financialChanged)s=await stable<Statement>(url,'PUT',input,updated.version);
  if(s && shouldConfirm && !s.confirmed)s=await stable<Statement>(url+'/confirm','POST',{expectedStatementVersion:s.statementVersion,confirmedFieldNames:Object.values(financeMap),documentReferences:s.statement.sourceDocumentReferences},financialChanged?s.containerVersion:updated.version);
  const result=await application(id); result.draft={...draft};return result;
}
type WireProduct={productId:string;version:number;name:string;purpose:string;minAmount:{amountMinor:number};maxAmount:{amountMinor:number};maxMonths:number;preliminaryDisclosure:string};
async function products(_need?:Need):Promise<Product[]> { return (await list<WireProduct>('/api/v1/products?'+companyQuery())).map(p=>({id:p.productId,version:p.version,title:referenceText(p.name),description:p.purpose,minAmount:String(p.minAmount.amountMinor),maxAmount:String(p.maxAmount.amountMinor),maxMonths:p.maxMonths,rate:'Ставка не определена',eligible:true,restriction:referenceText(p.preliminaryDisclosure),benefits:[]})); }
let pendingNeed:{company:string;need:Need}|undefined;
async function information(id:string,requestId:string):Promise<InformationRequest> {
  const rows=await request<{items:{requestId:string;version:number;items:{fieldPath?:string;label:string;kind:string}[];deadline:string;status:string}[]}>(path(id)+'/information-requests');
  const r=rows.items.find(r=>requestId?r.requestId===requestId:r.status==='OPEN');if(!r)throw new ApiError(404,'Открытый запрос уточнений не найден');
  const base=path(id)+`/information-requests/${enc(r.requestId)}/draft`;
  const [d,s]=await Promise.all([request<{draftVersion:number;requestVersion:number;requirementsVersion:number}>(base),request<Statement>(base+'/financial-statement')]);
  return {id:r.requestId,applicationId:id,requestVersion:d.requestVersion,requirementsVersion:d.requirementsVersion,draftVersion:d.draftVersion,financialVersion:s.statementVersion,editableFields:(Object.keys(financeMap) as FinanceKey[]).filter(k=>r.items.some(i=>i.fieldPath==='financialStatement.values.'+financeMap[k])),message:r.items.map(i=>i.label).join('; '),dueAt:r.deadline,documentRequired:r.items.some(i=>i.kind==='DOCUMENT'),finance:finance(s),confirmed:s.confirmed};
}
async function saveInformation(r:InformationRequest) {
  const url=path(r.applicationId)+`/information-requests/${enc(r.id)}/draft/financial-statement`;
  const original=await request<Statement>(url);
  const input={...original.statement,values:{...original.statement.values}};
  for(const k of r.editableFields) input.values[financeMap[k]]=minor(r.finance[k],signedFields.includes(k));
  const s=await stable<Statement>(url,'PUT',input,r.draftVersion);
  if(r.confirmed)await stable<Statement>(url+'/confirm','POST',{expectedStatementVersion:s.statementVersion,confirmedFieldNames:Object.values(financeMap),documentReferences:input.sourceDocumentReferences},s.containerVersion);
  return information(r.applicationId,r.id);
}
type WireOffer={offerId:string;applicationId:string;version:number;status:Offer['status'];amount:{amountMinor:number};termMonths:number;termsDisclosure:string;validUntil:string};
async function offer(id:string):Promise<Offer>{const w=await request<WireOffer>('/api/v1/offers/'+enc(id));return {id:w.offerId,applicationId:w.applicationId,version:w.version,status:w.status,amount:String(w.amount.amountMinor),months:w.termMonths,rate:'См. условия',termsDisclosure:referenceText(w.termsDisclosure),expiresAt:w.validUntil};}
type AssistantResponse={message_id:string;status:AssistantMessage['state'];answer:string;citations:{title:string;type:string;document_id?:string;version?:number;url?:string;metadata?:{source_url?:string;source_type?:string;is_synthetic?:boolean}}[]};
function assistantMessage(r:AssistantResponse):AssistantMessage {
  const hidden = r.citations.some(c => c.type === 'KNOWLEDGE' &&
    (c.metadata?.is_synthetic !== false || !['PUBLIC_NOTE', 'WEB'].includes(c.metadata?.source_type ?? '')));
  return {
    id: r.message_id, role: 'assistant',
    text: hidden ? 'Ответ скрыт: источник больше недоступен.' : r.answer,
    state: hidden ? 'INSUFFICIENT_EVIDENCE' : r.status,
    sources: hidden ? [] : r.citations.flatMap(c => {
      const href = c.type === 'KNOWLEDGE' ? c.metadata?.source_url : c.url;
      return href ? [{ title: c.title, href }] : [];
    }),
  };
}
async function stableAssistant(id:string,text:string,signal:AbortSignal){return request<AssistantResponse>('/api/v1/assistant/conversations/'+enc(id)+'/messages',{method:'POST',signal,body:json({clientMessageId:crypto.randomUUID(),text})});}
export const api={
  session,companies,
  login:async(login:string,password:string)=>session(await request<WireSession>('/api/v1/auth/login',{method:'POST',body:json({login:login.trim(),password})})),
  logout:()=>request<void>('/api/v1/session/logout',{method:'POST'}),
  selectCompany:async(companyId:string)=>session(await request<WireSession>('/api/v1/session/company',{method:'POST',body:json({companyId})})),
  needs:async(need:Need)=>{pendingNeed={company:context.get()?.companyId??'',need};return need;},
  getNeed:async()=>pendingNeed && pendingNeed.company===context.get()?.companyId?pendingNeed.need:{purpose:'Пополнение оборотных средств',amount:'50000000',months:12},
  products,product:async(id:string)=>{const p=(await products()).find(p=>p.id===id);if(!p)throw new ApiError(404,'Продукт недоступен');return p;},
  application,applications:async()=>Promise.all((await list<WireApp>('/api/v1/applications?'+companyQuery())).map(a=>application(a.applicationId))),
  createApplication:(productId:string,need:Need)=>{const key=crypto.randomUUID();return command(async()=>{const product=await api.product(productId);const a=await request<WireApp>('/api/v1/applications',{method:'POST',headers:{'Idempotency-Key':key},body:json({companyId:context.get()?.companyId,productId,productVersion:product.version,need:{purpose:need.purpose,amount:{amountMinor:minor(fromKopecks(need.amount)),currency:'RUB'},termMonths:need.months}})});return application(a.applicationId);});},
  save,
  submit:(a:Application,docs:DocumentItem[]=[])=>command(async()=>{const s=await request<Statement>(path(a.id)+'/financial-statement');if(!s.confirmed)throw new Error('Подтвердите все финансовые значения');const req=await request<{requirementsVersion:number}>(path(a.id)+'/document-requirements');await stable(path(a.id)+'/submit','POST',{expectedVersion:a.version,financialStatementVersion:s.statementVersion,requirementsVersion:req.requirementsVersion,consentRecordIds:[],documentIds:references(docs).map(d=>d.documentId),documentReferences:references(docs)});return application(a.id);}),
  documents:async(id:string):Promise<DocumentItem[]> => Promise.all((await list<{documentId:string;version:number;fileName:string;scanState:string;extractionState:string;extractionId?:string;objectVersion:string;sizeBytes?:number;contentType?:string}>(path(id)+'/documents')).map(async d=>{
    const item:DocumentItem={id:d.documentId,applicationId:id,name:d.fileName,size:d.sizeBytes??0,type:d.contentType??'',documentVersion:d.version,objectVersion:d.objectVersion,status:d.scanState==='CLEAN'?'CLEAN':d.scanState==='QUARANTINED'?'QUARANTINE':['QUARANTINE','SCANNING'].includes(d.scanState)?d.scanState as 'QUARANTINE'|'SCANNING':'FAILED',ocrStatus:['READY','FAILED'].includes(d.extractionState)?d.extractionState as 'READY'|'FAILED':'PENDING',extractionId:d.extractionId,canDownload:d.scanState==='CLEAN'};
    if(item.ocrStatus==='READY'){
      const e=await request<{extractionId:string;documentVersion:number;objectVersion:string;fields:{name:string;value:string}[]}>('/api/v1/documents/'+enc(d.documentId)+'/extraction');
      item.extractionId=e.extractionId;
      item.extractedPeriod=e.fields.find(f=>f.name==='period')?.value;
      item.values=Object.fromEntries(Object.keys(financeFields).map(k=>[k,e.fields.find(f=>f.name===k)?.value??''])) as Finance;
    }
    return item;
  })),
  upload:async(id:string,file:File,onProgress:(n:number)=>void)=>{const r=await request<{requirementsVersion:number;items:{requirementId:string;allowedContentTypes:string[]}[]}>(path(id)+'/document-requirements');const req=r.items.find(r=>r.allowedContentTypes.includes(file.type));if(!req)throw new Error('Нет серверного требования для такого типа файла');const intent=await stable<{uploadUrl:string;grant:string;documentId:string;maxBytes:number}>(path(id)+'/documents/upload-intents','POST',{fileName:file.name,declaredMimeType:file.type,sizeBytes:file.size,documentType:req.requirementId==='financial-statement'?'FINANCIAL_STATEMENT':req.requirementId,requirementId:req.requirementId,requirementsVersion:r.requirementsVersion});if(file.size>intent.maxBytes)throw new Error('Файл слишком большой');await request<void>(intent.uploadUrl,{method:'PUT',headers:{'Content-Type':file.type,'X-Upload-Grant':intent.grant},body:file});onProgress(100);return intent.documentId;},
  file:async(id:string)=>{const d=await request<{downloadUrl:string;grant:string}>('/api/v1/documents/'+enc(id)+'/download-intents',{method:'POST'});return request<Blob>(d.downloadUrl,{headers:{'X-Download-Grant':d.grant}},true);},
  confirmOcr:async(id:string,doc:DocumentItem,f:Draft['finance'],c:Draft['confirmed'],v:number)=>{
    const [fresh,extraction]=await Promise.all([application(id),request<{extractionId:string;documentVersion:number;objectVersion:string}>('/api/v1/documents/'+enc(doc.id)+'/extraction')]);
    if(fresh.financialVersion!==v || extraction.extractionId!==doc.extractionId || extraction.objectVersion!==doc.objectVersion)throw new ApiError(409,'Документ или финансовые данные изменились. Откройте сверку заново.');
    if(doc.extractedPeriod && doc.extractedPeriod!==fresh.draft.period && doc.extractedPeriod!==`${fresh.draft.period}-01-01/${fresh.draft.period}-12-31`)throw new ApiError(422,'Период документа отличается от отчётного года заявки. Сначала исправьте год на шаге финансов.');
    const selected=(Object.keys(financeFields) as FinanceKey[]).filter(k=>c[k]);
    if(!selected.length)throw new Error('Отметьте показатели, которые хотите перенести в анкету');
    const merged={...fresh.draft,finance:{...fresh.draft.finance},confirmed:{...fresh.draft.confirmed}};
    for(const key of selected){
      minor(f[key],signedFields.includes(key));
      merged.finance[key]=f[key];merged.confirmed[key]=true;
    }
    return save(id,merged,fresh.version,doc);
  },
  information,saveInformation,
  respond:(r:InformationRequest,_docs:DocumentItem[]=[])=>command(async()=>{const s=await request<Statement>(path(r.applicationId)+`/information-requests/${enc(r.id)}/draft/financial-statement`);if(!s.confirmed)throw new Error('Подтвердите уточнения');await stable(path(r.applicationId)+`/information-requests/${enc(r.id)}/responses`,'POST',{requestVersion:r.requestVersion,requirementsVersion:r.requirementsVersion,draftVersion:r.draftVersion,financialStatementVersion:s.statementVersion,documentIds:[],documentReferences:[]});return application(r.applicationId);}),
  offer,offerForApplication:async(id:string)=>{const d=await request<{offerIds:string[]}>(path(id)+'/decision');if(!d.offerIds.length)throw new ApiError(404,'Предложение отсутствует');return offer(d.offerIds[0]);},
  accept:(o:Offer)=>command(async()=>{await stable('/api/v1/offers/'+enc(o.id)+'/accept','POST',{expectedVersion:o.version},o.version);return offer(o.id);}),
  complete:(o:Offer)=>command(async()=>{await stable('/api/v1/offers/'+enc(o.id)+'/complete','POST',{expectedVersion:o.version},o.version);return offer(o.id);}),
  notices:()=>unsupported<Notice[]>(),readNotice:(_id:string)=>unsupported<void>(),
  conversation:async(id:string)=>{
    const h=await request<{messages:{client_message_id:string;message:string;response?:AssistantResponse}[]}>('/api/v1/assistant/conversations/'+enc(id)+'/messages');
    return h.messages.flatMap(m=>[{id:m.client_message_id,role:'user' as const,text:m.message},...(m.response?[assistantMessage(m.response)]:[])]);
  },
  ask:async(id:string,text:string,signal:AbortSignal)=>assistantMessage(await stableAssistant(id,text,signal)),
  preferences:()=>request<Preferences>('/api/v1/feed/preferences?'+companyQuery()),
  savePreferences:(p:Preferences)=>request<Preferences>('/api/v1/feed/preferences?'+companyQuery(),{method:'PUT',body:json(p)}),
  feed:(cursor?:string)=>request<Feed>('/api/v1/feed?'+companyQuery()+(cursor?'&cursor='+enc(cursor):'')),
  saved:(cursor?:string)=>request<SavedFeed>('/api/v1/feed/saved?'+companyQuery()+(cursor?'&cursor='+enc(cursor):'')),
  feedback:(event:{clientEventId:string;exposureId:string;itemId:string;action:'VIEW'|'CLICK'|'HELPFUL'|'NOT_INTERESTED';occurredAt:string})=>request('/api/v1/recommendation-feedback',{method:'POST',headers:{'Idempotency-Key':event.clientEventId},body:json(event)}),
  exposure:(_itemId:string,_type:'VIEW'|'CLICK',_exposureId:string)=>unsupported<void>(),
};
