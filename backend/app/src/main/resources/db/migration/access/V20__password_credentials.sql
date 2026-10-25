CREATE TABLE access.credential (
    login text PRIMARY KEY,
    actor_id text NOT NULL UNIQUE REFERENCES access.actor(actor_id),
    password_hash text NOT NULL,
    failed_attempts integer NOT NULL DEFAULT 0,
    locked_until timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);
