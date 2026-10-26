package ru.alfahack.credit.journey.application;

import java.time.Clock;
import java.util.List;
import java.util.Optional;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import ru.alfahack.credit.journey.infrastructure.InformationRequestRepository;
import ru.alfahack.credit.platform.support.Times;

/** Запросы банка: OPEN → RESPONDED (ответ клиента) → CLOSED (банк принял). Один открытый на заявку. */
@Service
public class InformationRequests {

    private final InformationRequestRepository requests;
    private final Clock clock;

    public InformationRequests(InformationRequestRepository requests, Clock clock) {
        this.requests = requests;
        this.clock = clock;
    }

    @Transactional(propagation = Propagation.MANDATORY)
    public void open(InformationRequestView request) {
        requests.insert(request);
    }

    public Optional<InformationRequestView> find(String requestId) {
        return requests.find(requestId);
    }

    public List<InformationRequestView> forApplication(String applicationId) {
        return requests.forApplication(applicationId);
    }

    @Transactional(propagation = Propagation.MANDATORY)
    public boolean markResponded(String requestId) {
        return requests.transition(requestId, "OPEN", "RESPONDED", Times.now(clock));
    }

    @Transactional(propagation = Propagation.MANDATORY)
    public boolean close(String requestId) {
        return requests.transition(requestId, "RESPONDED", "CLOSED", Times.now(clock));
    }
}
