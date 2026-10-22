package ru.alfahack.credit.applications.application;

import java.util.Arrays;
import java.util.List;
import java.util.Optional;

/** Восемь полей DEMO Financial v1 с именами из контракта. */
public enum FinancialField {
    TOTAL_ASSETS("totalAssetsMinor"),
    TOTAL_LIABILITIES("totalLiabilitiesMinor"),
    CURRENT_ASSETS("currentAssetsMinor"),
    CURRENT_LIABILITIES("currentLiabilitiesMinor"),
    EQUITY("equityMinor"),
    REVENUE("revenueMinor"),
    NET_PROFIT("netProfitMinor"),
    EBIT("ebitMinor");

    private final String wireName;

    FinancialField(String wireName) {
        this.wireName = wireName;
    }

    public String wireName() {
        return wireName;
    }

    public static Optional<FinancialField> fromWire(String name) {
        return Arrays.stream(values()).filter(field -> field.wireName.equals(name)).findFirst();
    }

    public static List<String> wireNames() {
        return Arrays.stream(values()).map(FinancialField::wireName).toList();
    }
}
