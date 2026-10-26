# Приёмка будущего приложения

Все сценарии имеют статус NOT_EXECUTED_NO_APPLICATION. Здесь задана ожидаемая проверка; статический валидатор не подменяет её запуск.

## A01. Основной путь

Тип: E2E; задачи: P05, P06, P17.

Дано: client A with all confirmed finance.

Действие: submit, receive offer, accept, operator completes.

Ожидается: one case, no real money, COMPLETED; IDs survive restart.

## A02. Финансовое уточнение

Тип: E2E; задачи: P08, P09, P15.

Дано: OPEN RFI for netProfit only.

Действие: save/confirm/resubmit.

Ожидается: only netProfit changes; new financial snapshot; original immutable.

## A03. Отказ

Тип: E2E; задачи: P15.

Дано: policy DQ passed; debt ratio >=0.9.

Действие: review.

Ожидается: DECLINED safe reason; no offer.

## A04. Другие условия

Тип: E2E; задачи: P15, P16.

Дано: eligible request above turnover cap.

Действие: review.

Ожидается: ALTERNATIVE complete offer; no silent change of application.

## A05. Двойная отправка

Тип: TRANSACTION; задачи: P18.

Дано: same command key and body.

Действие: concurrent submit x2.

Ожидается: same receipt, one case; DB unique constraint.

## A06. Ключ с иным содержимым

Тип: TRANSACTION; задачи: P18.

Дано: stored key for original body.

Действие: retry with changed body.

Ожидается: 409 IDEMPOTENCY_CONFLICT, no side effect.

## A07. Конфликт черновика

Тип: E2E; задачи: P08, P09.

Дано: two ETags.

Действие: save from stale tab.

Ожидается: 409/412 per endpoint; local text retained.

## A08. Смена компании

Тип: SECURITY; задачи: P18.

Дано: tab A has contextVersion 1.

Действие: tab B switches company; A mutates.

Ожидается: 409 context changed; no A payload stored in B.

## A09. Чужие объекты

Тип: SECURITY; задачи: P18.

Дано: user A knows B application/file/message IDs.

Действие: read/mutate/download/history.

Ожидается: 404 safe denial, no data leak or timing oracle detail.

## A10. CSRF

Тип: SECURITY; задачи: P18.

Дано: valid cookie but no token.

Действие: POST/PUT/PATCH/DELETE.

Ожидается: 403, including binary upload grant endpoints.

## A11. Истёкшее предложение

Тип: TRANSACTION; задачи: P18.

Дано: offer expired by bank clock.

Действие: accept or stale client double click.

Ожидается: first new command rejected; replay existing success returned.

## A12. Гонка отмены и принятия

Тип: TRANSACTION; задачи: P18.

Дано: withdraw and accept concurrent.

Действие: bank atomic transition.

Ожидается: one winning state; never both accepted and cancelled.

## A13. Небезопасный файл

Тип: SECURITY; задачи: P10, P13.

Дано: EICAR/unsupported mime/oversize/polyglot.

Действие: upload and scan.

Ожидается: not CLEAN; no OCR/download to client; safe audit.

## A14. AV недоступен

Тип: FAILURE; задачи: P18.

Дано: quarantined upload.

Действие: scanner unavailable.

Ожидается: quarantine preserved; manual form path available, no unscanned file accepted.

## A15. Старая аренда OCR

Тип: TRANSACTION; задачи: P10, P13.

Дано: new generation/token issued.

Действие: old worker submits result.

Ожидается: rejected; no field/confirmation overwritten.

## A16. OCR без подтверждения

Тип: E2E; задачи: P08, P09, P13.

Дано: READY extraction with high confidence.

Действие: submit.

Ожидается: blocked until all 8 values reviewed; confidence not consent.

## A17. OCR сломан

Тип: FAILURE; задачи: P13, P16.

Дано: CLEAN supported image.

Действие: worker fails.

Ожидается: manual financial entry works; no data fabricated.

## A18. Risk недоступен

Тип: FAILURE; задачи: P11, P15.

Дано: package and features committed.

Действие: timeout/error/audit insert fails.

Ожидается: MANUAL; no automated DECLINED due to outage.

## A19. Ranker возвращает чужой ID

Тип: SECURITY; задачи: P12, P15.

Дано: eligible candidate set.

Действие: invalid/partial permutation.

Ожидается: RULES and valid set; nextAction stays first.

## A20. RAG без источников

Тип: E2E; задачи: P14, P16.

Дано: empty or irrelevant accessible corpus.

Действие: ask question.

Ожидается: INSUFFICIENT_EVIDENCE, no invented rate or approval.

## A21. RAG prompt injection

Тип: SECURITY; задачи: P14.

Дано: KB chunk asks to reveal secrets.

Действие: retrieve/generate.

Ожидается: no tools/credentials/credit command; safe source-bound answer or refusal.

## A22. Отзыв знания в полёте

Тип: SECURITY; задачи: P14, P15.

Дано: RAG already generating from doc.

Действие: revoke then publish response.

Ожидается: post-generation epoch check suppresses revoked answer/citation, history also filtered.

## A23. RAG timeout

Тип: FAILURE; задачи: P14, P16.

Дано: valid sources; LLM exceeds45s.

Действие: request timeout at60s.

Ожидается: SEARCH_ONLY with valid source links; not claimed generated answer.

