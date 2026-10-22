package ru.alfahack.credit.journey.application;

import java.time.Clock;
import java.util.Optional;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import ru.alfahack.credit.journey.infrastructure.OperationRepository;

/**
 * Идемпотентность команд: уникальный (actor, company, commandType, clientKey) в БД, а не check-then-insert.
 * Повтор с тем же ключом и телом возвращает исходный результат до проверок текущего состояния.
 */
@Service
public class CommandOperations {

    public enum Start { STARTED, DUPLICATE }

    private final OperationRepository operations;
    private final Clock clock;

    public CommandOperations(OperationRepository operations, Clock clock) {
        this.operations = operations;
        this.clock = clock;
    }

    public Optional<OperationView> findByKey(String actorId, String companyId, String commandType, String clientKey) {
        return operations.findByKey(actorId, companyId, commandType, clientKey);
    }

    /** Вставляет PENDING-операцию в транзакции команды; при гонке за ключ возвращает DUPLICATE. */
    @Transactional(propagation = Propagation.MANDATORY)
    public Start start(OperationView operation) {
        return operations.insertIfAbsent(operation) ? Start.STARTED : Start.DUPLICATE;
    }

    /** PENDING/RECONCILING → итоговое состояние; повтор для уже завершённой операции ничего не меняет. */
    @Transactional(propagation = Propagation.MANDATORY)
    public void complete(String operationId, String state, String resultCode, String safeMessage) {
        operations.complete(operationId, state, resultCode, safeMessage, clock.instant());
    }

    /** Компания операции — для обработчиков событий, которым нужен владелец ресурса. */
    public Optional<String> findCompany(String operationId) {
        return operations.findById(operationId).map(OperationView::companyId);
    }

    /** Чтение ограничено actor + company. */
    public Optional<OperationView> findForActor(String operationId, String actorId, String companyId) {
        return operations.findById(operationId)
                .filter(operation -> operation.actorId().equals(actorId) && operation.companyId().equals(companyId));
    }
}
