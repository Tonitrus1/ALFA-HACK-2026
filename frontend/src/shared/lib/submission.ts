import type { Application, DocumentItem, Finance, FinanceKey } from '../types/domain';
import { financeFields, signedFields } from '../types/domain';
import { toKopecks } from './money';
export const documentReferences = (documents: DocumentItem[]) =>
  documents
    .filter((d) => d.status === 'CLEAN')
    .map((d) => ({ documentId: d.id, objectVersion: d.objectVersion }));
export function financialSnapshot(finance: Finance): Finance {
  return Object.fromEntries(
    (Object.keys(financeFields) as FinanceKey[]).map((k) => [
      k,
      toKopecks(finance[k], signedFields.includes(k)),
    ]),
  ) as Finance;
}
export function submissionBody(application: Application, documents: DocumentItem[]) {
  if (documents.some((d) => d.status === 'SCANNING' || d.status === 'QUARANTINE'))
    throw new Error('Дождитесь проверки загруженных документов');
  return {
    financialVersion: application.financialVersion,
    financialSnapshot: financialSnapshot(application.draft.finance),
    documentReferences: documentReferences(documents),
  };
}
