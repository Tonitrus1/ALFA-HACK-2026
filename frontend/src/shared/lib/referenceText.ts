// Presentation of reference data from the server; identifiers and API values stay unchanged.
export function referenceText(value: string): string {
  return value
    .replace(/\s*\((?:demo|синтетический)\)/gi, '')
    .replace(/Демо ([АБ])/g, 'Компания $1')
    .replace('Синтетический продукт для демонстрации. ', '')
    .replace('Предварительные условия синтетического demo-продукта.', 'Предварительные условия продукта.')
    .replace('Завершить демооформление', 'Завершить оформление');
}
