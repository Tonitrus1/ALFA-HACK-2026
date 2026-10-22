package ru.alfahack.credit.support;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.ByteBuffer;

import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.encryption.AccessPermission;
import org.apache.pdfbox.pdmodel.encryption.StandardProtectionPolicy;

/** Синтетические файлы для проверок загрузки. */
public final class TestFiles {

    /** Стандартная тестовая строка антивирусов EICAR (не вредоносна). */
    public static final String EICAR = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*";

    private TestFiles() {
    }

    public static byte[] pdf(int pages) {
        return pdf(pages, null, false);
    }

    /** PDF с N пустыми страницами; trailerComment дописывается комментарием после %%EOF. */
    public static byte[] pdf(int pages, String trailerComment, boolean encrypted) {
        try (PDDocument document = new PDDocument(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            for (int i = 0; i < pages; i++) {
                document.addPage(new PDPage());
            }
            if (encrypted) {
                StandardProtectionPolicy policy = new StandardProtectionPolicy("owner", "user", new AccessPermission());
                policy.setEncryptionKeyLength(128);
                document.protect(policy);
            }
            document.save(out);
            if (trailerComment != null) {
                out.write(("\n% " + trailerComment + "\n").getBytes(java.nio.charset.StandardCharsets.ISO_8859_1));
            }
            return out.toByteArray();
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    /** Заголовок PNG с IHDR заданных размеров (без данных изображения — для проверки лимита пикселей). */
    public static byte[] pngHeader(int width, int height) {
        ByteBuffer buffer = ByteBuffer.allocate(33);
        buffer.put(new byte[] {(byte) 0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A});
        buffer.putInt(13).put("IHDR".getBytes(java.nio.charset.StandardCharsets.US_ASCII));
        buffer.putInt(width).putInt(height).put((byte) 8).put((byte) 2).put((byte) 0).put((byte) 0).put((byte) 0);
        buffer.putInt(0);
        return buffer.array();
    }

    /** Минимальный JPEG-заголовок: SOI, APP0, SOF0 с размерами. */
    public static byte[] jpegHeader(int width, int height) {
        return new byte[] {
                (byte) 0xFF, (byte) 0xD8,
                (byte) 0xFF, (byte) 0xE0, 0x00, 0x04, 0x00, 0x00,
                (byte) 0xFF, (byte) 0xC0, 0x00, 0x0B, 0x08,
                (byte) (height >> 8), (byte) height, (byte) (width >> 8), (byte) width,
                0x01, 0x01, 0x11, 0x00,
                (byte) 0xFF, (byte) 0xD9};
    }
}
