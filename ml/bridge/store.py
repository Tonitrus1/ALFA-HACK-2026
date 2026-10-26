"""Durable, release-pinned calls; concurrent retries share one committed result."""
from collections.abc import Callable

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from scoring.features import digest


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, dsn):
        self.dsn = dsn

    def connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=1,
                              options='-c statement_timeout=1800 -c lock_timeout=1200')

    def ready(self):
        with self.connect() as db:
            db.execute('select 1 from ml.bridge_call limit 1')

    def get(self, key):
        with self.connect() as db:
            return db.execute('select * from ml.bridge_call where call_key=%s', (key,)).fetchone()

    def call(self, key: str, body: dict, prepare: Callable, execute: Callable):
        fingerprint = digest(body)
        # Commit the exact release/input BEFORE contacting an upstream. Failure never repins a retry.
        with self.connect() as db:
            db.execute('select pg_advisory_xact_lock(hashtextextended(%s, 1))', (key,))
            row = db.execute('select * from ml.bridge_call where call_key=%s', (key,)).fetchone()
            if row is None:
                request = prepare()
                db.execute('insert into ml.bridge_call(call_key,input_hash,request) values(%s,%s,%s)',
                           (key, fingerprint, Jsonb(request)))
            elif row['input_hash'] != fingerprint:
                raise Conflict('Idempotency identity reused with a different input')
        with self.connect() as db:
            db.execute('select pg_advisory_xact_lock(hashtextextended(%s, 1))', (key,))
            row = db.execute('select * from ml.bridge_call where call_key=%s', (key,)).fetchone()
            if row['response'] is not None:
                return row['response']
            response = execute(row['request'])
            db.execute('update ml.bridge_call set response=%s where call_key=%s and response is null',
                       (Jsonb(response), key))
        return response
