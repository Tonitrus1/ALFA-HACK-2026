-- Access: участники, компании, членство с ролями и серверные сессии (data-model: Session).

CREATE TABLE access.actor (
    actor_id      text        PRIMARY KEY,
    display_name  text        NOT NULL,
    kind          text        NOT NULL CHECK (kind IN ('REPRESENTATIVE', 'DEMO_OPERATOR')),
    -- Увеличение auth_epoch мгновенно отзывает все сессии участника.
    auth_epoch    bigint      NOT NULL DEFAULT 1 CHECK (auth_epoch > 0),
    disabled      boolean     NOT NULL DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE access.company (
    company_id        text        PRIMARY KEY,
    display_name      text        NOT NULL,
    tax_id            text,
    source_updated_at timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE access.company_membership (
    actor_id   text        NOT NULL REFERENCES access.actor (actor_id),
    company_id text        NOT NULL REFERENCES access.company (company_id),
    role       text        NOT NULL CHECK (role IN ('REPRESENTATIVE')),
    granted_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (actor_id, company_id, role)
);

CREATE INDEX company_membership_company_idx ON access.company_membership (company_id);

CREATE TABLE access.session (
    -- SHA-256 токена cookie; сам токен не хранится.
    session_hash        text        PRIMARY KEY CHECK (length(session_hash) = 64),
    actor_id            text        NOT NULL REFERENCES access.actor (actor_id),
    selected_company_id text        REFERENCES access.company (company_id),
    context_version     bigint      NOT NULL DEFAULT 1 CHECK (context_version > 0),
    csrf_token          text        NOT NULL,
    auth_epoch          bigint      NOT NULL CHECK (auth_epoch > 0),
    created_at          timestamptz NOT NULL,
    expires_at          timestamptz NOT NULL,
    revoked_at          timestamptz,
    version             bigint      NOT NULL DEFAULT 1 CHECK (version > 0),
    CHECK (expires_at > created_at)
);

CREATE INDEX session_actor_idx ON access.session (actor_id);
CREATE INDEX session_expires_idx ON access.session (expires_at);
