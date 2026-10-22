-- Синтетический demo-набор (git-and-jury-guide: 2 компании A/B, представитель каждой, отдельный оператор).
-- Только профиль demo. Реальных ИНН, имён и паролей нет. Повторный прогон не дублирует данные.

INSERT INTO access.actor (actor_id, display_name, kind) VALUES
    ('representative-a', 'Представитель компании А (синтетический)', 'REPRESENTATIVE'),
    ('representative-b', 'Представитель компании Б (синтетический)', 'REPRESENTATIVE'),
    ('operator-demo',    'Оператор имитатора банка (синтетический)', 'DEMO_OPERATOR')
ON CONFLICT (actor_id) DO NOTHING;

INSERT INTO access.company (company_id, display_name) VALUES
    ('company-a', 'ООО «Демо А»'),
    ('company-b', 'ООО «Демо Б»')
ON CONFLICT (company_id) DO NOTHING;

INSERT INTO access.company_membership (actor_id, company_id, role) VALUES
    ('representative-a', 'company-a', 'REPRESENTATIVE'),
    ('representative-b', 'company-b', 'REPRESENTATIVE')
ON CONFLICT DO NOTHING;
