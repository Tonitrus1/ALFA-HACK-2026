-- ML: записи инференса фиксируются до использования результата (data-model: InferenceRecord).
CREATE TABLE ml.inference_record (
    inference_id            text        PRIMARY KEY,
    request_id              text        NOT NULL UNIQUE,
    application_id          text        NOT NULL,
    financial_snapshot_id   text        NOT NULL,
    feature_snapshot_id     text        NOT NULL,
    feature_snapshot_digest text        NOT NULL,
    score                   numeric(8, 6) NOT NULL CHECK (score >= 0 AND score <= 1),
    score_kind              text        NOT NULL,
    calibration_status      text        NOT NULL,
    release_id              text        NOT NULL,
    model_version           text        NOT NULL,
    mode                    text        NOT NULL CHECK (mode IN ('MODEL', 'CONTRACT_DOUBLE')),
    created_at              timestamptz NOT NULL
);
