package ru.alfahack.credit.ports.objects;

/** Результат AV-проверки точной версии объекта. */
public record ScanReceipt(String objectId, long version, String sha256, ScanStatus result) {
}
