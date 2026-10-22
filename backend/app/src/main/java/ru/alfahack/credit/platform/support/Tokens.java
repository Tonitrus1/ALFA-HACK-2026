package ru.alfahack.credit.platform.support;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Base64;

/** Случайные секреты (гранты, токены аренды); в БД хранится только SHA-256. */
public final class Tokens {

    private static final SecureRandom RANDOM = new SecureRandom();

    private Tokens() {
    }

    public static String random() {
        byte[] bytes = new byte[32];
        RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    public static boolean matchesHash(String presented, String expectedHash) {
        if (presented == null || expectedHash == null) {
            return false;
        }
        return MessageDigest.isEqual(
                Digests.sha256(presented).getBytes(StandardCharsets.UTF_8),
                expectedHash.getBytes(StandardCharsets.UTF_8));
    }
}
