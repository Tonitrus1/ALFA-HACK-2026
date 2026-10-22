package ru.alfahack.credit.workspace.application;

import java.time.Instant;
import java.util.List;

/** Клиентская проекция статуса заявки (схема StatusView). */
public record StatusViewModel(
        String applicationId,
        String status,
        long viewVersion,
        Long caseVersion,
        Instant updatedAt,
        boolean stale,
        NextAction nextAction,
        List<HistoryEvent> history,
        String streamCursor) {

    public StatusViewModel {
        history = List.copyOf(history);
    }

    public record NextAction(String type, String label, String targetPath) {
    }

    public record HistoryEvent(String eventId, Instant occurredAt, String label) {
    }
}
