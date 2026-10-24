import { useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Button, Tag } from 'antd';
import { ArrowRight, Check, Layers3, Package, Wallet } from 'lucide-react';
import { api } from '../../shared/api/client';
import type { Need, Product } from '../../shared/types/domain';
import { fromKopecks, money, toKopecks } from '../../shared/lib/money';
import { needSchema } from '../../shared/lib/validation';
import { ErrorState, Field, LoadingState, PageTitle, Panel } from '../../shared/ui/common';
import { useExposure } from '../feed/useExposure';
export function Needs() {
  const navigate = useNavigate(),
    [error, setError] = useState<unknown>();
  const form = useForm({
    defaultValues: { purpose: 'Пополнение оборотных средств', amount: '3000000', months: 12 },
  });
  const [stage, setStage] = useState(0);
  const save = useMutation({ mutationFn: api.needs, onSuccess: () => navigate('/products') });
  const submit = form.handleSubmit(async (v) => {
    const parsed = needSchema.safeParse(v);
    if (!parsed.success) {
      for (const e of parsed.error.issues)
        form.setError(e.path[0] as keyof typeof v, { message: e.message });
      return;
    }
    try {
      await save.mutateAsync({ ...parsed.data, amount: toKopecks(parsed.data.amount) });
    } catch (e) {
      setError(e);
    }
  });
  return (
    <>
      <PageTitle
        eyebrow="ПОДБОР ФИНАНСИРОВАНИЯ"
        title="Давайте начнём с вашей цели"
        description="Пара вопросов — и мы покажем подходящие варианты. Это ещё не заявка."
      />
      <div className="two-column">
        <Panel>
          <p className="eyebrow">ШАГ {stage + 1} ИЗ 2</p>
          <form
            onSubmit={
              stage === 0
                ? (e) => {
                    e.preventDefault();
                    setStage(1);
                  }
                : submit
            }
          >
            {stage === 0 ? (
              <>
                <h2>Что поможет бизнесу расти?</h2>
                <div className="purpose-options">
                  {[
                    'Пополнение оборотных средств',
                    'Покупка оборудования',
                    'Кассовый разрыв',
                    'Расширение бизнеса',
                  ].map((p, i) => (
                    <label key={p} className="purpose-option">
                      <input type="radio" value={p} {...form.register('purpose')} />
                      <span>
                        {
                          [
                            <Package key="p" />,
                            <Layers3 key="l" />,
                            <Wallet key="w" />,
                            <ArrowRight key="a" />,
                          ][i]
                        }
                      </span>
                      {p}
                    </label>
                  ))}
                </div>
              </>
            ) : (
              <>
                <h2>Сколько нужно для следующего шага?</h2>
                <Field id="amount" label="Сумма, ₽" error={form.formState.errors.amount?.message}>
                  <input id="amount" inputMode="decimal" {...form.register('amount')} />
                </Field>
                <Field
                  id="months"
                  label="На какой срок?"
                  error={form.formState.errors.months?.message}
                >
                  <select id="months" {...form.register('months', { valueAsNumber: true })}>
                    {[3, 6, 12, 18, 24, 36].map((n) => (
                      <option value={n} key={n}>
                        {n} месяцев
                      </option>
                    ))}
                  </select>
                </Field>
              </>
            )}
            <div className="form-actions">
              {stage === 1 && <Button onClick={() => setStage(0)}>Назад</Button>}
              <Button type="primary" htmlType="submit" size="large" loading={save.isPending}>
                {stage === 0 ? 'Продолжить' : 'Подобрать варианты'}
                <ArrowRight size={16} />
              </Button>
            </div>
            {!!error && <ErrorState error={error} />}
          </form>
        </Panel>
        <Panel className="soft-panel">
          <span className="large-icon">
            <Wallet />
          </span>
          <h2>
            Финансирование
            <br />
            под вашу задачу
          </h2>
          <p className="muted">
            Выберите сумму и срок. Мы покажем доступные по параметрам продукты, их преимущества и
            ограничения.
          </p>
        </Panel>
      </div>
    </>
  );
}
function ProductCard({ product: p, index }: { product: Product; index: number }) {
  const { ref, click } = useExposure(p.id);
  return (
    <article ref={ref} className="product-card">
      <div className="spread">
        <span className={'product-icon tone-' + index}>
          {index === 0 ? <Package /> : index === 1 ? <Layers3 /> : <Wallet />}
        </span>
        <Tag color={p.eligible ? 'green' : 'default'}>
          {p.eligible ? 'Подходит по параметрам' : 'Вне параметров'}
        </Tag>
      </div>
      <h2>{p.title}</h2>
      <p className="muted">{p.description}</p>
      <div className="product-terms">
        <div>
          <small>Сумма до</small>
          <strong>{money(p.maxAmount)}</strong>
        </div>
        <div>
          <small>Срок до</small>
          <strong>{p.maxMonths} мес.</strong>
        </div>
      </div>
      <ul className="benefits">
        {p.benefits.map((b) => (
          <li key={b}>
            <Check size={16} />
            {b}
          </li>
        ))}
      </ul>
      <Link
        onClick={click}
        className={'button ' + (p.eligible ? 'red' : 'white')}
        to={'/products/' + p.id}
      >
        Подробнее <ArrowRight size={16} />
      </Link>
    </article>
  );
}
export function Products() {
  const need = useQuery({ queryKey: ['need'], queryFn: api.getNeed });
  const p = useQuery({
    queryKey: ['products', need.data],
    queryFn: () => api.products(need.data),
    enabled: !!need.data,
  });
  return (
    <>
      <PageTitle
        eyebrow="ФИНАНСИРОВАНИЕ"
        title="Возможности для вашего бизнеса"
        description="Три инструмента для разных задач. Выбирайте тот, который подходит вам."
        action={
          <Link className="button white" to="/needs">
            Изменить параметры
          </Link>
        }
      />
      {need.data && (
        <div className="selection-summary">
          <span>Ваша потребность</span>
          <strong>{money(need.data.amount)}</strong>
          <span>{need.data.months} мес.</span>
          <span>{need.data.purpose}</span>
        </div>
      )}
      {p.isPending ? (
        <LoadingState />
      ) : p.error ? (
        <ErrorState error={p.error} retry={() => void p.refetch()} />
      ) : (
        <div className="product-grid">
          {p.data.map((product, index) => (
            <ProductCard key={product.id} product={product} index={index} />
          ))}
        </div>
      )}
    </>
  );
}
export function ProductDetails() {
  const createCommand = useRef<ReturnType<typeof api.createApplication> | null>(null);
  const { productId = '' } = useParams(),
    navigate = useNavigate();
  const product = useQuery({
      queryKey: ['product', productId],
      queryFn: () => api.product(productId),
    }),
    need = useQuery({ queryKey: ['need'], queryFn: api.getNeed });
  const create = useMutation({
    mutationFn: ({ p, n }: { p: string; n: Need }) => {
      if (!createCommand.current) createCommand.current = api.createApplication(p, n);
      return createCommand.current.send();
    },
    onSuccess: (a) => navigate(`/applications/${a.id}/company`),
  });
  if (product.isPending || need.isPending) return <LoadingState />;
  if (product.error || need.error) return <ErrorState error={product.error ?? need.error} />;
  const p = product.data!,
    n = need.data!,
    eligible =
      BigInt(n.amount) <= BigInt(p.maxAmount) &&
      BigInt(n.amount) >= BigInt(p.minAmount) &&
      n.months <= p.maxMonths;
  return (
    <>
      <Link className="back-link" to="/products">
        ← Все варианты
      </Link>
      <PageTitle eyebrow="ФИНАНСИРОВАНИЕ БИЗНЕСА" title={p.title} description={p.description} />
      <div className="two-column">
        <Panel>
          <h2>Ваш следующий шаг — ближе</h2>
          <ul className="benefits large">
            {p.benefits.map((b) => (
              <li key={b}>
                <Check size={19} />
                {b}
              </li>
            ))}
          </ul>
          <h3>Что нужно учесть</h3>
          <p>{p.restriction}</p>
          <p>
            Окончательные условия определяются после рассмотрения. Ставка по продукту — {p.rate}%
            годовых.
          </p>
        </Panel>
        <Panel>
          <p className="eyebrow">ПАРАМЕТРЫ ВАШЕЙ ЗАЯВКИ</p>
          <strong className="hero-amount">{money(n.amount)}</strong>
          <p>
            На {n.months} месяцев · {n.purpose}
          </p>
          <p className="muted">Введено: {fromKopecks(n.amount)} ₽</p>
          {!eligible && (
            <p className="field-error">
              Сумма или срок выходят за параметры этого продукта. Измените потребность.
            </p>
          )}
          <Button
            block
            type="primary"
            size="large"
            loading={create.isPending}
            disabled={!eligible}
            onClick={() => create.mutate({ p: p.id, n })}
          >
            Перейти к заявке <ArrowRight size={16} />
          </Button>
          {create.error && <ErrorState error={create.error} />}
          <small className="muted mt">
            Можно сохранить черновик и вернуться позже в этой вкладке.
          </small>
        </Panel>
      </div>
    </>
  );
}
