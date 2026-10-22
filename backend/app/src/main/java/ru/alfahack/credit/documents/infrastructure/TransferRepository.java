package ru.alfahack.credit.documents.infrastructure;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

/** Разрешения загрузки (upload-state с CAS) и скачивания. Гранты хранятся только как SHA-256. */
@Repository
public class TransferRepository {

    public record Upload(
            String uploadId, String transferId, String documentId, String grantHash, String sessionHash,
            String actorId, String companyId, long maxBytes, String state, long version, String clientKey,
            String bodyDigest, Instant expiresAt, Instant createdAt) {
    }

    public record DownloadGrant(
            String transferId, String grantHash, String sessionHash, String documentId, String objectVersion,
            Instant expiresAt) {
    }

    private static final String SELECT_UPLOAD = """
            SELECT upload_id, transfer_id, document_id, grant_hash, session_hash, actor_id, company_id, max_bytes,
                   state, version, client_key, body_digest, expires_at, created_at
            FROM documents.upload
            """;

    private final JdbcClient jdbc;

    public TransferRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<Upload> findUploadByKey(String actorId, String companyId, String clientKey) {
        return jdbc.sql(SELECT_UPLOAD + " WHERE actor_id = :actor AND company_id = :company AND client_key = :key")
                .param("actor", actorId).param("company", companyId).param("key", clientKey)
                .query((rs, row) -> upload(rs)).optional();
    }

    public Optional<Upload> findUpload(String uploadId) {
        return jdbc.sql(SELECT_UPLOAD + " WHERE upload_id = :id").param("id", uploadId)
                .query((rs, row) -> upload(rs)).optional();
    }

    public Optional<Upload> findUploadByTransfer(String transferId) {
        return jdbc.sql(SELECT_UPLOAD + " WHERE transfer_id = :id").param("id", transferId)
                .query((rs, row) -> upload(rs)).optional();
    }

    /** false — ключ идемпотентности уже занят (гонка двух одинаковых запросов). */
    public boolean insertUpload(Upload upload) {
        return jdbc.sql("""
                        INSERT INTO documents.upload (upload_id, transfer_id, document_id, grant_hash, session_hash,
                            actor_id, company_id, max_bytes, state, version, client_key, body_digest, expires_at,
                            created_at)
                        VALUES (:id, :transfer, :document, :grant, :session, :actor, :company, :maxBytes, 'PENDING', 1,
                                :key, :digest, :expiresAt, :createdAt)
                        ON CONFLICT (actor_id, company_id, client_key) DO NOTHING
                        """)
                .param("id", upload.uploadId())
                .param("transfer", upload.transferId())
                .param("document", upload.documentId())
                .param("grant", upload.grantHash())
                .param("session", upload.sessionHash())
                .param("actor", upload.actorId())
                .param("company", upload.companyId())
                .param("maxBytes", upload.maxBytes())
                .param("key", upload.clientKey())
                .param("digest", upload.bodyDigest())
                .param("expiresAt", Timestamp.from(upload.expiresAt()))
                .param("createdAt", Timestamp.from(upload.createdAt()))
                .update() == 1;
    }

    /** Повтор intent выдаёт новый грант той же ожидающей загрузке (старый перестаёт действовать). */
    public boolean rotateGrant(String uploadId, String grantHash, Instant expiresAt) {
        return jdbc.sql("""
                        UPDATE documents.upload SET grant_hash = :grant, expires_at = :expiresAt, version = version + 1
                        WHERE upload_id = :id AND state = 'PENDING'
                        """)
                .param("grant", grantHash).param("expiresAt", Timestamp.from(expiresAt)).param("id", uploadId)
                .update() == 1;
    }

    /** Единый CAS upload-state: финализация и отмена конкурируют за одну версию. */
    public boolean transitionUpload(String uploadId, long expectedVersion, String to) {
        return jdbc.sql("""
                        UPDATE documents.upload SET state = :to, version = version + 1
                        WHERE upload_id = :id AND version = :version AND state = 'PENDING'
                        """)
                .param("to", to).param("id", uploadId).param("version", expectedVersion)
                .update() == 1;
    }

    public void insertDownloadGrant(DownloadGrant grant, Instant now) {
        jdbc.sql("""
                        INSERT INTO documents.download_grant (transfer_id, grant_hash, session_hash, document_id,
                                                              object_version, expires_at, created_at)
                        VALUES (:transfer, :grant, :session, :document, :objectVersion, :expiresAt, :now)
                        """)
                .param("transfer", grant.transferId())
                .param("grant", grant.grantHash())
                .param("session", grant.sessionHash())
                .param("document", grant.documentId())
                .param("objectVersion", grant.objectVersion())
                .param("expiresAt", Timestamp.from(grant.expiresAt()))
                .param("now", Timestamp.from(now))
                .update();
    }

    public Optional<DownloadGrant> findDownloadGrant(String transferId) {
        return jdbc.sql("""
                        SELECT transfer_id, grant_hash, session_hash, document_id, object_version, expires_at
                        FROM documents.download_grant WHERE transfer_id = :id
                        """)
                .param("id", transferId)
                .query((rs, row) -> new DownloadGrant(
                        rs.getString("transfer_id"), rs.getString("grant_hash"), rs.getString("session_hash"),
                        rs.getString("document_id"), rs.getString("object_version"),
                        rs.getTimestamp("expires_at").toInstant()))
                .optional();
    }

    private static Upload upload(ResultSet rs) throws SQLException {
        return new Upload(
                rs.getString("upload_id"), rs.getString("transfer_id"), rs.getString("document_id"),
                rs.getString("grant_hash"), rs.getString("session_hash"), rs.getString("actor_id"),
                rs.getString("company_id"), rs.getLong("max_bytes"), rs.getString("state"), rs.getLong("version"),
                rs.getString("client_key"), rs.getString("body_digest"), rs.getTimestamp("expires_at").toInstant(),
                rs.getTimestamp("created_at").toInstant());
    }
}
