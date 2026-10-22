package ru.alfahack.credit.workspace.application;

import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import ru.alfahack.credit.platform.support.Digests;

import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.json.JsonMapper;

import java.io.IOException;
import java.util.*;

@Component
public class FeedCatalog {
    public final long version;
    public final String digest;
    public final Map<String, Map<String, Object>> cards = new TreeMap<>();
    private final JsonMapper json;

    public FeedCatalog(JsonMapper json) throws IOException {
        this.json = json;
        Map<String, Object> source =
                json.readValue(
                        new ClassPathResource("feed/cards.json").getInputStream(),
                        new TypeReference<>() {});
        version = ((Number) source.get("catalogVersion")).longValue();
        digest = hash(source);
        for (Object item : (List<?>) source.get("cards")) {
            @SuppressWarnings("unchecked")
            Map<String, Object> card = (Map<String, Object>) item;
            if ("PUBLISHED".equals(card.get("status"))) cards.put((String) card.get("id"), card);
        }
    }

    public String hash(Object value) {
        return Digests.sha256(json.writeValueAsString(canonical(value)));
    }

    private Object canonical(Object value) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> result = new TreeMap<>();
            map.forEach((k, v) -> result.put(k.toString(), canonical(v)));
            return result;
        }
        if (value instanceof List<?> list) return list.stream().map(this::canonical).toList();
        return value;
    }

    public Map<String, Object> card(String id, Map<String, Object> explanation, String reaction) {
        Map<String, Object> source = cards.get(id), result = new LinkedHashMap<>();
        result.put("contentId", id);
        for (String key : List.of("version", "title", "text", "topic", "depth"))
            result.put(key, source.get(key));
        result.put("illustration", "/assets/feed/v" + version + "/" + source.get("illustration"));
        result.put(
                "reasonCategory",
                explanation.getOrDefault("reasonCategory", "DETERMINISTIC_RULES"));
        result.put(
                "reason",
                explanation.getOrDefault("message", "Материал о финансировании бизнеса."));
        result.put("userReaction", reaction);
        return result;
    }

    public Map<String, Object> rules(Map<String, Object> request) {
        @SuppressWarnings("unchecked")
        List<String> ids = (List<String>) request.get("candidateIds");
        @SuppressWarnings("unchecked")
        Map<String, Object> profile = (Map<String, Object>) request.get("profile");
        @SuppressWarnings("unchecked")
        Map<String, Map<String, Number>> reactions =
                (Map<String, Map<String, Number>>) request.get("topicReactions");
        Map<String, String> topics =
                Map.of(
                        "PURCHASE",
                        "WORKING_CAPITAL",
                        "CASH_GAP",
                        "CASH_GAP",
                        "EQUIPMENT",
                        "EQUIPMENT",
                        "EXPANSION",
                        "EQUIPMENT",
                        "EXPLORING",
                        "APPLICATION");
        Map<String, Double> scores = new HashMap<>();
        for (String id : ids) {
            Map<String, Object> c = cards.get(id);
            double score =
                    (profile.get("task") != null
                                    && Objects.equals(
                                            topics.get(profile.get("task")), c.get("topic")))
                            ? .12
                            : 0;
            if (((List<?>) c.get("help")).contains(profile.get("help"))) score += .10;
            if (((List<?>) c.get("applicationStages")).contains(profile.get("applicationStage")))
                score += .04;
            if (((List<?>) c.get("businessCategories")).contains(profile.get("businessCategory")))
                score += .04;
            if (profile.get("depth") == null && "BASICS".equals(c.get("depth"))) score += .02;
            if (Objects.equals(profile.get("depth"), c.get("depth"))) score += .03;
            Map<String, Number> counts = reactions.getOrDefault(c.get("topic"), Map.of());
            score +=
                    .05
                            * Math.clamp(
                                    counts.getOrDefault("helpful", 0).intValue()
                                            - counts.getOrDefault("notInterested", 0).intValue(),
                                    -2,
                                    2);
            scores.put(id, score);
        }
        List<String> remaining = new ArrayList<>(ids), ranked = new ArrayList<>();
        remaining.sort(
                Comparator.<String>comparingDouble(scores::get)
                        .reversed()
                        .thenComparing(Comparator.naturalOrder()));
        while (!remaining.isEmpty()) {
            Map<Object, Integer> counts = new HashMap<>();
            for (int i = 0; i < 6 && !remaining.isEmpty(); i++) {
                String chosen =
                        remaining.stream()
                                .filter(
                                        id ->
                                                counts.getOrDefault(cards.get(id).get("topic"), 0)
                                                        < 2)
                                .findFirst()
                                .orElse(remaining.getFirst());
                ranked.add(chosen);
                remaining.remove(chosen);
                counts.merge(cards.get(chosen).get("topic"), 1, Integer::sum);
            }
        }
        Map<String, Object> explanations = new HashMap<>();
        ids.forEach(
                id ->
                        explanations.put(
                                id,
                                Map.of(
                                        "reasonCategory",
                                        "DETERMINISTIC_RULES",
                                        "message",
                                        "Подборка по правилам и выбранным предпочтениям.")));
        Map<String, Object> result = new LinkedHashMap<>();
        for (String k :
                List.of("requestId", "exposureId", "candidateSetDigest", "catalogDigest", "scope"))
            result.put(k, request.get(k));
        result.putAll(
                Map.of(
                        "rankedIds",
                        ranked,
                        "mode",
                        "RULES",
                        "releaseId",
                        "feed-rules-v1",
                        "reasonCategory",
                        "DETERMINISTIC_RULES",
                        "explanations",
                        explanations));
        return result;
    }
}
