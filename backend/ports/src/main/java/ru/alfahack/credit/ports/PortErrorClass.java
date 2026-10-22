package ru.alfahack.credit.ports;

/** Классы ошибок порта. Адаптер переводит ошибки SDK в этот набор. */
public enum PortErrorClass {
    INVALID_INPUT,
    NOT_FOUND,
    FORBIDDEN,
    VERSION_CONFLICT,
    UNAVAILABLE,
    DEADLINE_EXCEEDED,
    PROVIDER_NOT_IMPLEMENTED
}
