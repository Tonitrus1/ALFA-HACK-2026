import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { Alert } from 'antd';
import { api } from '../../shared/api/client';
import { request } from '../../shared/api/http';
import { money } from '../../shared/lib/money';
import { userMessage } from '../../shared/lib/userMessage';
import { ErrorState, LoadingState, PageTitle, Panel, StatusBadge } from '../../shared/ui/common';

export function ResultPage(){
  const {id=''}=useParams();
  const application=useQuery({queryKey:['application',id],queryFn:()=>api.application(id)});
  const status=application.data?.status;
  const decision=useQuery({queryKey:['decision',id],enabled:status==='COMPLETED'||status==='DECLINED',queryFn:()=>request<{publicExplanation:string}>(`/api/v1/applications/${encodeURIComponent(id)}/decision`)});
  const offer=useQuery({queryKey:['result-offer',id],enabled:status==='COMPLETED',queryFn:()=>api.offerForApplication(id)});
  if(application.isPending)return <LoadingState/>;
  if(application.error)return <ErrorState error={application.error} retry={()=>void application.refetch()}/>;
  const app=application.data;
  const final=['COMPLETED','DECLINED','CANCELLED','EXPIRED'].includes(app.status);
  return <>
    <PageTitle title="Результат заявки" eyebrow={'ЗАЯВКА № '+id.slice(0,8)} description="Итог рассмотрения и сохранённые условия финансирования."/>
    <Panel>
      <StatusBadge status={app.status}/>
      {app.status==='COMPLETED' ? <>
        <h2>Оформление завершено</h2>
        {offer.isPending?<LoadingState/>:offer.error?<ErrorState error={offer.error} retry={()=>void offer.refetch()}/>:<>
          <p>Согласованная сумма</p><strong className="amount">{money(offer.data.amount)}</strong>
          <p>Срок финансирования: {offer.data.months} мес.</p>
          <p>Запрошенная сумма: {money(app.need.amount)}</p>
          <p>{offer.data.termsDisclosure}</p>
        </>}
        <Alert type="success" showIcon message="Оформление завершено" description="Условия предложения приняты и сохранены."/>
      </>:<>
        <h2>{app.status==='DECLINED'?'В финансировании отказано':app.status==='CANCELLED'?'Заявка отменена':app.status==='EXPIRED'?'Срок действия заявки истёк':'Рассмотрение ещё не завершено'}</h2>
        <p>Запрошенная сумма: {money(app.need.amount)}</p>
      </>}
      {decision.data && app.status==='DECLINED' && <p>{userMessage(decision.data.publicExplanation,'Финансовые показатели не соответствуют условиям выбранного продукта.')}</p>}
      {decision.error && <ErrorState error={decision.error} retry={()=>void decision.refetch()}/>}
      {!final && <p>Актуальный этап и следующие действия доступны в истории заявки.</p>}
      <div className="form-actions">
        <Link className="button white" to={`/applications/${id}/status`}>История заявки</Link>
        <Link className="button white" to={`/applications/${id}/files`}>Документы заявки</Link>
        <Link className="button red" to="/workspace">В кабинет</Link>
      </div>
    </Panel>
  </>;
}
