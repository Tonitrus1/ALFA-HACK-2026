package ru.alfahack.credit.ml.application;

import java.util.HashSet;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import ru.alfahack.credit.platform.support.Digests;
import ru.alfahack.credit.platform.support.Ids;

/**
 * Ранжирование только разрешённого набора. Ответ модели принимается, лишь если это полная перестановка
 * кандидатов с тем же requestId и digest набора; иначе (чужой ID, пропуск, дубль, сбой) — RULES в исходном
 * порядке backend. Право на показ определяет backend до вызова, ранжировщик его не расширяет.
 */
@Service
public class RankingGateway {

    private static final Logger log = LoggerFactory.getLogger(RankingGateway.class);

    public record Candidate(String itemId, String text) {
    }

    public record Ranking(List<String> rankedIds, String mode, String exposureId, String releaseId,
                          String reasonCategory) {
    }

    private final MlClient client;

    public RankingGateway(MlClient client) {
        this.client = client;
    }

    public Ranking rank(String scope, List<Candidate> candidates, long catalogVersion, Long eligibilityVersion,
                        String stage, String contextCategory, String fundingPurpose, String contextText) {
        List<String> ids = candidates.stream().map(Candidate::itemId).toList();
        String digest = Digests.sha256(String.join("\n", ids));
        String requestId = Ids.newId();
        try {
            MlContracts.RankingResult result = client.rank(requestId, new MlContracts.RankingRequest(
                    requestId, scope, ids, digest, catalogVersion, eligibilityVersion, stage, contextCategory,
                    fundingPurpose, contextText,
                    candidates.stream().map(c -> new MlContracts.CandidateText(c.itemId(), c.text())).toList()));
            if (isPermutation(ids, result.rankedIds()) && requestId.equals(result.requestId())
                    && digest.equals(result.candidateSetDigest()) && scope.equals(result.scope())) {
                return new Ranking(List.copyOf(result.rankedIds()), result.mode(), result.exposureId(),
                        result.releaseId(), result.reasonCategory());
            }
            log.warn("Ranking result rejected requestId={}", requestId);
        } catch (RuntimeException e) {
            log.warn("Ranking unavailable requestId={} error={}", requestId, e.getClass().getSimpleName());
        }
        return new Ranking(ids, "RULES", "rules-" + requestId, "rules", "DEFAULT_ORDER");
    }

    static boolean isPermutation(List<String> candidates, List<String> ranked) {
        return ranked != null && ranked.size() == candidates.size()
                && new HashSet<>(ranked).size() == ranked.size()
                && new HashSet<>(ranked).equals(new HashSet<>(candidates));
    }
}
