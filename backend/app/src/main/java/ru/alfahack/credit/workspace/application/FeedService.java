package ru.alfahack.credit.workspace.application;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.access.application.CompanyAccessService;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;
import ru.alfahack.credit.workspace.infrastructure.FeedRepository;

import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.json.JsonMapper;

import java.time.Instant;
import java.util.*;

/**
 * Durable feed state belongs to backend; ML receives only candidates and allowlisted preferences.
 */
@Service
@Transactional
public class FeedService {
    private final FeedRepository repo;
    private final FeedCatalog catalog;
    private final FeedRanking ranking;
    private final CompanyAccessService access;
    private final JsonMapper json;

    public FeedService(
            FeedRepository repo,
            FeedCatalog catalog,
            FeedRanking ranking,
            CompanyAccessService access,
            JsonMapper json) {
        this.repo = repo;
        this.catalog = catalog;
        this.ranking = ranking;
        this.access = access;
        this.json = json;
    }

    private String id() {
        return UUID.randomUUID().toString();
    }

    private void authorize(AuthenticatedSession s, String company) {
        access.requireSelectedCompany(s, company);
        repo.lock(s.actorId(), company);
    }

    private Map<String, Object> parse(Object value) {
        return json.readValue(value.toString(), new TypeReference<>() {});
    }

    private long number(Map<String, Object> row, String key) {
        return ((Number) row.get(key)).longValue();
    }

    private ApplicationException conflict(String code) {
        return new ApplicationException(
                ErrorKind.CONFLICT, code, "Подборка изменилась; начните чтение заново");
    }

    public Map<String, Object> preferences(AuthenticatedSession s, String company) {
        authorize(s, company);
        return parse(repo.state(s.actorId(), company).get("preferences_json"));
    }

    public Map<String, Object> preferences(
            AuthenticatedSession s, String company, Map<String, Object> value) {
        authorize(s, company);
        Map<String, Set<String>> allowed =
                Map.of(
                        "task",
                        Set.of("PURCHASE", "CASH_GAP", "EQUIPMENT", "EXPANSION", "EXPLORING"),
                        "help",
                        Set.of("AMOUNT", "OPTIONS", "COST", "APPLICATION"),
                        "depth",
                        Set.of("BASICS", "EXPLAINED", "PRACTICAL"));
        Map<String, Object> normalized = new TreeMap<>();
        for (var entry : value.entrySet()) {
            if (!allowed.containsKey(entry.getKey())
                    || (entry.getValue() != null
                            && !allowed.get(entry.getKey()).contains(entry.getValue())))
                throw new ApplicationException(
                        ErrorKind.UNPROCESSABLE,
                        "INVALID_PREFERENCES",
                        "Недопустимые предпочтения");
            if (entry.getValue() != null) normalized.put(entry.getKey(), entry.getValue());
        }
        repo.sql()
                .sql(
                        "UPDATE workspace.feed_state SET preferences=CAST(:p AS"
                            + " jsonb),preferences_version=preferences_version+1 WHERE actor_id=:a"
                            + " AND company_id=:c")
                .param("p", json.writeValueAsString(normalized))
                .param("a", s.actorId())
                .param("c", company)
                .update();
        return normalized;
    }

    private Map<String, String> reactions(AuthenticatedSession s, String company) {
        Map<String, String> result = new HashMap<>();
        repo.reactions(s.actorId(), company)
                .forEach(
                        row -> {
                            if (row.get("reaction") != null)
                                result.put(
                                        row.get("content_id").toString(),
                                        row.get("reaction").toString());
                        });
        return result;
    }

