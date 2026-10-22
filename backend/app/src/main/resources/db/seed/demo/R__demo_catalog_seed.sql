-- Синтетический каталог demo-policy v1 (backend guide: «Каталог»). Все три продукта требуют
-- восемь подтверждённых финансовых значений DEMO Financial v1. Повторный прогон не дублирует данные.
INSERT INTO catalog.product (product_id, version, name, purpose, min_amount_minor, max_amount_minor,
                             min_months, max_months, min_business_age_months, financial_required,
                             requirements_version, preliminary_disclosure) VALUES
    ('working-capital', 1, 'Оборотный кредит (demo)', 'Пополнение оборотных средств',
     10000000, 500000000, 3, 24, 6, true, 1,
     'Синтетический продукт для демонстрации. Условия предварительные и не являются офертой.'),
    ('credit-line', 1, 'Кредитная линия (demo)', 'Возобновляемое финансирование',
     30000000, 1000000000, 6, 36, 12, true, 1,
     'Синтетический продукт для демонстрации. Условия предварительные и не являются офертой.'),
    ('overdraft', 1, 'Овердрафт (demo)', 'Покрытие кассовых разрывов',
     5000000, 200000000, 1, 12, 12, true, 1,
     'Синтетический продукт для демонстрации. Условия предварительные и не являются офертой.')
ON CONFLICT (product_id, version) DO NOTHING;
