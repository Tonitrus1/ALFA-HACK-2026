package ru.alfahack.credit.ports.sessions;

import java.time.Instant;

public record RevocationReceipt(String sessionHash, long version, Instant revokedAt) {
}
