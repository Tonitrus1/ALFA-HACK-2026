"""Render every final PDF for human visual review; output is outside deliverables by default."""
from pathlib import Path
import os,sys,json,argparse,hashlib
extra=os.environ.get('CREDIT_RENDER_DEPS')
if extra:sys.path.insert(0,extra)
import pypdfium2 as pdfium
from PIL import Image,ImageOps,ImageDraw
O=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
 manifest=[]
 for p in sorted(O.rglob('*.pdf')):
  name=p.stem;doc=pdfium.PdfDocument(str(p));pages=[]
  for j in range(len(doc)):
   page=doc[j];img=page.render(scale=1.55).to_pil().convert('RGB');f=out/f'{name}-{j+1:02d}.png';img.save(f);pages.append(f);page.close()
  doc.close()
  contacts=[]
  for start in range(0,len(pages),4):
   cw=660;ch=955;sheet=Image.new('RGB',(cw*2,ch*2),'#dce6e8');draw=ImageDraw.Draw(sheet)
   for k,f in enumerate(pages[start:start+4]):
    im=Image.open(f);im.thumbnail((cw-16,ch-42));x=(k%2)*cw+(cw-im.width)//2;y=(k//2)*ch+32;sheet.paste(im,(x,y));draw.text(((k%2)*cw+10,(k//2)*ch+10),f'{name} | page {start+k+1}',fill='#182b3b')
   target=out/f'contact-{name}-{start//4+1:02d}.png';sheet.save(target);contacts.append(str(target))
  manifest.append(dict(path=str(p.relative_to(O)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),pages=len(pages),renders=[str(f) for f in pages],contacts=contacts))
 (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'pdfs':len(manifest),'pages':sum(x['pages'] for x in manifest),'contacts':sum(len(x['contacts']) for x in manifest),'manifest':str(out/'manifest.json')},ensure_ascii=False))
if __name__=='__main__':main()
