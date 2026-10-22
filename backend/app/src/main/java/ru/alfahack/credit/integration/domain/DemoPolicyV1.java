package ru.alfahack.credit.integration.domain;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Продуктовая demo-policy v1 (backend guide, раздел 5). Порядок: качество данных → RFI; eligibility;
 * нулевая выручка → MANUAL; отрицательный equity или liabilities/assets ≥ 0,9 → DECLINED; сбой риска → MANUAL;
 * сумма сверх min(product.max, 25% выручки) → ALTERNATIVE; score ≥ 0,5 → MANUAL; иначе APPROVED.
 * Все пороги искусственные; score — BANKRUPTCY_PROXY, не PD. Банковской нормой не является.
 */
public final class DemoPolicyV1 {

    public static final String VERSION = "demo-policy-v1";
    static final BigDecimal LEVERAGE_LIMIT = new BigDecimal("0.9");
    static final BigDecimal TURNOVER_SHARE = new BigDecimal("0.25");
    static final BigDecimal CONTRADICTION_SHARE = new BigDecimal("0.5");
    static final double MANUAL_SCORE = 0.5;
    static final String REVENUE_PATH = "financialStatement.values.revenueMinor";

    public enum Outcome { APPROVED, ALTERNATIVE, MANUAL, DECLINED, NEEDS_INFO }

    /** values — 8 полей DEMO Financial v1 (копейки) по их именам в контракте. */
    public record Input(
            long productMinAmountMinor,
            long productMaxAmountMinor,
            int productMinBusinessAgeMonths,
            long requestedAmountMinor,
            int termMonths,
            Long businessAgeMonths,
            Long preliminaryAnnualRevenueMinor,
            Map<String, Long> values,
            boolean informationAlreadyRequested) {
    }

    public record Decision(
            Outcome outcome, List<String> reasonCodes, String publicExplanation, Long offerAmountMinor,
            Integer offerTermMonths, List<String> requestedFieldPaths) {

        static Decision of(Outcome outcome, String reason, String explanation) {
            return new Decision(outcome, List.of(reason), explanation, null, null, List.of());
        }
    }

    private DemoPolicyV1() {
    }

    /** Решение без модели риска либо пусто, если нужен прогноз. */
    public static Optional<Decision> beforeRisk(Input input) {
        Map<String, Long> v = input.values();
        List<String> missing = v.entrySet().stream().filter(e -> e.getValue() == null).map(Map.Entry::getKey).toList();
        if (!missing.isEmpty() || v.size() != 8) {
            return Optional.of(new Decision(Outcome.NEEDS_INFO, List.of("FINANCIAL_DATA_INCOMPLETE"),
                    "Нужно уточнить финансовые показатели", null, null,
                    missing.stream().map(name -> "financialStatement.values." + name).toList()));
        }
        long revenue = v.get("revenueMinor");
        Long preliminary = input.preliminaryAnnualRevenueMinor();
        if (!input.informationAlreadyRequested() && preliminary != null && revenue > 0
                && BigDecimal.valueOf(Math.abs(preliminary - revenue))
                .compareTo(BigDecimal.valueOf(revenue).multiply(CONTRADICTION_SHARE)) > 0) {
            return Optional.of(new Decision(Outcome.NEEDS_INFO, List.of("REVENUE_CONTRADICTION"),
                    "Выручка в анкете заметно отличается от отчётности — уточните её", null, null,
                    List.of(REVENUE_PATH)));
        }
        if (input.businessAgeMonths() == null) {
            return Optional.of(Decision.of(Outcome.MANUAL, "BUSINESS_AGE_UNKNOWN",
                    "Заявка передана на дополнительную проверку"));
        }
        if (input.businessAgeMonths() < input.productMinBusinessAgeMonths()) {
            return Optional.of(Decision.of(Outcome.DECLINED, "BUSINESS_AGE_BELOW_MINIMUM",
                    "Срок работы бизнеса меньше требования продукта"));
        }
        if (revenue == 0) {
            return Optional.of(Decision.of(Outcome.MANUAL, "ZERO_REVENUE", "Заявка передана на дополнительную проверку"));
        }
        long assets = v.get("totalAssetsMinor");
        long liabilities = v.get("totalLiabilitiesMinor");
        if (v.get("equityMinor") < 0) {
            return Optional.of(Decision.of(Outcome.DECLINED, "NEGATIVE_EQUITY",
                    "Финансовые показатели не соответствуют условиям продукта"));
        }
        if (assets <= 0 || BigDecimal.valueOf(liabilities)
                .divide(BigDecimal.valueOf(assets), 6, RoundingMode.HALF_UP).compareTo(LEVERAGE_LIMIT) >= 0) {
            return Optional.of(Decision.of(Outcome.DECLINED, "DEBT_RATIO_LIMIT",
                    "Долговая нагрузка выше допустимой для продукта"));
        }
        return Optional.empty();
    }

    /** Завершение решения; riskScore пусто — технический сбой риска (MANUAL, без автоматического отказа). */
    public static Decision withRisk(Input input, Optional<Double> riskScore) {
        Optional<Decision> early = beforeRisk(input);
        if (early.isPresent()) {
            return early.get();
        }
        if (riskScore.isEmpty()) {
            return Decision.of(Outcome.MANUAL, "RISK_UNAVAILABLE", "Заявка передана на дополнительную проверку");
        }
        long revenue = input.values().get("revenueMinor");
        long cap = Math.min(input.productMaxAmountMinor(), BigDecimal.valueOf(revenue).multiply(TURNOVER_SHARE)
                .setScale(0, RoundingMode.DOWN).longValueExact());
        if (input.requestedAmountMinor() > cap) {
            if (cap < input.productMinAmountMinor()) {
                return Decision.of(Outcome.DECLINED, "CAP_BELOW_PRODUCT_MINIMUM",
                        "Допустимая сумма меньше минимальной суммы продукта");
            }
            return new Decision(Outcome.ALTERNATIVE, List.of("TURNOVER_CAP"),
                    "Можем предложить меньшую сумму: не более 25% годовой выручки", cap, input.termMonths(), List.of());
        }
        if (riskScore.get() >= MANUAL_SCORE) {
            return Decision.of(Outcome.MANUAL, "RISK_SCORE_HIGH", "Заявка передана на дополнительную проверку");
        }
        return new Decision(Outcome.APPROVED, List.of("POLICY_PASSED"), "Предварительное предложение готово",
                input.requestedAmountMinor(), input.termMonths(), List.of());
    }
}
