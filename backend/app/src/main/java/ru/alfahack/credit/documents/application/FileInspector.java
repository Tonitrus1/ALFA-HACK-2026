package ru.alfahack.credit.documents.application;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.regex.Pattern;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentNameDictionary;
import org.springframework.stereotype.Component;

/**
 * Проверка сигнатуры и структуры в карантине до AV (backend guide, раздел 4): сигнатура совпадает с
 * объявленным типом; PDF без шифрования, JavaScript, вложений и действий запуска, не больше лимита страниц;
 * изображение не больше 40 млн пикселей по заголовку — без декодирования полного буфера. Полиглоты отклоняются.
 * Полный рендер выполняет изолированный OCR-worker; здесь только безопасный разбор.
 */
@Component
public class FileInspector {

    public static final int MAX_PAGES = 5;
    public static final long MAX_PIXELS = 40_000_000L;

    private static final byte[] PDF = "%PDF-".getBytes(StandardCharsets.US_ASCII);
    private static final byte[] PNG = {(byte) 0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A};
    private static final byte[] JPEG = {(byte) 0xFF, (byte) 0xD8, (byte) 0xFF};
    private static final Pattern ACTIVE_PDF = Pattern.compile(
            "/(JavaScript|JS|Launch|EmbeddedFile|EmbeddedFiles|RichMedia|XFA|SubmitForm|ImportData)(?![A-Za-z0-9])");

    public sealed interface Result {
        record Accepted(String contentType, int pages) implements Result {
        }

        record Rejected(String reason) implements Result {
        }
    }

    public Result inspect(byte[] bytes, String declaredType, int maxPages) {
        int pageLimit = Math.min(Math.max(maxPages, 1), MAX_PAGES);
        return switch (declaredType) {
            case "application/pdf" -> startsWith(bytes, PDF) ? inspectPdf(bytes, pageLimit) : rejected("SIGNATURE");
            case "image/png" -> startsWith(bytes, PNG) ? inspectPng(bytes) : rejected("SIGNATURE");
            case "image/jpeg" -> startsWith(bytes, JPEG) ? inspectJpeg(bytes) : rejected("SIGNATURE");
            default -> rejected("CONTENT_TYPE");
        };
    }

    private static Result inspectPdf(byte[] bytes, int pageLimit) {
        if (ACTIVE_PDF.matcher(new String(bytes, StandardCharsets.ISO_8859_1)).find()) {
            return rejected("ACTIVE_CONTENT");
        }
        try (PDDocument document = Loader.loadPDF(bytes)) {
            if (document.isEncrypted()) {
                return rejected("ENCRYPTED");
            }
            PDDocumentNameDictionary names = document.getDocumentCatalog().getNames();
            if (names != null && (names.getJavaScript() != null || names.getEmbeddedFiles() != null)) {
                return rejected("ACTIVE_CONTENT");
            }
            int pages = document.getNumberOfPages();
            if (pages < 1) {
                return rejected("MALFORMED");
            }
            if (pages > pageLimit) {
                return rejected("PAGE_LIMIT");
            }
            return new Result.Accepted("application/pdf", pages);
        } catch (IOException | RuntimeException e) {
            return rejected(e.getClass().getSimpleName().contains("Password") ? "ENCRYPTED" : "MALFORMED");
        }
    }

    private static Result inspectPng(byte[] bytes) {
        if (containsPdfMarker(bytes) || bytes.length < 24) {
            return rejected(bytes.length < 24 ? "MALFORMED" : "POLYGLOT");
        }
        boolean ihdr = bytes[12] == 'I' && bytes[13] == 'H' && bytes[14] == 'D' && bytes[15] == 'R';
        if (!ihdr) {
            return rejected("MALFORMED");
        }
        return checkPixels(readInt(bytes, 16), readInt(bytes, 20), "image/png");
    }

    private static Result inspectJpeg(byte[] bytes) {
        if (containsPdfMarker(bytes)) {
            return rejected("POLYGLOT");
        }
        int offset = 2;
        while (offset + 9 < bytes.length) {
            if ((bytes[offset] & 0xFF) != 0xFF) {
                return rejected("MALFORMED");
            }
            int marker = bytes[offset + 1] & 0xFF;
            if (marker == 0xFF) {
                offset++;
                continue;
            }
            int length = ((bytes[offset + 2] & 0xFF) << 8) | (bytes[offset + 3] & 0xFF);
            boolean startOfFrame = marker >= 0xC0 && marker <= 0xCF && marker != 0xC4 && marker != 0xC8 && marker != 0xCC;
            if (startOfFrame) {
                long height = ((bytes[offset + 5] & 0xFF) << 8) | (bytes[offset + 6] & 0xFF);
                long width = ((bytes[offset + 7] & 0xFF) << 8) | (bytes[offset + 8] & 0xFF);
                return checkPixels(width, height, "image/jpeg");
            }
            if (length < 2) {
                return rejected("MALFORMED");
            }
            offset += 2 + length;
        }
        return rejected("MALFORMED");
    }

    private static Result checkPixels(long width, long height, String contentType) {
        if (width <= 0 || height <= 0) {
            return rejected("MALFORMED");
        }
        if (width * height > MAX_PIXELS) {
            return rejected("PIXEL_LIMIT");
        }
        return new Result.Accepted(contentType, 1);
    }

    private static boolean containsPdfMarker(byte[] bytes) {
        for (int i = 1; i + PDF.length <= bytes.length; i++) {
            if (Arrays.equals(bytes, i, i + PDF.length, PDF, 0, PDF.length)) {
                return true;
            }
        }
        return false;
    }

    private static boolean startsWith(byte[] bytes, byte[] prefix) {
        return bytes.length >= prefix.length && Arrays.equals(bytes, 0, prefix.length, prefix, 0, prefix.length);
    }

    private static long readInt(byte[] bytes, int offset) {
        return ((long) (bytes[offset] & 0xFF) << 24) | ((bytes[offset + 1] & 0xFF) << 16)
                | ((bytes[offset + 2] & 0xFF) << 8) | (bytes[offset + 3] & 0xFF);
    }

    private static Result rejected(String reason) {
        return new Result.Rejected(reason);
    }
}
