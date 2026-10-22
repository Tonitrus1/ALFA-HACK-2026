import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { App, Alert, Button, Checkbox, Modal } from 'antd';
import { ArrowRight, CheckCircle2, FileCheck2 } from 'lucide-react';
import { api } from '../../shared/api/client';
import type { Offer } from '../../shared/types/domain';
import { money } from '../../shared/lib/money';
import { Disclosure, ErrorState, LoadingState, PageTitle, Panel } from '../../shared/ui/common';
export function OfferPage() {
  const { offerId = '', id = '' } = useParams(),
    o = useQuery({ queryKey: ['offer', offerId || id], queryFn: () => offerId ? api.offer(offerId) : api.offerForApplication(id) });
  return o.isPending ? (
    <LoadingState />
  ) : o.error ? (
    <ErrorState error={o.error} retry={() => void o.refetch()} />
  ) : (
    <OfferView key={o.data.id + ':' + o.data.version} offer={o.data} />
  );
}
function OfferView({ offer: o }: { offer: Offer }) {
  const { message } = App.useApp();
  const query = useQueryClient(),
    [checked, setChecked] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [confirm, setConfirm] = useState(false);
  const command = useMemo(() => (o.status === 'AVAILABLE' ? api.accept(o) : api.complete(o)), [o]);
  const expired = o.status === 'AVAILABLE' && Date.parse(o.expiresAt) <= Date.now();
  const run = async () => {
    setBusy(true);
    try {
      const result = await command.send();
      void message.success(
        result.status === 'COMPLETED'
          ? 'Демонстрационное оформление завершено'
          : 'Условия предложения приняты',
      );
      query.setQueriesData<Offer>({queryKey:['offer']}, existing => existing?.id===result.id ? result : existing);
      void query.invalidateQueries({ queryKey: ['application', o.applicationId] });
      setConfirm(false);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageTitle
        eyebrow="ВАШЕ ПРЕДЛОЖЕНИЕ"
        title={o.status === 'COMPLETED' ? 'Новый этап вашего дела' : 'Финансирование обрело форму'}
        description={`Предложение версии ${o.version} · действительно до ${new Date(o.expiresAt).toLocaleString('ru-RU')}`}
      />
      {o.status === 'COMPLETED' ? (
        <Panel className="success-panel">
          <CheckCircle2 size={60} />
          <h2>Демонстрация, деньги не перечисляются</h2>
          <p>Вы прошли весь путь: от потребности до демонстрационного оформления.</p>
          <Link className="button red" to={`/applications/${o.applicationId}/status`}>
            К истории заявки
          </Link>
        </Panel>
      ) : (
        <div className="two-column">
          <Panel>
            <div className="offer-symbol">
              <FileCheck2 size={35} />
            </div>
            <h2>Ваши демонстрационные условия</h2>
            <strong className="hero-amount">{money(o.amount)}</strong>
            <div className="offer-terms">
              <div>
                <small>Срок</small>
                <strong>{o.months} мес.</strong>
              </div>
              <div>
                <small>Условия предложения</small>
                <strong>{o.rate}</strong>
              </div>
            </div>
            <dl className="details">
              <dt>Статус</dt>
              <dd>{o.status === 'ACCEPTED' ? 'Условия приняты' : 'Доступно к принятию'}</dd>
              <dt>Версия</dt>
              <dd>{o.version}</dd>
              <dt>Действует до</dt>
              <dd>{new Date(o.expiresAt).toLocaleDateString('ru-RU')}</dd>
            </dl>
            <p>{o.termsDisclosure}</p><Disclosure />
          </Panel>
          <Panel>
            <h2>
              {o.status === 'ACCEPTED' ? 'Остался последний шаг' : 'Ознакомьтесь с условиями'}
            </h2>
            <p className="muted">
              {o.status === 'ACCEPTED'
                ? 'Условия уже приняты. Завершите демонстрационное оформление.'
                : 'Принятие фиксирует версию предложения. Это не перевод денежных средств.'}
            </p>
            <Checkbox checked={checked} onChange={(e) => setChecked(e.target.checked)}>
              Я ознакомился с демонстрационными условиями и понимаю, что деньги не перечисляются.
            </Checkbox>
            {expired && (
              <Alert className="mt" type="warning" message="Срок действия предложения истёк" />
            )}
            <Button
              block
              className="mt"
              type="primary"
              size="large"
              disabled={!checked || expired || !['AVAILABLE','ACCEPTED'].includes(o.status)}
              onClick={() => setConfirm(true)}
            >
              {o.status === 'ACCEPTED' ? 'Завершить демооформление' : 'Принять предложение'}
              <ArrowRight size={16} />
            </Button>
            {!!error && (
              <div className="mt">
                <ErrorState error={error} />
                <Button
                  className="mt"
                  onClick={() => void query.invalidateQueries({ queryKey: ['offer', o.id] })}
                >
                  Обновить предложение
                </Button>
              </div>
            )}
          </Panel>
        </div>
      )}
      <Modal
        title={o.status === 'ACCEPTED' ? 'Завершить демонстрацию?' : 'Принять условия предложения?'}
        open={confirm}
        onCancel={() => setConfirm(false)}
        onOk={() => void run()}
        confirmLoading={busy}
        okText="Подтвердить"
        cancelText="Вернуться"
      >
        <p>
          {money(o.amount)} · {o.months} мес. · версия {o.version}
        </p>
        <p>Демонстрация, деньги не перечисляются.</p>
        {!!error && <ErrorState error={error} />}
      </Modal>
    </>
  );
}
