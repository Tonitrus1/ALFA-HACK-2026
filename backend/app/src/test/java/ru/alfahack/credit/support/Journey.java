package ru.alfahack.credit.support;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.UUID;

import com.jayway.jsonpath.JsonPath;

import org.springframework.test.web.servlet.MockMvc;

import ru.alfahack.credit.integration.application.ReviewWorker;
import ru.alfahack.credit.journey.application.OutboxDispatcher;

/** Полный путь заявки до рассмотрения симулятором. */
public record Journey(MockMvc mvc, DemoClient client, OutboxDispatcher dispatcher, ReviewWorker reviews) {

    /** Создаёт, заполняет бизнес и финансы, отправляет; возвращает applicationId. */
    public String submit(long amountMinor, String businessJson, String valuesJson) throws Exception {
        String created = mvc.perform(client.json(post("/api/v1/applications"),
                        Bodies.create("company-a", amountMinor, 12))
                        .header("Idempotency-Key", "create-" + UUID.randomUUID()))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        String id = JsonPath.read(created, "$.applicationId");
        mvc.perform(client.json(patch("/api/v1/applications/" + id), "{\"business\":" + businessJson + "}")
                        .header("If-Match", "\"v1\""))
                .andExpect(status().isOk());
        long version = Financials.fillAndConfirm(mvc, client, id, 2, valuesJson);
        mvc.perform(client.json(post("/api/v1/applications/" + id + "/submit"), Bodies.submit(version, 1))
                        .header("Idempotency-Key", "submit-" + UUID.randomUUID()))
                .andExpect(status().isAccepted());
        return id;
    }

    /** Доставка событий и рассмотрение до полной остановки очередей. */
    public void settle() {
        boolean progressed = true;
        while (progressed) {
            progressed = false;
            while (dispatcher.dispatchOnce() > 0) {
                progressed = true;
            }
            while (reviews.processOnce()) {
                progressed = true;
            }
        }
    }
}
