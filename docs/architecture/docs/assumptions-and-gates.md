# Допущения и внешние условия

## Что принято

Команда 3-5 человек, окно 48-72 часа; обязательны 4 реальные ML-функции, но не полный MLOps runtime. Наличие NVIDIA известно, точная модель/VRAM нет. Поэтому обязательный профиль CPU; GPU только дополнение. Все demonstration users/documents/companies/financials synthetic, bank APIs simulated. Исследовательское обучение может использовать атрибутированный открытый dataset вне пользовательского seed.

Язык документации русский. Часовой пояс пользовательских примеров Asia/Yekaterinburg; сервер хранит UTC и ISO8601, business validUntil проверяется банковским clock. Значения и горизонты demo-policy не являются правилами Альфа-Банка.

## Условия допуска

| Gate | Владелец | Для чего обязательно | Критерий закрытия |
| --- | --- | --- | --- |
| G01 | Integration + IAM owner | Банк | Протокол identity/company/roles, усиленная web-auth и отрицательные access tests |
| G02 | Bank adapter owner | Банк | Идемпотентные команды, версии, полный журнал результатов и сверка потерянного ответа |
| G03 | Data/privacy owner | Банк | Утверждённые цели, субъекты, полномочия, использование данных и отзыв |
| G04 | Security/platform | Банк | Хранение, ключи, backup encryption/access, retention/deletion и threat review |
| G05 | Integration + ML | MVP и банк | Exact versions/OCI digests/model revisions/лицензии/notices; CPU boot и CVE review |
| G06 | Platform + bank adapter | Банк | Репетиция DR с потерей локальных mapping и внешним журналом окна RPO |
| G07 | Platform + QA | Банк | Измеренные SLO/capacity/failover/restore; три домена отказа |
| G08 | Risk/content/product | Банк | Согласованные labels, модельная/продуктовая валидация и independent release approval |

Для local-mvp G01/G02 реализуются явно обозначенными симуляторами, G03/G04 - синтетикой и ограниченной средой, G06/G07 - только соответствующими локальными restart/resource smoke. Это не закрывает банковские gates. G05 обязателен до любого демонстрационного runtime-релиза; сейчас стоит NOT_EXECUTED. Модельные метрики и лицензионные файлы нуждаются в проверке фактически включённых артефактов, не только названий проектов.
