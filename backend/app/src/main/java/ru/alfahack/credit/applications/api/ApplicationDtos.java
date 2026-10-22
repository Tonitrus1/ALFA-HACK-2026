package ru.alfahack.credit.applications.api;

import java.time.Instant;
import java.util.List;
import java.util.Set;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import com.fasterxml.jackson.annotation.JsonInclude;

import ru.alfahack.credit.applications.application.ApplicationCommands;
import ru.alfahack.credit.applications.application.ApplicationView;
import ru.alfahack.credit.applications.application.BusinessData;
import ru.alfahack.credit.platform.support.Money;

/** HTTP-схемы applications публичного контракта (additionalProperties: false). */
final class ApplicationDtos {

    static final long MAX_SAFE = 9007199254740991L;

    private ApplicationDtos() {
    }

    record Need(
            @NotBlank @Size(max = 2000) String purpose,
            @NotNull @Valid Money amount,
            @NotNull @Min(1) @Max(MAX_SAFE) Integer termMonths,
            @Pattern(regexp = "NORMAL|URGENT") String urgency) {
    }

    record CreateApplication(
            @NotBlank @Size(max = 256) String companyId,
            @NotBlank @Size(max = 256) String productId,
            @NotNull @Min(1) @Max(MAX_SAFE) Long productVersion,
            @NotNull @Valid Need need) {

        ApplicationCommands.Create toCommand() {
            return new ApplicationCommands.Create(
                    companyId, productId, productVersion, need.purpose(), need.amount().amountMinor(),
                    need.termMonths(), need.urgency());
        }
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    record Business(
            @Valid Money annualRevenue,
            @Valid Money annualExpenses,
            @Valid Money currentDebt,
            @Min(0) @Max(MAX_SAFE) Long businessAgeMonths,
            @Size(max = 2000) String activityDescription,
            @Size(max = 256) String sourceConfirmationVersion) {

        BusinessData toData() {
            return new BusinessData(
                    minor(annualRevenue), minor(annualExpenses), minor(currentDebt), businessAgeMonths,
                    activityDescription, sourceConfirmationVersion);
        }

        static Business of(BusinessData data) {
            return new Business(
                    Money.rubOrNull(data.annualRevenueMinor()), Money.rubOrNull(data.annualExpensesMinor()),
                    Money.rubOrNull(data.currentDebtMinor()), data.businessAgeMonths(), data.activityDescription(),
                    data.sourceConfirmationVersion());
        }

        private static Long minor(Money money) {
            return money == null ? null : money.amountMinor();
        }
    }

    /** DraftPatch: и запрос PATCH, и поле terms ответа. */
    @JsonInclude(JsonInclude.Include.NON_NULL)
    record DraftPatch(
            @Size(max = 2000) String purpose,
            @Valid Money amount,
            @Min(1) @Max(MAX_SAFE) Integer termMonths,
            @Valid Business business,
            @Size(min = 1, max = 100) Set<String> clearFields) {

        boolean isEmpty() {
            return purpose == null && amount == null && termMonths == null && business == null && clearFields == null;
        }

        ApplicationCommands.Patch toCommand() {
            return new ApplicationCommands.Patch(
                    purpose, amount == null ? null : amount.amountMinor(), termMonths,
                    business == null ? null : business.toData(), clearFields);
        }
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    record Application(
            String applicationId,
            String companyId,
            String productId,
            long productVersion,
            long version,
            String status,
            DraftPatch terms,
            Instant updatedAt,
            List<String> confirmedExtractionIds,
            Long financialStatementVersion,
            String financialSnapshotId) {

        static Application of(ApplicationView view) {
            Business business = view.business().isEmpty() ? null : Business.of(view.business());
            return new Application(
                    view.applicationId(), view.companyId(), view.productId(), view.productVersion(), view.version(),
                    view.status(),
                    new DraftPatch(view.purpose(), Money.rub(view.amountMinor()), view.termMonths(), business, null),
                    view.updatedAt(), null, view.financialStatementVersion(), view.financialSnapshotId());
        }
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    record ApplicationList(List<Application> items, String nextCursor) {
    }

    record DocumentReference(
            @NotBlank @Size(max = 256) String documentId,
            @NotNull @Min(1) @Max(MAX_SAFE) Long documentVersion,
            @NotBlank @Size(max = 256) String objectVersion) {
    }

    record Submit(
            @NotNull @Min(1) @Max(MAX_SAFE) Long expectedVersion,
            @NotNull @Size(max = 100) List<@NotBlank @Size(max = 256) String> consentRecordIds,
            @NotNull @Size(max = 100) List<@NotBlank @Size(max = 256) String> documentIds,
            @NotNull @Size(max = 100) List<@NotNull @Valid DocumentReference> documentReferences,
            @NotNull @Min(1) @Max(MAX_SAFE) Long requirementsVersion,
            @NotNull @Min(1) @Max(MAX_SAFE) Long financialStatementVersion) {

        ApplicationCommands.Submit toCommand() {
            return new ApplicationCommands.Submit(
                    expectedVersion, consentRecordIds, documentIds,
                    documentReferences.stream()
                            .map(ref -> new ApplicationCommands.DocumentReference(
                                    ref.documentId(), ref.documentVersion(), ref.objectVersion()))
                            .toList(),
                    requirementsVersion, financialStatementVersion);
        }
    }

    record CommandReceipt(String operationId, String applicationId, Instant acceptedAt, String statusUrl) {

        static CommandReceipt of(ApplicationCommands.Receipt receipt) {
            return new CommandReceipt(
                    receipt.operationId(), receipt.applicationId(), receipt.acceptedAt(),
                    "/api/v1/operations/" + receipt.operationId());
        }
    }
}
