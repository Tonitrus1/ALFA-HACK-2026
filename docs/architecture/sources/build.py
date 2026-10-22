"""Build the self-contained architecture deliverables. Does not build an application."""
from pathlib import Path
import os,sys,json,hashlib,html,re,shutil,zipfile,math,xml.etree.ElementTree as ET
extra=os.environ.get('CREDIT_RENDER_DEPS')
if extra:sys.path.insert(0,extra)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle,KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor,white
from reportlab.lib.pagesizes import A4,A3,landscape
from pypdf import PdfReader
from markdown_it import MarkdownIt
O=Path(__file__).resolve().parents[1]
def rd(p):return json.loads((O/p).read_text())
def wr(p,v):(O/p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for n,f in [('DV','DejaVuSans.ttf'),('DVB','DejaVuSans-Bold.ttf')]:pdfmetrics.registerFont(TTFont(n,str(O/'sources/fonts'/f)))
pdfmetrics.registerFontFamily('DV',normal='DV',bold='DVB',italic='DV',boldItalic='DVB')
INK='#182b3b';MUTED='#5a6b7b';ACCENT='#0d7b78';LIGHT='#edf6f5'
HTTP={'get','post','put','patch','delete'}

def tasks_summary():
 ts=rd('tasks.json');by={t['id']:t for t in ts};done={}
 def end(id):
  if id not in done:done[id]=by[id]['personHours']+max([end(x) for x in by[id]['dependsOn']] or [0])
  return done[id]
 for t in ts:end(t['id'])
 id='P23';path=[]
 while True:
  path.append(id);deps=by[id]['dependsOn']
  if not deps:break
  id=max(deps,key=lambda x:done[x])
 path.reverse();hours=sum(t['personHours'] for t in ts if t['profile']=='mvp')
 per={r:sum(t['personHours'] for t in ts if t['ownerRole']==r and t['profile']=='mvp') for r in sorted({t['ownerRole'] for t in ts})}
 result=dict(optionalIntegrationPersonHours=sum(t['personHours'] for t in ts if t['profile']=='optional-integrations'),personHours=hours,with25PercentReserve=hours*1.25,byRole=per,dependencyCriticalPath=path,dependencyLowerBoundHours=done['P23'],note='Unlimited-role DAG lower bound; does not account for serial tasks by one ML specialist, sleeping or shared role contention.',singleMlSpecialistModelWorkHours=per['ML'])
 wr('evidence/schedule-analysis.json',result);return result

def audit():
 f=rd('findings.json');sc=tasks_summary()
 block=''
 for x in f:
  ev=x['evidence']
  block+=f"### {x['id']} [{x['severity']}] {x['title']}\n\nИсточник: `{ev['path']}:{ev['line']}`; фрагмент «{ev['fragment']}». SHA-256 и исходник - в evidence/. Класс: {x['category']}.\n\nСценарий/последствия: {x['failureScenario']}\n\nИсправление: {x['correction']}\n\nПроверка: {', '.join(x['verification'])}. Статус: исправлено в спецификации; runtime не проверен.\n\n"
 values={'FINDING_COUNT':str(len(f)),'P1':str(sum(x['severity']=='P1' for x in f)),'P2':str(sum(x['severity']=='P2' for x in f)),'ARCHIVE_COUNT':str(len(rd('evidence/original-sha256.json'))),'HOURS':str(sc['personHours']),'RESERVE':f"{sc['with25PercentReserve']:.1f}",'CRITICAL_PATH':' → '.join(sc['dependencyCriticalPath']),'CRITICAL_HOURS':str(sc['dependencyLowerBoundHours']),'ML_HOURS':str(sc['singleMlSpecialistModelWorkHours']),'FINDINGS':block}
 text=(O/'sources/audit-template.md').read_text()
 for k,v in values.items():text=text.replace('{{'+k+'}}',v)
 (O/'docs/architecture-audit.md').write_text(text)
 taskblock=''
 for row in rd('tasks.json'):
  taskblock+=f"### {row['id']}. {row['title']}\n\nВладелец: {row['ownerRole']}; оценка: {row['personHours']} ч; зависимости: {', '.join(row['dependsOn']) or 'нет'}; профиль: {row['profile']}.\n\nРезультат: {row['deliverable']}.\n\nГотово, когда: {row['doneWhen']}.\n\n"
 taskblock+=f"Базовая оценка: **{sc['personHours']} человеко-часа**; с резервом 25% - **{sc['with25PercentReserve']:.1f} человеко-часа**. P27 - ещё 8 часов отдельной необязательной интеграции; не включена в обязательную сумму. P24 - отдельный неоценённый промышленный этап.\n"
 text=(O/'sources/development-plan.template.md').read_text().replace('{{TASKS}}',taskblock)
 (O/'docs/development-plan.md').write_text(text)

def inline(text):
 text=html.escape(text)
 text=re.sub(r'`([^`]+)`',lambda m:'<font color="#245a70">'+m.group(1)+'</font>',text)
 text=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',text)
 text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',lambda m:'<link href="'+m.group(2)+'" color="#0d7b78">'+m.group(1)+'</link>',text)
 return text
ST={
 'p':ParagraphStyle('body',fontName='DV',fontSize=9.3,leading=13.5,textColor=HexColor(INK),spaceAfter=6.8,splitLongWords=True),
 'h2':ParagraphStyle('h2',fontName='DVB',fontSize=15.5,leading=20,textColor=HexColor(INK),spaceBefore=14,spaceAfter=8,keepWithNext=True),
 'h3':ParagraphStyle('h3',fontName='DVB',fontSize=11.3,leading=15,textColor=HexColor(ACCENT),spaceBefore=12,spaceAfter=7,keepWithNext=True),
 'cell':ParagraphStyle('cell',fontName='DV',fontSize=8,leading=11.5,textColor=HexColor(INK),spaceAfter=2),
 'th':ParagraphStyle('th',fontName='DVB',fontSize=8,leading=11,textColor=white),
 'bullet':ParagraphStyle('bullet',fontName='DV',fontSize=9.3,leading=13.5,textColor=HexColor(INK),leftIndent=12,firstLineIndent=-9,spaceAfter=6.8),
}

def mdflow(text):
 lines=text.splitlines();out=[];i=0
 while i<len(lines):
  line=lines[i].strip()
  if not line:i+=1;continue
  if line.startswith('# '):i+=1;continue
  if line.startswith('### '):out.append(Paragraph(inline(line[4:]),ST['h3']));i+=1;continue
  if line.startswith('## '):out.append(Paragraph(inline(line[3:]),ST['h2']));i+=1;continue
  if line.startswith('|'):
   rows=[]
   while i<len(lines) and lines[i].strip().startswith('|'):
    row=[x.strip() for x in lines[i].strip().strip('|').split('|')]
    if not all(re.fullmatch(r':?-+:?',x.replace(' ','')) for x in row):rows.append(row)
    i+=1
   if not rows:continue
   cols=max(map(len,rows));width=A4[0]-100
   proportions={2:[.30,.70],3:[.22,.35,.43],4:[.14,.23,.22,.41]}.get(cols,[1/cols]*cols)
   cells=[[Paragraph(inline(x),ST['th'] if ri==0 else ST['cell']) for x in row+['']*(cols-len(row))] for ri,row in enumerate(rows)]
   tab=Table(cells,colWidths=[width*p for p in proportions],repeatRows=1,hAlign='LEFT')
   tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#17394b')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('ROWBACKGROUNDS',(0,1),(-1,-1),[HexColor('#f1f6f7'),white]),('LINEBELOW',(0,0),(-1,0),.7,HexColor(ACCENT))]))
   out.extend([tab,Spacer(1,9)]);continue
  if line.startswith('- '):out.append(Paragraph('• '+inline(line[2:]),ST['bullet']));i+=1;continue
  para=[line];i+=1
  while i<len(lines) and lines[i].strip() and not lines[i].lstrip().startswith(('#','|','- ')):
   para.append(lines[i].strip());i+=1
  out.append(Paragraph(inline(' '.join(para)),ST['p']))
 grouped=[];j=0
 while j<len(out):
  flow=out[j]
  if isinstance(flow,Paragraph) and flow.style.name=='h3' and re.match(r'[HP][0-9]{2}[ .]',flow.getPlainText()):
   group=[flow];j+=1
   while j<len(out) and not(isinstance(out[j],Paragraph) and out[j].style.name in ['h2','h3']):group.append(out[j]);j+=1
   grouped.append(KeepTogether(group))
  else:grouped.append(flow);j+=1
 final=[];j=0
 while j<len(grouped):
  item=grouped[j]
  if isinstance(item,Paragraph) and item.style.name=='h2' and j+1<len(grouped) and isinstance(grouped[j+1],KeepTogether):
   final.append(KeepTogether([item]+grouped[j+1]._content));j+=2
  else:final.append(item);j+=1
 return final

def pdf(md_path,pdf_path,label,eyebrow,subtitle):
 text=(O/md_path).read_text();title=next(l[2:] for l in text.splitlines() if l.startswith('# '))
 doc=SimpleDocTemplate(str(O/pdf_path),pagesize=A4,rightMargin=50,leftMargin=50,topMargin=48,bottomMargin=47,title=title,author='Credit Workspace / Architecture Review',invariant=1,pageCompression=1)
 def decor(c,d):
  c.setFillColor(HexColor(ACCENT));c.rect(0,A4[1]-10,A4[0],10,fill=1,stroke=0)
  c.setFont('DV',7.2);c.setFillColor(HexColor(MUTED));c.drawString(50,26,label+'  |  HACKATHON-1.5');c.drawRightString(A4[0]-50,26,str(d.page));c.setStrokeColor(HexColor('#d8e4e7'));c.line(50,39,A4[0]-50,39)
 cover=[Spacer(1,40),Paragraph(eyebrow.upper(),ParagraphStyle('eyebrow',fontName='DVB',fontSize=10,leading=16,textColor=HexColor(ACCENT))),Spacer(1,20),Paragraph(html.escape(title),ParagraphStyle('title',fontName='DVB',fontSize=28,leading=36,textColor=HexColor(INK))),Spacer(1,22),Paragraph(subtitle,ParagraphStyle('subtitle',fontName='DV',fontSize=12,leading=19,textColor=HexColor(MUTED))),Spacer(1,35)]
 banner=Table([[Paragraph('20 октября 2026<br/><b>Согласованная спецификация</b>',ST['cell']),Paragraph('Команда 3-5 человек<br/><b>Окно 48-72 часа</b>',ST['cell'])]],colWidths=[(A4[0]-100)/2]*2)
 banner.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),HexColor(LIGHT)),('BOX',(0,0),(-1,-1),.6,HexColor('#cde2de')),('TOPPADDING',(0,0),(-1,-1),14),('BOTTOMPADDING',(0,0),(-1,-1),14),('LEFTPADDING',(0,0),(-1,-1),14)]))
 cover +=[banner,Spacer(1,26),Paragraph('Приложение не реализовано. Статические проверки документации и контрактов отделены от будущих испытаний runtime.',ST['p']),PageBreak()]
 if md_path.startswith('packages/'):
  text=text.split('## Общие нормативные материалы')[0]
  if md_path=='packages/general/docs/guide.md':text=text.split('\n[Полная спецификация адаптеров]')[0]
  cover.insert(-1,Paragraph('Связанные источники, контракты и приёмка доступны в Markdown-руководстве и общем index.html комплекта.',ST['p']))
 doc.build(cover+mdflow(text),onFirstPage=decor,onLaterPages=decor)

