package ru.alfahack.credit.workspace.api;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;

import org.springframework.core.io.ClassPathResource;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.workspace.application.FeedService;

import java.io.IOException;
import java.time.Instant;
import java.util.Map;

@RestController
@Validated
class FeedController {
    private final FeedService feed;

    FeedController(FeedService feed) {
        this.feed = feed;
    }

    @GetMapping("/api/v1/feed/preferences")
    Map<String, Object> preferences(
            AuthenticatedSession s,
            @RequestParam String companyId,
            @RequestHeader("X-Company-Context") long context) {
        return feed.preferences(s, companyId);
    }

    @PutMapping("/api/v1/feed/preferences")
    Map<String, Object> preferences(
            AuthenticatedSession s,
            @RequestParam String companyId,
            @RequestHeader("X-Company-Context") long context,
            @RequestBody Map<String, Object> preferences) {
        return feed.preferences(s, companyId, preferences);
    }

    @GetMapping("/api/v1/feed")
    Map<String, Object> feed(
            AuthenticatedSession s,
            @RequestParam String companyId,
            @RequestHeader("X-Company-Context") long context,
            @RequestParam(required = false) @Size(min = 1, max = 128) String cursor) {
        return feed.page(s, companyId, cursor, false);
    }

    @GetMapping("/api/v1/feed/saved")
    Map<String, Object> saved(
            AuthenticatedSession s,
            @RequestParam String companyId,
            @RequestHeader("X-Company-Context") long context,
            @RequestParam(required = false) @Size(min = 1, max = 128) String cursor) {
        return feed.page(s, companyId, cursor, true);
    }

    record Feedback(
            @NotBlank @Size(max = 128) String clientEventId,
            @NotBlank @Size(max = 128) String exposureId,
            @NotBlank @Size(max = 128) String itemId,
            @NotNull Action action,
            @NotNull Instant occurredAt) {
        enum Action {
            VIEW,
            CLICK,
            HELPFUL,
            NOT_INTERESTED
        }

        Map<String, Object> value() {
            return Map.of(
                    "clientEventId",
                    clientEventId,
                    "exposureId",
                    exposureId,
                    "itemId",
                    itemId,
                    "action",
                    action.name(),
                    "occurredAt",
                    occurredAt.toString());
        }
    }

    @PostMapping("/api/v1/recommendation-feedback")
    Map<String, Object> feedback(
            AuthenticatedSession s,
            @RequestHeader("X-Company-Context") long context,
            @RequestHeader("Idempotency-Key") @NotBlank @Size(max = 128) String key,
            @Valid @RequestBody Feedback event) {
        return feed.feedback(s, event.value(), key);
    }

    @GetMapping(value = "/assets/feed/{release:v1|v2}/illustrations/{name}", produces = "image/svg+xml")
    ResponseEntity<byte[]> illustration(
            @PathVariable String release, @PathVariable @Pattern(regexp = "[a-z_]+\\.svg") String name) throws IOException {
        ClassPathResource resource = new ClassPathResource(("v2".equals(release) ? "feed/releases/v2/illustrations/" : "feed/illustrations/") + name);
        if (!resource.exists()) throw ApplicationException.notFound();
        return ResponseEntity.ok()
                .header("Cache-Control", "public, max-age=3600")
                .body(resource.getContentAsByteArray());
    }
}
