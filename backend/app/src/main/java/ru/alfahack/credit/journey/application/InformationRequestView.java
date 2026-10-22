package ru.alfahack.credit.journey.application;

import java.time.Instant;
import java.util.List;

/** Запрос банка о дополнительных сведениях (схема InformationRequest). */
public record InformationRequestView(
        String requestId,
        String applicationId,
        String companyId,
        String caseId,
        long version,
        String status,
        List<Item> items,
        Instant deadline,
        Instant createdAt) {

    public InformationRequestView {
        items = List.copyOf(items);
    }

    /** FIELD адресует fieldPath, DOCUMENT — requirementId, EXPLANATION — ни то, ни другое. */
    public record Item(
            String itemId, String kind, String label, String reason, boolean required, String fieldPath,
            String requirementId) {
    }

    public List<String> requestedFieldPaths() {
        return items.stream().filter(item -> "FIELD".equals(item.kind())).map(Item::fieldPath).toList();
    }
}