PALETTE={'core':('#edf3fb','#527ba5'),'client':('#fff0ed','#d27669'),'bank':('#eef1f3','#738898'),'ml':('#f0edfb','#8d79b1'),'data':('#eaf5ef','#6e9e86'),'security':('#fff4df','#b99b5d')}
def wrap(text,width,size,bold=False):
 name='DVB' if bold else 'DV';lines=[]
 for para in text.split('\n'):
  buf=''
  for w in para.split():
   if pdfmetrics.stringWidth((buf+' '+w).strip(),name,size)>width and buf:lines.append(buf);buf=w
   else:buf=(buf+' '+w).strip()
  lines.append(buf)
 return lines

def points(a,b):
 ac=(a['x']+a['w']/2,a['y']+a['h']/2);bc=(b['x']+b['w']/2,b['y']+b['h']/2)
 if abs(ac[1]-bc[1])<30:
  return [(a['x']+a['w'],ac[1]),(b['x'],bc[1])] if ac[0]<bc[0] else [(a['x'],ac[1]),(b['x']+b['w'],bc[1])]
 # vertically aligned or diagonal via midpoint; saved routing is shared SVG/PDF/drawio.
 if bc[1]>ac[1]:start=(ac[0],a['y']+a['h']);end=(bc[0],b['y'])
 else:start=(ac[0],a['y']);end=(bc[0],b['y']+b['h'])
 mid=(start[1]+end[1])/2
 return [start,(start[0],mid),(end[0],mid),end]

