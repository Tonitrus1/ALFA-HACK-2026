# Проверенные технические источники

Проверено 20 октября 2026 года. Факты документации не означают успешной сборки приложения. Выводы и ограничения сохранены в evidence/technical-evidence.json.

## S01. Spring Boot requirements

[Spring Boot requirements](https://docs.spring.io/spring-boot/system-requirements.html)

Boot4.1.1 supports Java21; Maven>=3.6.3; this is not an application build.

## S02. Spring Modulith compatibility

[Spring Modulith compatibility](https://docs.spring.io/spring-modulith/reference/appendix.html)

table does not confirm 2.1/4.1; optional target dependency only.

## S03. PostgreSQL support

[PostgreSQL support](https://www.postgresql.org/support/versioning/)

17 branch supported; page lists17.11; patch/digest verified at image freeze.

## S04. React versions

[React versions](https://react.dev/versions)

19.3.0 documented; exact frontend lock generated at implementation.

## S05. Node releases

[Node releases](https://nodejs.org/en/about/previous-releases)

Node24 is LTS; exact patch pinned at P02.

## S06. Qwen model card

[Qwen model card](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct)

Apache2.0; Russian listed; no in-domain quality guarantee.

## S07. Official Qwen GGUF

[Official Qwen GGUF](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF)

Q4_K_M supported by official model repository.

## S08. E5 model card

[E5 model card](https://huggingface.co/intfloat/multilingual-e5-small/raw/main/README.md)

MIT; multilingual; query/passage prefixes and normalization required.

## S09. llama.cpp Docker

[llama.cpp Docker](https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md)

CPU server image plus optional CUDA; pin immutable digest, never latest.

## S10. Tesseract models

[Tesseract models](https://tesseract-ocr.github.io/tessdoc/Data-Files.html)

tessdata_fast rus+eng for bounded synthetic form.

## S11. UCI dataset365

[UCI dataset365](https://archive.ics.uci.edu/dataset/365/polish+companies+bankruptcy+data)

CCBY4.0; 5year5910 samples/410 positive; bankruptcy within1year, not bank PD.

## S12. Docker profiles

[Docker profiles](https://docs.docker.com/compose/how-tos/profiles/)

profiles opt in extra services; readiness still needs healthchecks.

## S13. FastAPI releases

[FastAPI releases](https://fastapi.tiangolo.com/release-notes/)

pin selected Python3.12 compatible release with Pydantic2 at P02.

## S14. Logistic regression

[Logistic regression](https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression)

baseline algorithm, not validation of bank risk quality.

## Дополнение 1.5: границы адаптеров

[Qdrant filtering](https://qdrant.tech/documentation/search/filtering/): фильтры payload/ID позволяют ограничить поиск разрешёнными refs. Права и актуальный отзыв остаются за backend. [Feast retrieval](https://docs.feast.dev/getting-started/concepts/feature-retrieval): historical и online retrieval - разные механизмы; online latest не заменяет исторический join. [Redis Java Lettuce](https://redis.io/docs/latest/develop/clients/lettuce/): официальный Java client; точная пара SDK/server и Spring BOM проверяется при P02/P27. [MLflow workflow](https://mlflow.org/docs/latest/ml/model-registry/workflow/): registry/aliases связываются с версиями; наш controller дополнительно закрепляет digest и approval перед активацией.

Проверено 20.10.2026. Это основание для проектного mapping, а не подтверждение совместимости ещё не собранных адаптеров. Локальные замены являются собственными архитектурными решениями и не заявляются официальными эмуляторами этих продуктов.
