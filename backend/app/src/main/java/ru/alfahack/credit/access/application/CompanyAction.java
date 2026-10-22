package ru.alfahack.credit.access.application;

/** Действия над ресурсами компании (схема Capability публичного контракта). */
public enum CompanyAction {
    CREATE_APPLICATION,
    EDIT_DRAFT,
    UPLOAD_DOCUMENT,
    SUBMIT,
    RESPOND,
    WITHDRAW,
    ACCEPT_OFFER,
    DOWNLOAD_DOCUMENT
}
