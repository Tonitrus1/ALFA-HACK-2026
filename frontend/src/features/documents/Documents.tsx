import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { App, Alert, Button, Modal, Progress, Tag } from 'antd';
import { Download, FileText, UploadCloud } from 'lucide-react';
import { api } from '../../shared/api/client';
import type { DocumentItem, Finance, FinanceKey } from '../../shared/types/domain';
import { financeFields } from '../../shared/types/domain';
import { financeErrors } from '../../shared/lib/validation';
import { useDraft } from '../application/DraftProvider';
import {
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  PageTitle,
  Panel,
} from '../../shared/ui/common';
const states = {
  QUARANTINE: 'Карантин',
  SCANNING: 'Проверка безопасности',
  CLEAN: 'Проверен',
  FAILED: 'Проверка не пройдена',
};
export function DocumentUploader({ applicationId }: { applicationId: string }) {
  const { message } = App.useApp();
  const query = useQueryClient(),
    documents = useQuery({
      queryKey: ['documents', applicationId],
      queryFn: () => api.documents(applicationId),
      refetchInterval: (q) =>
        q.state.data?.some((d) => ['QUARANTINE', 'SCANNING'].includes(d.status)) ? 1500 : false,
    }),
    [progress, setProgress] = useState<number>(),
    [error, setError] = useState<unknown>();
  const upload = async (file: File) => {
    setError(undefined);
    setProgress(0);
    try {
      if (file.size > 10 * 1024 * 1024) throw new Error('Максимальный размер — 10 МБ');
      await api.upload(applicationId, file, setProgress);
      void message.success('Документ загружен и отправлен на проверку');
      await query.invalidateQueries({ queryKey: ['documents', applicationId] });
    } catch (e) {
      setError(e);
    } finally {
      setProgress(undefined);
    }
  };
  return (
    <Panel>
      <h2>Документы заявки</h2>
      <label className={'upload-zone ' + (progress !== undefined ? 'uploading' : '')}>
        <input
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.txt"
          aria-label="Загрузить документ"
          disabled={progress !== undefined}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void upload(file);
            e.target.value = '';
          }}
        />
        <UploadCloud size={33} />
        <strong>
          {progress !== undefined ? 'Загружаем документ…' : 'Выберите файл для загрузки'}
        </strong>
        <span>PDF, PNG, JPG или TXT · до 10 МБ</span>
      </label>
      {progress !== undefined && <Progress percent={progress} />}
      <p className="muted small">
        После загрузки документ пройдёт проверку. Распознанные значения можно сверить перед
        отправкой заявки.
      </p>
      {!!error && <ErrorState error={error} />}
      <div className="file-list">
        {documents.data?.map((d) => (
          <div className="file-row" key={d.id}>
            <FileText size={23} />
            <div>
              <strong>{d.name}</strong>
              <small>
                Версия {d.objectVersion} · {Math.ceil(d.size / 1024)} КБ · OCR:{' '}
                {d.ocrStatus === 'READY'
                  ? 'готово'
                  : d.ocrStatus === 'FAILED'
                    ? 'ошибка, доступен ручной ввод'
                    : 'ожидание'}
              </small>
            </div>
            <Tag color={d.status === 'CLEAN' ? 'green' : d.status === 'FAILED' ? 'red' : 'orange'}>
              {states[d.status]}
            </Tag>
          </div>
        ))}
      </div>
      {documents.error && <ErrorState error={documents.error} />}
    </Panel>
  );
}
export function OcrReview() {
  const { application } = useDraft();
  const docs = useQuery({
      queryKey: ['documents', application.id],
      queryFn: () => api.documents(application.id),
    }),
    [selected, setSelected] = useState<DocumentItem>();
  const ready = docs.data?.filter((d) => d.status === 'CLEAN' && d.ocrStatus === 'READY') ?? [];
  return (
    <>
      {ready.map((d) => (
        <Panel className="mt" key={d.id}>
          <div className="spread">
            <div>
              <h3>Распознавание готово</h3>
              <p className="muted">
                {d.name} · страница 1 · версия {d.objectVersion}. Предложенные значения требуют
                вашей проверки.
              </p>
            </div>
            <Button onClick={() => setSelected(d)}>Сверить показатели</Button>
          </div>
        </Panel>
      ))}
      {docs.data?.some((d) => d.ocrStatus === 'FAILED') && (
        <Alert
          className="mt"
          type="warning"
          message="Распознавание не удалось"
          description={
            <span>
              Заполните значения вручную на шаге{' '}
              <Link to={`/applications/${application.id}/business`}>«Финансы»</Link>.
            </span>
          }
        />
      )}
      <Modal
        width={850}
        title="Сверка финансовых показателей"
        open={!!selected}
        footer={null}
        onCancel={() => setSelected(undefined)}
        destroyOnHidden
      >
        {selected && (
          <OcrForm
            key={selected.extractionId}
            document={selected}
            close={() => setSelected(undefined)}
          />
        )}
      </Modal>
    </>
  );
}
function OcrForm({ document, close }: { document: DocumentItem; close: () => void }) {
  const { application, form: main, flush, replace, version } = useDraft(),
    form = useForm<{ finance: Finance; confirmed: Record<FinanceKey, boolean> }>({
      defaultValues: {
        finance: document.values,
        confirmed: Object.fromEntries(Object.keys(financeFields).map((k) => [k, false])) as Record<
          FinanceKey,
          boolean
        >,
      },
    }),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const submit = form.handleSubmit(async (values) => {
    setError(undefined);
    if (
      !Object.values(values.confirmed).every(Boolean) ||
      Object.keys(financeErrors(values.finance)).length
    ) {
      setError(new Error('Проверьте и подтвердите каждое из восьми значений'));
      return;
    }
    setBusy(true);
    try {
      await flush();
      const fresh = await api.application(application.id);
      if (fresh.version !== version())
        throw new Error('Данные изменились. Сопоставьте версии перед подтверждением OCR.');
      const result = await api.confirmOcr(
        application.id,
        document,
        values.finance,
        values.confirmed,
        fresh.financialVersion,
      );
      replace(result);
      close();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  });
  return (
    <form onSubmit={submit}>
      <p>Источник: {document.name}, страница 1. Любое изменение сбрасывает подтверждение.</p>
      <div className="financial-grid">
        {(Object.entries(financeFields) as [FinanceKey, string][]).map(([k, label]) => (
          <div key={k}>
            <Field
              id={'ocr-' + k}
              label={label}
              hint={'Ваш ввод: ' + main.getValues(`finance.${k}`) + ' ₽'}
            >
              <input
                id={'ocr-' + k}
                inputMode="decimal"
                {...form.register(`finance.${k}`, {
                  onChange: () => form.setValue(`confirmed.${k}`, false),
                })}
              />
            </Field>
            <label className="native-check">
              <input
                type="checkbox"
                aria-label={'Проверено по документу: ' + label}
                {...form.register(`confirmed.${k}`)}
              />
              Проверено по документу
            </label>
          </div>
        ))}
      </div>
      {!!error && <ErrorState error={error} />}
      <Button className="mt" type="primary" htmlType="submit" loading={busy}>
        Подтвердить проверенные значения
      </Button>
    </form>
  );
}
export function FilesPage() {
  const { id = '' } = useParams(),
    docs = useQuery({ queryKey: ['documents', id], queryFn: () => api.documents(id) }),
    [error, setError] = useState<unknown>();
  const download = async (d: DocumentItem) => {
    try {
      const blob = await api.file(d.id),
        url = URL.createObjectURL(blob),
        anchor = window.document.createElement('a');
      anchor.href = url;
      anchor.download = d.name;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(e);
    }
  };
  return (
    <>
      <PageTitle
        title="Документы заявки"
        description="Скачивание доступно после успешной проверки безопасности документа."
      />
      {docs.isPending ? (
        <LoadingState />
      ) : docs.error ? (
        <ErrorState error={docs.error} />
      ) : !docs.data.length ? (
        <EmptyState description="К этой заявке ещё не прикрепляли документы" />
      ) : (
        <Panel>
          {docs.data.map((d) => (
            <div className="file-row" key={d.id}>
              <FileText />
              <div>
                <strong>{d.name}</strong>
                <small>
                  {d.type} · версия {d.objectVersion} · {states[d.status]}
                </small>
                {(!d.canDownload || d.status !== 'CLEAN') && (
                  <small>Скачивание недоступно до успешной проверки.</small>
                )}
              </div>
              <Button
                icon={<Download size={16} />}
                disabled={!d.canDownload || d.status !== 'CLEAN'}
                onClick={() => void download(d)}
              >
                Скачать
              </Button>
            </div>
          ))}
        </Panel>
      )}
      {!!error && <ErrorState error={error} />}
    </>
  );
}
