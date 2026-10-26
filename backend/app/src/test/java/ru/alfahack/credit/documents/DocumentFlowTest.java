package ru.alfahack.credit.documents;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.UUID;

import com.jayway.jsonpath.JsonPath;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

import ru.alfahack.credit.documents.application.ScannerWorker;
import ru.alfahack.credit.support.Bodies;
import ru.alfahack.credit.support.DemoClient;
import ru.alfahack.credit.support.Financials;
import ru.alfahack.credit.support.IntegrationTest;
import ru.alfahack.credit.support.StubMalwareScanner;
import ru.alfahack.credit.support.TestFiles;
import ru.alfahack.credit.support.TestTokens;

/** P10 «infected/error not CLEAN; limit 10MiB/5 pages; stale lease rejected» и файловый шлюз. */
@IntegrationTest
@Import(StubMalwareScanner.class)
class DocumentFlowTest {

    @Autowired
    MockMvc mvc;

    @Autowired
    JdbcClient jdbc;

    @Autowired
    ScannerWorker scanner;

    DemoClient a;
    String applicationId;

    record Intent(String uploadId, String documentId, String uploadUrl, String grant) {
    }

    @BeforeEach
    void draft() throws Exception {
        a = DemoClient.login(mvc, "representative-a");
        String body = mvc.perform(a.json(post("/api/v1/applications"), Bodies.create("company-a", 50_000_000, 12))
                        .header("Idempotency-Key", "create-" + UUID.randomUUID()))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        applicationId = JsonPath.read(body, "$.applicationId");
        drainScans();
    }

    static String uploadInput(String mime, long size) {
        return """
                {"fileName":"report-2025.pdf","declaredMimeType":"%s","sizeBytes":%d,"documentType":"FINANCIAL_STATEMENT",
                 "requirementId":"financial-statement","requirementsVersion":1}
                """.formatted(mime, size);
    }

    Intent intent(String mime, long size) throws Exception {
        String body = mvc.perform(a.json(post("/api/v1/applications/" + applicationId + "/documents/upload-intents"),
                        uploadInput(mime, size)).header("Idempotency-Key", "upload-" + UUID.randomUUID()))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.maxBytes").value(size))
                .andReturn().getResponse().getContentAsString();
        return new Intent(JsonPath.read(body, "$.uploadId"), JsonPath.read(body, "$.documentId"),
                JsonPath.read(body, "$.uploadUrl"), JsonPath.read(body, "$.grant"));
    }

    ResultActions upload(DemoClient client, Intent intent, String grant, String contentType, byte[] bytes)
            throws Exception {
        return mvc.perform(client.sign(put(intent.uploadUrl()))
                .header("X-Upload-Grant", grant)
                .contentType(contentType)
                .content(bytes));
    }

    /** Загрузка + проверка сканером; возвращает id документа. */
    String uploadAndScan(byte[] bytes) throws Exception {
        Intent intent = intent("application/pdf", bytes.length);
        upload(a, intent, intent.grant(), "application/pdf", bytes).andExpect(status().isNoContent());
        documentState(intent.documentId(), "QUARANTINED");
        drainScans();
        return intent.documentId();
    }

    void drainScans() {
        while (scanner.processOnce()) {
            // очередь SCAN-заданий
        }
    }

