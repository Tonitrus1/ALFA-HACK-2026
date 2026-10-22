package ru.alfahack.credit.applications.domain;

/** Статусы заявки (state-machine.json v1.4). Редактируемые данные меняются только в DRAFT. */
public enum ApplicationStatus {
    DRAFT,
    SUBMITTED,
    REVIEW,
    MANUAL,
    NEEDS_INFO,
    APPROVED,
    ALTERNATIVE,
    DECLINED,
    ACCEPTED,
    COMPLETED,
    CANCELLED,
    EXPIRED
}