def diagrams():
 scenes=rd('sources/diagrams.json');mx=ET.Element('mxfile',host='app.diagrams.net',modified='2026-10-20T00:00:00.000Z',agent='Credit Workspace source builder',version='24.7.17')
 outpdf=canvas.Canvas(str(O/'architecture-atlas.pdf'),pagesize=landscape(A3),invariant=1)
 manifest=[]
 for num,s in enumerate(scenes,1):
  svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1380" height="900" viewBox="0 0 1380 900"><rect width="1380" height="900" fill="#ffffff"/><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 Z" fill="#6d8291"/></marker></defs>']
  svg +=[f'<text x="40" y="55" font-family="DejaVu Sans,sans-serif" font-size="31" font-weight="bold" fill="{INK}">{html.escape(s["title"])}</text>',f'<text x="40" y="92" font-family="DejaVu Sans,sans-serif" font-size="17" fill="{MUTED}">{html.escape(s["subtitle"])}</text>']
  page=ET.SubElement(mx,'diagram',id=s['id'],name=s['title']);model=ET.SubElement(page,'mxGraphModel',dx='1380',dy='900',page='1',pageWidth='1380',pageHeight='900');root=ET.SubElement(model,'root');ET.SubElement(root,'mxCell',id='0');ET.SubElement(root,'mxCell',id='1',parent='0')
  ET.SubElement(ET.SubElement(root,'mxCell',id='title',value=s['title'],vertex='1',parent='1',style='text;html=0;align=left;fontSize=28;fontStyle=1;'), 'mxGeometry',x='40',y='15',width='1300',height='50',**{'as':'geometry'})
  nodes={n['id']:n for n in s['nodes']}
  outpdf.saveState();pw,ph=landscape(A3);scale=min(pw/1380,ph/900);outpdf.translate((pw-1380*scale)/2,(ph-900*scale)/2);outpdf.scale(scale,scale)
  def txt(x,y,t,size=17,bold=False,color=INK):outpdf.setFont('DVB' if bold else 'DV',size);outpdf.setFillColor(HexColor(color));outpdf.drawString(x,900-y,t)
  txt(40,55,s['title'],31,True);txt(40,92,s['subtitle'],17,False,MUTED)
  for j,ed in enumerate(s['edges']):
   pts=ed.get('points') or points(nodes[ed['source']],nodes[ed['target']]);dash=' stroke-dasharray="8 6"' if ed['mode']=='async' else ''
   svg.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in pts)+'" fill="none" stroke="#6d8291" stroke-width="2" marker-end="url(#arrow)"'+dash+'/>')
   outpdf.setStrokeColor(HexColor('#6d8291'));outpdf.setLineWidth(1.7);outpdf.setDash([7,5] if ed['mode']=='async' else [])
   pa=outpdf.beginPath();pa.moveTo(pts[0][0],900-pts[0][1])
   for x,y in pts[1:]:pa.lineTo(x,900-y)
   outpdf.drawPath(pa);outpdf.setDash([])
   x,y=pts[-1];u,v=pts[-2];angle=math.atan2(y-v,x-u);L=9
   arr=[(x,y),(x-L*math.cos(angle-.4),y-L*math.sin(angle-.4)),(x-L*math.cos(angle+.4),y-L*math.sin(angle+.4))]
   pa=outpdf.beginPath();pa.moveTo(arr[0][0],900-arr[0][1]);pa.lineTo(arr[1][0],900-arr[1][1]);pa.lineTo(arr[2][0],900-arr[2][1]);pa.close();outpdf.setFillColor(HexColor('#6d8291'));outpdf.drawPath(pa,fill=1,stroke=0)
   ce=ET.SubElement(root,'mxCell',id='edge-'+str(j),value=ed['label'],edge='1',parent='1',source=ed['source'],target=ed['target'],style='edgeStyle=orthogonalEdgeStyle;rounded=0;html=0;endArrow=block;fontSize=14;'+('dashed=1;' if ed['mode']=='async' else ''))
   geo=ET.SubElement(ce,'mxGeometry',relative='1',**{'as':'geometry'})
   if ed.get('points'):
    arrxml=ET.SubElement(geo,'Array',**{'as':'points'})
    for xx,yy in ed['points'][1:-1]:ET.SubElement(arrxml,'mxPoint',x=str(xx),y=str(yy))
   if ed['label']:
    # For simple horizontal links use the gap midpoint; diagonal labels sit near the middle elbow.
    seg=pts[len(pts)//2-1:len(pts)//2+1];lx=(seg[0][0]+seg[-1][0])/2;ly=(seg[0][1]+seg[-1][1])/2-8
    svg.append(f'<text x="{lx}" y="{ly}" text-anchor="middle" font-family="DejaVu Sans,sans-serif" font-size="14" fill="{MUTED}">{html.escape(ed["label"])}</text>')
    w=pdfmetrics.stringWidth(ed['label'],'DV',14);txt(lx-w/2,ly,ed['label'],14,False,MUTED)
  for n in s['nodes']:
   fill,stroke=PALETTE[n['kind']];x,y,w,h=n['x'],n['y'],n['w'],n['h']
   svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="1.8"/>')
   outpdf.setFillColor(HexColor(fill));outpdf.setStrokeColor(HexColor(stroke));outpdf.roundRect(x,900-y-h,w,h,12,fill=1,stroke=1)
   cursor=y+29
   for line in wrap(n['title'],w-28,18,True):
    svg.append(f'<text x="{x+14}" y="{cursor}" font-family="DejaVu Sans,sans-serif" font-size="18" font-weight="bold" fill="{INK}">{html.escape(line)}</text>');txt(x+14,cursor,line,18,True);cursor+=24
   cursor+=7
   for line in wrap(n['text'],w-28,16):
    svg.append(f'<text x="{x+14}" y="{cursor}" font-family="DejaVu Sans,sans-serif" font-size="16" fill="{MUTED}">{html.escape(line)}</text>');txt(x+14,cursor,line,16,False,MUTED);cursor+=22
   assert cursor<=y+h+10,(s['id'],n['id'],'text-overflow')
   value=n['title']+'\n\n'+n['text']
   ce=ET.SubElement(root,'mxCell',id=n['id'],value=value,vertex='1',parent='1',style=f'rounded=1;html=0;whiteSpace=wrap;fillColor={fill};strokeColor={stroke};fontColor={INK};fontSize=18;align=left;verticalAlign=middle;spacing=14;')
   ET.SubElement(ce,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),**{'as':'geometry'})
  for k,note in enumerate(s['notes']):
   yy=820+k*28
   svg.append(f'<text x="40" y="{yy}" font-family="DejaVu Sans,sans-serif" font-size="15" fill="{MUTED}">{html.escape(note)}</text>');txt(40,yy,note,15,False,MUTED)
  svg.append(f'<text x="40" y="887" font-family="DejaVu Sans,sans-serif" font-size="12" fill="{MUTED}">HACKATHON-1.5 · 20.10.2026 · {num:02d}/{len(scenes):02d} · проектная схема, runtime не проверен</text></svg>')
  txt(40,887,f'HACKATHON-1.5 | 20.10.2026 | {num:02d}/{len(scenes):02d} | Проектная схема',12,False,MUTED)
  (O/'diagrams'/f'{s["id"]}.svg').write_text('\n'.join(svg));outpdf.restoreState();outpdf.showPage()
  manifest.append(dict(id=s['id'],title=s['title'],svg=f'diagrams/{s["id"]}.svg',nodes=len(s['nodes']),edges=len(s['edges'])))
 outpdf.save();ET.ElementTree(mx).write(O/'architecture.drawio',encoding='utf-8',xml_declaration=True);wr('diagram-manifest.json',manifest)


