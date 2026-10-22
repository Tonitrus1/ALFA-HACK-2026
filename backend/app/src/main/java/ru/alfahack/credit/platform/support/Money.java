package ru.alfahack.credit.platform.support;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;

/** Схема Money: целые minor units, RUB — копейки. */
public record Money(
        @NotNull @Min(0) @Max(9007199254740991L) Long amountMinor,
        @NotNull @Pattern(regexp = "RUB") String currency) {

    public static Money rub(long amountMinor) {
        return new Money(amountMinor, "RUB");
    }

    public static Money rubOrNull(Long amountMinor) {
        return amountMinor == null ? null : rub(amountMinor);
    }
}
