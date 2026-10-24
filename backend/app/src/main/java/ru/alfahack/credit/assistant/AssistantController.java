package ru.alfahack.credit.assistant;

import java.net.http.HttpClient;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.access.application.CompanyAccessService;
import ru.alfahack.credit.applications.application.ApplicationService;
import ru.alfahack.credit.catalog.application.CatalogService;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;

/** Browser sessions/CSRF remain authoritative; service keys and assistant tokens never reach the UI. */
@RestController
@RequestMapping("/api/v1/assistant/conversations/{conversationId}")
public class AssistantController {
    public record Message(@NotBlank @Size(max=128) String clientMessageId,
                          @NotBlank @Size(max=2000) String text) {}
    private record Remote(String id, String token) {}
    private final JdbcClient jdbc;
    private final CompanyAccessService access;
    private final ApplicationService applications;
    private final CatalogService catalog;
    private final RestClient remote;
    private final String key;

    public AssistantController(JdbcClient jdbc, CompanyAccessService access,
            ApplicationService applications, CatalogService catalog,
            @Value("${credit.assistant.base-url:}") String url,
            @Value("${credit.assistant.service-token:}") String key) {
        this.jdbc=jdbc; this.access=access; this.applications=applications; this.catalog=catalog; this.key=key;
        var factory=new JdkClientHttpRequestFactory(HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build());
        factory.setReadTimeout(Duration.ofSeconds(65));
        this.remote=RestClient.builder().baseUrl(url.isBlank()?"http://127.0.0.1:1":url).requestFactory(factory).build();
    }

    @GetMapping("/messages")
    @Transactional
    public Map<?,?> history(AuthenticatedSession session, @PathVariable String conversationId) {
        Remote s=conversation(session, conversationId);
        try {
            return remote.get().uri("/v1/sessions/{id}/messages",s.id()).header("Authorization","Bearer "+s.token()).retrieve().body(Map.class);
        } catch (RestClientException ex) { throw unavailable(); }
    }

    @GetMapping("/sources/{documentId}/{version}")
    @Transactional
    public Map<?,?> source(AuthenticatedSession session, @PathVariable String conversationId,
            @PathVariable String documentId, @PathVariable int version) {
        Remote s=conversation(session,conversationId);
        try {
            return remote.get().uri("/v1/sessions/{id}/sources/{doc}/{version}",s.id(),documentId,version)
                .header("Authorization","Bearer "+s.token()).retrieve().body(Map.class);
        } catch(RestClientResponseException ex) {
            if(ex.getStatusCode().value()==404)throw ApplicationException.notFound();
            throw unavailable();
        } catch(RestClientException ex) { throw unavailable(); }
    }

    @PostMapping("/messages")
    @Transactional
    public Map<?,?> message(AuthenticatedSession session, @PathVariable String conversationId, @Valid @RequestBody Message body) {
        Remote s=conversation(session, conversationId);
        try {
            Map<?,?> result=remote.post().uri("/v1/sessions/{id}/messages",s.id())
                .header("Authorization","Bearer "+s.token()).header("X-Admin-Key",key)
                .body(Map.of("client_message_id",body.clientMessageId(),"message",body.text(),"bank_context",bankContext(session)))
                .retrieve().body(Map.class);
            // Membership can be revoked while a long LLM request is running.
            access.getCompany(session,access.selectedCompany(session));
            return result;
        } catch (RestClientResponseException ex) {
            if(ex.getStatusCode().value()==409)throw new ApplicationException(ErrorKind.CONFLICT,"ASSISTANT_BUSY","Дождитесь завершения предыдущего сообщения");
            throw unavailable();
        } catch (RestClientException ex) { throw unavailable(); }
    }

    private Remote conversation(AuthenticatedSession session,String name) {
        if(key.length()<32)throw unavailable();
        if(!name.matches("[a-zA-Z0-9_-]{1,128}"))throw new ApplicationException(ErrorKind.INVALID_REQUEST,"INVALID_CONVERSATION","Недопустимый идентификатор диалога");
        String company=access.selectedCompany(session);
        access.getCompany(session,company);
        jdbc.sql("SELECT pg_advisory_xact_lock(hashtextextended(:scope,0))")
            .param("scope",session.sessionHash()+"|"+company+"|"+name).query().singleRow();
        jdbc.sql("DELETE FROM assistant.conversation WHERE expires_at < now()").update();
        var old=jdbc.sql("SELECT remote_id,remote_token FROM assistant.conversation WHERE owner_hash=:owner AND company_id=:company AND conversation_id=:name")
            .param("owner",session.sessionHash()).param("company",company).param("name",name)
            .query((rs,n)->new Remote(rs.getString(1),rs.getString(2))).optional();
        if(old.isPresent()) {
            try {
                remote.get().uri("/v1/sessions/{id}/messages",old.get().id()).header("Authorization","Bearer "+old.get().token()).retrieve().toBodilessEntity();
                return old.get();
            } catch(RestClientResponseException ex) { if(ex.getStatusCode().value()!=404)throw unavailable(); }
            catch(RestClientException ex) { throw unavailable(); }
        }
        try {
            Map<?,?> created=remote.post().uri("/v1/sessions").header("X-Admin-Key",key)
                .body(Map.of("identity",Map.of("actor_id",session.actorId(),"company_id",company)))
                .retrieve().body(Map.class);
            Remote s=new Remote((String)created.get("session_id"),(String)created.get("session_token"));
            jdbc.sql("INSERT INTO assistant.conversation VALUES (:owner,:company,:name,:remote,:token,now()+interval '55 minutes') ON CONFLICT (owner_hash,company_id,conversation_id) DO UPDATE SET remote_id=excluded.remote_id,remote_token=excluded.remote_token,expires_at=excluded.expires_at")
                .param("owner",session.sessionHash()).param("company",company).param("name",name).param("remote",s.id()).param("token",s.token()).update();
            return s;
        } catch(RestClientException ex) { throw unavailable(); }
    }

    private Map<String,Object> bankContext(AuthenticatedSession session) {
        String company=access.selectedCompany(session);
        List<Object> products=new ArrayList<>();
        String cursor=null;
        do {
            var page=catalog.listActive(cursor,100);
            for(var p:page.items())products.add(Map.of("id",p.productId(),"name",p.name(),"purpose",p.purpose(),
                "min_amount_minor",p.minAmountMinor(),"max_amount_minor",p.maxAmountMinor(),
                "documents",catalog.requirements(p.productId(),p.requirementsVersion()),"disclosure",p.preliminaryDisclosure()));
            cursor=page.nextCursor();
        } while(cursor!=null);
        List<Object> apps=new ArrayList<>();
        cursor=null;
        do {
            var page=applications.list(session,company,cursor,100);
            for(var a:page.items())apps.add(Map.of("id",a.applicationId(),"company_id",company,"product_id",a.productId(),"status",a.status(),"version",a.version()));
            cursor=page.nextCursor();
        } while(cursor!=null);
        return Map.of("company_id",company,"products",products,"applications",apps);
    }
    private static ApplicationException unavailable() {
        return new ApplicationException(ErrorKind.UNAVAILABLE,"ASSISTANT_UNAVAILABLE","Помощник временно недоступен. Проверьте настройки LLM и состояние сервиса.");
    }
}
