-- Catalog: требования к документам версии продукта (requirementsVersion продукта).
CREATE TABLE catalog.document_requirement (
    product_id               text    NOT NULL,
    product_version          bigint  NOT NULL,
    requirement_id           text    NOT NULL,
    title                    text    NOT NULL,
    reason                   text    NOT NULL,
    required                 boolean NOT NULL,
    allowed_content_types    text[]  NOT NULL,
    max_bytes                integer NOT NULL CHECK (max_bytes BETWEEN 1 AND 10485760),
    max_pages_for_extraction integer NOT NULL CHECK (max_pages_for_extraction BETWEEN 1 AND 20),
    PRIMARY KEY (product_id, product_version, requirement_id),
    FOREIGN KEY (product_id, product_version) REFERENCES catalog.product (product_id, version)
);
