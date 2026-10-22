package ru.alfahack.credit.ports.objects;

/** Подмножество состояний Document из публичного контракта, относящееся к байтам объекта. */
public enum ScanStatus {
    QUARANTINED,
    CLEAN,
    REJECTED
}
