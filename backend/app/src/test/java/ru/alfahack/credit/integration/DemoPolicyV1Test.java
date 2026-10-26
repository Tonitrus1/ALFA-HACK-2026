package ru.alfahack.credit.integration;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

import org.junit.jupiter.api.Test;

import ru.alfahack.credit.integration.domain.DemoPolicyV1;
import ru.alfahack.credit.integration.domain.DemoPolicyV1.Decision;
import ru.alfahack.credit.integration.domain.DemoPolicyV1.Outcome;

/** demo-policy v1: A03 отказ по долговой нагрузке, A04 другие условия, A18 сбой риска → MANUAL. */
class DemoPolicyV1Test {

    static Map<String, Long> values(long assets, long liabilities, long equity, long revenue) {
        Map<String, Long> values = new HashMap<>();
        values.put("totalAssetsMinor", assets);
        values.put("totalLiabilitiesMinor", liabilities);
        values.put("currentAssetsMinor", assets / 2);
        values.put("currentLiabilitiesMinor", liabilities / 2);
        values.put("equityMinor", equity);
        values.put("revenueMinor", revenue);
        values.put("netProfitMinor", 1_000_000L);
        values.put("ebitMinor", 2_000_000L);
        return values;
    }

    /** Оборотный кредит: 100 тыс.–5 млн RUB, возраст бизнеса от 6 мес. */
    static DemoPolicyV1.Input input(long requested, Long age, Long preliminaryRevenue, Map<String, Long> values,
                                    boolean alreadyRequested) {
        return new DemoPolicyV1.Input(10_000_000, 500_000_000, 6, requested, 12, age, preliminaryRevenue, values,
                alreadyRequested);
    }

    static Decision decide(DemoPolicyV1.Input input, Double score) {
        return DemoPolicyV1.withRisk(input, Optional.ofNullable(score));
    }

    @Test
    void approvesWithinCapAndLowScore() {
        Decision decision = decide(input(50_000_000, 40L, null, values(100_000_000, 40_000_000, 60_000_000, 300_000_000), false), 0.25);

        assertThat(decision.outcome()).isEqualTo(Outcome.APPROVED);
        assertThat(decision.offerAmountMinor()).isEqualTo(50_000_000);
        assertThat(decision.offerTermMonths()).isEqualTo(12);
    }

    @Test
    void declinesOnDebtRatioOrNegativeEquityWithoutRisk() {
        DemoPolicyV1.Input highDebt = input(50_000_000, 40L, null, values(100_000_000, 90_000_000, 10_000_000, 300_000_000), false);
        assertThat(DemoPolicyV1.beforeRisk(highDebt)).map(Decision::outcome).contains(Outcome.DECLINED);
        assertThat(DemoPolicyV1.beforeRisk(highDebt).orElseThrow().reasonCodes()).containsExactly("DEBT_RATIO_LIMIT");

        DemoPolicyV1.Input negativeEquity = input(50_000_000, 40L, null, values(100_000_000, 40_000_000, -5_000_000, 300_000_000), false);
        assertThat(DemoPolicyV1.beforeRisk(negativeEquity)).map(Decision::outcome).contains(Outcome.DECLINED);
    }

    @Test
    void offersAlternativeAboveTurnoverCap() {
        Decision decision = decide(input(50_000_000, 40L, null, values(100_000_000, 40_000_000, 60_000_000, 100_000_000), false), 0.2);

        assertThat(decision.outcome()).isEqualTo(Outcome.ALTERNATIVE);
        assertThat(decision.offerAmountMinor()).isEqualTo(25_000_000);
        assertThat(decide(input(50_000_000, 40L, null, values(100_000_000, 40_000_000, 60_000_000, 20_000_000), false), 0.2)
                .outcome()).isEqualTo(Outcome.DECLINED);
    }

    @Test
    void riskOutageAndHighScoreGoToManual() {
        DemoPolicyV1.Input input = input(50_000_000, 40L, null, values(100_000_000, 40_000_000, 60_000_000, 300_000_000), false);

        assertThat(decide(input, null).outcome()).isEqualTo(Outcome.MANUAL);
        assertThat(decide(input, null).reasonCodes()).containsExactly("RISK_UNAVAILABLE");
        assertThat(decide(input, 0.5).outcome()).isEqualTo(Outcome.MANUAL);
    }

    @Test
    void zeroRevenueAndUnknownAgeGoToManualAndYoungBusinessIsDeclined() {
        assertThat(decide(input(50_000_000, 40L, null, values(100_000_000, 40_000_000, 60_000_000, 0), false), 0.1)
                .outcome()).isEqualTo(Outcome.MANUAL);
        assertThat(decide(input(50_000_000, null, null, values(100_000_000, 40_000_000, 60_000_000, 300_000_000), false), 0.1)
                .reasonCodes()).containsExactly("BUSINESS_AGE_UNKNOWN");
        assertThat(decide(input(50_000_000, 3L, null, values(100_000_000, 40_000_000, 60_000_000, 300_000_000), false), 0.1)
                .outcome()).isEqualTo(Outcome.DECLINED);
    }

    @Test
    void contradictoryRevenueRequestsFinancialFieldOnce() {
        Map<String, Long> values = values(100_000_000, 40_000_000, 60_000_000, 300_000_000);

        Decision first = decide(input(50_000_000, 40L, 1_000_000_000L, values, false), 0.1);
        assertThat(first.outcome()).isEqualTo(Outcome.NEEDS_INFO);
        assertThat(first.requestedFieldPaths()).containsExactly("financialStatement.values.revenueMinor");

        assertThat(decide(input(50_000_000, 40L, 1_000_000_000L, values, true), 0.1).outcome())
                .isEqualTo(Outcome.APPROVED);
        assertThat(decide(input(50_000_000, 40L, 320_000_000L, values, false), 0.1).outcome())
                .isEqualTo(Outcome.APPROVED);
    }
}
