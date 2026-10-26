package ru.alfahack.credit.ml;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.function.Function;

import org.junit.jupiter.api.Test;

import ru.alfahack.credit.ml.application.AssistantGateway;
import ru.alfahack.credit.ml.application.MlClient;
import ru.alfahack.credit.ml.application.MlContracts;
import ru.alfahack.credit.ml.application.RankingGateway;
import ru.alfahack.credit.ml.application.RankingGateway.Candidate;

/** A19: ранжировщик с чужим/неполным набором → RULES; RAG: цитаты только из allowlist и актуальной эпохи. */
class MlGatewaysTest {

    static MlClient client(Function<MlContracts.RankingRequest, MlContracts.RankingResult> ranking,
                           Function<MlContracts.RagInput, MlContracts.AssistantResponse> rag) {
        return new MlClient() {
            @Override
            public String mode() {
                return "MODEL";
            }

            @Override
            public MlContracts.FeatureSnapshot createFeatureSnapshot(String key, MlContracts.FeatureSnapshotInput in) {
                throw new UnsupportedOperationException();
            }

            @Override
            public MlContracts.RiskResult evaluateRisk(String key, MlContracts.RiskRequest request) {
                throw new UnsupportedOperationException();
            }

            @Override
            public MlContracts.RankingResult rank(String key, MlContracts.RankingRequest request) {
                return ranking.apply(request);
            }

            @Override
            public MlContracts.AssistantResponse answer(MlContracts.RagInput input) {
                return rag.apply(input);
            }
        };
    }

    static final List<Candidate> CANDIDATES = List.of(
            new Candidate("working-capital", "Оборотный кредит"),
            new Candidate("credit-line", "Кредитная линия"),
            new Candidate("overdraft", "Овердрафт"));

    static RankingGateway.Ranking rankWith(List<String> rankedIds) {
        RankingGateway gateway = new RankingGateway(client(request -> new MlContracts.RankingResult(
                request.requestId(), request.scope(), rankedIds, request.candidateSetDigest(), "exp-1", "rel-1",
                "MODEL", "SEMANTIC"), input -> null));
        return gateway.rank("PRODUCT", CANDIDATES, 1, 1L, "DRAFT", "WORKING_CAPITAL", "stock", "закупка товара");
    }

    @Test
    void acceptsFullPermutation() {
        RankingGateway.Ranking ranking = rankWith(List.of("overdraft", "working-capital", "credit-line"));

        assertThat(ranking.mode()).isEqualTo("MODEL");
        assertThat(ranking.rankedIds()).containsExactly("overdraft", "working-capital", "credit-line");
    }

    @Test
    void foreignPartialOrDuplicateIdsFallBackToRules() {
        for (List<String> invalid : List.of(
                List.of("overdraft", "working-capital", "secret-product"),
                List.of("overdraft", "working-capital"),
                List.of("overdraft", "overdraft", "credit-line"))) {
            RankingGateway.Ranking ranking = rankWith(invalid);

            assertThat(ranking.mode()).isEqualTo("RULES");
            assertThat(ranking.rankedIds()).containsExactly("working-capital", "credit-line", "overdraft");
        }
    }

    @Test
    void rankerOutageFallsBackToRules() {
        RankingGateway gateway = new RankingGateway(client(request -> {
            throw new IllegalStateException("timeout");
        }, input -> null));

        assertThat(gateway.rank("PRODUCT", CANDIDATES, 1, 1L, "DRAFT", "c", "p", "t").mode()).isEqualTo("RULES");
    }

    static final MlContracts.Citation ALLOWED =
            new MlContracts.Citation("kb-1", 2, "c1", "Овердрафт", "p1", "/api/v1/knowledge/kb-1/versions/2");
    static final MlContracts.Citation FOREIGN =
            new MlContracts.Citation("kb-9", 1, "c9", "Чужое", "p9", "/api/v1/knowledge/kb-9/versions/1");

    static MlContracts.RagInput input() {
        return new MlContracts.RagInput("req-1", "company-a", "representative-a", "Какой срок овердрафта?", null, 7,
                List.of(new MlContracts.AllowedSource("kb-1", 2)));
    }

    static MlContracts.AssistantResponse answer(List<MlContracts.Citation> citations, long epoch) {
        return new MlContracts.AssistantResponse("conv", "msg", "ANSWER", "До 12 месяцев.", citations, "rel",
                "0".repeat(64), epoch);
    }

    @Test
    void ragAnswerWithAllowedCitationPasses() {
        AssistantGateway gateway = new AssistantGateway(client(r -> null, in -> answer(List.of(ALLOWED), 7)));

        assertThat(gateway.answer(input()).orElseThrow().status()).isEqualTo("ANSWER");
    }

    @Test
    void ragCitationOutsideAllowlistOrStaleEpochIsSuppressed() {
        AssistantGateway foreign = new AssistantGateway(client(r -> null, in -> answer(List.of(ALLOWED, FOREIGN), 7)));
        AssistantGateway stale = new AssistantGateway(client(r -> null, in -> answer(List.of(ALLOWED), 6)));

        MlContracts.AssistantResponse suppressed = foreign.answer(input()).orElseThrow();
        assertThat(suppressed.status()).isEqualTo("INSUFFICIENT_EVIDENCE");
        assertThat(suppressed.answer()).isEmpty();
        assertThat(suppressed.citations()).isEmpty();
        assertThat(stale.answer(input()).orElseThrow().status()).isEqualTo("INSUFFICIENT_EVIDENCE");
    }

    @Test
    void ragOutageIsEmpty() {
        AssistantGateway gateway = new AssistantGateway(client(r -> null, in -> {
            throw new IllegalStateException("timeout");
        }));

        assertThat(gateway.answer(input())).isEmpty();
    }
}
