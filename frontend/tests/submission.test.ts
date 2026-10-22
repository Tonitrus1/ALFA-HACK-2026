import { describe, expect, it } from 'vitest';
import { documentReferences, financialSnapshot } from '../src/shared/lib/submission';
import { initialFinance } from '../src/mocks/store';
import { canTransition } from '../src/shared/lib/stateMachine';
describe('отправляемый снимок', () => {
  it('содержит точные копейки, допускает отрицательный капитал', () => {
    const snapshot = financialSnapshot({ ...initialFinance, equity: '-1,01', netProfit: '0,00' });
    expect(snapshot.equity).toBe('-101');
    expect(snapshot.netProfit).toBe('0');
    expect(snapshot.revenue).toBe('1200000000');
  });
  it('не включает небезопасные версии документов', () =>
    expect(
      documentReferences([
        {
          id: 'a',
          applicationId: 'app',
          name: 'a',
          type: 'text/plain',
          size: 1,
          objectVersion: 2,
          status: 'CLEAN',
          ocrStatus: 'FAILED',
          canDownload: true,
        },
        {
          id: 'b',
          applicationId: 'app',
          name: 'b',
          type: 'text/plain',
          size: 1,
          objectVersion: 1,
          status: 'SCANNING',
          ocrStatus: 'PENDING',
          canDownload: false,
        },
      ]),
    ).toEqual([{ documentId: 'a', objectVersion: 2 }]));
  it('не допускает произвольные бизнес-переходы', () => {
    expect(canTransition('MANUAL', 'DECLINED')).toBe(false);
    expect(canTransition('DRAFT', 'COMPLETED')).toBe(false);
    expect(canTransition('PROCESSING', 'NEEDS_INFORMATION')).toBe(true);
  });
});
