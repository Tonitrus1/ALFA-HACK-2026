# Контрактные решения и совместимость

## Нормативный источник

contracts/public.openapi.json - единственный редактируемый клиентский OpenAPI 3.1.0, версия 1.4.0-design, 60 операций. contracts/internal.openapi.json - внутренние границы, contracts/demo.openapi.json - 6 изолированных demo-операций. API-копии в packages/*/api генерируются и проверяются по SHA-256. Ручное редактирование копий запрещено.

49 baseline + 11 ML-дополнений сохранены: 6 операций финансовой формы/RFI, 3 assistant, recommendation-feedback и чтение KB. Не добавлять второй independent API для того же пользовательского действия. Общий Error и MLError сохранены как имена DTO; обработка frontend нормализует их в единый safe view.

## Принятые изменения относительно прежнего preview

- Submit/InformationResponse требуют financialStatementVersion для всех трёх demo-продуктов. financialSnapshotId принимает только серверный response/пакет, не клиентский command.
- ReportingStandard в MVP только DEMO; RSBU/IFRS отклоняются до отдельного mapping.
- RecommendationList/Feed требуют rankingMetadata; PRODUCT дополнительно требует eligibilityVersion на серверной проверке.
- CreditPackage.SUBMISSION/AMENDMENT содержат financialSnapshotId/financialStatementVersion и полную неизменяемую financialStatement. FeatureSnapshotInput несёт эти значения и digest от адаптера к feature-builder; произвольного чтения текущих анкет нет. Эти поля неизменяемы после commit.
- Старые internal risk v1 и feed/ranking v1 исключены; risk/rankings v2 имеют namespace ML для DTO без столкновения с прежними именами.
- Добавлены GET feature-snapshot и POST assistant/answers; RankingRequest дополнен текстами контекста и кандидатов. Это две новые внутренние операции, число публичных остаётся 60.
- Для RAG общий deadline60 с/генерация 45 с/UI65 с. Для локального ranker2 с, risk3 с. Target latency остаётся отдельной целью.

## Семантика, которую не выражает одна JSON Schema

Сравнение company/subject с session identity, актуальность ролей и contextVersion; If-Match и CAS; принадлежность точных documentReferences; совпадение financial confirmation и сохранённого ввода; незапрошенные RFI-поля; exact permutation кандидатов; наличие источника в текущем allowlist; snapshot digest и availableAt≤asOf - серверные инварианты. Для них поставляются semantic fixtures и приёмочные сценарии. Положительный schema fixture не доказывает их реализацию.

Credit events v1 и ML events v1 хранятся отдельными схемами: 16 и 9 типов. Payload credit event не менялся: содержит ссылки на пакет; новые финансовые данные доступны по версии пакета. Поэтому фиктивная event v2 не создаётся. Добавление полей в строгий payload впоследствии требует новой wire-version/topic, а не обещания безусловной совместимости.

## Переход с предыдущих пакетов

Приложения и live consumers нет; согласовать all-at-once изменение генераторов типов и client/adapter ports в P01/P02. Схема 1.4 - не production migration. Если появится живой 1.2 consumer, этот порядок запрещён: нужен отдельный план coexistence и сохранения семантики.

Старые output/architecture-v2, credit-workspace-* и architecture-review считаются историческими входами. Их материалы сохранены в evidence/originals.zip и не являются нормативным текущим API. Старые скрипты продолжают собирать только исторические пакеты. Для текущего комплекта использовать sources/build.py; он не читает соседние исходники и не восстанавливает старые preview-флаги.