    void documentState(String documentId, String scanState) throws Exception {
        mvc.perform(a.sign(get("/api/v1/documents/" + documentId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.scanState").value(scanState));
    }

    @Test
    void requirementsAreServedForTheProduct() throws Exception {
        mvc.perform(a.sign(get("/api/v1/applications/" + applicationId + "/document-requirements")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.requirementsVersion").value(1))
                .andExpect(jsonPath("$.items[0].requirementId").value("financial-statement"))
                .andExpect(jsonPath("$.items[0].maxBytes").value(10485760))
                .andExpect(jsonPath("$.items[0].required").value(false));
    }

    @Test
    void cleanPdfBecomesCleanAndCanBeDownloaded() throws Exception {
        byte[] pdf = TestFiles.pdf(2);
        String documentId = uploadAndScan(pdf);

        mvc.perform(a.sign(get("/api/v1/documents/" + documentId)))
                .andExpect(jsonPath("$.scanState").value("CLEAN"))
                .andExpect(jsonPath("$.extractionState").value("PENDING"))
                .andExpect(jsonPath("$.sizeBytes").value(pdf.length))
                .andExpect(jsonPath("$.objectVersion").isNotEmpty());

        String download = mvc.perform(a.sign(post("/api/v1/documents/" + documentId + "/download-intents")))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        byte[] downloaded = mvc.perform(a.sign(get((String) JsonPath.read(download, "$.downloadUrl")))
                        .header("X-Download-Grant", (String) JsonPath.read(download, "$.grant")))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsByteArray();
        assertThat(downloaded).isEqualTo(pdf);

        mvc.perform(a.sign(get((String) JsonPath.read(download, "$.downloadUrl")))
                        .header("X-Download-Grant", "forged"))
                .andExpect(status().isForbidden());
    }

    @Test
    void infectedFileIsRejectedAndNeverClean() throws Exception {
        String documentId = uploadAndScan(TestFiles.pdf(1, TestFiles.EICAR, false));

        documentState(documentId, "REJECTED");
        mvc.perform(a.sign(post("/api/v1/documents/" + documentId + "/download-intents")))
                .andExpect(status().isConflict());
    }

    @Test
    void scannerErrorKeepsQuarantineAndFailsAfterRetries() throws Exception {
        String documentId = uploadAndScan(TestFiles.pdf(1, StubMalwareScanner.ERROR_MARKER, false));
        documentState(documentId, "QUARANTINED");

        for (int attempt = 0; attempt < 10; attempt++) {
            jdbc.sql("UPDATE documents.document_job SET next_attempt_at = now() - interval '1 second' "
                    + "WHERE document_id = :id AND state = 'PENDING'").param("id", documentId).update();
            drainScans();
        }
        String jobState = jdbc.sql("SELECT state FROM documents.document_job WHERE document_id = :id AND job_type = 'SCAN'")
                .param("id", documentId).query(String.class).single();
        assertThat(jobState).isEqualTo("FAILED");
        documentState(documentId, "QUARANTINED");
    }

    @Test
    void pageLimitAndStructureAreEnforced() throws Exception {
        documentState(uploadAndScan(TestFiles.pdf(6)), "REJECTED");
        documentState(uploadAndScan(TestFiles.pdf(1, "/JavaScript (x)", false)), "REJECTED");
    }

    @Test
    void sizeLimitsAreEnforced() throws Exception {
        mvc.perform(a.json(post("/api/v1/applications/" + applicationId + "/documents/upload-intents"),
                        uploadInput("application/pdf", 10_485_761)).header("Idempotency-Key", "upload-" + UUID.randomUUID()))
                .andExpect(status().isBadRequest());

        byte[] pdf = TestFiles.pdf(1);
        Intent declaredSmaller = intent("application/pdf", pdf.length - 10);
        upload(a, declaredSmaller, declaredSmaller.grant(), "application/pdf", pdf)
                .andExpect(status().isUnprocessableContent())
                .andExpect(jsonPath("$.code").value("FILE_TOO_LARGE"));

        Intent declaredLarger = intent("application/pdf", pdf.length + 10);
        upload(a, declaredLarger, declaredLarger.grant(), "application/pdf", pdf)
                .andExpect(status().isUnprocessableContent())
                .andExpect(jsonPath("$.code").value("FILE_SIZE_MISMATCH"));
    }

    @Test
    void grantIsBoundToSessionTypeAndState() throws Exception {
        byte[] pdf = TestFiles.pdf(1);
        Intent intent = intent("application/pdf", pdf.length);

        upload(a, intent, "forged-grant", "application/pdf", pdf).andExpect(status().isForbidden());
        DemoClient otherSession = DemoClient.login(mvc, "representative-a");
        upload(otherSession, intent, intent.grant(), "application/pdf", pdf).andExpect(status().isForbidden());
        DemoClient b = DemoClient.login(mvc, "representative-b");
        upload(b, intent, intent.grant(), "application/pdf", pdf).andExpect(status().isNotFound());
        upload(a, intent, intent.grant(), "image/png", pdf).andExpect(status().isUnprocessableContent());

        mvc.perform(a.sign(delete("/api/v1/uploads/" + intent.uploadId()))).andExpect(status().isNoContent());
        upload(a, intent, intent.grant(), "application/pdf", pdf)
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("UPLOAD_NOT_PENDING"));
        documentState(intent.documentId(), "DELETED");
    }

    @Test
    void otherCompanyCannotSeeDocuments() throws Exception {
        String documentId = uploadAndScan(TestFiles.pdf(1));
        DemoClient b = DemoClient.login(mvc, "representative-b");

        mvc.perform(b.sign(get("/api/v1/documents/" + documentId))).andExpect(status().isNotFound());
        mvc.perform(b.sign(get("/api/v1/applications/" + applicationId + "/documents"))).andExpect(status().isNotFound());
        mvc.perform(b.sign(post("/api/v1/documents/" + documentId + "/download-intents")))
                .andExpect(status().isNotFound());
    }

    @Test
    void extractionLeaseRejectsStaleGenerationAndExpiry() throws Exception {
        String documentId = uploadAndScan(TestFiles.pdf(1));
        jdbc.sql("UPDATE documents.document_job SET state = 'DONE' WHERE job_type = 'EXTRACT' AND document_id <> :id")
                .param("id", documentId).update();

        mvc.perform(post("/internal/v1/document-jobs/claim").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"workerId\":\"ocr-1\",\"jobType\":\"EXTRACT\"}"))
                .andExpect(status().isUnauthorized());
        mvc.perform(post("/internal/v1/document-jobs/claim").header("X-Service-Token", TestTokens.SCANNER)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"workerId\":\"ocr-1\",\"jobType\":\"EXTRACT\"}"))
                .andExpect(status().isForbidden());

        String first = claimExtract("ocr-1");
        String jobId = JsonPath.read(first, "$.jobId");
        String objectVersion = JsonPath.read(first, "$.objectVersion");
        assertThat((String) JsonPath.read(first, "$.documentId")).isEqualTo(documentId);

        mvc.perform(get("/internal/v1/document-jobs/" + jobId + "/content")
                        .header("X-Service-Token", TestTokens.OCR).header("X-Worker-Id", "ocr-1")
                        .header("X-Lease-Generation", 1).header("X-Lease-Token", (String)JsonPath.read(first,"$.leaseToken")))
                .andExpect(status().isOk());
        mvc.perform(get("/internal/v1/document-jobs/" + jobId + "/content")
                        .header("X-Service-Token", TestTokens.SCANNER).header("X-Worker-Id", "ocr-1")
                        .header("X-Lease-Generation", 1).header("X-Lease-Token", (String)JsonPath.read(first,"$.leaseToken")))
                .andExpect(status().isForbidden());

        // Аренда истекла и задание перехвачено другим worker: результат первого поколения отклоняется.
        jdbc.sql("UPDATE documents.document_job SET lease_until = now() - interval '1 second' WHERE job_id = :id")
                .param("id", jobId).update();
        String second = claimExtract("ocr-2");
        assertThat(((Number) JsonPath.read(second, "$.generation")).longValue()).isEqualTo(2);

        mvc.perform(get("/internal/v1/document-jobs/" + jobId + "/content")
                        .header("X-Service-Token", TestTokens.OCR).header("X-Worker-Id", "ocr-1")
                        .header("X-Lease-Generation", 1).header("X-Lease-Token", (String)JsonPath.read(first,"$.leaseToken")))
                .andExpect(status().isConflict());
        extractionResult(jobId, first, "ocr-1", objectVersion)
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("LEASE_STALE"));
        extractionResult(jobId, second, "ocr-2", "other:v1")
                .andExpect(status().isConflict());

        mvc.perform(post("/internal/v1/document-jobs/" + jobId + "/renew").header("X-Service-Token", TestTokens.OCR)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"workerId\":\"ocr-2\",\"generation\":2,\"leaseToken\":\"%s\"}"
                                .formatted((String) JsonPath.read(second, "$.leaseToken"))))
                .andExpect(status().isOk());
        extractionResult(jobId, second, "ocr-2", objectVersion).andExpect(status().isOk());

        mvc.perform(a.sign(get("/api/v1/documents/" + documentId)))
                .andExpect(jsonPath("$.extractionState").value("READY"));
        mvc.perform(a.sign(get("/api/v1/documents/" + documentId + "/extraction")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.fields[0].name").value("revenueMinor"))
                .andExpect(jsonPath("$.objectVersion").value(objectVersion));
    }

    @Test
    void submitAcceptsExactCleanReferencesOnly() throws Exception {
        String documentId = uploadAndScan(TestFiles.pdf(1));
        String document = mvc.perform(a.sign(get("/api/v1/documents/" + documentId)))
                .andReturn().getResponse().getContentAsString();
        long documentVersion = ((Number) JsonPath.read(document, "$.version")).longValue();
        String objectVersion = JsonPath.read(document, "$.objectVersion");
        long version = Financials.fillAndConfirm(mvc, a, applicationId, 1);

        String stale = submitBody(version, documentId, documentVersion - 1, objectVersion);
        mvc.perform(a.json(post("/api/v1/applications/" + applicationId + "/submit"), stale)
                        .header("Idempotency-Key", "submit-" + UUID.randomUUID()))
                .andExpect(status().isUnprocessableContent())
                .andExpect(jsonPath("$.code").value("DOCUMENT_REFERENCES_MISMATCH"));
        mvc.perform(a.json(post("/api/v1/applications/" + applicationId + "/submit"),
                        submitBody(version, documentId, documentVersion, objectVersion))
                        .header("Idempotency-Key", "submit-" + UUID.randomUUID()))
                .andExpect(status().isAccepted());
    }

    String claimExtract(String workerId) throws Exception {
        return mvc.perform(post("/internal/v1/document-jobs/claim").header("X-Service-Token", TestTokens.OCR)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"workerId\":\"%s\",\"jobType\":\"EXTRACT\"}".formatted(workerId)))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
    }

    ResultActions extractionResult(String jobId, String lease, String workerId, String objectVersion)
            throws Exception {
        return mvc.perform(post("/internal/v1/document-jobs/" + jobId + "/extraction-result")
                .header("X-Service-Token", TestTokens.OCR)
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"generation":%d,"objectVersion":"%s","engineVersion":"ocr-test/1","status":"READY",
                         "fields":[{"name":"revenueMinor","value":"250000000","confidence":0.93,"page":1}],
                         "workerId":"%s","leaseToken":"%s"}
                        """.formatted(((Number) JsonPath.read(lease, "$.generation")).longValue(), objectVersion,
                        workerId, (String) JsonPath.read(lease, "$.leaseToken"))));
    }

    static String submitBody(long version, String documentId, long documentVersion, String objectVersion) {
        return """
                {"expectedVersion":%d,"consentRecordIds":[],"documentIds":["%s"],
                 "documentReferences":[{"documentId":"%s","documentVersion":%d,"objectVersion":"%s"}],
                 "requirementsVersion":1,"financialStatementVersion":1}
                """.formatted(version, documentId, documentId, documentVersion, objectVersion);
    }
}
