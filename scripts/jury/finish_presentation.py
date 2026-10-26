#!/usr/bin/env python3
"""Package Artifact Session renders as a faithful PDF and add native Office hyperlinks.

The editable deck is authored/exported by Artifact Session. This script changes
only hyperlink relationships in its copy. PDF visuals use the reviewed 2x slide
renders, with an invisible searchable text layer and real URI annotations.
"""
import argparse
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--session-export-dir', required=True, type=Path)
parser.add_argument('--font', type=Path, default=Path('/System/Library/Fonts/Supplemental/Arial.ttf'))
args = parser.parse_args()
source = args.session_export_dir
build = ROOT/'.local/jury/presentation'
build.mkdir(parents=True,exist_ok=True)
out = ROOT/'docs/jury/presentation'
out.mkdir(parents=True,exist_ok=True)
demo = 'https://president-diameter-endearing.ngrok-free.dev'
repo = 'https://github.com/Tonitrus1/ALFA-HACK-2026'
tag = repo+'/tree/submission-2026-10-26-r2'
ns = {'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
      'p':'http://schemas.openxmlformats.org/presentationml/2006/main',
      'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
for prefix,uri in ns.items(): ET.register_namespace(prefix,uri)
rel_ns = 'http://schemas.openxmlformats.org/package/2006/relationships'
data = {}
with zipfile.ZipFile(source/'potok-draft.pptx') as archive:
    data = {n:archive.read(n) for n in archive.namelist()}
slide = ET.fromstring(data['ppt/slides/slide12.xml'])
rels_path = 'ppt/slides/_rels/slide12.xml.rels'
rels = ET.fromstring(data[rels_path])
links = [('rIdJuryDemo',demo),('rIdJuryRepo',repo),('rIdJuryTag',tag)]
for rid,url in links:
    ET.SubElement(rels,'{'+rel_ns+'}Relationship',Id=rid,Type=ns['r']+'/hyperlink',Target=url,TargetMode='External')
for shape in slide.findall('.//p:sp',ns):
    value=''.join(n.text or '' for n in shape.findall('.//a:t',ns))
    rid = 'rIdJuryDemo' if demo in value else 'rIdJuryRepo' if 'github.com/Tonitrus1/ALFA-HACK-2026' in value else 'rIdJuryTag' if value=='submission-2026-10-26-r2' else None
    if rid:
        for run in shape.findall('.//a:r',ns):
            props=run.find('a:rPr',ns)
            if props is None: props=ET.Element('{'+ns['a']+'}rPr');run.insert(0,props)
            ET.SubElement(props,'{'+ns['a']+'}hlinkClick',{'{'+ns['r']+'}id':rid})
for picture,rid in zip(slide.findall('.//p:pic',ns),['rIdJuryDemo','rIdJuryTag']):
    props=picture.find('p:nvPicPr/p:cNvPr',ns)
    if props is not None:ET.SubElement(props,'{'+ns['a']+'}hlinkClick',{'{'+ns['r']+'}id':rid})
data['ppt/slides/slide12.xml']=ET.tostring(slide,encoding='utf-8',xml_declaration=True)
data[rels_path]=ET.tostring(rels,encoding='utf-8',xml_declaration=True)
with zipfile.ZipFile(build/'linked-candidate.pptx','w',compression=zipfile.ZIP_DEFLATED) as archive:
    for name,content in data.items():archive.writestr(name,content)

pdfmetrics.registerFont(TTFont('JurySearch',str(args.font)))
pdf=canvas.Canvas(str(out/'potok-gambit-yvaga.pdf'),pagesize=(960,540),pageCompression=1)
pdf.setTitle('Поток — умный кредитный кабинет предпринимателя')
pdf.setAuthor('Gambit_Yvaga')
pdf.setSubject('Альфа Хак 2026 · submission-2026-10-26-r2')
notes=['# Заметки докладчика · Gambit_Yvaga','','Презентация рассчитана на 5–7 минут. PDF повторяет проверенную вёрстку; текст и схемы редактируются в PPTX.','']
for number in range(1,13):
    pdf.drawImage(str(source/f'slide-{number}.png'),0,0,width=960,height=540)
    doc=ET.fromstring(data[f'ppt/slides/slide{number}.xml'])
    # Text is invisible and preserves exact Unicode strings for copying passwords/search.
    for shape in doc.findall('.//p:sp',ns):
        off=shape.find('p:spPr/a:xfrm/a:off',ns)
        if off is None:continue
        x=int(off.get('x','0'))/12700
        y=540-int(off.get('y','0'))/12700
        props=shape.find('.//a:rPr',ns)
        size=float(props.get('sz','1800'))/100 if props is not None else 18
        cursor=pdf.beginText();cursor.setTextRenderMode(3);cursor.setFont('JurySearch',size);cursor.setLeading(size*1.15);cursor.setTextOrigin(x,y-size)
        for paragraph in shape.findall('p:txBody/a:p',ns):
            value=''.join(n.text or '' for n in paragraph.findall('.//a:t',ns))
            cursor.textLine(value)
        pdf.drawText(cursor)
    # Native tables also receive copyable/searchable Unicode text.
    for table in doc.findall('.//a:tbl',ns):
        cursor=pdf.beginText();cursor.setTextRenderMode(3);cursor.setFont('JurySearch',11);cursor.setLeading(15);cursor.setTextOrigin(42,440)
        for row in table.findall('a:tr',ns):
            cursor.textLine(' / '.join(''.join(n.text or '' for n in cell.findall('.//a:t',ns)) for cell in row.findall('a:tc',ns)))
        pdf.drawText(cursor)
    if number==12:
        for url,(x,y,w,h) in [(demo,(64,164,164,164)),(demo,(268,234,922,70)),(tag,(64,360,164,164)),(repo,(268,425,922,44)),(tag,(268,478,922,38))]:
            pdf.linkURL(url,(x*.75,540-(y+h)*.75,(x+w)*.75,540-y*.75),relative=0,thickness=0)
    pdf.showPage()
    note_doc=ET.fromstring(data[f'ppt/notesSlides/notesSlide{number}.xml'])
    values=[n.text or '' for n in note_doc.findall('.//a:t',ns)]
    title=next((n.text for n in doc.findall('.//a:t',ns) if n.text),'Поток')
    notes.extend([f'## {number:02}. {title}','','\n'.join(values),''])
pdf.save()
(out/'speaker-notes.md').write_text('\n'.join(notes))
print('Prepared linked PPTX candidate and 12-page PDF:',(out/'potok-gambit-yvaga.pdf').stat().st_size,'bytes')
