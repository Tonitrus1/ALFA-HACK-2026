#!/usr/bin/env python3
"""Create a self-contained jury handoff with public demo access and exact scenarios."""
from pathlib import Path
import hashlib,html,json,zipfile
ROOT=Path(__file__).resolve().parents[2];jury=ROOT/'docs/jury';out=jury/'presentation';quick=ROOT/'.local/jury/bundle';quick.mkdir(parents=True,exist_ok=True)
a=json.loads((jury/'demo-access.json').read_text());s=json.loads((jury/'demo-scenarios.json').read_text());repo='https://github.com/Tonitrus1/ALFA-HACK-2026';tag=repo+'/tree/submission-2026-10-26';esc=html.escape
rows=[['Предварительная выручка в анкете',*[x['preliminaryRevenueRub'] for x in s['scenarios']]]]
for k,label in [('totalAssets','Активы'),('totalLiabilities','Обязательства'),('currentAssets','Оборотные активы'),('currentLiabilities','Краткосрочные обязательства'),('equity','Капитал'),('revenue','Выручка в отчётности'),('netProfit','Чистая прибыль'),('ebit','EBIT')]:rows.append([label,*[x['valuesRub'][k] for x in s['scenarios']]])
fmt=lambda v:f'{v:,}'.replace(',',' ') if isinstance(v,int) else v
md='# Поток · Gambit_Yvaga\n\nНачните с этого файла. Презентации лежат рядом: `potok-gambit-yvaga.pdf` и `potok-gambit-yvaga.pptx`. Для кликабельной страницы откройте `README.html`.\n\n'
md+=f'## Быстрый вход\n\n1. [Открыть работающий сайт]({a["baseUrl"]}).\n2. На странице ngrok нажать **Visit Site**, если она появится.\n3. Войти одним из аккаунтов ниже.\n4. [Открыть GitHub]({repo}) или [точную версию сдачи]({tag}).\n5. [Полная документация]({tag}/docs/jury): архитектура, запуск Docker, API и план внедрения.\n\n'
md+='| Логин | Пароль |\n|---|---|\n'+''.join(f'| `{x["login"]}` | `{x["password"]}` |\n' for x in a['accounts'])
md+='\nУчётные записи публичного синтетического демо, публикация согласована владельцем. Кабинеты общие. Настоящие сведения клиентов не нужны.\n\n## Проверить четыре результата\n\nДля каждого результата создайте **новую** заявку на **оборотный кредит 500 000 ₽**, срок **12 месяцев**, возраст бизнеса **40 месяцев**. Период финансов: **2025 год**. Документы можно пропустить и внести показатели вручную. **Все суммы в рублях**, не в тысячах и не в копейках. Подтвердите восемь показателей и отправьте заявку.\n\n'
md+='| Поле | '+ ' | '.join(x['name'] for x in s['scenarios'])+' |\n|---|---:|---:|---:|---:|\n'+''.join('| '+' | '.join(str(fmt(v)) for v in row)+' |\n' for row in rows)
md+='| Результат | APPROVED | DECLINED | MANUAL | ALTERNATIVE |\n| Предложенная сумма | 500 000 ₽ | Нет | Нет | 250 000 ₽ |\n\n'
md+='Предварительная выручка должна совпадать с колонкой: расхождение может вызвать уточнение NEEDS_INFO. Для одобрения и других условий должен быть доступен Risk; при его сбое возможен MANUAL. Все четыре набора проверены на локальном Docker-демо с настоящим Risk. Создание этих заявок на общем сервере отдельно не проверялось.\n\nПосле одобрения или других условий откройте предложение, примите его и завершите демооформление. После отказа прочитайте причину. MANUAL показывает передачу на проверку, рабочее место сотрудника относится к следующему этапу внедрения.\n\nНа онлайн-демо при подготовке ассистент работал в поиске по источникам (SEARCH_ONLY), генерация была недоступна. Лента возвращала RULES. Основной кредитный путь допускает ручной ввод финансов.\n\nВерсия сдачи: `submission-2026-10-26`. При недоступности туннеля используйте воспроизводимый локальный запуск из корневого README в GitHub.\n'
(quick/'README.md').write_text(md)
accounts=''.join(f'<tr><td><strong>{esc(x["login"])}</strong></td><td><code>{esc(x["password"])}</code></td></tr>' for x in a['accounts'])
headers='<tr><th>Поле, ₽</th>'+''.join('<th>'+esc(x['name'])+'</th>' for x in s['scenarios'])+'</tr>'
body=''.join('<tr>'+''.join('<td>'+esc(str(fmt(v)))+'</td>' for v in row)+'</tr>' for row in rows)
page=f'''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Поток · Быстрый вход для жюри</title>
<style>body{{margin:0;background:#f5f3f1;color:#171717;font:17px/1.55 Arial,sans-serif}}main{{max-width:1100px;margin:auto;padding:45px 28px 70px}}h1{{font-size:66px;line-height:1;margin:12px 0;color:#f52b22}}h2{{font-size:28px;margin:40px 0 14px}}a{{color:#d72019}}nav{{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}}nav a{{background:#f52b22;color:white;padding:13px 19px;text-decoration:none;font-weight:bold}}table{{width:100%;border-collapse:collapse;background:white;font-size:16px}}th,td{{padding:11px 13px;border-bottom:1px solid #ddd;text-align:left}}th{{background:#171717;color:white}}code{{word-break:break-all;font-size:15px}}.scroll{{overflow:auto}}small{{color:#626262}}.lead{{font-size:22px}}</style>
<main><small>АЛЬФА ХАК 2026 / GAMBIT_YVAGA</small><h1>Поток</h1><p class="lead">Умный кредитный кабинет предпринимателя</p>
<nav><a href="{a['baseUrl']}">Открыть демо</a><a href="{repo}">Репозиторий GitHub</a><a href="{tag}/docs/jury">Документация</a><a href="potok-gambit-yvaga.pdf">Презентация PDF</a></nav>
<p>Если ngrok показывает промежуточную страницу, нажмите <strong>Visit Site</strong>. Затем введите один из аккаунтов. Презентация PDF и редактируемый PPTX лежат рядом с этим файлом.</p>
<div class="scroll"><table><thead><tr><th>Логин</th><th>Пароль</th></tr></thead><tbody>{accounts}</tbody></table></div>
<p><small>Публичное синтетическое демо. Публикация паролей согласована владельцем. Кабинеты общие, настоящие данные клиентов не требуются.</small></p>
<h2>Четыре результата заявки</h2><p>Для каждой колонки создайте новую заявку: <strong>оборотный кредит 500 000 ₽, 12 месяцев, бизнес 40 месяцев, отчётность за 2025 год</strong>. Документы можно пропустить. Все значения вводите <strong>в рублях</strong>, подтвердите восемь финансовых показателей и отправьте заявку.</p>
<div class="scroll"><table><thead>{headers}</thead><tbody>{body}<tr><td>Статус</td><td>APPROVED</td><td>DECLINED</td><td>MANUAL</td><td>ALTERNATIVE</td></tr><tr><td>Предложение</td><td>500 000 ₽</td><td>Нет</td><td>Нет</td><td>250 000 ₽</td></tr></tbody></table></div>
<p>Предварительную выручку заполните по колонке: расхождение с отчётностью может привести к запросу уточнения. Для одобрения и других условий нужен доступный Risk. При его сбое возможен MANUAL. Все четыре набора проверены на локальном Docker-демо с настоящим Risk, создание на общем сервере отдельно не проверялось.</p>
<p>После одобрения или других условий откройте и примите предложение, завершите демооформление. При отказе кабинет показывает причину. MANUAL означает дополнительную проверку, рабочее место сотрудника предстоит внедрить.</p>
<p><small>На онлайн-демо при подготовке ассистент работал с источниками в SEARCH_ONLY без генерации, лента возвращала RULES. Версия сдачи: <a href="{tag}">submission-2026-10-26</a>. При недоступном туннеле используйте локальный Docker-запуск из GitHub README.</small></p></main></html>'''
(quick/'README.html').write_text(page)
zip_path=out/'potok-gambit-yvaga-submission.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
 for src,name in [(quick/'README.md','README.md'),(quick/'README.html','README.html'),(out/'potok-gambit-yvaga.pdf','potok-gambit-yvaga.pdf'),(out/'potok-gambit-yvaga.pptx','potok-gambit-yvaga.pptx')]:z.write(src,name)
with zipfile.ZipFile(zip_path) as z:assert z.testzip() is None
files=[out/'potok-gambit-yvaga.pdf',out/'potok-gambit-yvaga.pptx',zip_path]
(out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))
assert all(p.stat().st_size<18000000 for p in files)
print(json.dumps({p.name:p.stat().st_size for p in files},indent=2))
