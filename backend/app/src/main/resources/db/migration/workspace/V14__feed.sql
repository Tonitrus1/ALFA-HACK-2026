CREATE TABLE workspace.feed_state (
 actor_id text NOT NULL, company_id text NOT NULL,
 preferences_version bigint NOT NULL DEFAULT 0, saved_version bigint NOT NULL DEFAULT 0,
 preferences jsonb NOT NULL DEFAULT '{}'::jsonb,
 PRIMARY KEY(actor_id,company_id)
);
CREATE TABLE workspace.feed_selection (
 selection_id text PRIMARY KEY, actor_id text NOT NULL, company_id text NOT NULL,
 preferences_version bigint NOT NULL, catalog_digest text NOT NULL,
 issued jsonb NOT NULL DEFAULT '[]'::jsonb
);
CREATE TABLE workspace.feed_page (
 cursor text PRIMARY KEY, selection_id text,
 actor_id text NOT NULL, company_id text NOT NULL,
 kind text NOT NULL CHECK(kind IN ('FEED','SAVED')),
 state_version bigint NOT NULL, catalog_digest text NOT NULL,
 page_offset integer NOT NULL DEFAULT 0,
 exposure_id text NOT NULL UNIQUE, response jsonb,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE workspace.feed_event (
 actor_id text NOT NULL, company_id text NOT NULL, event_id text NOT NULL,
 fingerprint text NOT NULL, payload jsonb NOT NULL,
 PRIMARY KEY(actor_id,company_id,event_id)
);
CREATE TABLE workspace.feed_reaction (
 actor_id text NOT NULL, company_id text NOT NULL, content_id text NOT NULL,
 reaction text CHECK(reaction IN ('HELPFUL','NOT_INTERESTED')),
 viewed boolean NOT NULL DEFAULT false,
 reaction_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(actor_id,company_id,content_id)
);
