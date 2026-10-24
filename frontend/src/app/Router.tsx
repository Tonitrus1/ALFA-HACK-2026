import { BrowserRouter, Link, Navigate, Route, Routes, useParams } from 'react-router-dom';
import { SessionProvider } from './session';
import { Layout } from './Layout';
import { Login, Companies } from '../features/access/Pages';
import { Workspace } from '../features/feed/Workspace';
import { Needs, ProductDetails, Products } from '../features/catalog/Pages';
import { DraftRoute } from '../features/application/DraftProvider';
import {
  BusinessStep,
  CompanyStep,
  DocumentsStep,
  ReviewStep,
} from '../features/application/Steps';
import { StatusPage } from '../features/journey/StatusPage';
import { InformationPage } from '../features/journey/InformationPage';
import { OfferPage } from '../features/offers/OfferPage';
import { Assistant, AssistantSource } from '../features/assistant/Assistant';
import { FilesPage } from '../features/documents/Documents';
import { Disclosure, PageTitle, Panel } from '../shared/ui/common';
function Unavailable({title}: {title: string}) { return <><PageTitle title={title} /><Panel>Функция пока недоступна. История, запросы уточнений и результаты доступны на странице заявки.</Panel></>; }
function Help() {
  const { topic } = useParams();
  return (
    <>
      <PageTitle
        eyebrow="БАЗА ЗНАНИЙ · ДЕМО"
        title={
          topic === 'finance' ? 'Финансовые данные без сложностей' : 'От потребности до предложения'
        }
      />
      <Panel className="reading">
        <h2>
          {topic === 'finance' ? 'Проверьте период и единицы' : 'Подготовьте сведения о компании'}
        </h2>
        <p>
          {topic === 'finance'
            ? 'Все восемь показателей указываются в рублях за выбранный год. Прибыль, EBIT и собственный капитал могут быть отрицательными. Пустое поле не заменяется нулём.'
            : 'Начните с цели, суммы и срока. Сравните доступные продукты и откройте черновик заявки. Проверьте название, деятельность и адрес компании.'}
        </p>
        <h2>{topic === 'finance' ? 'Подтвердите каждое значение' : 'Двигайтесь по шагам'}</h2>
        <p>
          {topic === 'finance'
            ? 'После распознавания сверьте значения с документом; недостающие поля заполните вручную. Отметьте каждый показатель только после проверки. Изменение суммы или периода сбрасывает подтверждение. '
            : 'Финансы → документы и согласия → проверка. Дождитесь сохранения перед отправкой. Если потребуется уточнение, откройте запрос в той же заявке. Ручная проверка не означает отказ.'}
        </p>
        <h2>Ограничения демонстрации</h2>
        <p>
          Все данные искусственные. Заявки и результаты хранятся на сервере. Рассмотрение выполняют демонстрационная политика и модели. Финансовые операции не выполняются.
        </p>
        <Disclosure />
        <Link to="/workspace">Вернуться в кабинет →</Link>
      </Panel>
    </>
  );
}
export function Router() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/workspace" replace />} />
            <Route path="companies" element={<Companies />} />
            <Route path="workspace" element={<Workspace />} />
            <Route path="needs" element={<Needs />} />
            <Route path="products" element={<Products />} />
            <Route path="products/:productId" element={<ProductDetails />} />
            <Route path="applications/:id" element={<DraftRoute />}>
              <Route index element={<Navigate to="company" replace />} />
              <Route path="company" element={<CompanyStep />} />
              <Route path="business" element={<BusinessStep />} />
              <Route path="documents" element={<DocumentsStep />} />
              <Route path="review" element={<ReviewStep />} />
            </Route>
            <Route path="applications/:id/status" element={<StatusPage />} />
            <Route path="applications/:id/information" element={<InformationPage />} />
            <Route path="applications/:id/offer" element={<OfferPage />} />
            <Route path="applications/:id/information/:requestId" element={<InformationPage />} />
            <Route path="applications/:id/files" element={<FilesPage />} />
            <Route path="offers/:offerId" element={<OfferPage />} />
            <Route path="inbox" element={<Unavailable title="Сообщения" />} />
            <Route path="assistant/:conversationId/sources/:documentId/:version" element={<AssistantSource />} />
            <Route path="assistant/:conversationId?" element={<Assistant />} />
            <Route path="help/:topic" element={<Help />} />
            <Route
              path="*"
              element={
                <>
                  <PageTitle
                    title="Страница не найдена"
                    description="Проверьте адрес или вернитесь в кабинет."
                  />
                  <Link to="/workspace" className="button red">
                    В кабинет
                  </Link>
                </>
              }
            />
          </Route>
        </Routes>
      </SessionProvider>
    </BrowserRouter>
  );
}
