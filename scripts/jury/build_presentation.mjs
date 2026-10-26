// Run inside artifactSession.run with the viewer-bound presentation facade.
// All diagrams and text remain native editable PowerPoint objects.
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const RED = '#F52B22', INK = '#171717', MUTED = '#626262', PALE = '#F3F3F3';
const TAG = 'submission-2026-10-26';
export async function build(presentation) {
  if (presentation.slides.items.length) throw new Error('Build expects an empty presentation');
  presentation.theme.defaultFont = 'Arial';
  function text(slide,value,x,y,w,h,size=28,color=INK,bold=false,align='left') {
    const s=slide.shapes.add({geometry:'textbox',name:value.split('\n')[0].slice(0,64),
      position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0},
      text:{text:value,style:{fontSize:size,color,bold,alignment:align,verticalAlignment:'top'}}});
    s.text.typeface='Arial'; return s;
  }
  function slide(title,red=false) {
    const s=presentation.slides.add({width:1280,height:720,background:{fill:red?RED:'#FFFFFF'}});
    if(title)text(s,title,64,44,1152,120,48,red?'#FFFFFF':INK,true);
    const number=presentation.slides.items.length;
    text(s,'Поток · Gambit_Yvaga',64,678,720,24,16,red?'#FFFFFF':MUTED);
    text(s,String(number).padStart(2,'0'),1150,678,64,24,16,red?'#FFFFFF':MUTED,false,'right');
    return s;
  }
  function image(s,name,x,y,w,h) {return s.images.add({path:ROOT+'/docs/jury/assets/'+name,alt:name.replace('.png',''),position:{left:x,top:y,width:w,height:h},fit:'contain'});}
  function node(s,label,x,y,w=224,h=72,red=false) {
    const sh=s.shapes.add({geometry:'rect',name:label,position:{left:x,top:y,width:w,height:h},
      fill:red?RED:PALE,line:{fill:'none',width:0},text:{text:label,style:{fontSize:24,bold:true,color:red?'#FFFFFF':INK,alignment:'center',verticalAlignment:'middle'}}});
    sh.text.typeface='Arial';return sh;
  }
  function connect(s,a,b,from='right',to='left') {
    return s.shapes.connect(a,b,{kind:'elbow',fromSide:from,toSide:to,line:{fill:'#777777',width:2},tail:{type:'arrow',width:'med',length:'med'}});
  }
  function notes(s,copy,source) {s.speakerNotes.text=copy+'\n\nИсточники: '+source;}

  let s=slide('',true);
  text(s,'Поток',64,100,1140,145,112,'#FFFFFF',true);
  text(s,'Умный кредитный кабинет\nпредпринимателя',72,290,1110,150,48,'#FFFFFF');
  text(s,'Gambit_Yvaga',72,526,1060,56,32,'#FFFFFF',true);
  text(s,'Альфа Хак 2026',72,590,1060,36,24,'#FFFFFF');
  notes(s,'0:00–0:20. Мы сделали связанный кредитный путь для предпринимателя: от потребности до результата по заявке. Это работающий демонстрационный MVP, который можно самостоятельно открыть и запустить.','README.md; docs/jury/README.md');

  s=slide('Кредитная заявка требует общего контекста');
  text(s,'Предприниматель',64,188,540,55,34,RED,true);
  text(s,'Как выбрать продукт?\nКакие данные подготовить?\nЧто делать после подачи?',64,272,530,230,32);
  text(s,'Банк',692,188,500,55,34,RED,true);
  text(s,'Собрать данные в одном деле\nСогласовать проверки и правила\nОбъяснить следующий шаг',692,272,520,230,30);
  text(s,'Продуктовая гипотеза: единый кабинет уменьшает разрывы между этапами',64,570,1140,70,26,MUTED);
  notes(s,'0:20–0:50. Кейс включает не только анкету: клиент выбирает продукт, готовит данные и должен понимать движение заявки. Банку важно сохранить связность рассмотрения. Мы исходили из этих задач. Подтверждённый CustDev и измеренную экономию времени не заявляем.','Предоставленный кейс, страницы 4–9; docs/jury/requirements.md');

  s=slide('Один продукт для клиента и рассмотрения',true);
  text(s,'Для клиента',64,200,500,55,32,'#FFFFFF',true);
  text(s,'Понятные этапы\nСохранённые данные\nСледующее действие',64,278,500,170,32,'#FFFFFF');
  text(s,'Для банка',692,200,500,55,32,'#FFFFFF',true);
  text(s,'Версии и снимки\nОтдельные риск и политика\nКонтролируемые переходы',692,278,520,170,30,'#FFFFFF');
  text(s,'Документы, персональная лента и помощник сопровождают основной путь',64,540,1150,86,30,'#FFFFFF');
  notes(s,'0:50–1:15. Кабинет сохраняет введённые данные и показывает следующий шаг. Backend фиксирует версии и снимки для рассмотрения. Помощник и OCR встроены в путь, при этом ручной ввод и основная кредитная логика остаются доступны.','docs/jury/architecture.md; docs/jury/data-model.md');

  s=slide('Сквозной путь предпринимателя');
  const labels=['Потребность','Продукт','Компания','Документы','Финансы','Рассмотрение','Предложение','Демооформление'];
  const top=labels.slice(0,4).map((v,i)=>node(s,v,64+i*300,205,244,84,i===0));
  const bottom=labels.slice(4).map((v,i)=>node(s,v,64+i*300,412,244,84,i===3));
  for(let i=0;i<3;i++){connect(s,top[i],top[i+1]);connect(s,bottom[i],bottom[i+1]);}
  connect(s,top[3],bottom[0],'bottom','top');
  text(s,'Уточнение возвращает заявку на рассмотрение с новой подтверждённой версией данных',64,565,1150,70,26,MUTED);
  notes(s,'1:15–1:45. Пользователь выбирает потребность и продукт, вводит сведения и финансы, может добавить документы. После подачи система рассматривает заявку. При запросе уточнения клиент дополняет исходное дело. Принятие предложения и демооформление завершают путь без реальной выдачи.','docs/jury/architecture.md; docs/jury/demo.md');

  s=slide('Работающий кабинет');
  image(s,'workspace-detail.png',64,168,820,461);
  text(s,'Статус заявки',926,194,290,48,30,RED,true);
  text(s,'Сохранённый черновик\nи следующий шаг',926,250,290,96,26);
  text(s,'Персональная лента',926,385,290,92,30,RED,true);
  text(s,'Материалы по интересам\nи контексту бизнеса',926,484,290,110,26);
  notes(s,'1:45–2:10. Это реальный экран опубликованного сервиса, не макет. Покажем сохранённую заявку и следующий шаг. Ниже располагается персональная подборка материалов. При обновлении страницы данные читаются с backend.','docs/jury/assets/workspace-detail.png, реальный серверный UI 26.10.2026; docs/jury/evidence/live-readonly.json');

  s=slide('Оценка риска и кредитное решение');
  const a=node(s,'Подтверждённые\nфинансы',64,190,286,100),b=node(s,'CatBoost Risk\nBANKRUPTCY_PROXY',496,190,286,100),c=node(s,'Java\nDemoPolicyV1',928,190,286,100,true);
  connect(s,a,b);connect(s,b,c);
  text(s,'Возможные результаты',64,362,1120,50,32,RED,true);
  text(s,'Одобрение\nАльтернативные условия',64,442,360,120,28);
  text(s,'Уточнение данных\nОтказ',484,442,360,120,28);
  text(s,'MANUAL\nДополнительная проверка',900,442,320,120,27);
  text(s,'Искусственные правила и синтетическая модель. Рабочее место сотрудника требует внедрения',64,604,1140,44,20,MUTED);
  notes(s,'2:10–2:45. Скоринг возвращает оценку риска, а итог определяет отдельная продуктовая политика с проверкой данных и ограничений. Часть правил применяется ещё до модели. Сбой Risk ведёт к MANUAL. Его завершение сотрудником пока не реализовано. Пороги искусственные, score не является банковской PD.','backend/app/src/main/java/ru/alfahack/credit/integration/domain/DemoPolicyV1.java; ml/artifacts/baseline/model-card.md');

  s=slide('Документы и подтверждение финансов');
  image(s,'financial-form.png',64,178,700,394);
  text(s,'Карантин и ClamAV',824,190,390,50,30,RED,true);
  text(s,'Только CLEAN-версия\nпоступает на распознавание',824,252,390,88,26);
  text(s,'Tesseract и LLM',824,362,390,50,30,RED,true);
  text(s,'Поля с источником\nи проверкой JSON Schema',824,422,390,90,26);
  text(s,'Пользователь сверяет найденное и подтверждает восемь показателей',64,594,1146,56,28,RED,true);
  notes(s,'2:45–3:20. Антивирусная проверка предшествует OCR. Модель предлагает значения, привязанные к источнику и версии файла. Пользователь проверяет период, единицы и все значимые поля. Можно объединить несколько документов и дополнить пропуски вручную. Для live-показа подготовлен только синтетический материал.','docs/jury/architecture.md; docs/jury/assets/financial-form.png; reports/local-qwen3b/ocr-validation.json');

  s=slide('Персональная лента и помощник');
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
  notes(s,'4:00–4:40. Backend представляет модульный монолит с общей транзакционной базой, ML/OCR/RAG работают отдельно. Сессии и бизнес-события сохраняются в PostgreSQL. Документы лежат в версионированном томе, Qdrant действительно подключён. Стрелка к локальной Qwen описывает поддерживаемый local-профиль, а точный режим модели публичного сервера этим слайдом не утверждается. SearXNG, отдельная ML DB, init/worker процессы показаны в полной документации.','compose.yaml; deploy/compose.local-llm.yaml; docs/jury/architecture.md; docs/jury/deployment.md');

  s=slide('Проверки и границы MVP');
  const metrics=[['77','Frontend','unit-тестов'],['139','Backend','4 opt-in пропущены'],['38','OCR','unit / contract'],['79','Ассистент','2 integration пропущены']];
  metrics.forEach(([v,label,desc],i)=>{const x=64+i*300;text(s,v,x,180,248,120,86,RED,true);text(s,label,x,322,250,50,30,INK,true);text(s,desc,x,378,258,74,22,MUTED);});
  text(s,'Сессии, CSRF, изоляция компаний, версии и идемпотентность',64,497,1150,60,30);
  text(s,'Реальные inference-пробы описаны отдельно. Банковская валидация и нагрузочный тест требуют продолжения',64,584,1140,64,23,MUTED);
  notes(s,'4:40–5:15. Это свежие локальные проверки версии кода, а не сумма всех исторических отчётов. Backend: 139, из них 4 опциональных пропущены; frontend 77, OCR 38, assistant 79 и 2 пропущены. Unit/contract tests AI используют управляемые двойники. Настоящие Tesseract/Qwen и retrieval проверялись отдельными probes, условия приведены в документации. Производительность серверной VM и качество на банковских данных не заявляются.','docs/jury/verification.md; backend/**/target/surefire-reports; reports/local-qwen3b/validation.json; reports/local-qwen3b/ocr-validation.json');

  s=slide('Следующий этап: банковское внедрение',true);
  text(s,'Банковский процесс',64,198,350,90,34,'#FFFFFF',true);
  text(s,'SSO и роли\nРабочее место сотрудника\nБКИ / KYC / АБС / ЭП',64,320,350,190,29,'#FFFFFF');
  text(s,'Надёжность',484,198,350,90,34,'#FFFFFF',true);
  text(s,'HA и восстановление\nОбъектное хранилище\nМониторинг и аудит',484,320,350,190,29,'#FFFFFF');
  text(s,'Качество моделей',904,198,310,90,34,'#FFFFFF',true);
  text(s,'Разрешённые данные\nНезависимая валидация\nРеестр и откат',904,320,310,190,28,'#FFFFFF');
  text(s,'Целевая архитектура и критерии приёмки каждого шага описаны в репозитории',64,582,1152,68,26,'#FFFFFF');
  notes(s,'5:15–5:55. Развитие начинается с пилота, доступа и управляемого процесса сотрудника. Затем подключаются банковские проверки, договоры и выдача. Надёжность и масштабирование проверяются учениями и нагрузкой. ML требует разрешённых данных и независимой валидации. Эти компоненты запланированы, а не представлены как уже работающие.','docs/jury/bank-roadmap.md');

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
  notes(s,'5:55–6:20. Сервис и исходный код доступны по ссылкам и QR-кодам. На ngrok при первом визите нажмите Visit Site. Две учётные записи предназначены исключительно для синтетической демонстрации, публикация согласована владельцем. Версия к сдаче закреплена тегом. В README есть запуск, проверочные данные и все архитектурные материалы.','docs/jury/demo-access.json; docs/jury/demo.md; README.md');
  return {slides:presentation.slides.items.length};
}
