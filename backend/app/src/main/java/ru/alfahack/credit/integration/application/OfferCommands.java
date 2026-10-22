package ru.alfahack.credit.integration.application;

import java.sql.Timestamp;
import java.time.Clock;
import java.util.Set;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.access.application.CompanyAccessService;
import ru.alfahack.credit.access.application.CompanyAction;
import ru.alfahack.credit.integration.infrastructure.BankCaseRepository;
import ru.alfahack.credit.integration.infrastructure.DecisionRepository;
import ru.alfahack.credit.platform.support.Digests;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;
import tools.jackson.databind.json.JsonMapper;

/** Durable demonstration acceptance/completion. No money movement. */
@Service
public class OfferCommands {
    private final JdbcClient jdbc;
    private final DecisionRepository decisions;
    private final BankCaseRepository cases;
    private final CompanyAccessService access;
    private final Clock clock;
    private final JsonMapper json;
    public OfferCommands(JdbcClient jdbc, DecisionRepository decisions, BankCaseRepository cases,
                         CompanyAccessService access, Clock clock, JsonMapper json) {
        this.jdbc=jdbc; this.decisions=decisions; this.cases=cases; this.access=access; this.clock=clock; this.json=json;
    }
    @Transactional
    public OfferView execute(AuthenticatedSession s, String id, long expected, String key, boolean complete) {
        String company=access.selectedCompany(s);
        access.requireAction(s,company,CompanyAction.ACCEPT_OFFER);
        access.recheckAction(s.actorId(),company,CompanyAction.ACCEPT_OFFER);
        String fingerprint=Digests.sha256(id+"|"+expected+"|"+complete);
        jdbc.sql("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")
            .param("key",s.actorId()+"|"+company+"|"+key).query((rs,row)->true).single();
        var old=jdbc.sql("SELECT fingerprint,response::text AS response FROM integration.offer_command WHERE actor_id=:a AND company_id=:c AND client_key=:k")
            .param("a",s.actorId()).param("c",company).param("k",key).query().listOfRows().stream().findFirst();
        if(old.isPresent()) {
            if(!fingerprint.equals(old.get().get("fingerprint")))throw conflict("IDEMPOTENCY_KEY_REUSED");
            return json.readValue(old.get().get("response").toString(),OfferView.class);
        }
        jdbc.sql("SELECT offer_id FROM integration.offer WHERE offer_id=:id AND company_id=:c FOR UPDATE")
            .param("id",id).param("c",company).query(String.class).optional().orElseThrow(ApplicationException::notFound);
        OfferView offer=decisions.offer(id).orElseThrow(ApplicationException::notFound);
        var bank=cases.findByApplication(offer.applicationId()).orElseThrow(ApplicationException::notFound);
        String from=complete?"ACCEPTED":"AVAILABLE", to=complete?"COMPLETED":"ACCEPTED";
        if(offer.version()!=expected)throw conflict("OFFER_VERSION_CONFLICT");
        if(!from.equals(offer.effectiveStatus(clock.instant()))
           || (complete?!"ACCEPTED".equals(bank.status()):!Set.of("APPROVED","ALTERNATIVE").contains(bank.status())))throw conflict("OFFER_STATE_CONFLICT");
        if(!cases.transition(bank.caseId(),bank.caseVersion(),bank.status(),to,null,clock.instant()))throw conflict("CASE_VERSION_CONFLICT");
        int changed=jdbc.sql("UPDATE integration.offer SET status=:to,version=version+1 WHERE offer_id=:id AND version=:v AND status=:from")
            .param("to",to).param("id",id).param("v",expected).param("from",from).update();
        if(changed!=1)throw conflict("OFFER_VERSION_CONFLICT");
        OfferView result=decisions.offer(id).orElseThrow();
        jdbc.sql("INSERT INTO integration.offer_command(actor_id,company_id,client_key,fingerprint,response,created_at) VALUES(:a,:c,:k,:f,CAST(:r AS jsonb),:now)")
            .param("a",s.actorId()).param("c",company).param("k",key).param("f",fingerprint)
            .param("r",json.writeValueAsString(result)).param("now",Timestamp.from(clock.instant())).update();
        return result;
    }
    private static ApplicationException conflict(String code) {
        return new ApplicationException(ErrorKind.CONFLICT,code,"Предложение изменилось. Обновите условия перед действием");
    }
}
