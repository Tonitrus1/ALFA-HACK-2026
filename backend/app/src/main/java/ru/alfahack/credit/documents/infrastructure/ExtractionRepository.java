package ru.alfahack.credit.documents.infrastructure;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Optional;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.json.JsonMapper;

import ru.alfahack.credit.documents.application.ExtractionView;

@Repository
public class ExtractionRepository {

    private static final TypeReference<List<ExtractionView.Field>> FIELDS = new TypeReference<>() {
    };

    private final JdbcClient jdbc;
    private final JsonMapper json;

    public ExtractionRepository(JdbcClient jdbc, JsonMapper json) {
        this.jdbc = jdbc;
        this.json = json;
    }

    public void insert(ExtractionView extraction, Instant now) {
        jdbc.sql("""
                        INSERT INTO documents.extraction (extraction_id, document_id, document_version, object_version,
                                                          model_version, status, fields, created_at)
                        VALUES (:id, :document, :documentVersion, :objectVersion, :model, :status,
                                CAST(:fields AS jsonb), :now)
                        """)
                .param("id", extraction.extractionId())
                .param("document", extraction.documentId())
                .param("documentVersion", extraction.documentVersion())
                .param("objectVersion", extraction.objectVersion())
                .param("model", extraction.modelVersion())
                .param("status", extraction.status())
                .param("fields", json.writeValueAsString(extraction.fields()))
                .param("now", Timestamp.from(now))
                .update();
    }

    public Optional<ExtractionView> find(String extractionId) {
        return jdbc.sql("""
                        SELECT extraction_id, document_id, document_version, object_version, model_version, status,
                               fields::text AS fields
                        FROM documents.extraction WHERE extraction_id = :id
                        """)
                .param("id", extractionId)
                .query((rs, row) -> new ExtractionView(
                        rs.getString("extraction_id"), rs.getString("document_id"), rs.getLong("document_version"),
                        rs.getString("object_version"), rs.getString("model_version"), rs.getString("status"),
                        json.readValue(rs.getString("fields"), FIELDS)))
                .optional();
    }
}
