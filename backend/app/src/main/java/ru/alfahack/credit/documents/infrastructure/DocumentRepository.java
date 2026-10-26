package ru.alfahack.credit.documents.infrastructure;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import ru.alfahack.credit.documents.application.DocumentView;

@Repository
public class DocumentRepository {

    private static final String SELECT = """
            SELECT document_id, application_id, company_id, requirement_id, requirements_version, document_type,
                   file_name, declared_mime_type, declared_size_bytes, content_type, size_bytes, sha256, object_id,
                   object_version, scan_state, extraction_state, extraction_id, max_pages, replaces_document_id,
                   version, created_by, created_at, updated_at
            FROM documents.document
            """;

    private final JdbcClient jdbc;

    public DocumentRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<DocumentView> find(String documentId) {
        return jdbc.sql(SELECT + " WHERE document_id = :id").param("id", documentId)
                .query((rs, row) -> map(rs)).optional();
    }

    public Optional<DocumentView> lock(String documentId) {
        return jdbc.sql(SELECT + " WHERE document_id = :id FOR UPDATE").param("id", documentId)
                .query((rs, row) -> map(rs)).optional();
    }

    public List<DocumentView> listForApplication(String applicationId, Instant afterCreatedAt, String afterId, int limit) {
        return jdbc.sql(SELECT + """
                        WHERE application_id = :application
                          AND (CAST(:after AS timestamptz) IS NULL
                               OR (created_at, document_id) > (CAST(:after AS timestamptz), :afterId))
                        ORDER BY created_at, document_id
                        LIMIT :limit
                        """)
                .param("application", applicationId)
                .param("after", afterCreatedAt == null ? null : Timestamp.from(afterCreatedAt))
                .param("afterId", afterId)
                .param("limit", limit)
                .query((rs, row) -> map(rs))
                .list();
    }

    public void insert(DocumentView document) {
        jdbc.sql("""
                        INSERT INTO documents.document (document_id, application_id, company_id, requirement_id,
                            requirements_version, document_type, file_name, declared_mime_type, declared_size_bytes,
                            scan_state, extraction_state, max_pages, replaces_document_id, version, created_by,
                            created_at, updated_at)
                        VALUES (:id, :application, :company, :requirement, :requirementsVersion, :type, :fileName,
                                :mime, :size, 'UPLOADING', 'NOT_REQUESTED', :maxPages, :replaces, 1, :createdBy,
                                :now, :now)
                        """)
                .param("id", document.documentId())
                .param("application", document.applicationId())
                .param("company", document.companyId())
                .param("requirement", document.requirementId())
                .param("requirementsVersion", document.requirementsVersion())
                .param("type", document.documentType())
                .param("fileName", document.fileName())
                .param("mime", document.declaredMimeType())
                .param("size", document.declaredSizeBytes())
                .param("maxPages", document.maxPages())
                .param("replaces", document.replacesDocumentId())
                .param("createdBy", document.createdBy())
                .param("now", Timestamp.from(document.createdAt()))
                .update();
    }

    /** UPLOADING → QUARANTINED с точной версией объекта. */
    public boolean markQuarantined(String documentId, String objectId, String objectVersion, String contentType,
                                   long size, String sha256, Instant now) {
        return jdbc.sql("""
                        UPDATE documents.document
                        SET scan_state = 'QUARANTINED', object_id = :objectId, object_version = :objectVersion,
                            content_type = :contentType, size_bytes = :size, sha256 = :sha, version = version + 1,
                            updated_at = :now
                        WHERE document_id = :id AND scan_state = 'UPLOADING'
                        """)
                .param("objectId", objectId)
                .param("objectVersion", objectVersion)
                .param("contentType", contentType)
                .param("size", size)
                .param("sha", sha256)
                .param("now", Timestamp.from(now))
                .param("id", documentId)
                .update() == 1;
    }

    /** Переход состояния проверки только из ожидаемого состояния и для той же версии объекта. */
    public boolean transitionScan(String documentId, String from, String to, String objectVersion,
                                  String extractionState, Instant now) {
        return jdbc.sql("""
                        UPDATE documents.document
                        SET scan_state = :to, extraction_state = COALESCE(:extraction, extraction_state),
                            version = version + 1, updated_at = :now
                        WHERE document_id = :id AND scan_state = :from
                          AND (CAST(:objectVersion AS text) IS NULL OR object_version = :objectVersion)
                        """)
                .param("to", to)
                .param("extraction", extractionState)
                .param("now", Timestamp.from(now))
                .param("id", documentId)
                .param("from", from)
                .param("objectVersion", objectVersion)
                .update() == 1;
    }

    public boolean recordExtraction(String documentId, String objectVersion, String extractionState,
                                    String extractionId, Instant now) {
        return jdbc.sql("""
                        UPDATE documents.document
                        SET extraction_state = :state, extraction_id = :extraction, version = version + 1,
                            updated_at = :now
                        WHERE document_id = :id AND scan_state = 'CLEAN' AND object_version = :objectVersion
                        """)
                .param("state", extractionState)
                .param("extraction", extractionId)
                .param("now", Timestamp.from(now))
                .param("id", documentId)
                .param("objectVersion", objectVersion)
                .update() == 1;
    }

    private static DocumentView map(ResultSet rs) throws SQLException {
        return new DocumentView(
                rs.getString("document_id"),
                rs.getString("application_id"),
                rs.getString("company_id"),
                rs.getString("requirement_id"),
                rs.getLong("requirements_version"),
                rs.getString("document_type"),
                rs.getString("file_name"),
                rs.getString("declared_mime_type"),
                rs.getLong("declared_size_bytes"),
                rs.getString("content_type"),
                rs.getObject("size_bytes", Long.class),
                rs.getString("sha256"),
                rs.getString("object_id"),
                rs.getString("object_version"),
                rs.getString("scan_state"),
                rs.getString("extraction_state"),
                rs.getString("extraction_id"),
                rs.getInt("max_pages"),
                rs.getString("replaces_document_id"),
                rs.getLong("version"),
                rs.getString("created_by"),
                rs.getTimestamp("created_at").toInstant(),
                rs.getTimestamp("updated_at").toInstant());
    }
}
