package ru.alfahack.credit.applications.application;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** Значения DEMO Financial v1 в копейках; null — значение не указано (не ноль). */
public record FinancialValues(
        Long totalAssetsMinor,
        Long totalLiabilitiesMinor,
        Long currentAssetsMinor,
        Long currentLiabilitiesMinor,
        Long equityMinor,
        Long revenueMinor,
        Long netProfitMinor,
        Long ebitMinor) {

    public Long get(FinancialField field) {
        return switch (field) {
            case TOTAL_ASSETS -> totalAssetsMinor;
            case TOTAL_LIABILITIES -> totalLiabilitiesMinor;
            case CURRENT_ASSETS -> currentAssetsMinor;
            case CURRENT_LIABILITIES -> currentLiabilitiesMinor;
            case EQUITY -> equityMinor;
            case REVENUE -> revenueMinor;
            case NET_PROFIT -> netProfitMinor;
            case EBIT -> ebitMinor;
        };
    }

    public List<FinancialField> missing() {
        return Arrays.stream(FinancialField.values()).filter(field -> get(field) == null).toList();
    }

    /**
     * Проверяемые равенства подтверждения: totalAssets > 0, currentAssets ≤ totalAssets,
     * currentLiabilities ≤ totalLiabilities и баланс с demo-допуском max(100 копеек, 1% totalAssets).
     * Допуск не является банковской нормой. Возвращает нарушенные правила.
     */
    public List<String> invariantViolations() {
        if (!missing().isEmpty()) {
            return List.of("Заполните все финансовые показатели");
        }
        ArrayList<String> violations = new ArrayList<>();
        if (totalAssetsMinor <= 0) {
            violations.add("Сумма активов должна быть больше нуля");
        }
        if (currentAssetsMinor > totalAssetsMinor) {
            violations.add("Оборотные активы не могут превышать сумму всех активов");
        }
        if (currentLiabilitiesMinor > totalLiabilitiesMinor) {
            violations.add("Краткосрочные обязательства не могут превышать сумму всех обязательств");
        }
        BigDecimal assets = BigDecimal.valueOf(totalAssetsMinor);
        BigDecimal difference = assets
                .subtract(BigDecimal.valueOf(totalLiabilitiesMinor))
                .subtract(BigDecimal.valueOf(equityMinor))
                .abs();
        BigDecimal tolerance = assets.multiply(new BigDecimal("0.01"))
                .setScale(0, RoundingMode.HALF_UP)
                .max(BigDecimal.valueOf(100));
        if (difference.compareTo(tolerance) > 0) {
            violations.add("Сумма активов должна совпадать с суммой всех обязательств и собственного капитала. Проверьте эти три показателя");
        }
        return List.copyOf(violations);
    }
}
