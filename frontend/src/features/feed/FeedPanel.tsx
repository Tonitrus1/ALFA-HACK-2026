import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from 'antd';
import { api } from '../../shared/api/client';
import type { Card, Preferences, Feed, SavedFeed } from '../../shared/api/client';
import { context } from '../../shared/api/http';
import { ErrorState, LoadingState, Panel } from '../../shared/ui/common';
type Action = 'VIEW'|'CLICK'|'HELPFUL'|'NOT_INTERESTED';
const pending = new Map<string, Parameters<typeof api.feedback>[0]>();
function FeedbackCard({card, exposureId, onHidden}: {card:Card;exposureId:string;onHidden:(id:string)=>void}) {
  const query=useQueryClient(),ref=useRef<HTMLElement>(null),viewed=useRef(false);
  const [error,setError]=useState<unknown>(),[opened,setOpened]=useState(false),[busy,setBusy]=useState(false),[reaction,setReaction]=useState(card.userReaction);
  const identity=[context.get()?.actor,context.get()?.companyId,exposureId,card.contentId].join(':');
  const sendRef=useRef<(action:Action)=>Promise<void>>(async()=>{});
  const send=async(action:Action)=>{
    const key=identity+':'+action;
    let event=pending.get(key);
    if(!event){event={clientEventId:crypto.randomUUID(),exposureId,itemId:card.contentId,action,occurredAt:new Date().toISOString()};pending.set(key,event);}
    setBusy(true);
    try{await api.feedback(event);pending.delete(key);setError(undefined);
      if(action==='VIEW')viewed.current=true;
      if(action==='HELPFUL'||action==='NOT_INTERESTED'){setReaction(action);await query.invalidateQueries({queryKey:['saved-feed']});if(action==='NOT_INTERESTED')onHidden(card.contentId);}
      if(action==='CLICK')setOpened(true);
    }catch(e){setError(e);throw e;}finally{setBusy(false);}
  };
  sendRef.current=send;
  useEffect(()=>{
    const el=ref.current;if(!el)return;
    let timer:ReturnType<typeof setTimeout>|undefined,ratio=0;
    const update=()=>{clearTimeout(timer);if(ratio>=.5&&document.visibilityState==='visible'&&!viewed.current)timer=setTimeout(()=>{void sendRef.current('VIEW').catch(()=>{});},1000);};
    const observer=new IntersectionObserver(entries=>{ratio=entries[0]?.intersectionRatio??0;update();},{threshold:[0,.5,1]});
    observer.observe(el);document.addEventListener('visibilitychange',update);
    return()=>{clearTimeout(timer);observer.disconnect();document.removeEventListener('visibilitychange',update);};
  },[identity]);
  const retry=async()=>{for(const event of [...pending.values()].filter(e=>e.exposureId===exposureId&&e.itemId===card.contentId))await send(event.action);};
  return <article ref={ref} className="article" data-testid="feed-card" data-content-id={card.contentId}>
    <img src={card.illustration} alt="" width="220" height="110" />
    <h3>{card.title}</h3><p className="muted">{card.reason}</p>{opened&&<p>{card.text}</p>}
    <div className="form-actions">
      <Button disabled={busy} onClick={()=>void send('CLICK').catch(()=>{})}>Читать</Button>
      <Button disabled={busy} onClick={()=>void send('HELPFUL').catch(()=>{})}>{reaction==='HELPFUL'?'✓ В полезном':'Полезно'}</Button>
      <Button disabled={busy} onClick={()=>void send('NOT_INTERESTED').catch(()=>{})}>Не интересно</Button>
    </div>{!!error&&<ErrorState error={error} retry={()=>void retry().catch(()=>{})} />}
  </article>;
}
export function FeedPanel(){
  const company=context.get()?.companyId,query=useQueryClient();
  const [tab,setTab]=useState<'feed'|'saved'>('feed'),[cursor,setCursor]=useState<string>(),[hidden,setHidden]=useState<string[]>([]),[error,setError]=useState<unknown>();
  const p=useQuery({queryKey:['preferences',company],queryFn:api.preferences});
  const [form,setForm]=useState<Preferences>({});
  useEffect(()=>{if(p.data)setForm(p.data);},[p.data]);
  const f=useQuery<Feed|SavedFeed>({queryKey:[tab==='feed'?'feed':'saved-feed',company,cursor],queryFn:()=>tab==='feed'?api.feed(cursor):api.saved(cursor),staleTime:Infinity});
  const save=async()=>{try{await api.savePreferences(form);setCursor(undefined);setHidden([]);await query.invalidateQueries({queryKey:['preferences']});await query.resetQueries({queryKey:['feed']});setError(undefined);}catch(e){setError(e);}};
  const changeTab=(v:'feed'|'saved')=>{setTab(v);setCursor(undefined);setHidden([]);};
  const page=f.data,exposure=page&&('rankingMetadata'in page?page.rankingMetadata.exposureId:page.exposureId);
  return <Panel>
    <div className="form-grid">{(['task','help','depth']as const).map(k=><label key={k}>{({task:'Ваша задача',help:'Чем помочь',depth:'Глубина материала'})[k]}
      <select aria-label={k} value={form[k]??''} onChange={e=>setForm({...form,[k]:e.target.value||null})}>
        <option value="">Без предпочтения</option>
        {({task:[['PURCHASE','Закупка'],['CASH_GAP','Кассовый разрыв'],['EQUIPMENT','Оборудование'],['EXPANSION','Расширение'],['EXPLORING','Изучаю']],help:[['AMOUNT','Сумма'],['OPTIONS','Варианты'],['COST','Стоимость'],['APPLICATION','Заявка']],depth:[['BASICS','Основы'],['EXPLAINED','С объяснением'],['PRACTICAL','Практика']]})[k].map(([v,t])=><option value={v} key={v}>{t}</option>)}
      </select></label>)}</div>
    <div className="form-actions"><Button onClick={()=>void save()}>Сохранить предпочтения</Button><Button onClick={()=>changeTab('feed')}>Подборка</Button><Button onClick={()=>changeTab('saved')}>Полезные материалы</Button></div>
    {!!(p.error||error)&&<ErrorState error={p.error||error} />}
    {f.isPending?<LoadingState />:f.error?<ErrorState error={f.error} retry={()=>{setCursor(undefined);void f.refetch();}} />:<>
      {page&&'rankingMode'in page&&<p className="muted">{page.rankingMode==='MODEL'?'Персональная подборка':'Подборка по правилам'}</p>}
      <div className="articles">{page?.cards.filter(c=>!hidden.includes(c.contentId)).map(c=><FeedbackCard key={exposure+':'+c.contentId} card={c} exposureId={exposure!} onHidden={id=>setHidden(v=>[...v,id])} />)}</div>
      {!page?.cards.length&&<p>Материалов пока нет. Измените предпочтения или вернитесь позже.</p>}
      {page?.hasMore&&<Button onClick={()=>setCursor(page.nextCursor)}>Следующая страница</Button>}
    </>}
  </Panel>;
}
