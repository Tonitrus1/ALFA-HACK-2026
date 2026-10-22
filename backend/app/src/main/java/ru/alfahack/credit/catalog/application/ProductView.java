package ru.alfahack.credit.catalog.application;

/** Версия продукта каталога. Суммы — копейки. */
public record ProductView(
        String productId,
        long version,
        String name,
        String purpose,
        long minAmountMinor,
        long maxAmountMinor,
        int minMonths,
        int maxMonths,
        int minBusinessAgeMonths,
        boolean financialRequired,
        long requirementsVersion,
        String preliminaryDisclosure,
        boolean active) {

    public boolean allowsAmount(long amountMinor) {
        return amountMinor >= minAmountMinor && amountMinor <= maxAmountMinor;
    }

    public boolean allowsTerm(int months) {
        return months >= minMonths && months <= maxMonths;
    }
}
