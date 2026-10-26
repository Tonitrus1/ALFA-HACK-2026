// Run inside artifactSession.run with the viewer-bound presentation facade.
// All diagrams and text remain native editable PowerPoint objects.
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const RED = '#F52B22', INK = '#171717', MUTED = '#626262', PALE = '#F4F2F0';
const TAG = 'submission-2026-10-26';
export async function build(presentation) {
  if (presentation.slides.items.length) throw new Error('Build expects an empty presentation');
  presentation.theme.defaultFont = 'Arial';
  let dark=false;
  function text(slide,value,x,y,w,h,size=28,color=undefined,bold=false,align='left') {
    color=color===undefined?(dark?'#FFFFFF':INK):(dark&&color===MUTED?'#C6C6C6':color);
    const s=slide.shapes.add({geometry:'textbox',name:value.split('\n')[0].slice(0,64),
      position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0},
      text:{text:value,style:{fontSize:size,color,bold,alignment:align,verticalAlignment:'top'}}});
    s.text.typeface='Arial'; return s;
  }
  function slide(title,tone=false) {
    dark=!!tone;
    const fill=tone==='dark'?INK:tone?RED:'#FFFFFF';
    const s=presentation.slides.add({width:1280,height:720,background:{fill}});
    const number=presentation.slides.items.length;
    text(s,'АЛЬФА ХАК 2026',56,26,700,24,13,tone?'#FFFFFF':RED,true);
    if(title)text(s,title,56,70,1168,106,49,tone?'#FFFFFF':INK,true);
    text(s,'Поток / Gambit_Yvaga',56,678,720,24,15,tone?'#FFFFFF':MUTED);
    text(s,String(number).padStart(2,'0'),1158,678,66,24,15,tone?'#FFFFFF':MUTED,false,'right');
    return s;
  }
  function table(s,values,x,y,w,h,widths,size=22) {
    const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,columnWidths:widths,values});
    t.borders.assign({fill:'#D7D3D0',width:0.5,style:'solid'});
    for(let r=0;r<values.length;r++){
      t.rows[r].height=h/values.length;
      for(let c=0;c<values[0].length;c++){
        const cell=t.getCell(r,c);cell.fill=r===0?RED:r%2===0?PALE:'#FFFFFF';
        cell.text.typeface='Arial';cell.text.style={fontSize:size,color:r===0?'#FFFFFF':INK,bold:r===0||c===0,alignment:c===0?'left':'center',verticalAlignment:'middle'};
      }
    }
    return t;
  }
  function image(s,name,x,y,w,h) {return s.images.add({path:ROOT+'/docs/jury/assets/'+name,alt:name.replace('.png',''),position:{left:x,top:y,width:w,height:h},fit:'contain'});}
  function node(s,label,x,y,w=224,h=72,red=false) {
    const sh=s.shapes.add({geometry:'rect',name:label,position:{left:x,top:y,width:w,height:h},
      fill:red?RED:dark?'#333333':PALE,line:{fill:dark?'#555555':'#D7D3D0',width:1},text:{text:label,style:{fontSize:24,bold:true,color:red||dark?'#FFFFFF':INK,alignment:'center',verticalAlignment:'middle'}}});
    sh.text.typeface='Arial';return sh;
  }
  function connect(s,a,b,from='right',to='left') {
    return s.shapes.connect(a,b,{kind:'elbow',fromSide:from,toSide:to,line:{fill:'#777777',width:2},tail:{type:'arrow',width:'med',length:'med'}});
  }
  function notes(s,copy,source) {s.speakerNotes.text=copy+'\n\nИсточники: '+source;}

  let s=slide('',true);
  text(s,'Поток',56,116,1168,204,172,'#FFFFFF',true);
  text(s,'Умный кредитный кабинет\nпредпринимателя',64,354,1100,142,51,'#FFFFFF');
  text(s,'Gambit_Yvaga',64,574,760,56,34,'#FFFFFF',true);
  text(s,'Работающий сервис и открытый код',64,630,1000,32,22,'#FFFFFF');
  notes(s,'0:00–0:15. Поток объединяет потребность, документы и кредитное рассмотрение в одном кабинете предпринимателя. Сервис и репозиторий доступны жюри.','README.md; docs/jury/README.md');

  s=slide('Кредитная заявка требует общего контекста');
  text(s,'Предприниматель',64,188,540,55,34,RED,true);
  text(s,'Как выбрать продукт?\nКакие данные подготовить?\nЧто делать после подачи?',64,272,530,230,32);
  text(s,'Банк',692,188,500,55,34,RED,true);
  text(s,'Собрать данные в одном деле\nСогласовать проверки и правила\nОбъяснить следующий шаг',692,272,520,230,30);
  text(s,'Продуктовая гипотеза: единый кабинет уменьшает разрывы между этапами',64,570,1140,70,26,MUTED);
  notes(s,'0:15–0:40. Кейс включает не только анкету: клиент выбирает продукт, готовит данные и должен понимать движение заявки. Банку важно сохранить связность рассмотрения. Мы исходили из этих задач. Подтверждённый CustDev и измеренную экономию времени не заявляем.','Предоставленный кейс, страницы 4–9; docs/jury/requirements.md');

  s=slide('Одна заявка. Весь путь.',true);
  text(s,'Клиент',56,208,460,58,42,'#FFFFFF',true);
  text(s,'Видит статус и следующий шаг\nВозвращается к сохранённым данным\nПолучает понятный результат',56,300,525,210,30,'#FFFFFF');
  text(s,'Банк',704,208,500,58,42,'#FFFFFF',true);
  text(s,'Рассматривает связанное дело\nРазделяет риск и кредитную политику\nСохраняет версии и основания',704,300,520,210,29,'#FFFFFF');
  text(s,'OCR и помощник сопровождают клиента внутри кабинета',56,584,1168,58,30,'#FFFFFF',true);
  notes(s,'0:40–1:00. Клиенту доступны сохранённые данные, статус и следующее действие. Банк получает версии и снимки, отдельные оценку риска и продуктовую политику. Документы, лента и помощник встроены в этот путь.','docs/jury/architecture.md; docs/jury/data-model.md');

  s=slide('Сквозной путь предпринимателя');
  const labels=['Потребность','Продукт','Компания','Документы','Финансы','Рассмотрение','Предложение','Демооформление'];
  const top=labels.slice(0,4).map((v,i)=>node(s,v,64+i*300,205,244,84,i===0));
  const bottom=labels.slice(4).map((v,i)=>node(s,v,64+i*300,412,244,84,i===3));
  for(let i=0;i<3;i++){connect(s,top[i],top[i+1]);connect(s,bottom[i],bottom[i+1]);}
  connect(s,top[3],bottom[0],'bottom','top');
  text(s,'Уточнение возвращает заявку на рассмотрение с новой подтверждённой версией данных',64,565,1150,70,26,MUTED);
  notes(s,'1:00–1:25. Пользователь выбирает потребность и продукт, вводит сведения и финансы, может добавить документы. После подачи система рассматривает заявку. При запросе уточнения клиент дополняет исходное дело. Принятие предложения и демооформление завершают путь без реальной выдачи.','docs/jury/architecture.md; docs/jury/demo.md');

  s=slide('Работающий кабинет','dark');
  image(s,'workspace-detail.png',64,168,820,461);
  text(s,'Статус заявки',926,194,290,48,30,RED,true);
  text(s,'Сохранённый черновик\nи следующий шаг',926,250,290,96,26);
  text(s,'Персональная лента',926,385,290,92,30,RED,true);
  text(s,'Материалы по интересам\nи контексту бизнеса',926,484,290,110,26);
  notes(s,'1:25–1:45. Это реальный экран опубликованного сервиса, не макет. Покажем сохранённую заявку и следующий шаг. Ниже располагается персональная подборка материалов. При обновлении страницы данные читаются с backend.','docs/jury/assets/workspace-detail.png, реальный серверный UI 26.10.2026; docs/jury/evidence/live-readonly.json');

  s=slide('Четыре результата рассмотрения','dark');
  const submitted=node(s,'Заявка и подтверждённые финансы',350,180,580,68,true);
  const outcomes=[['Одобрение','APPROVED','Предложение на заявленную сумму'],['Отказ','DECLINED','Причина отказа в кабинете'],['Ручная проверка','MANUAL','Передача на дополнительное рассмотрение'],['Другие условия','ALTERNATIVE','Предложение меньшей суммы']];
  outcomes.forEach(([name,code,desc],i)=>{
    const x=56+i*300,n=node(s,name,x,344,268,80,i===0);
    connect(s,submitted,n,'bottom','top');
    text(s,code,x,446,270,32,19,'#FFFFFF',true);
    text(s,desc,x,494,270,96,25,'#FFFFFF');
  });
  text(s,'Отдельная ветка уточнения: клиент дополняет данные и возвращает заявку на рассмотрение',56,610,1168,44,22,MUTED);
  notes(s,'1:45–2:20. После рассмотрения есть четыре исхода. Одобрение и другие условия открывают предложение. Отказ сопровождается объяснением. MANUAL означает дополнительную проверку, операторский интерфейс относится к развитию. Уточнение данных возвращает заявку на рассмотрение. Итог определяет Java DemoPolicyV1 с Risk.','backend/app/src/main/java/ru/alfahack/credit/integration/domain/DemoPolicyV1.java; docs/jury/demo.md');

  s=slide('Данные для проверки каждой развилки');
  text(s,'Оборотный кредит 500 000 ₽ / 12 месяцев / бизнес 40 месяцев / отчётность за 2025 год',56,150,1168,36,22,MUTED);
  const scenarioData=JSON.parse(await (await import('node:fs/promises')).readFile(ROOT+'/docs/jury/demo-scenarios.json','utf8'));
  const scenarios=scenarioData.scenarios,fmt=v=>new Intl.NumberFormat('ru-RU').format(v);
  const matrix=[['Все суммы в рублях',...scenarios.map(v=>v.name)],['Выручка в анкете',...scenarios.map(v=>fmt(v.preliminaryRevenueRub))]];
  for(const [key,label] of [['totalAssets','Активы'],['totalLiabilities','Обязательства'],['currentAssets','Оборотные активы'],['currentLiabilities','Краткосрочные обяз.'],['equity','Капитал'],['revenue','Выручка в отчётности'],['netProfit','Чистая прибыль'],['ebit','EBIT']]) matrix.push([label,...scenarios.map(v=>fmt(v.valuesRub[key]))]);
  table(s,matrix,56,200,1168,404,[288,220,220,220,220],21);
  text(s,'Ожидаемо: 500 000 ₽ / отказ / ручная проверка / предложение 250 000 ₽',56,618,1168,36,24,RED,true);
  notes(s,'2:20–2:50. Для каждой колонки создаётся новая заявка на оборотный кредит 500 тысяч рублей, срок 12 месяцев, возраст бизнеса 40 месяцев. Предварительную выручку нужно заполнить как в первой строке, иначе может появиться запрос уточнения. Все восемь финансовых полей подтвердить. Документы можно пропустить. Значения в рублях. Одобрение и другие условия требуют доступного Risk. Наборы проверяются отдельно на локальном демо с настоящим Risk.','docs/jury/demo-scenarios.json; docs/jury/evidence/local-scenarios.json; docs/jury/demo.md');

  s=slide('Документы и подтверждение финансов');
  image(s,'financial-form.png',64,178,700,394);
  text(s,'Карантин и ClamAV',824,190,390,50,30,RED,true);
  text(s,'Только CLEAN-версия\nпоступает на распознавание',824,252,390,88,26);
  text(s,'Tesseract и LLM',824,362,390,50,30,RED,true);
  text(s,'Поля с источником\nи проверкой JSON Schema',824,422,390,90,26);
  text(s,'Пользователь сверяет найденное и подтверждает восемь показателей',64,594,1146,56,28,RED,true);
  notes(s,'2:50–3:20. Антивирусная проверка предшествует OCR. Модель предлагает значения, привязанные к источнику и версии файла. Пользователь проверяет период, единицы и все значимые поля. Можно объединить несколько документов и дополнить пропуски вручную. Для live-показа подготовлен только синтетический материал.','docs/jury/architecture.md; docs/jury/assets/financial-form.png; reports/local-qwen3b/ocr-validation.json');

  s=slide('Персональная лента и помощник','dark');
  text(s,'Лента E5',64,184,500,52,34,RED,true);
  text(s,'Интересы и контекст компании\nОткрытие статей и сохранение\nRULES при недоступности модели',64,266,525,190,29);
  text(s,'Ассистент RAG',694,184,510,52,34,RED,true);
  text(s,'E5 и BM25, индекс Qdrant\nКонтекст компании от backend\nОтветы с разрешёнными источниками',694,266,520,190,28);
  text(s,'Локальный профиль: Qwen2.5 3B без платного API',64,524,1140,56,30);
  text(s,'На серверном демо подтверждён поиск. Генерация сейчас недоступна',64,596,1140,50,23,MUTED);
  notes(s,'3:20–4:00. Лента ранжирует авторские материалы по типизированному профилю и контексту. Ассистент получает права и продукты от backend и использует разрешённые источники. Он не принимает кредитных решений и не меняет заявку. При свежей онлайн-проверке сервер вернул SEARCH_ONLY с источниками: поиск работает, генерация недоступна. Это не выдаётся за полноценный LLM-ответ. Ранее реальная генерация локальной Qwen проверялась отдельно. Research License требует отдельного решения для коммерческого внедрения.','docs/jury/architecture.md; docs/jury/evidence/live-assistant.json; reports/local-qwen3b/validation.json; THIRD_PARTY_NOTICES.md');

  s=slide('Фактическая архитектура MVP');
  const ui=node(s,'React / Nginx',64,180,250,70),be=node(s,'Spring Boot',487,180,284,70,true),db=node(s,'PostgreSQL',960,180,254,70);
  connect(s,ui,be);connect(s,be,db);
  const br=node(s,'ML bridge',64,350,250,70),risk=node(s,'CatBoost Risk',64,500,250,70),feed=node(s,'E5 Feed',375,500,250,70);
  connect(s,be,br,'bottom','top');connect(s,br,risk,'bottom','top');connect(s,br,feed,'bottom','top');
  const ocr=node(s,'ClamAV / OCR',487,350,284,70),rag=node(s,'RAG-ассистент',960,350,254,70),qdrant=node(s,'Qdrant / SQLite',960,500,254,70),llm=node(s,'LLM · Qwen local',672,500,242,70);
  connect(s,be,ocr,'bottom','top');connect(s,be,rag,'bottom','top');connect(s,rag,qdrant,'bottom','top');connect(s,ocr,llm,'bottom','top');connect(s,rag,llm,'bottom','top');
  text(s,'Внешний доступ: сервер и ngrok. Redis / Kafka / S3 предусмотрены для развития',64,612,1152,42,22,MUTED);
  notes(s,'4:00–5:05. Backend представляет модульный монолит с общей транзакционной базой, ML/OCR/RAG работают отдельно. Сессии и бизнес-события сохраняются в PostgreSQL. Документы лежат в версионированном томе, Qdrant действительно подключён. Стрелка к локальной Qwen описывает поддерживаемый local-профиль, а точный режим модели публичного сервера этим слайдом не утверждается. SearXNG, отдельная ML DB, init/worker процессы показаны в полной документации.','compose.yaml; deploy/compose.local-llm.yaml; docs/jury/architecture.md; docs/jury/deployment.md');

  s=slide('Технологии банковского внедрения');
  text(s,'Конкретные изменения инфраструктуры и AI, которые требуют отдельного внедрения',56,150,1168,34,23,MUTED);
  table(s,[
    ['Слой','Сейчас','Кандидат для банковского контура'],
    ['LLM','Qwen2.5 3B / Ollama','Qwen3-32B / vLLM / GPU'],
    ['Данные','Одиночный PostgreSQL','PostgreSQL / Patroni / pgBackRest'],
    ['Внешний доступ','ngrok, публичный HTTPS','Домен банка / WAF / TLS / cert-manager'],
    ['Доступ и секреты','Demo-логины, .env','Keycloak / OIDC / MFA / OpenBao'],
    ['Документы и события','Файловый том, outbox','Ceph S3 / Kafka с сохранением outbox'],
    ['Эксплуатация','Compose, healthchecks','Kubernetes / Prometheus / Grafana']
  ],56,210,1168,364,[250,326,592],23);
  text(s,'Сильнее модель выбираем по оценке качества. PostgreSQL сохраняем и делаем отказоустойчивым',56,600,1168,54,23,RED,true);
  notes(s,'5:05–5:45. Это предлагаемый стек, а не уже выполненная миграция. Для LLM кандидат Qwen3-32B с Apache 2.0 через vLLM на GPU: превосходство на наших задачах нужно подтвердить. PostgreSQL подходит банку, поэтому меняем одиночное развёртывание на HA с Patroni и резервированием pgBackRest. ngrok заменяется доменом банка, WAF и управлением сертификатами через cert-manager и PKI банка. HTTPS на текущем демо уже есть. Для доступа Keycloak и MFA, секреты OpenBao. Для документов Ceph S3, для событий Kafka с сохранением outbox, эксплуатация Kubernetes и наблюдаемость. Нужны также рабочее место сотрудника и интеграции БКИ, KYC, АБС и ЭП.','docs/jury/bank-roadmap.md; https://huggingface.co/Qwen/Qwen3-32B; https://patroni.readthedocs.io/en/latest/; https://pgbackrest.org/; https://cert-manager.io/docs/configuration/ca/; https://www.keycloak.org/; https://openbao.org/; https://rook.io/');

  s=slide('Демо и исходный код');
  image(s,'qr-demo.png',64,164,164,164);
  text(s,'Работающий сервис',268,166,900,52,32,RED,true);
  text(s,'https://president-diameter-endearing.ngrok-free.dev',268,234,922,70,24);
  image(s,'qr-github.png',64,360,164,164);
  text(s,'Репозиторий и документация',268,358,900,52,32,RED,true);
  text(s,'github.com/Tonitrus1/ALFA-HACK-2026',268,425,922,44,25);
  text(s,TAG,268,478,922,38,22,MUTED);
  text(s,'company-a   xc-fWfKQYhasOO_xpEB4h3VFXHHA9HAv8YlunS2YM8VLvqJ4',64,568,1148,36,20);
  text(s,'company-b   5ykMqYlqwkXTGc8cqGKYDz8hwBeHT89LzPpDQL3l-ecI5MrJ',64,614,1148,36,20);
  notes(s,'5:45–6:15. Сервис и исходный код доступны по ссылкам и QR-кодам. На ngrok при первом визите нажмите Visit Site. Две учётные записи предназначены исключительно для синтетической демонстрации, публикация согласована владельцем. Версия к сдаче закреплена тегом. В README есть запуск, проверочные данные и все архитектурные материалы.','docs/jury/demo-access.json; docs/jury/demo.md; README.md');
  return {slides:presentation.slides.items.length};
}
