package ru.alfahack.credit.applications.application;

/** Предварительные сведения о бизнесе (схема Business); суммы — копейки, все поля необязательны. */
public record BusinessData(
        Long annualRevenueMinor,
        Long annualExpensesMinor,
        Long currentDebtMinor,
        Long businessAgeMonths,
        String activityDescription,
        String sourceConfirmationVersion) {

    public static final BusinessData EMPTY = new BusinessData(null, null, null, null, null, null);

    public boolean isEmpty() {
        return equals(EMPTY);
    }
}
