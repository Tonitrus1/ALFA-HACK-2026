-- Catalog: версионированные продукты. Версия продукта неизменяема; новая редакция — новая строка.
CREATE TABLE catalog.product (
    product_id              text        NOT NULL,
    version                 bigint      NOT NULL CHECK (version > 0),
    name                    text        NOT NULL,
    purpose                 text,
    min_amount_minor        bigint      NOT NULL CHECK (min_amount_minor >= 0),
    max_amount_minor        bigint      NOT NULL CHECK (max_amount_minor >= min_amount_minor),
    min_months              integer     NOT NULL CHECK (min_months > 0),
    max_months              integer     NOT NULL CHECK (max_months >= min_months),
    min_business_age_months integer     NOT NULL CHECK (min_business_age_months >= 0),
    financial_required      boolean     NOT NULL,
    requirements_version    bigint      NOT NULL CHECK (requirements_version > 0),
    preliminary_disclosure  text        NOT NULL,
    active                  boolean     NOT NULL DEFAULT true,
    created_at              timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (product_id, version)
);
