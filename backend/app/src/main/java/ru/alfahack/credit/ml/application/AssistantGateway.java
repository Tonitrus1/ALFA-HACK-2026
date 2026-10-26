package ru.alfahack.credit.ml.application;

import java.util.HashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/**
 * RAG-ответ в контексте, сформированном backend. После генерации цитаты повторно сверяются с allowlist
 * (документ и версия); ответ без допустимых цитат превращается в INSUFFICIENT_EVIDENCE, а не в выдумку.
 * Сбой генерации — пусто: вызывающий честно показывает недоступность или SEARCH_ONLY.
 */
@Service
public class AssistantGateway {

    private static final Logger log = LoggerFactory.getLogger(AssistantGateway.class);

    private final MlClient client;

    public AssistantGateway(MlClient client) {
        this.client = client;
    }

    public Optional<MlContracts.AssistantResponse> answer(MlContracts.RagInput input) {
        try {
            MlContracts.AssistantResponse response = client.answer(input);
            if (response.kbEpoch() != input.kbEpoch()) {
                return Optional.of(insufficient(response));
            }
            Set<String> allowed = new HashSet<>();
            input.allowedSources().forEach(s -> allowed.add(s.documentId() + ":" + s.documentVersion()));
            List<MlContracts.Citation> citations = response.citations().stream()
                    .filter(c -> allowed.contains(c.documentId() + ":" + c.documentVersion()))
                    .toList();
            boolean needsCitations = "ANSWER".equals(response.status()) || "SEARCH_ONLY".equals(response.status());
            if (citations.size() != response.citations().size() || (needsCitations && citations.isEmpty())) {
                return Optional.of(insufficient(response));
            }
            return Optional.of(response);
        } catch (RuntimeException e) {
            log.warn("Assistant unavailable requestId={} error={}", input.requestId(), e.getClass().getSimpleName());
            return Optional.empty();
        }
    }

    private static MlContracts.AssistantResponse insufficient(MlContracts.AssistantResponse response) {
        return new MlContracts.AssistantResponse(response.conversationId(), response.messageId(),
                "INSUFFICIENT_EVIDENCE", "", List.of(), response.releaseId(), response.bundleDigest(),
                response.kbEpoch());
    }
}
