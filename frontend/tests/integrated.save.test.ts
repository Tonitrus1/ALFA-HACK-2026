import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../src/shared/api/client';
import { ApiError, context, request } from '../src/shared/api/http';
import { financeFields, type Draft, type DocumentItem } from '../src/shared/types/domain';

vi.mock('../src/shared/api/http', async (original) => ({
  ...await original<typeof import('../src/shared/api/http')>(), request: vi.fn(),
}));

const refs=[{documentId:'doc',documentVersion:4,objectVersion:'object-v1'}];
let version:number;
let statement: {statementVersion:number;containerVersion:number;confirmed:boolean;statement:Record<string,unknown>} | undefined;
let writes:{path:string;body:Record<string,unknown>}[];
function draft(populated=false):Draft {
  return {companyName:'Demo',inn:'',address:'',activity:'Продажи',businessAgeMonths:'36',preliminaryRevenue:'5000000',
    period:'2025',currency:'RUB',unit:'RUB',consents:false,
    finance:Object.fromEntries(Object.keys(financeFields).map(k=>[k,populated?'100':''])) as Draft['finance'],
    confirmed:Object.fromEntries(Object.keys(financeFields).map(k=>[k,populated])) as Draft['confirmed']};
}
beforeEach(()=>{
  version=1; statement=undefined; writes=[];
  context.set({actor:'user',companyId:'company',contextVersion:1,csrfToken:'csrf',expiresAt:'2030',companies:[]});
  vi.mocked(request).mockReset();
  vi.mocked(request).mockImplementation(async (path,init)=>{
    const body=init?.body?JSON.parse(String(init.body)):undefined;
    if(init?.method && init.method!=='GET') writes.push({path,body});
    if(path.endsWith('/extraction'))return path.includes('/doc-two/')?{extractionId:'extraction-two',objectVersion:'object-v2',fields:[]}:{extractionId:'extraction',objectVersion:'object-v1',fields:[]};
    if(path.endsWith('/documents'))return {items:[{documentId:'doc',version:4,scanState:'CLEAN',extractionState:'FAILED',objectVersion:'object-v1',fileName:'report.png'},{documentId:'doc-two',version:5,scanState:'CLEAN',extractionState:'FAILED',objectVersion:'object-v2',fileName:'income.png'}]};
    if(path.endsWith('/status'))return {status:'DRAFT',history:[],nextAction:{type:'CONTINUE',label:'Continue',targetPath:''}};
    if(path.endsWith('/confirm')){
      expect(body.documentReferences).toEqual(statement!.statement.sourceDocumentReferences);
      statement={...statement!,confirmed:true,containerVersion:++version};return statement;
    }
    if(path.endsWith('/financial-statement')){
      if(init?.method==='PUT'){
        statement={statementVersion:1,containerVersion:++version,confirmed:false,statement:body};return statement;
      }
      if(!statement)throw new ApiError(404,'Not started');return statement;
    }
    if(init?.method==='PATCH')version++;
    return {applicationId:'app',companyId:'company',productId:'product',version,updatedAt:'2026-10-25',terms:{purpose:'Demo',amount:{amountMinor:100},termMonths:12,business:{activityDescription:'Продажи',businessAgeMonths:36}}};
  });
});

