package ru.alfahack.credit.applications.application;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class FinancialValuesMessagesTest {
    @Test
    void invalidBalanceExplainsEachProblemWithoutInternalFieldNames() {
        var values = new FinancialValues(0L, 100L, 10L, 200L, 100L, 1000L, 100L, 100L);
        assertThat(values.invariantViolations()).contains(
                "Сумма активов должна быть больше нуля",
                "Оборотные активы не могут превышать сумму всех активов",
                "Краткосрочные обязательства не могут превышать сумму всех обязательств");
        values.invariantViolations().forEach(message ->
                assertThat(message).doesNotContainPattern("[A-Za-z<>=]"));
    }

    @Test
    void incompleteFinancialsUsePublicLabels() {
        var error = FinancialStatementService.incomplete(java.util.List.of("totalAssetsMinor", "equityMinor"));
        assertThat(error.getMessage()).contains("Все активы", "Собственный капитал").doesNotContain("Minor");
    }
}
