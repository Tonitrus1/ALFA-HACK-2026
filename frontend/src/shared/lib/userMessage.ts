const fallback = 'Не удалось выполнить действие. Проверьте данные и попробуйте ещё раз.';
const financialRules: Record<string,string> = {
  'totalAssetsMinor>0':'Сумма активов должна быть больше нуля',
  'currentAssetsMinor<=totalAssetsMinor':'Оборотные активы не могут превышать сумму всех активов',
  'currentLiabilitiesMinor<=totalLiabilitiesMinor':'Краткосрочные обязательства не могут превышать сумму всех обязательств',
  'totalAssetsMinor=totalLiabilitiesMinor+equityMinor':'Сумма активов должна совпадать с суммой всех обязательств и собственного капитала',
};
const labels:Record<string,string>={
  totalAssetsMinor:'Все активы',totalLiabilitiesMinor:'Все обязательства',currentAssetsMinor:'Оборотные активы',
  currentLiabilitiesMinor:'Краткосрочные обязательства',equityMinor:'Собственный капитал',revenueMinor:'Выручка',
  netProfitMinor:'Чистая прибыль',ebitMinor:'Прибыль до уплаты процентов и налогов',
  businessAgeMonths:'Срок работы бизнеса',annualRevenue:'Годовая выручка',activityDescription:'Основная деятельность',
  periodStart:'Начало отчётного периода',periodEnd:'Конец отчётного периода',termMonths:'Срок финансирования',
  amountMinor:'Сумма',consents:'Согласие',confirmed:'Подтверждение',period:'Отчётный год',
  companyName:'Название компании',address:'Адрес',activity:'Деятельность',
};

/** Public UI text never falls back to a server field path, formula or exception dump. */
export function userMessage(value:unknown, defaultMessage=fallback):string {
  if(typeof value!=='string' || !value.trim())return defaultMessage;
  let text=value;
  for(const [rule,description] of Object.entries(financialRules))text=text.split(rule).join(description);
  text=text.replace(/(?:financialStatement\.values\.|statement\.values\.|finance\.|business\.)/g,'');
  text=text.replace(/\b[a-zA-Z][a-zA-Z0-9]*\b/g,word=>labels[word]??({OCR:'распознавание',API:'сервис',CSRF:'защита сессии',EBIT:'прибыль до уплаты процентов и налогов',RUB:'рубли',PDF:'ПДФ',PNG:'ПНГ',JPG:'изображение',TXT:'текстовый файл',LLM:'языковая модель'} as Record<string,string>)[word]??word);
  if(!/[А-Яа-яЁё]/.test(text) || /[A-Za-z]|[<>{}=`]|https?:|\b\d{3}[:/]/.test(text))return defaultMessage;
  return text.trim();
}

export function fieldLabel(path:string):string {
  const name=path.split('.').at(-1)??'';
  return labels[name]??({revenue:'Выручка',netProfit:'Чистая прибыль',ebit:'Прибыль до уплаты процентов и налогов',equity:'Собственный капитал',totalAssets:'Все активы',currentAssets:'Оборотные активы',currentLiabilities:'Краткосрочные обязательства',totalLiabilities:'Все обязательства'} as Record<string,string>)[name]??'Поле заявки';
}