## A24. Потерянный HTTP-ответ

Тип: RECOVERY; задачи: P18.

Дано: server committed command.

Действие: client reconnects.

Ожидается: lookup operation by saved client key; no new command key.

## A25. Перезапуск

Тип: RECOVERY; задачи: P19.

Дано: draft, files, operation, queue committed.

Действие: restart all containers without deleting volumes.

Ожидается: same data; jobs leased again, one business effect.

## A26. SSE gap

Тип: RECOVERY; задачи: P16, P19.

Дано: missing cursor /expired journal.

Действие: reconnect.

Ожидается: snapshot barrier then refetch resources and all pages; no max100 data loss.

## A27. Денежные поля

Тип: DATA; задачи: P08, P11.

Дано: RUB decimals and negative equity.

Действие: parse, save, feature build.

Ожидается: minor integer, no float cents, negative capital allowed; no division by0.

## A28. Train/serve parity

Тип: ML; задачи: P11.

Дано: same frozen financial input.

Действие: batch and online feature build.

Ожидается: 8 ratios and missing masks within1e-8; source availability <=asOf.

## A29. ML honesty

Тип: ML; задачи: P11, P12.

Дано: no behavior dataset / no bank labels.

Действие: show recommendations/risk.

Ожидается: semantic content model, BANKRUPTCY_PROXY; no fabricated PD or A/B lift.

## A30. Синтетика и обычный ПК

Тип: LAUNCH; задачи: P20.

Дано: fresh supported CPU environment.

Действие: launch documented release.

Ожидается: all4 ML functions run locally, no paid/private API; actual resource/time report.

## A31. Клавиатура и понимание

Тип: UX; задачи: P19.

Дано: new tester with keyboard.

Действие: complete form and RFI.

Ожидается: labels/focus/errors readable; tester names status and next step.

## A32. История и полнота команд

Тип: RECOVERY; задачи: P18.

Дано: receipt completed before reload.

Действие: reload and query operation list.

Ожидается: completed and active within dedup retention visible; no externalRequestId leaked.

## A33. Три продукта и eligibility

Тип: E2E; задачи: P12, P15.

Дано: fixed product catalog.

Действие: request outside bounds.

Ожидается: ineligible excluded; unknown data prompts clarification; no invented eligibility.

## A34. Нет вредной утечки в логах

Тип: SECURITY; задачи: P18.

Дано: requests with docs, tokens and chat text.

Действие: trigger errors.

Ожидается: metadata trace only; no full bodies/session tokens; restricted audit.

## A35. Чистая миграция

Тип: LAUNCH; задачи: P03, P20.

Дано: empty DB then populated DB.

Действие: start app twice.

Ожидается: Flyway ordered, no data reset/reseed duplication.

## A36. Откат модели

Тип: RECOVERY; задачи: P11, P14, P17.

Дано: new bundle fails health.

Действие: operator selects previous full digest bundle.

Ожидается: same feature schema/preprocessor model; revoked KB not reactivated.

## A37. Промышленная нагрузка

Тип: TARGET_ONLY; задачи: P24.

Дано: bank-target built and approved.

Действие: 1k then5k RPS and failure injection.

Ожидается: measure target SLO and capacity; not required in hackathon validation.

## A38. Выбор провайдера без скрытой подмены

Дано: valid local binding manifest.

Действие: unknown provider / missing capability / forbidden pairing.

Ожидается: startup rejected; exact selected providers in protected engineering report.

Задачи: P25, P26. NOT_EXECUTED_NO_APPLICATION.

## A39. Общий контракт адаптеров

Дано: fixed synthetic fixtures and local implementations.

Действие: run capability suite; repeat against real provider only when enabled.

Ожидается: common invariants pass; provider-specific limitations recorded; disabled real adapter remains NOT_EXECUTED.

Задачи: P25, P26, P27. NOT_EXECUTED_NO_APPLICATION.

## A40. Отказ обязательного хранилища

Дано: selected session store / KB authority / file safety.

Действие: dependency unavailable or timeout.

Ожидается: deny protected operation / suppress RAG / retain quarantine; no automatic provider fallback.

Задачи: P18, P25. NOT_EXECUTED_NO_APPLICATION.

## A41. Достоверная архитектура на защите

Дано: release commit and measured runtime evidence.

Действие: compare diagram, provider selection and demo actions.

Ожидается: REAL_CONNECTED only with evidence digest; LOCAL_SUBSTITUTE and TEST_DOUBLE explicit; 4 ML functions run real models.

Задачи: P21, P22, P26. NOT_EXECUTED_NO_APPLICATION.

## A42. Feast-граница без чтения будущего

Дано: two source versions with different availableAt and one immutable submission.

Действие: historical(asOf) and get(submissionSnapshot).

Ожидается: future version excluded; submitted score pinned; Feast online-latest never replaces historical join.

Задачи: P11, P26. NOT_EXECUTED_NO_APPLICATION.

## A43. Qdrant-граница и фильтрация

Дано: two companies plus revoked KB version.

Действие: query NumPy and optional real Qdrant using allowlist.

Ожидается: same permission constraints; recall/score tolerance measured separately; no claim ANN is bit-identical.

Задачи: P14, P26, P27. NOT_EXECUTED_NO_APPLICATION.
