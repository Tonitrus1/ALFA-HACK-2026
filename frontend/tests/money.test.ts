import { describe, expect, it } from 'vitest';
import { formatAmount, fromKopecks, money, toKopecks } from '../src/shared/lib/money';
describe('разряды в денежных полях', () => {
  it.each([
    ['3000000', '3 000 000'],
    ['3\u00a0000\u202f000,01', '3 000 000,01'],
    ['-1234567.89', '-1 234 567.89'],
    ['999999999999999999,99', '999 999 999 999 999 999,99'],
    ['1234,', '1 234,'],
    ['0,00', '0,00'],
    ['', ''],
    ['-', '-'],
    ['1e6', '1e6'],
    ['1,2,3', '1,2,3'],
  ])('%j → %j', (input, formatted) => expect(formatAmount(input)).toBe(formatted));
  it('сохраняет точное значение в копейках', () => {
    for (const value of ['3000000', '-1234567,89', '999999999999999999,99'])
      expect(toKopecks(formatAmount(value), true)).toBe(toKopecks(value, true));
  });
});
describe('точные денежные преобразования', () => {
  it.each([
    ['0', '0'],
    ['0,01', '1'],
    ['12.10', '1210'],
    ['1 234 567,89', '123456789'],
    ['999999999999999999,99', '99999999999999999999'],
  ])('%s → %s', (input, result) => expect(toKopecks(input)).toBe(result));
  it('разрешает отрицательные показатели явно', () => {
    expect(toKopecks('-1,01', true)).toBe('-101');
    expect(() => toKopecks('-1')).toThrow();
    expect(fromKopecks('-101')).toBe('-1,01');
  });
  it.each(['', ' ', '1.001', 'NaN', 'Infinity', '1e6', '1,2,3'])('отклоняет %j', (input) =>
    expect(() => toKopecks(input)).toThrow(),
  );
  it('форматирует без потери точности', () =>
    expect(money('123456789')).toBe('1\u00a0234\u00a0567,89\u00a0₽'));
});
