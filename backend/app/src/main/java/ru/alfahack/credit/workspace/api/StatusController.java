package ru.alfahack.credit.workspace.api;

import java.time.Instant;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonInclude;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.platform.support.ETags;
import ru.alfahack.credit.workspace.application.StatusViewModel;
import ru.alfahack.credit.workspace.application.StatusViewService;

@RestController
class StatusController {

    /** Схема StatusView: sourceVersion сохранён для совместимости и равен caseVersion. */
    @JsonInclude(JsonInclude.Include.NON_NULL)
    record StatusView(
            String applicationId,
            String status,
            long viewVersion,
            Long sourceVersion,
            Instant updatedAt,
            boolean stale,
            StatusViewModel.NextAction nextAction,
            List<StatusViewModel.HistoryEvent> history,
            String streamCursor,
            Long caseVersion) {

        static StatusView of(StatusViewModel model) {
            return new StatusView(
                    model.applicationId(), model.status(), model.viewVersion(), model.caseVersion(),
                    model.updatedAt(), model.stale(), model.nextAction(), model.history(), model.streamCursor(),
                    model.caseVersion());
        }
    }

    private final StatusViewService statuses;

    StatusController(StatusViewService statuses) {
        this.statuses = statuses;
    }

    @GetMapping("/api/v1/applications/{applicationId}/status")
    ResponseEntity<StatusView> status(
            AuthenticatedSession session,
            @RequestHeader("X-Company-Context") long companyContext,
            @PathVariable String applicationId) {
        StatusViewModel model = statuses.status(session, applicationId);
        return ResponseEntity.ok().eTag(ETags.of(model.viewVersion())).body(StatusView.of(model));
    }
}
