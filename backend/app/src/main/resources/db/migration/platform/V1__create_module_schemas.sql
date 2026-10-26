-- Схемы PostgreSQL по модулям-владельцам (docs/architecture/packages/backend/docs/guide.md, раздел 1).
-- Таблицы создают миграции соответствующих модулей.
CREATE SCHEMA IF NOT EXISTS access;
CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS applications;
CREATE SCHEMA IF NOT EXISTS consents;
CREATE SCHEMA IF NOT EXISTS documents;
CREATE SCHEMA IF NOT EXISTS journey;
CREATE SCHEMA IF NOT EXISTS integration;
CREATE SCHEMA IF NOT EXISTS workspace;
CREATE SCHEMA IF NOT EXISTS ml;
CREATE SCHEMA IF NOT EXISTS kb;