def request_collection():
 spec=rd('contracts/public.openapi.json');collection={'info':{'name':'Credit Workspace HACKATHON-1.5 - contract request templates','schema':'https://schema.getpostman.com/json/collection/v2.1.0/collection.json','description':'API templates generated from the canonical public contract. This is not an executed E2E collection. Set runtime IDs/session/CSRF and provide body from the canonical schema. No application is included.'},'variable':[{'key':'baseUrl','value':'http://localhost:8080'},{'key':'companyContext','value':'1'},{'key':'csrfToken','value':''}],'item':[]}
 for path,item in spec['paths'].items():
  for m,op in item.items():
   if m not in HTTP:continue
   url=re.sub(r'\{([^}]+)\}',r'{{\1}}',path);headers=[{'key':'Accept','value':'application/json'},{'key':'X-Company-Context','value':'{{companyContext}}'}]
   if m!='get':headers.append({'key':'X-CSRF-Token','value':'{{csrfToken}}'})
   for param in op.get('parameters',[]):
    if param.get('in')=='header' and param.get('required') and param['name'] not in {h['key'] for h in headers}:
     key={'If-Match':'etag','Idempotency-Key':'idempotencyKey'}.get(param['name'],param['name']);headers.append({'key':param['name'],'value':'{{'+key+'}}'})
   req={'method':m.upper(),'url':'{{baseUrl}}'+url,'header':headers,'description':op.get('summary','')+'\nCanonical operationId: '+op['operationId']+'\nRequest schema: '+str(op.get('requestBody',{}).get('content',{}).get('application/json',{}).get('schema',{}))}
   collection['item'].append({'name':m.upper()+' '+path,'request':req})
 wr('contracts/requests.postman_collection.json',collection)

