package ru.alfahack.credit.documents.application;

import java.time.Instant;
import java.util.List;

public final class JobCommands {

    private JobCommands() {
    }

    /** Аренда задания; leaseToken выдаётся один раз и в БД хранится только его хеш. */
    public record JobLease(
            String jobId, long generation, Instant leaseUntil, String documentId, String objectVersion,
            String objectRef, String jobType, String leaseToken) {

        @Override
        public String toString() {
            return "JobLease[jobId=" + jobId + ", generation=" + generation + ", type=" + jobType + "]";
        }
    }

    public record LeaseProof(String workerId, long generation, String leaseToken) {

        @Override
        public String toString() {
            return "LeaseProof[workerId=" + workerId + ", generation=" + generation + "]";
        }
    }

    public record ScanResult(
            LeaseProof lease, String objectVersion, String verdict, String engineVersion, String cleanObjectRef) {
    }

    public record ExtractionResult(
            LeaseProof lease, String objectVersion, String engineVersion, String status,
            List<ExtractionView.Field> fields) {
    }

    public record Receipt(String receiptId, Instant recordedAt) {
    }
}