    private void newPage(
            String cursor,
            String selection,
            AuthenticatedSession s,
            String company,
            String kind,
            long version,
            int offset) {
        repo.sql()
                .sql(
                        "INSERT INTO"
                            + " workspace.feed_page(cursor,selection_id,actor_id,company_id,kind,state_version,catalog_digest,page_offset,exposure_id)"
                            + " VALUES(:id,:selection,:a,:c,:kind,:v,:digest,:offset,:exposure)")
                .param("id", cursor)
                .param("selection", selection)
                .param("a", s.actorId())
                .param("c", company)
                .param("kind", kind)
                .param("v", version)
                .param("digest", catalog.digest)
                .param("offset", offset)
                .param("exposure", id())
                .update();
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> page(
            AuthenticatedSession s, String company, String cursor, boolean saved) {
        authorize(s, company);
        String kind = saved ? "SAVED" : "FEED";
        Map<String, Object> state = repo.state(s.actorId(), company);
        long version = number(state, saved ? "saved_version" : "preferences_version");
        if (cursor == null) {
            String selection = saved ? null : id();
            cursor = id();
            if (!saved)
                repo.sql()
                        .sql(
                                "INSERT INTO"
                                    + " workspace.feed_selection(selection_id,actor_id,company_id,preferences_version,catalog_digest)"
                                    + " VALUES(:id,:a,:c,:v,:digest)")
                        .param("id", selection)
                        .param("a", s.actorId())
                        .param("c", company)
                        .param("v", version)
                        .param("digest", catalog.digest)
                        .update();
            newPage(cursor, selection, s, company, kind, version, 0);
        }
        Map<String, Object> page =
                repo.page(cursor, s.actorId(), company).orElseThrow(ApplicationException::notFound);
        if (!kind.equals(page.get("kind"))) throw ApplicationException.notFound();
        if (number(page, "state_version") != version
                || !catalog.digest.equals(page.get("catalog_digest")))
            throw conflict(saved ? "FEED_SAVED_EXPIRED" : "FEED_SELECTION_EXPIRED");
        Map<String, String> reactions = reactions(s, company);
        if (page.get("response_json") != null)
            return replay(parse(page.get("response_json")), reactions);
        List<Map<String, Object>> rows = repo.reactions(s.actorId(), company);
        List<String> candidates;
        Set<String> issued = new HashSet<>();
        if (saved) {
            candidates =
                    rows.stream()
                            .filter(r -> "HELPFUL".equals(r.get("reaction")))
                            .map(r -> r.get("content_id").toString())
                            .filter(catalog.cards::containsKey)
                            .toList();
            int offset = ((Number) page.get("page_offset")).intValue();
            candidates = candidates.subList(Math.min(offset, candidates.size()), candidates.size());
        } else {
            String raw =
                    repo.sql()
                            .sql(
                                    "SELECT issued::text FROM workspace.feed_selection WHERE"
                                        + " selection_id=:id")
                            .param("id", page.get("selection_id"))
                            .query(String.class)
                            .single();
            issued.addAll(json.readValue(raw, new TypeReference<List<String>>() {}));
            Set<String> excluded = new HashSet<>(issued);
            rows.forEach(
                    r -> {
                        if (Boolean.TRUE.equals(r.get("viewed"))
                                || "NOT_INTERESTED".equals(r.get("reaction")))
                            excluded.add(r.get("content_id").toString());
                    });
            candidates =
                    catalog.cards.keySet().stream().filter(i -> !excluded.contains(i)).toList();
        }
        Map<String, Object> topicReactions = new TreeMap<>();
        for (var entry : reactions.entrySet()) {
            if (!catalog.cards.containsKey(entry.getKey())) continue;
            String topic = catalog.cards.get(entry.getKey()).get("topic").toString();
            Map<String, Integer> counts =
                    (Map<String, Integer>)
                            topicReactions.computeIfAbsent(
                                    topic,
                                    k -> new HashMap<>(Map.of("helpful", 0, "notInterested", 0)));
            counts.merge(
                    "HELPFUL".equals(entry.getValue()) ? "helpful" : "notInterested",
                    1,
                    Integer::sum);
        }
        String exposure = page.get("exposure_id").toString();
        Map<String, Object> request = new LinkedHashMap<>();
        request.putAll(
                Map.of(
                        "requestId",
                        exposure,
                        "scope",
                        "FEED",
                        "exposureId",
                        exposure,
                        "candidateIds",
                        candidates,
                        "candidateSetDigest",
                        catalog.hash(candidates.stream().sorted().toList()),
                        "catalogVersion",
                        catalog.version,
                        "catalogDigest",
                        catalog.digest,
                        "profile",
                        parse(state.get("preferences_json")),
                        "topicReactions",
                        topicReactions));
        Map<String, Object> result;
        if (saved || candidates.isEmpty()) {
            result =
                    new HashMap<>(
                            Map.of(
                                    "rankedIds",
                                    candidates,
                                    "mode",
                                    "RULES",
                                    "releaseId",
                                    saved ? "feed-saved-v1" : "feed-rules-v1",
                                    "explanations",
                                    Map.of()));
        } else result = ranking.rank(request);
        List<String> ranked = (List<String>) result.get("rankedIds");
        List<String> ids = ranked.subList(0, Math.min(6, ranked.size()));
        Map<String, Map<String, Object>> explanations =
                (Map<String, Map<String, Object>>) result.get("explanations");
        List<Map<String, Object>> cards =
                ids.stream()
                        .map(
                                i ->
                                        catalog.card(
                                                i,
                                                explanations.getOrDefault(i, Map.of()),
                                                reactions.get(i)))
                        .toList();
        boolean hasMore = ranked.size() > 6;
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("cards", cards);
        response.put("hasMore", hasMore);
        if (saved)
            response.putAll(
                    Map.of(
                            "exposureId",
                            exposure,
                            "catalogVersion",
                            catalog.version,
                            "catalogDigest",
                            catalog.digest,
                            "savedVersion",
                            version));
        else
            response.putAll(
                    Map.of(
                            "rankingMode",
                            result.get("mode"),
                            "rankingMetadata",
                            Map.of(
                                    "exposureId",
                                    exposure,
                                    "mode",
                                    result.get("mode"),
                                    "releaseId",
                                    result.get("releaseId"),
                                    "candidateSetDigest",
                                    request.get("candidateSetDigest"),
                                    "catalogVersion",
                                    catalog.version,
                                    "catalogDigest",
                                    catalog.digest)));
        if (hasMore) {
            String next = id();
            newPage(
                    next,
                    (String) page.get("selection_id"),
                    s,
                    company,
                    kind,
                    version,
                    ((Number) page.get("page_offset")).intValue() + 6);
            response.put("nextCursor", next);
        }
        repo.sql()
                .sql(
                        "UPDATE workspace.feed_page SET response=CAST(:response AS jsonb) WHERE"
                            + " cursor=:id")
                .param("response", json.writeValueAsString(response))
                .param("id", cursor)
                .update();
        if (!saved) {
            issued.addAll(ids);
            repo.sql()
                    .sql(
                            "UPDATE workspace.feed_selection SET issued=CAST(:issued AS jsonb)"
                                + " WHERE selection_id=:id")
                    .param("issued", json.writeValueAsString(issued.stream().sorted().toList()))
                    .param("id", page.get("selection_id"))
                    .update();
        }
        return response;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> replay(
            Map<String, Object> response, Map<String, String> reactions) {
        List<Map<String, Object>> cards = (List<Map<String, Object>>) response.get("cards");
        response.put(
                "cards",
                cards.stream()
                        .filter(c -> !"NOT_INTERESTED".equals(reactions.get(c.get("contentId"))))
                        .map(
                                c -> {
                                    c.put("userReaction", reactions.get(c.get("contentId")));
                                    return c;
                                })
                        .toList());
        return response;
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> feedback(
            AuthenticatedSession s, Map<String, Object> event, String clientKey) {
        String company = access.selectedCompany(s);
        authorize(s, company);
        String eventId = event.get("clientEventId").toString(),
                item = event.get("itemId").toString(),
                action = event.get("action").toString();
        String fingerprint = catalog.hash(event);
        List<Map<String, Object>> old =
                repo.sql()
                        .sql(
                                "SELECT fingerprint,client_key FROM workspace.feed_event WHERE"
                                    + " actor_id=:a AND company_id=:c AND (event_id=:id OR"
                                    + " client_key=:key)")
                        .param("a", s.actorId())
                        .param("c", company)
                        .param("id", eventId)
                        .param("key", clientKey)
                        .query()
                        .listOfRows();
        if (!old.isEmpty()) {
            if (old.size() != 1
                    || !old.getFirst().get("fingerprint").equals(fingerprint)
                    || !old.getFirst().get("client_key").equals(clientKey))
                throw conflict("FEEDBACK_ID_REUSED");
            return Map.of("operationId", eventId, "status", "SUCCEEDED", "resourceId", item);
        }
        String raw =
                repo.sql()
                        .sql(
                                "SELECT response::text FROM workspace.feed_page WHERE"
                                    + " exposure_id=:id AND actor_id=:a AND company_id=:c AND"
                                    + " response IS NOT NULL")
                        .param("id", event.get("exposureId"))
                        .param("a", s.actorId())
                        .param("c", company)
                        .query(String.class)
                        .optional()
                        .orElseThrow(ApplicationException::notFound);
        List<Map<String, Object>> issued = (List<Map<String, Object>>) parse(raw).get("cards");
        if (issued.stream().noneMatch(c -> item.equals(c.get("contentId")))
                || !catalog.cards.containsKey(item)) throw ApplicationException.notFound();
        if (!Set.of("VIEW", "CLICK", "HELPFUL", "NOT_INTERESTED").contains(action))
            throw new ApplicationException(
                    ErrorKind.UNPROCESSABLE, "INVALID_ACTION", "Недопустимая реакция");
        Instant.parse(event.get("occurredAt").toString());
        String previous = reactions(s, company).get(item);
        if (Set.of("HELPFUL", "NOT_INTERESTED").contains(action) && !action.equals(previous)) {
            repo.sql()
                    .sql(
                            "INSERT INTO"
                                + " workspace.feed_reaction(actor_id,company_id,content_id,reaction)"
                                + " VALUES(:a,:c,:id,:r) ON"
                                + " CONFLICT(actor_id,company_id,content_id) DO UPDATE SET"
                                + " reaction=EXCLUDED.reaction,reaction_at=clock_timestamp()")
                    .param("a", s.actorId())
                    .param("c", company)
                    .param("id", item)
                    .param("r", action)
                    .update();
            if ("HELPFUL".equals(previous) || "HELPFUL".equals(action))
                repo.sql()
                        .sql(
                                "UPDATE workspace.feed_state SET saved_version=saved_version+1"
                                    + " WHERE actor_id=:a AND company_id=:c")
                        .param("a", s.actorId())
                        .param("c", company)
                        .update();
        }
        if ("VIEW".equals(action))
            repo.sql()
                    .sql(
                            "INSERT INTO"
                                + " workspace.feed_reaction(actor_id,company_id,content_id,viewed)"
                                + " VALUES(:a,:c,:id,true) ON"
                                + " CONFLICT(actor_id,company_id,content_id) DO UPDATE SET"
                                + " viewed=true")
                    .param("a", s.actorId())
                    .param("c", company)
                    .param("id", item)
                    .update();
        repo.sql()
                .sql(
                        "INSERT INTO"
                            + " workspace.feed_event(actor_id,company_id,event_id,client_key,fingerprint,payload)"
                            + " VALUES(:a,:c,:id,:key,:f,CAST(:p AS jsonb))")
                .param("a", s.actorId())
                .param("c", company)
                .param("id", eventId)
                .param("key", clientKey)
                .param("f", fingerprint)
                .param("p", json.writeValueAsString(event))
                .update();
        return Map.of("operationId", eventId, "status", "SUCCEEDED", "resourceId", item);
    }
}
