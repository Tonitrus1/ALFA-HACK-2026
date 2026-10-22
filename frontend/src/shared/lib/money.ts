export function toKopecks(input: string, allowNegative = false): string {
  const value = input.replace(/[\s\u00a0]/g, '').replace(',', '.');
  if (!/^-?\d+(?:\.\d{1,2})?$/.test(value))
    throw new Error('Введите сумму с точностью до двух знаков');
  const negative = value.startsWith('-');
  if (negative && !allowNegative) throw new Error('Значение не может быть отрицательным');
  const [whole, fraction = ''] = value.replace('-', '').split('.');
  const total = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  return (negative ? -total : total).toString();
}
export function fromKopecks(value: string): string {
  const n = BigInt(value),
    positive = n < 0n ? -n : n;
  return `${n < 0n ? '-' : ''}${positive / 100n},${(positive % 100n).toString().padStart(2, '0')}`;
}
export function money(value: string): string {
  const [integer, fraction] = fromKopecks(value).split(',');
  return (
    integer.replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0') +
    (fraction === '00' ? '' : ',' + fraction) +
    '\u00a0₽'
  );
}
