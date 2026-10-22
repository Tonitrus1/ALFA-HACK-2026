package ru.alfahack.credit.documents.application;

import java.util.List;

/** Поля-кандидаты OCR точной версии объекта; не меняют подтверждённые данные автоматически. */
public record ExtractionView(
        String extractionId,
        String documentId,
        long documentVersion,
        String objectVersion,
        String modelVersion,
        String status,
        List<Field> fields) {

    public ExtractionView {
        fields = List.copyOf(fields);
    }

    public record Field(String name, String value, double confidence, Integer page) {
    }
}
