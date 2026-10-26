import type { Status } from '../types/domain';
// Только временная демомодель. Заменить генерацией из contracts/state-machine.json.
export const demoTransitions: Record<Status, Status[]> = {
  DRAFT: ['SUBMITTED'],
  SUBMITTED: ['REVIEW'],
  REVIEW: ['NEEDS_INFO', 'MANUAL', 'DECLINED', 'APPROVED'],
  NEEDS_INFO: ['REVIEW'],
  MANUAL: [],
  DECLINED: [],
  APPROVED: ['ACCEPTED'],
  ACCEPTED: ['COMPLETED'],
  COMPLETED: [], ALTERNATIVE: ['ACCEPTED'], CANCELLED: [], EXPIRED: [],
};
export const canTransition = (from: Status, to: Status) => demoTransitions[from]?.includes(to) ?? false;
