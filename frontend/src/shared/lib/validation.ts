import { z } from 'zod';
import { financeFields, signedFields } from '../types/domain';
import { toKopecks } from './money';
export const needSchema = z.object({
  purpose: z.string().min(1, 'Выберите цель'),
  amount: z.string().refine((v) => {
    try {
      const n = BigInt(toKopecks(v));
      return n >= 10000000n && n <= 5000000000n;
    } catch {
      return false;
    }
  }, 'От 100 000 до 50 000 000 ₽'),
  months: z.coerce.number({error:'Укажите срок в месяцах'}).int('Укажите целое число месяцев').min(1,'Минимальный срок — 1 месяц').max(36,'Максимальный срок — 36 месяцев'),
});
export function financeErrors(finance: Record<string, string>): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const key of Object.keys(financeFields)) {
    try {
      toKopecks(finance[key] ?? '', signedFields.includes(key as keyof typeof financeFields));
    } catch (e) {
      errors[key] = (e as Error).message;
    }
  }
  return errors;
}