def human_indexes():
 for name,title in [('general','Общая архитектура'),('backend','Backend'),('frontend','Frontend'),('ml','ML')]:
  pack=O/'packages'/name;(pack/'api').mkdir(exist_ok=True)
  for src,dst in [('public.openapi.json','openapi.json'),('internal.openapi.json','internal.openapi.json'),('demo.openapi.json','demo.openapi.json')]:shutil.copyfile(O/'contracts'/src,pack/'api'/dst)
  (pack/'README.md').write_text(f'# {title}: HACKATHON-1.5\n\nНормативная редакция в новом объединённом комплекте. Приложение не реализовано.\n\n- [Руководство](docs/guide.md)\n- [PDF]({name}-guide.pdf)\n- [Общий API](../../contracts/public.openapi.json) - локальные api-копии генерируются, не редактируются.\n- [Общий атлас](../../architecture-atlas.pdf)\n- [План разработки](../../docs/development-plan.md)\n- [Git и защита](../../docs/git-and-jury-guide.md)\n- [Полный стек и адаптеры](../../docs/technology-adapters.md)\n\nСборка только из корня комплекта: python sources/build.py. Все изменения вносятся в docs/guide.md и canonical contracts/, затем выполняется общая сборка.\n')
 md=MarkdownIt('commonmark').enable('table')
 docs=[('Адаптеры и полный стек','docs/technology-adapters.md','technology-adapters.pdf'),('Аудит','docs/architecture-audit.md','architecture-audit.pdf'),('Git и защита','docs/git-and-jury-guide.md','git-and-jury-guide.pdf'),('План разработки','docs/development-plan.md','development-plan.pdf')]+[(n.title(),f'packages/{n}/docs/guide.md',f'packages/{n}/{n}-guide.pdf') for n in ['general','backend','frontend','ml']]
 nav=''.join(f'<a href="{p}">{html.escape(t)}</a>' for t,_,p in docs)
 def render_html(rel):
  rendered=md.render((O/rel).read_text())
  def link(m):
   target=m.group(1)
   if target.startswith(('http:','https:','#')):return m.group(0)
   return 'href="'+os.path.normpath(str(Path(rel).parent/target))+'"'
  return re.sub(r'href="([^"]+)"',link,rendered)
 body=''.join(f'<section id="{k}"><span class="tag">HACKATHON-1.5</span>{render_html(p)}<p><a href="{pdfp}">Открыть PDF</a></p></section>' for k,(_,p,pdfp) in enumerate(docs))
 imgs=''.join(f'<figure><img src="{s["svg"]}" alt="{html.escape(s["title"])}"/><figcaption>{html.escape(s["title"])}</figcaption></figure>' for s in rd('diagram-manifest.json'))
 css='body{font:16px/1.65 system-ui,sans-serif;color:#182b3b;background:#f1f5f5;margin:0}header{background:#17394b;color:white;padding:40px max(5vw,24px)}main{max-width:1080px;margin:auto;padding:28px}nav{display:flex;gap:14px;flex-wrap:wrap}a{color:#0d7b78}header a{color:#b0e4dd}section,figure{background:white;padding:32px;margin:24px 0;border-radius:14px}section h1{font-size:28px}h2{margin-top:34px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #dce6e8;padding:10px;text-align:left;vertical-align:top}th{background:#edf6f5}img{width:100%;height:auto}.tag{color:#0d7b78;font-size:12px;font-weight:700}code{overflow-wrap:anywhere}figcaption{color:#5a6b7b}p{overflow-wrap:anywhere}'
 (O/'index.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Кредитный кабинет - аудит и спецификация</title><style>'+css+'</style><header><h1>Кредитный кабинет</h1><p>Аудит · согласованная архитектура · разработка · защита</p><nav>'+nav+'<a href="architecture-atlas.pdf">Атлас схем</a></nav></header><main><p>Самодостаточная спецификация. Приложение не реализовано; статические проверки отдельно от runtime.</p>'+imgs+body+'</main></html>')
 links='\n'.join(f'- [{title}]({pdfpath}) - [Markdown]({mdpath}).' for title,mdpath,pdfpath in docs)
 (O/'README.md').write_text('''# Кредитный кабинет: согласованный комплект HACKATHON-1.5

20 октября 2026 года. Начните с [офлайн-обзора](index.html), затем с аудита и руководства по Git/защите. Приложение не реализовано. Это спецификация. Публикация/приглашение жюри не выполнялись.

'''+links+'''
- [Атлас схем](architecture-atlas.pdf), [редактируемый draw.io](architecture.drawio), [SVG](diagrams/).
- [Контрактные решения](docs/contract-decisions.md), [модель данных](docs/data-model.md), [приёмка](docs/acceptance.md).
- [Проверенные источники](docs/sources.md), [допущения и gates](docs/assumptions-and-gates.md).
- findings.json / tasks.json / acceptance-cases.json - машинные реестры.
- contracts/ - единственные редактируемые контракты; копии в пакетах генерируются.
- evidence/originals.zip - исходные файлы и генераторы, original-sha256.json - полная инвентаризация. Старые пакеты вне этой папки исторические.
- validation-report.json - результаты статических проверок; visual-review.json - отдельный визуальный протокол, привязанный к hashes PDF. Отсутствие/устаревание visual-review означает незавершённый просмотр.
- templates/ - шаблоны будущего репозитория приложения; не готовые настройки CI/доступа и не рабочий Docker-проект.

## Повторная сборка

Python3.12+. Создать отдельную среду и установить sources/requirements-render.txt. Шрифты и лицензия вложены; старые пакеты/приватные runtime-пути не нужны. Выполнить python sources/build.py, затем python sources/validate.py. Builder сохраняет канонические Markdown/контракты; аудит и реестр задач генерируются из sources/*template.md и JSON-реестров. Он и пересобирает только представления, копии и отчёты. Если зависимости установлены вне среды, допускается CREDIT_RENDER_DEPS с явным путём.

Изменять Markdown в docs/ и packages/*/docs/; для генерируемых audit/development-plan - sources/*template.md. Изменять JSON в contracts/, реестры tasks/findings/acceptance и геометрию sources/diagrams.json. Draw.io - редактируемый экспорт; при ручном редактировании экспортировать смысловые изменения обратно в источник геометрии до пересборки. Старые генераторы не управляют новым комплектом.

После изменения PDF нужен новый визуальный просмотр; старые hashes не подтверждают новую редакцию. Архив финальной поставки и SHA256SUMS создаются sources/package.py только после успешного validate и актуального visual review. Приложение, Docker-сборка, модели/веса и их метрики этим builder не создаются.
''')

