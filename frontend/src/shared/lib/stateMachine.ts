import type { Status } from '../types/domain';
// Только временная демомодель. Заменить генерацией из contracts/state-machine.json.
export const demoTransitions: Record<Status, Status[]> = {
  DRAFT: ['SUBMITTED'],
  SUBMITTED: ['PROCESSING'],
  PROCESSING: ['NEEDS_INFORMATION', 'MANUAL', 'DECLINED', 'OFFERED'],
  NEEDS_INFORMATION: ['PROCESSING'],
  MANUAL: [],
  DECLINED: [],
  OFFERED: ['ACCEPTED'],
  ACCEPTED: ['COMPLETED'],
  COMPLETED: [],
};
export const canTransition = (from: Status, to: Status) => demoTransitions[from].includes(to);
