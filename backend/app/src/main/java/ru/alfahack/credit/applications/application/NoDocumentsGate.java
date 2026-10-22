package ru.alfahack.credit.applications.application;

import java.util.List;

import org.springframework.stereotype.Component;

/** До P10 документов нет: допустим только пустой список ссылок. */
@Component
class NoDocumentsGate implements DocumentReferenceGate {

    @Override
    public boolean allClean(ApplicationView application, List<ApplicationCommands.DocumentReference> references) {
        return references.isEmpty();
    }
}