def main():
 audit();diagrams();request_collection();human_indexes()
 pdf('docs/technology-adapters.md','technology-adapters.pdf','Полный стек и адаптеры','Qdrant · Redis · Feast','Порты, локальные реализации, настоящие сервисы и доказательства для жюри.')
 pdf('docs/architecture-audit.md','architecture-audit.pdf','Архитектурный аудит','Независимая оценка','Выводы, доказательства, исправления и границы готовности для банковского MVP.')
 pdf('docs/git-and-jury-guide.md','git-and-jury-guide.pdf','Git и защита','Регламент команды','Параллельная разработка, Git, интеграционные проверки и самостоятельная оценка жюри.')
 pdf('docs/development-plan.md','development-plan.pdf','План разработки','Роли и зависимости','Оценка объёма, граф работ, контрольные точки и критерии завершения.')
 for name in ['general','backend','frontend','ml']:
  pdf(f'packages/{name}/docs/guide.md',f'packages/{name}/{name}-guide.pdf',name.upper()+' / руководство','Согласованная архитектура','Единый контракт, проверяемые границы и конкретные правила реализации.')
 wr('build-report.json',{'status':'BUILT_STATIC_ARTIFACTS','pdfs':[{'path':str(p.relative_to(O)),'pages':len(PdfReader(p).pages),'sha256':sha(p)} for p in sorted(O.rglob('*.pdf'))],'requiresVisualReview':True,'applicationImplemented':False})
 print('Built',len(list(O.rglob('*.pdf'))),'PDFs, seven scenes, exact API copies and offline index.')
if __name__=='__main__':main()
