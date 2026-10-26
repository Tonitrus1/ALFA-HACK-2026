package ru.alfahack.credit.ports.objects;

public record ObjectRef(
        String objectId,
        long version,
        String sha256,
        long size,
        String mediaType,
        ScanStatus scanStatus) {
}
