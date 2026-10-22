#!/usr/bin/env python3
"""Build current architecture PDF/SVG and integration-specific checksums; keep historical PDFs intact."""
import hashlib
import html
import importlib.util
import json
from pathlib import Path
import re
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[2]
ARCH=ROOT/'docs/architecture'


def main():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Flowable
    from reportlab.lib.styles import ParagraphStyle
    from pypdf import PdfReader
    spec=importlib.util.spec_from_file_location('architecture_render',ARCH/'sources/build.py')
    renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
    renderer.ST['h2'].keepWithNext=False
    renderer.ST['h3'].keepWithNext=False
    nodes=[('UI / API client',20,70,140,64,'#edf3fb'),('HTTP gateway',195,70,140,64,'#fff4df'),('Java backend',370,70,150,64,'#edf3fb'),
           ('ML bridge',560,70,150,64,'#f0edfb'),('Risk / CatBoost',750,25,180,64,'#f0edfb'),
           ('Feed / E5 CPU',750,130,180,64,'#f0edfb'),('Backend PostgreSQL',240,260,200,64,'#eaf5ef'),
           ('ML PostgreSQL',500,260,200,64,'#eaf5ef'),('ClamAV',240,390,200,64,'#fff4df')]
    edges=[(160,102,195,102),(335,102,370,102),(520,102,560,102),(710,90,750,57),(710,115,750,162),
           (445,134,340,260),(635,134,600,260),(840,89,700,275),(340,324,340,390)]
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="980" height="510" viewBox="0 0 980 510">',
         '<rect width="980" height="510" fill="white"/>',
         '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#527183"/></marker></defs>']
    for x1,y1,x2,y2 in edges:svg.append(f'<path d="M{x1} {y1} L{x2} {y2}" stroke="#527183" stroke-width="2" marker-end="url(#arrow)"/>')
    for label,x,y,w,h,color in nodes:
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{color}" stroke="#758999"/>')
        svg.append(f'<text x="{x+w/2}" y="{y+h/2+5}" text-anchor="middle" font-family="sans-serif" font-size="16" fill="#182b3b">{escape(label)}</text>')
    svg.append('<text x="30" y="490" font-family="sans-serif" font-size="14">Runtime: internal network; only HTTP gateway is published. Two databases, separate owners.</text></svg>')
    diagram=ARCH/'diagrams/integrated-mvp.svg';diagram.write_text('\n'.join(svg)+'\n')
    class Diagram(Flowable):
        def __init__(self):super().__init__();self.width=495;self.height=258
        def draw(self):
            c=self.canv;c.saveState();c.scale(.50,.50);c.translate(0,510);c.scale(1,-1)
            c.setStrokeColor(colors.HexColor('#527183'));c.setLineWidth(2)
            for x1,y1,x2,y2 in edges:c.line(x1,y1,x2,y2)
            for label,x,y,w,h,color in nodes:
                c.setFillColor(colors.HexColor(color));c.roundRect(x,y,w,h,8,fill=1,stroke=1)
                c.saveState();c.translate(x+w/2,y+h/2);c.scale(1,-1);c.setFillColor(colors.HexColor('#182b3b'));c.setFont('DVB',14);c.drawCentredString(0,-5,label);c.restoreState()
            c.restoreState()
    output=ARCH/'integration-guide.pdf'
    doc=SimpleDocTemplate(str(output),pagesize=A4,rightMargin=50,leftMargin=50,topMargin=48,bottomMargin=48,
                         title='Backend + ML: интеграционный MVP',author='Project team',invariant=1)
    title=ParagraphStyle('integration-title',fontName='DVB',fontSize=27,leading=35,textColor=colors.HexColor('#182b3b'))
    story=[Spacer(1,30),Paragraph('Backend + ML<br/>Интеграционная архитектура',title),Spacer(1,20),
           Paragraph('22 октября 2026 · Runtime и границы поставки',renderer.ST['p']),Spacer(1,12),
           Paragraph('Приоритет доработок ML. Java backend сохраняет бизнес-решения и пользовательское состояние. Проверки, ограничения и источники отделены от исторической спецификации.',renderer.ST['p']),Spacer(1,16),Diagram(),PageBreak()]
    for filename in ('integration-mvp.md','integration-audit.md'):
        if filename == 'integration-audit.md':
            story.extend([Paragraph('Аудит расхождений', title), Spacer(1, 14)])
        text=(ROOT/'docs'/filename).read_text()
        text=re.sub(r'```mermaid.*?```','Схема компонентов приведена на титульной странице и в отдельном SVG.',text,flags=re.S)
        text=re.sub(r'```(?:sh)?\n(.*?)```', lambda m: '\n'.join('- `'+line.strip().rstrip('\\').strip()+'`' for line in m[1].splitlines() if line.strip()), text, flags=re.S)
        parts=text.split('## Сравнение вариантов')
        story.extend(renderer.mdflow(parts[0]))
        if len(parts)>1:
            story.append(PageBreak())
            story.extend(renderer.mdflow('## Сравнение вариантов'+parts[1]))
        story.append(PageBreak())
    story.pop()
    def footer(c,d):
        c.setFillColor(colors.HexColor('#0d7b78'));c.rect(0,A4[1]-9,A4[0],9,fill=1,stroke=0)
        c.setFillColor(colors.HexColor('#5a6b7b'));c.setFont('DV',8);c.drawString(50,25,'Integration MVP · 22.10.2026');c.drawRightString(A4[0]-50,25,str(d.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    paths=[ROOT/'docs/integration-mvp.md',ROOT/'docs/integration-audit.md',output,diagram,
           ARCH/'contracts/backend-ml.openapi.json',ROOT/'ml/openapi.json']
    report={'status':'BUILT','pdfPages':len(PdfReader(output).pages),'visualReview':'PENDING',
            'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    (ROOT/'reports/integration-20261022/document-build.json').write_text(json.dumps(report,indent=2)+'\n')
    (ARCH/'INTEGRATION-SHA256SUMS').write_text(''.join(f'{h}  {p}\n' for p,h in report['files'].items()))
    print(json.dumps({'pdfPages':report['pdfPages'],'output':str(output.relative_to(ROOT))}))

if __name__=='__main__':main()
