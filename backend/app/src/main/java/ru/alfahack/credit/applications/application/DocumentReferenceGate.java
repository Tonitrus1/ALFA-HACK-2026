package ru.alfahack.credit.applications.application;

import java.util.List;

/**
 * Проверка точных ссылок на документы заявки (принадлежность, версия, CLEAN-байты). Владелец — documents (P10).
 * Реализация отказывает закрыто: непроверяемая ссылка недопустима.
 */
public interface DocumentReferenceGate {

    boolean allClean(ApplicationView application, List<ApplicationCommands.DocumentReference> references);
}
