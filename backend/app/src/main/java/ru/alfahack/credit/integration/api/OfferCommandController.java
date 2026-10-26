package ru.alfahack.credit.integration.api;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.integration.application.OfferCommands;
import ru.alfahack.credit.integration.application.OfferView;
import ru.alfahack.credit.platform.support.ETags;
import ru.alfahack.credit.platform.support.Money;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;
@RestController
@Validated
class OfferCommandController {
    record Input(@NotNull @Min(1) @Max(9007199254740991L) Long expectedVersion) {}
    private final OfferCommands commands;
    OfferCommandController(OfferCommands commands){this.commands=commands;}
    @PostMapping(path="/api/v1/offers/{id}/{action:accept|complete}",consumes="application/json")
    DecisionController.Offer execute(AuthenticatedSession s, @PathVariable String id, @PathVariable String action,
            @RequestHeader("X-Company-Context") long context,
            @RequestHeader("Idempotency-Key") @NotBlank @Size(max=128) String key,
            @RequestHeader("If-Match") String etag, @Valid @RequestBody Input input) {
        if(ETags.parseIfMatch(etag)!=input.expectedVersion())throw new ApplicationException(ErrorKind.INVALID_REQUEST,"VERSION_MISMATCH","Версии команды различаются");
        OfferView o=commands.execute(s,id,input.expectedVersion(),key,"complete".equals(action));
        return new DecisionController.Offer(o.offerId(),o.applicationId(),o.version(),o.status(),Money.rub(o.amountMinor()),o.termMonths(),o.termsDisclosure(),o.validUntil());
    }
}
