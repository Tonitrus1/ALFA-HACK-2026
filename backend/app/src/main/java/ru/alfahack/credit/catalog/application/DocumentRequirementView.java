package ru.alfahack.credit.catalog.application;

import java.util.List;

/** Требование к документу версии продукта. */
public record DocumentRequirementView(
        String requirementId,
        String title,
        String reason,
        boolean required,
        List<String> allowedContentTypes,
        int maxBytes,
        int maxPagesForExtraction) {

    public DocumentRequirementView {
        allowedContentTypes = List.copyOf(allowedContentTypes);
    }
}