describe('saving a draft with uploaded documents',()=>{
  it('saves business details without creating finances or reading OCR documents',async()=>{
    const saved=await api.save('app',draft(),1);
    expect(writes.map(w=>w.path)).toEqual(['/api/v1/applications/app']);
    expect(saved.version).toBe(2);
    expect(writes[0].body.business).toMatchObject({businessAgeMonths:36,annualRevenue:{amountMinor:500000000}});
    expect(vi.mocked(request).mock.calls.some(([path])=>path.endsWith('/documents'))).toBe(false);
  });
  it('does not claim uploaded files as sources for manually entered financial values',async()=>{
    await api.save('app',draft(true),1);
    const saved=writes.find(w=>w.path.endsWith('/financial-statement'))!;
    expect(saved.body.sourceDocumentReferences).toEqual([]);
    expect(writes.some(w=>w.path.endsWith('/confirm'))).toBe(true);
  });
  it('refreshes the document revision for the same OCR object before saving and confirming',async()=>{
    statement={statementVersion:1,containerVersion:1,confirmed:false,statement:{periodStart:'2025-01-01',periodEnd:'2025-12-31',reportingStandard:'DEMO',currency:'RUB',values:{},sourceDocumentReferences:[]}};
    const doc:DocumentItem={id:'doc',applicationId:'app',name:'report',size:1,type:'image/png',status:'CLEAN',ocrStatus:'READY',documentVersion:3,objectVersion:'object-v1',extractionId:'extraction',canDownload:true};
    await api.confirmOcr('app',doc,draft(true).finance,draft(true).confirmed,1);
    expect(writes.find(w=>w.path.endsWith('/financial-statement'))!.body.sourceDocumentReferences).toEqual(refs);
    expect(writes.find(w=>w.path.endsWith('/confirm'))!.body.documentReferences).toEqual(refs);
  });
  it('rejects a replaced OCR object before changing the business draft',async()=>{
    const doc:DocumentItem={id:'doc',applicationId:'app',name:'report',size:1,type:'image/png',status:'CLEAN',ocrStatus:'READY',documentVersion:3,objectVersion:'replaced-object',canDownload:true};
    await expect(api.save('app',draft(true),1,doc)).rejects.toMatchObject({status:409});
    expect(writes).toEqual([]);
  });
  it('applies partial OCR without erasing manual values or requiring a complete statement',async()=>{
    statement={statementVersion:1,containerVersion:1,confirmed:false,statement:{periodStart:'2025-01-01',periodEnd:'2025-12-31',reportingStandard:'DEMO',currency:'RUB',values:{revenueMinor:300000000,netProfitMinor:10000000},sourceDocumentReferences:[]}};
    const doc:DocumentItem={id:'doc',applicationId:'app',name:'Баланс',size:1,type:'image/png',status:'CLEAN',ocrStatus:'READY',documentVersion:3,objectVersion:'object-v1',extractionId:'extraction',canDownload:true};
    const values={...draft().finance,totalAssets:'1000000',equity:'600000'};
    const selected={...draft().confirmed,totalAssets:true,equity:true};
    const saved=await api.confirmOcr('app',doc,values,selected,1);
    expect(writes.find(w=>w.path.endsWith('/financial-statement'))!.body.values).toEqual({totalAssetsMinor:100000000,equityMinor:60000000,revenueMinor:300000000,netProfitMinor:10000000});
    expect(writes.some(w=>w.path.endsWith('/confirm'))).toBe(false);
    expect(saved.draft.finance.revenue).toBe('3000000,00');
    expect(saved.draft.finance.totalLiabilities).toBe('');
  });
  it('combines a second document with the previous values and both source references',async()=>{
    statement={statementVersion:1,containerVersion:1,confirmed:false,statement:{periodStart:'2025-01-01',periodEnd:'2025-12-31',reportingStandard:'DEMO',currency:'RUB',values:{totalAssetsMinor:100000000,equityMinor:60000000},sourceDocumentReferences:refs}};
    const doc:DocumentItem={id:'doc-two',applicationId:'app',name:'Отчёт о результатах',size:1,type:'image/png',status:'CLEAN',ocrStatus:'READY',documentVersion:4,objectVersion:'object-v2',extractionId:'extraction-two',canDownload:true};
    await api.confirmOcr('app',doc,{...draft().finance,revenue:'3000000'},{...draft().confirmed,revenue:true},1);
    const saved=writes.find(w=>w.path.endsWith('/financial-statement'))!.body;
    expect(saved.values).toEqual({totalAssetsMinor:100000000,equityMinor:60000000,revenueMinor:300000000});
    expect(saved.sourceDocumentReferences).toEqual([...refs,{documentId:'doc-two',documentVersion:5,objectVersion:'object-v2'}]);
    expect(writes.some(w=>w.path.endsWith('/confirm'))).toBe(false);
  });
});
