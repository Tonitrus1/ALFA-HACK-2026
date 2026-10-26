package ru.alfahack.credit.integration.application;

import java.util.Optional;

import org.springframework.stereotype.Service;

import ru.alfahack.credit.integration.infrastructure.BankCaseRepository;

/** Чтение банковских дел для проекций. Компания проверяется вызывающим модулем. */
@Service
public class BankCases {

    private final BankCaseRepository cases;

    public BankCases(BankCaseRepository cases) {
        this.cases = cases;
    }

    public Optional<BankCaseView> forApplication(String applicationId) {
        return cases.findByApplication(applicationId);
    }
}
