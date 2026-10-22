"""Static architecture/contract validation. No runtime system is executed."""
from pathlib import Path
import os,sys,json,hashlib,re,copy,zipfile,xml.etree.ElementTree as ET,math
extra=os.environ.get('CREDIT_RENDER_DEPS')
if extra:sys.path.insert(0,extra)
from jsonschema import Draft202012Validator,FormatChecker
from openapi_spec_validator import validate as validate_openapi
from pypdf import PdfReader
O=Path(__file__).resolve().parents[1]
HTTP={'get','post','put','patch','delete'}
def rd(p):return json.loads((O/p).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def wr(p,v):(O/p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
checks=[];fixtures=[]
def ck(name,ok,detail=''):
 checks.append(dict(check=name,passed=bool(ok),detail=str(detail)[:1200]));return bool(ok)
def ops(d):return [(m,p,v) for p,x in d['paths'].items() for m,v in x.items() if m in HTTP]
P=rd('contracts/public.openapi.json');I=rd('contracts/internal.openapi.json');D=rd('contracts/demo.openapi.json')
def schema_validator(doc,name):
 return Draft202012Validator({'$ref':'#/components/schemas/'+name,'components':doc['components']},format_checker=FormatChecker())
def fixture(name,doc,schema,value,valid,origin='current'):
 if isinstance(doc,str):v=Draft202012Validator(rd(doc),format_checker=FormatChecker())
 else:v=schema_validator(doc,schema)
 errors=list(v.iter_errors(value));actual=not errors
 contract=doc if isinstance(doc,str) else ('contracts/public.openapi.json' if doc is P else 'contracts/internal.openapi.json' if doc is I else 'contracts/demo.openapi.json')
 fixtures.append(dict(id=name,contract=contract,schema=schema,expectedValid=valid,actualValid=actual,origin=origin,value=copy.deepcopy(value)))
 ck('fixture:'+name,actual==valid,'; '.join(e.message for e in errors[:2]) if actual!=valid else '')

def structure():
 for p in sorted(O.rglob('*.json')):
  try:json.loads(p.read_text());ck('json:'+str(p.relative_to(O)),True)
  except Exception as e:ck('json:'+str(p.relative_to(O)),False,e)
 for label,d in [('public',P),('internal',I),('demo',D)]:
  try:validate_openapi(d);ck(label+'-openapi',True)
  except Exception as e:ck(label+'-openapi',False,e)
  ids=[v['operationId'] for _,_,v in ops(d)];ck(label+'-unique-operation-ids',len(ids)==len(set(ids)))
  refs=set()
  def walk(v):
   if isinstance(v,dict):
    if '$ref' in v:refs.add(v['$ref'])
    for x in v.values():walk(x)
   elif isinstance(v,list):
    for x in v:walk(x)
  walk(d)
  bad=[]
  for ref in refs:
   try:
    assert ref.startswith('#/');target=d
    for part in ref[2:].split('/'):target=target[part.replace('~1','/').replace('~0','~')]
   except Exception:bad.append(ref)
  ck(label+'-all-refs-resolve',not bad,bad)
 ck('public-count',len(ops(P))==63);ck('demo-count',len(ops(D))==6)
 ck('demo-isolation',not(set(P['paths'])&set(D['paths'])))
 copies=[]
 for n in ['general','backend','frontend','ml']:
  for c,f in [('public','openapi.json'),('internal','internal.openapi.json'),('demo','demo.openapi.json')]:
   copies.append(sha(O/f'contracts/{c}.openapi.json')==sha(O/f'packages/{n}/api/{f}'))
 ck('copies-identical',all(copies));ck('all-four-packages',len(copies)==12)
 ck('no-legacy-risk','/internal/v1/risk/evaluations' not in I['paths'] and '/internal/v1/feed/ranking' not in I['paths'])
 ck('rag-internal-route','/internal/v2/assistant/answers' in I['paths'])
 ck('snapshot-read-route','/internal/v2/feature-snapshots/{featureSnapshotId}' in I['paths'])
 ck('financial-package-fields',all(set(['financialStatementVersion','financialSnapshotId','financialStatement'])<=set(I['components']['schemas'][x]['required']) for x in ['SubmissionPackage','AmendmentPackage']))
 ck('feature-input-complete',set(['financialStatement','financialSnapshotId','financialSnapshotDigest'])<=set(I['components']['schemas']['MLFeatureSnapshotInput']['required']))
 ck('ranking-text-inputs',set(['contextText','candidateTexts'])<=set(I['components']['schemas']['MLRankingRequest']['allOf'][0]['then']['required']))
 ck('ranking-metadata-required',all('rankingMetadata' in P['components']['schemas'][n]['required'] for n in ['RecommendationList','Feed']))
 ck('feed-service-identity',I['components']['securitySchemes']['ServiceIdentity']['name']=='X-Service-Token')
 ck('saved-feed-read-route',P['paths']['/api/v1/feed/saved']['get']['operationId']=='getSavedFeed')
 ck('feed-user-reaction-required','userReaction' in P['components']['schemas']['FeedCard']['required'])
 for name in ['Submit','InformationResponse']:ck(name.lower()+'-financial-required','financialStatementVersion' in P['components']['schemas'][name]['required'])
 ck('session-context-version','contextVersion' in P['components']['schemas']['Session']['required'])
 ck('no-public-external-key','externalRequestId' not in json.dumps(P['components']['schemas']['Operation']))
 ck('rfi-draft-version','draftVersion' in P['components']['schemas']['InformationResponse']['required'])
 ck('document-refs-required',all(set(['documentReferences','requirementsVersion'])<=set(P['components']['schemas'][n]['required']) for n in ['Submit','InformationResponse']))
 ck('rfi-confirm-route',any('draft/confirm-extraction' in p for p in P['paths']))
 ck('case-snapshot-route','/internal/v1/cases/{caseId}/snapshot' in I['paths'])
 ck('worker-lease-required',all(set(['leaseToken','workerId','generation','objectVersion'])<=set(I['components']['schemas'][n]['required']) for n in ['ScanResult','ExtractionResult']))
 for p in ['/api/v1/files/uploads/{transferId}','/api/v1/files/downloads/{transferId}']:
  for m,op in P['paths'][p].items():
   if m in HTTP:ck('file-error-schema:'+m,all('application/json' in v.get('content',{}) and 'Cache-Control' in v.get('headers',{}) for k,v in op['responses'].items() if str(k).startswith(('4','5'))))
 ck('operation-list-recovery','/api/v1/operations' in P['paths'] and '/api/v1/operations/lookup' in P['paths'])
 ck('public-no-raw-score',not any(x in P['components']['schemas'] for x in ['RiskResult','MLRiskResult']))
 for n in ['credit-events-v1','ml-events-v1','dataset-manifest','experiment-manifest','feature-snapshot','release-manifest']:
  try:Draft202012Validator.check_schema(rd(f'contracts/{n}.schema.json'));ck('jsonschema:'+n,True)
  except Exception as e:ck('jsonschema:'+n,False,e)


def regression_fixtures():
 with zipfile.ZipFile(O/'evidence/originals.zip') as z:
  base=json.loads(z.read('output/architecture-review/contract-fixtures.json'))
  ml=json.loads(z.read('output/credit-workspace-ml-architecture/contract-fixtures.json'))
 for f in base:
  doc=P if f['schema'] in P['components']['schemas'] else I
  if f['schema']=='DemoAction':doc=D
  val=copy.deepcopy(f['value'])
  if f['name']=='upload-request-version-required':val.pop('requestVersion',None)
  if f['name']=='stream-snapshot-barrier':val['complete']=False
  if f['name']=='credit-package-typed':val['data']={'kind':'ACCEPTANCE','offerId':'offer-1','offerVersion':2,'actorRef':'actor-1'}
  if f['schema'] in ['Submit','InformationResponse']:val['financialStatementVersion']=1
  fixture('regression-'+f['name'],doc,f['schema'],val,f['expectedValid'],'baseline fixture adapted for mandatory financialStatementVersion')
 for f in ml:
  val=copy.deepcopy(f['value']);schema=f['schema']
  if schema=='EVENT':doc='contracts/ml-events-v1.schema.json'
  elif schema in ['ReleaseManifest','DatasetManifest','ExperimentManifest']:
   doc='contracts/'+{'ReleaseManifest':'release-manifest','DatasetManifest':'dataset-manifest','ExperimentManifest':'experiment-manifest'}[schema]+'.schema.json'
  else:
   schema='ML'+schema;doc=P if schema in P['components']['schemas'] else I
  if schema=='MLFeatureSnapshot':val.update(financialSnapshotId='fin-demo-1',financialSnapshotDigest='a'*64)
  if schema=='MLRankingResult' and val.get('scope')=='FEED':
   val.update(catalogDigest='a'*64,explanations={})
  if schema=='MLRankingRequest' and val.get('scope')=='FEED':
   for key in ['stage','contextCategory','contextText','fundingPurpose','eligibilityVersion']:val.pop(key,None)
   val.update(profile={},catalogDigest='a'*64,exposureId='ex-fixture')
  if schema=='MLRankingRequest' and val.get('scope')=='PRODUCT':
   val.update(contextText='Оборотные средства',candidateTexts=[dict(itemId=x,text='Утверждённое описание '+x) for x in val.get('candidateIds',[])])
  fixture('regression-'+f['id'],doc,schema,val,f['valid'],'previous ML schema fixture, adapted only for explicit1.4 inputs')


def current_fixtures():
 saved_card={'contentId':'cash-01','version':1,'title':'Кассовый разрыв','text':'Пример полного текста карточки.',
             'topic':'CASH_GAP','depth':'BASICS','illustration':'/assets/feed/v1/illustrations/cash_gap.svg',
             'reasonCategory':'SAVED_HELPFUL','reason':'Вы отметили этот материал как полезный.','userReaction':'HELPFUL'}
 saved={'cards':[saved_card],'exposureId':'saved-ex-a','catalogVersion':1,'catalogDigest':'a'*64,
        'savedVersion':1,'hasMore':False}
 fixture('saved-feed-valid',P,'SavedFeed',saved,True)
 fixture('saved-feed-empty',P,'SavedFeed',dict(saved,cards=[],savedVersion=0),True)
 fixture('saved-feed-continuation',P,'SavedFeed',dict(saved,hasMore=True,nextCursor='opaque-saved-cursor'),True)
 fixture('saved-feed-missing-cursor',P,'SavedFeed',dict(saved,hasMore=True),False)
 fixture('saved-feed-extra-cursor',P,'SavedFeed',dict(saved,nextCursor='unnecessary'),False)
 for field in ['exposureId','savedVersion','catalogDigest']:
  val=copy.deepcopy(saved);val.pop(field);fixture('saved-feed-needs-'+field,P,'SavedFeed',val,False)
 val=copy.deepcopy(saved);val['cards'][0]['userReaction']='NOT_INTERESTED';fixture('saved-feed-only-helpful',P,'SavedFeed',val,False)
 val=copy.deepcopy(saved_card);val.pop('userReaction');fixture('feed-card-needs-reaction',P,'FeedCard',val,False)
 financial={'periodStart':'2025-01-01','periodEnd':'2025-12-31','reportingStandard':'DEMO','currency':'RUB','values':{'totalAssetsMinor':100000000,'totalLiabilitiesMinor':60000000,'currentAssetsMinor':50000000,'currentLiabilitiesMinor':25000000,'equityMinor':40000000,'revenueMinor':150000000,'netProfitMinor':12000000,'ebitMinor':18000000},'sourceDocumentReferences':[]}
 fixture('demo-financial-valid',P,'MLFinancialInput',financial,True)
 for standard in ['RSBU','IFRS']:
  v=copy.deepcopy(financial);v['reportingStandard']=standard;fixture('finance-standard-'+standard,P,'MLFinancialInput',v,False)
 for n in ['totalAssetsMinor','totalLiabilitiesMinor','equityMinor','netProfitMinor']:
  v=copy.deepcopy(financial);v['values'][n]=1.5;fixture('fractional-minor-'+n,P,'MLFinancialInput',v,False)
 v=copy.deepcopy(financial);v['confirmed']=True;fixture('forged-financial-confirmed',P,'MLFinancialInput',v,False)
 # New input objects are complete and reference exact immutable statements.
 fsi={'applicationId':'app-a','submissionSnapshotId':'sub-a','financialStatementVersion':1,'asOf':'2026-10-20T00:00:00Z','purpose':'DEMO_RESEARCH','financialSnapshotId':'fin-a','financialSnapshotDigest':'a'*64,'financialStatement':financial}
 fixture('feature-input-complete',I,'MLFeatureSnapshotInput',fsi,True)
 for n in ['financialSnapshotId','financialSnapshotDigest','financialStatement']:
  v=copy.deepcopy(fsi);v.pop(n);fixture('feature-input-needs-'+n,I,'MLFeatureSnapshotInput',v,False)
 for schema in ['SubmissionPackage','AmendmentPackage']:
  if schema=='SubmissionPackage':
   val={'kind':'SUBMISSION','productId':'working-capital','productVersion':1,'terms':{'purpose':'Оборотные средства','amount':{'amountMinor':10000000,'currency':'RUB'},'termMonths':12},'business':{},'documentReferences':[],'consentRecordIds':['consent-a'],'requirementsVersion':1}
  else:val={'kind':'AMENDMENT','requestId':'rfi-a','requestVersion':1,'draftVersion':1,'requirementsVersion':1,'documentReferences':[]}
  val.update(financialStatementVersion=1,financialSnapshotId='fin-a',financialStatement=financial)
  fixture('typed-package-'+schema,I,schema,val,True)
  for n in ['financialStatementVersion','financialSnapshotId','financialStatement']:
   v=copy.deepcopy(val);v.pop(n);fixture('typed-package-needs-'+schema+'-'+n,I,schema,v,False)
 rag={'requestId':'r-a','companyId':'company-a','subjectRef':'actor-a','message':'Как ответить на уточнение?','kbEpoch':1,'allowedSources':[{'documentId':'kb-a','documentVersion':1}]}
 fixture('rag-context-valid',I,'MLRagInput',rag,True)
 for n in ['companyId','subjectRef','allowedSources','kbEpoch']:
  v=copy.deepcopy(rag);v.pop(n);fixture('rag-context-needs-'+n,I,'MLRagInput',v,False)
 v=copy.deepcopy(rag);v['toolPermissions']=['accept-offer'];fixture('rag-no-tool-permissions',I,'MLRagInput',v,False)
 rank={'requestId':'rank-a','scope':'PRODUCT','candidateIds':['working-capital','credit-line'],'candidateSetDigest':'a'*64,'catalogVersion':1,'eligibilityVersion':1,'stage':'NEED','contextCategory':'SME','fundingPurpose':'Оборотные средства','contextText':'Закупка товара','candidateTexts':[{'itemId':'working-capital','text':'Разовая закупка товара'},{'itemId':'credit-line','text':'Повторное финансирование'}]}
 fixture('ranking-request-text-valid',I,'MLRankingRequest',rank,True)
 for n in ['contextText','candidateTexts']:
  v=copy.deepcopy(rank);v.pop(n);fixture('ranking-request-needs-'+n,I,'MLRankingRequest',v,False)
 for n in ['Feed','RecommendationList']:
  v={'cards':[],'rankingMode':'RULES','hasMore':False} if n=='Feed' else {'items':[]}
  fixture('metadata-absent-'+n,P,n,v,False)
  v['rankingMetadata']={'exposureId':'ex-a','releaseId':'rules-v1','mode':'RULES','candidateSetDigest':'a'*64,'catalogVersion':1}
  fixture('metadata-present-'+n,P,n,v,True)
 for folder,schema in [('credit','credit-events-v1'),('ml','ml-events-v1')]:
  for p in sorted((O/f'contracts/examples/{folder}').glob('*.json')):
   val=json.loads(p.read_text());fixture('event-'+folder+'-'+p.stem,'contracts/'+schema+'.schema.json','EVENT',val,True)
   bad=copy.deepcopy(val);bad['payload']['unexpected']='forbidden';fixture('event-strict-'+folder+'-'+p.stem,'contracts/'+schema+'.schema.json','EVENT',bad,False)
 # Schema assertions strengthen non-implemented runtime guard specifications.
 ck('negative-fixtures',sum(not f['expectedValid'] for f in fixtures)>=50)
 ck('typed-package-fixtures',any(f['id']=='typed-package-SubmissionPackage' for f in fixtures))
 wr('contract-fixtures.json',fixtures)
 replay=rd('contract-fixtures.json');ok=True
 for f in replay:
  doc=rd(f['contract']);v=schema_validator(doc,f['schema']) if 'openapi' in doc else Draft202012Validator(doc,format_checker=FormatChecker())
  valid=v.is_valid(f['value']);ok=ok and valid==f['expectedValid']
 ck('serialized-fixtures-revalidated',ok,'Reopened and validated '+str(len(replay))+' saved fixtures')
 migrations=[{'fixture':n,'reason':'Original persisted object was mutated after earlier validation; H20; exact original remains in archive.'} for n in ['upload-request-version-required','stream-snapshot-barrier','credit-package-typed']]
 wr('evidence/fixture-migration-log.json',migrations)
 ck('fixture-migration-log',len(migrations)==3)


def semantic_oracles():
 # These are reference-predicate examples only. They do not test application code.
 cases=[]
 def example(id,rule,v,valid):cases.append(dict(id=id,rule=rule,value=v,expectedAllowed=valid))
 for ids,ret,ok in [(['a','b'],['b','a'],True),(['a','b'],['a','a'],False),(['a','b'],['a','foreign'],False),(['a','b'],['a'],False)]:example('permutation-'+str(len(cases)),'permutation',{'candidateIds':ids,'rankedIds':ret},ok)
 for ids,texts,ok in [(['a','b'],['a','b'],True),(['a','b'],['a','foreign'],False),(['a','b'],['a','a'],False)]:example('candidate-texts-'+str(len(cases)),'texts',{'candidateIds':ids,'textIds':texts},ok)
 for ctx,session,ok in [(1,1,True),(1,2,False)]:example('context-'+str(len(cases)),'context',{'request':ctx,'session':session},ok)
 for request,saved,ok in [('abc','abc',True),('abc','def',False)]:example('snapshot-digest-'+str(len(cases)),'digest',{'request':request,'saved':saved},ok)
 for conf,edited,ok in [(3,3,True),(2,3,False)]:example('financial-version-'+str(len(cases)),'version',{'confirmed':conf,'saved':edited},ok)
 for epoch,now,revoked,ok in [(1,1,False,True),(1,2,True,False),(2,2,True,False)]:example('rag-revoke-'+str(len(cases)),'rag',{'capturedEpoch':epoch,'authorityEpoch':now,'revoked':revoked},ok)
 for scope,owner,item,shown,ok in [('a','a','p1',['p1'],True),('a','b','p1',['p1'],False),('a','a','foreign',['p1'],False)]:example('exposure-'+str(len(cases)),'exposure',{'actor':scope,'owner':owner,'item':item,'shown':shown},ok)
 for available,asof,ok in [('2026-10-19','2026-10-20',True),('2026-10-21','2026-10-20',False)]:example('asof-'+str(len(cases)),'time',{'availableAt':available,'asOf':asof},ok)
 predicates={'permutation':lambda v:len(v['rankedIds'])==len(set(v['rankedIds'])) and set(v['candidateIds'])==set(v['rankedIds']),'texts':lambda v:len(v['textIds'])==len(set(v['textIds'])) and set(v['candidateIds'])==set(v['textIds']),'context':lambda v:v['request']==v['session'],'digest':lambda v:v['request']==v['saved'],'version':lambda v:v['confirmed']==v['saved'],'rag':lambda v:v['capturedEpoch']==v['authorityEpoch'] and not v['revoked'],'exposure':lambda v:v['actor']==v['owner'] and v['item'] in v['shown'],'time':lambda v:v['availableAt']<=v['asOf']}
 for c in cases:ck('design-oracle:'+c['id'],predicates[c['rule']](c['value'])==c['expectedAllowed'])
 wr('semantic-fixtures.json',{'scope':'Design reference predicates only; not application testing','cases':cases})


def graphs_and_profiles():
 tasks=rd('tasks.json');by={t['id']:t for t in tasks};seen=set();active=set()
 def visit(id):
  if id in active:raise ValueError('cycle:'+id)
  if id in seen:return
  active.add(id)
  for dep in by[id]['dependsOn']:visit(dep)
  active.remove(id);seen.add(id)
 try:
  for id in by:visit(id)
  ck('task-dag',True)
 except Exception as e:ck('task-dag',False,e)
 ck('task-hours',sum(t['personHours'] for t in tasks if t['profile']=='mvp')==rd('evidence/schedule-analysis.json')['personHours'])
 ck('task-records',all(t['ownerRole'] and t['deliverable'] and t['doneWhen'] for t in tasks))
 ac=rd('acceptance-cases.json');ck('runtime-not-executed',all(c['executionStatus']=='NOT_EXECUTED_NO_APPLICATION' for c in ac))
 ck('acceptance-task-links',all(x in by for c in ac for x in c['taskIds']))
 graph=rd('contracts/state-machine.json');states=set(graph['states']);ck('state-coverage',states==set(P['components']['schemas']['Application']['properties']['status']['enum']))
 ck('state-transition-refs',all(t['source'] in states and t['target'] in states and t['actor'] and t['guard'] and t['effect'] for t in graph['transitions']))
 ck('terminal-states',not any(t['source'] in graph['terminal'] for t in graph['transitions']))
 reached={'DRAFT'}
 for _ in states:
  reached|={t['target'] for t in graph['transitions'] if t['source'] in reached}
 ck('all-states-reachable',reached==states)
 dep=rd('contracts/deployment-spec.json');names={x['name'] for x in dep['services']};ck('cpu-profile',names=={'web','backend','postgres','ml','llm','scanner'} and all(x['profile']=='local-mvp' for x in dep['services']))
 ck('service-role-map',all(op.get('x-allowed-service-role') and 'platform-internal' not in op['x-allowed-service-role'] for _,_,op in ops(I)))
 ck('service-deps-resolve',all(set(x['depends'])<=names for x in dep['services']))
 ck('only-web-exposed',all(not x['ports'] for x in dep['services'] if x['name']!='web'))
 pol=rd('contracts/runtime-policy.json');ck('cpu-no-required-gpu',not pol['gpu']['mandatory'])
 ck('model-selection',pol['cpu']['llm']['repository']=='Qwen/Qwen2.5-0.5B-Instruct-GGUF' and pol['cpu']['embedding']=='intfloat/multilingual-e5-small')
 ck('budget-consistency',pol['deadlinesSeconds']['ragGeneration']<pol['deadlinesSeconds']['ragTotal']<pol['deadlinesSeconds']['ragClient'])
 catalog=rd('contracts/technology-adapters.json');caps=catalog['capabilities'];capids={x['id'] for x in caps}
 ck('target-separation',len(caps)==13 and {'Qdrant','Redis','Feast','MLflow','Airflow','Evidently','vLLM','Kafka','S3','Prometheus','Grafana','Kubernetes'}=={x['technology'] for x in caps} and not catalog['runtimeImplemented'])
 ck('adapter-contract-records',all(all(x.get(k) for k in ['port','ownerRole','dataOwner','signature','dataContract','localBehavior','invariants','limitations','switchGate','contractCases','taskIds']) for x in caps))
 ck('adapter-task-links',all(set(x['taskIds'])<=set(by) for x in caps))
 bs=rd('contracts/adapter-bindings.schema.json');Draft202012Validator.check_schema(bs);bv=Draft202012Validator(bs)
 for profile in ['local-mvp','local-integrations','bank-target']:
  ex=rd('contracts/examples/profiles/'+profile+'.json')
  ck('binding-schema:'+profile,not list(bv.iter_errors(ex)))
  ck('binding-coverage:'+profile,set(ex['bindings'])==capids and ex['automaticProviderFallback'] is False)
  if profile=='local-mvp':ck('local-bindings-only',all(ex['bindings'][x['id']]==x['localProvider'] for x in caps))
  if profile=='bank-target':ck('target-bindings-only',all(ex['bindings'][x['id']]==x['realProvider'] for x in caps))
 base=rd('contracts/examples/profiles/local-mvp.json')
 for label,mutate in [('unknown',lambda x:x['bindings'].update(vectors='MagicAdapter')),('missing',lambda x:x['bindings'].pop('features')),('automatic-fallback',lambda x:x.update(automaticProviderFallback=True)),('wrong-pair',lambda x:x['bindings'].update(features='QdrantVectorIndexAdapter'))]:
  ex=copy.deepcopy(base);mutate(ex);ck('binding-negative:'+label,bool(list(bv.iter_errors(ex))))
 ck('adapter-not-runtime',all(x['implementationStatus']=='SPECIFIED_NOT_IMPLEMENTED' for x in caps))
 ck('optional-services-isolated',len(dep['optionalIntegrationServices'])==3 and all(not x['ports'] and not x['requiredInLocalMvp'] for x in dep['optionalIntegrationServices']))
 ck('token-budget-port',str(pol['cpu']['llm']['maxOutputTokens'])+' output-token' in next(x['dataContract'] for x in caps if x['id']=='generation'))
 ck('no-runtime-download-training',not pol['trainingAtRuntime'] and not pol['downloadAtRuntime'])
 ck('release-profiles','minCandidateRequests' not in json.dumps(pol['release']) and rd('contracts/bank-target-release-policy.json')['canary']['minCandidateRequests']==1000)
 doc=(O/'docs/git-and-jury-guide.md').read_text();ck('git-handbook',all(x in doc for x in ['main','PR','CODEOWNERS','force-with-lease','alfa-hack-2026','commit SHA','дедлайна']))
 ck('jury-traceability',all(x in doc for x in ['Целостность','UX','Согласованность','Enterprise','Потенциал','Готовность']))
 trace=rd('traceability.json');acids={c['id'] for c in ac}
 ck('requirement-traceability',len(trace)==12 and all(set(r['taskIds'])<=set(by) and set(r['acceptanceIds'])<=acids for r in trace))
 ck('screen-route-coverage','U16' in (O/'packages/frontend/docs/guide.md').read_text())
 # All public operations have an explicitly assigned implementing role and task group.
 rows=[]
 for method,path,op in ops(P):
  if '/assistant' in path or '/knowledge' in path:ts=['P14','P15','P16'];role='BACKEND+ML+FRONTEND'
  elif '/financial' in path:ts=['P08','P09','P11'];role='BACKEND+FRONTEND+ML'
  elif '/document' in path or '/files' in path or '/uploads' in path or 'extraction' in path:ts=['P10','P13','P16'];role='BACKEND+ML+FRONTEND'
  elif '/recommend' in path or '/feed' in path or '/content' in path or '/feedback' in path:ts=['P12','P15','P16'];role='BACKEND+ML+FRONTEND'
  elif '/information' in path:ts=['P08','P09','P15'];role='BACKEND+FRONTEND'
  elif '/session' in path or '/companies' in path or '/logout' in path:ts=['P03','P04'];role='BACKEND+FRONTEND'
  else:ts=['P05','P06','P15','P16'];role='BACKEND+FRONTEND'
  rows.append(dict(operationId=op['operationId'],method=method.upper(),path=path,owner=role,taskIds=ts,implemented=False))
 wr('operation-task-map.json',rows);ck('operation-task-coverage',len(rows)==63 and all(set(r['taskIds'])<=set(by) for r in rows))
 collection=rd('contracts/requests.postman_collection.json');ck('collection-coverage',len(collection['item'])==63)


def documents_and_evidence():
 # Resolve only actual Markdown links, not hypothetical application paths in prose.
 broken=[]
 for p in sorted(O.rglob('*.md')):
  for url in re.findall(r'\[[^\]]+\]\(([^)]+)\)',p.read_text()):
   if url.startswith(('http:','https:','#')):continue
   if not (p.parent/url.split('#')[0]).exists():broken.append(str(p.relative_to(O))+':'+url)
 ck('markdown-links',not broken,broken)
 htmlbroken=[]
 for url in re.findall(r'(?:href|src)="([^"]+)"',(O/'index.html').read_text()):
  if not url.startswith(('http:','https:','#')) and not (O/url.split('#')[0]).exists():htmlbroken.append(url)
 ck('offline-html-links',not htmlbroken,htmlbroken)
 root=ET.parse(O/'architecture.drawio').getroot();edges=root.findall('.//mxCell[@edge="1"]');vertices={x.attrib['id'] for x in root.findall('.//mxCell[@vertex="1"]')}
 ck('drawio-all-edges-bound',all(e.get('source') in vertices and e.get('target') in vertices for e in edges))
 ck('drawio-scene-count',len(root.findall('diagram'))==7)
 scenes=rd('sources/diagrams.json')
 overlaps=[]
 for scene in scenes:
  ns=scene['nodes']
  for j,a in enumerate(ns):
   for b in ns[j+1:]:
    if min(a['x']+a['w'],b['x']+b['w'])>max(a['x'],b['x']) and min(a['y']+a['h'],b['y']+b['h'])>max(a['y'],b['y']):overlaps.append((scene['id'],a['id'],b['id']))
 ck('diagram-node-no-overlap',not overlaps,overlaps)
 # Verify source fragments against archived byte-exact files, not changed current text.
 with zipfile.ZipFile(O/'evidence/originals.zip') as z:
  inv=rd('evidence/original-sha256.json');ck('archive-file-count',len(inv)==len(z.namelist()))
  bad=[x['path'] for x in inv if hashlib.sha256(z.read(x['path'])).hexdigest()!=x['sha256']];ck('archive-hashes',not bad,bad)
  for f in rd('findings.json'):
   e=f['evidence'];data=z.read(e['path']);lines=data.decode().splitlines();ck('finding-source:'+f['id'],e['fragment'] in lines[e['line']-1] and hashlib.sha256(data).hexdigest()==e['sha256'])
 ck('prior-audit-recheck',len(rd('evidence/prior-audit-recheck.json'))==30)
 files=list(O.rglob('*.pdf'));ck('nine-pdf-deliverables',len(files)==9)
 for p in files:
  try:
   reader=PdfReader(p);text='\n'.join(x.extract_text() or '' for x in reader.pages)
   ck('pdf-readable:'+str(p.relative_to(O)),len(reader.pages)>0 and len(text)>500 and '\ufffd' not in text)
  except Exception as e:ck('pdf-readable:'+str(p.relative_to(O)),False,e)
 scripts='\n'.join(p.read_text() for p in (O/'sources').glob('*.py'))
 rep=rd('evidence/reproducibility-report.json')
 ck('deterministic-build',rep['status']=='PASS' and rep.get('builderSha256')==sha(O/'sources/build.py') and all(sha(O/path)==digest for path,digest in rep.get('outputSha256',{}).items()) and len(rep.get('outputSha256',{}))==29)
 ck('self-contained','/'.join(['','Users','user']) not in scripts and ('/'+'tmp/credit-') not in scripts)
 ck('runtime-not-misrepresented',not rd('build-report.json')['applicationImplemented'] and 'Приложение не реализовано' in (O/'README.md').read_text())
 visual=O/'visual-review.json'
 if visual.exists():
  v=rd('visual-review.json');ck('visual-hashes-current',all((O/x['path']).exists() and sha(O/x['path'])==x['sha256'] for x in v.get('pdfs',[])))
 # Every finding verification label must map to real checks or named documentary acceptance.
 # Aliases are deliberately explicit; no PASS is inferred from mere presence of a label.
 aliases={'public-openapi':'public-openapi','internal-openapi':'internal-openapi','immutable-financial-reference':'financial-package-fields','rag-context-fixtures':'fixture:rag-context-valid','snapshot-digest-fixtures':'design-oracle:snapshot-digest-9','ranking-permutation-fixtures':'design-oracle:permutation-0','exposure-fixtures':'design-oracle:exposure-16','finance-standard-fixtures':'fixture:finance-standard-RSBU','submit-financial-required':'submit-financial-required','rfi-financial-required':'informationresponse-financial-required','supply-chain-gate':'model-selection','critical-path':'task-hours','deterministic-build':'deterministic-build','evidence-boundary':'runtime-not-executed'}
 names={c['check'] for c in checks};unknown=[];mapping=[]
 for f in rd('findings.json'):
  for name in f['verification']:
   resolved=aliases.get(name,name)
   if resolved not in names:unknown.append((f['id'],name,resolved))
   mapping.append(dict(findingId=f['id'],label=name,check=resolved))
 ck('finding-check-links',not unknown,unknown);wr('finding-check-map.json',mapping)


def main():
 structure();regression_fixtures();current_fixtures();semantic_oracles();graphs_and_profiles();documents_and_evidence()
 fails=[c for c in checks if not c['passed']]
 report=dict(status='PASS' if not fails else 'FAIL',scope='Static specification/contracts/design fixtures only. No application, models, Docker, performance, security, DR or bank integration executed.',applicationImplemented=False,runtimeTestsExecuted=False,counts=dict(checks=len(checks),failed=len(fails),schemaFixtures=len(fixtures),negativeSchemaFixtures=sum(not f['expectedValid'] for f in fixtures),semanticDesignOracles=len(rd('semantic-fixtures.json')['cases']),publicOperations=len(ops(P)),internalOperations=len(ops(I)),demoOperations=len(ops(D))),checks=checks)
 wr('validation-report.json',report)
 print(json.dumps({k:report[k] for k in ['status','counts']},ensure_ascii=False))
 for f in fails:print(f['check'],f['detail'])
 if fails:raise SystemExit(1)
if __name__=='__main__':main()
