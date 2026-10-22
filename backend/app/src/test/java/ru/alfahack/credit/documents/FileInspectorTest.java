package ru.alfahack.credit.documents;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;

import org.junit.jupiter.api.Test;

import ru.alfahack.credit.documents.application.FileInspector;
import ru.alfahack.credit.documents.application.FileInspector.Result;
import ru.alfahack.credit.support.TestFiles;

/** P10: сигнатура, структура и лимиты 5 страниц / 40 млн пикселей до AV. */
class FileInspectorTest {

    final FileInspector inspector = new FileInspector();

    static String rejection(Result result) {
        return result instanceof Result.Rejected rejected ? rejected.reason() : "ACCEPTED";
    }

    @Test
    void acceptsPlainPdfWithinPageLimit() {
        assertThat(inspector.inspect(TestFiles.pdf(5), "application/pdf", 5))
                .isEqualTo(new Result.Accepted("application/pdf", 5));
    }

    @Test
    void rejectsSixPages() {
        assertThat(rejection(inspector.inspect(TestFiles.pdf(6), "application/pdf", 5))).isEqualTo("PAGE_LIMIT");
    }

    @Test
    void requirementCannotRaisePageLimitAboveFive() {
        assertThat(rejection(inspector.inspect(TestFiles.pdf(6), "application/pdf", 20))).isEqualTo("PAGE_LIMIT");
    }

    @Test
    void rejectsActiveContentAndEncryption() {
        assertThat(rejection(inspector.inspect(TestFiles.pdf(1, "/JavaScript (app.alert(1))", false),
                "application/pdf", 5))).isEqualTo("ACTIVE_CONTENT");
        assertThat(rejection(inspector.inspect(TestFiles.pdf(1, null, true), "application/pdf", 5)))
                .isEqualTo("ENCRYPTED");
    }

    @Test
    void rejectsSignatureMismatchAndGarbage() {
        assertThat(rejection(inspector.inspect(TestFiles.pdf(1), "image/png", 5))).isEqualTo("SIGNATURE");
        assertThat(rejection(inspector.inspect("%PDF-1.7 garbage".getBytes(StandardCharsets.US_ASCII),
                "application/pdf", 5))).isEqualTo("MALFORMED");
    }

    @Test
    void imagesAreCheckedByHeaderPixels() {
        assertThat(inspector.inspect(TestFiles.pngHeader(2000, 1000), "image/png", 5))
                .isEqualTo(new Result.Accepted("image/png", 1));
        assertThat(rejection(inspector.inspect(TestFiles.pngHeader(10_000, 5_000), "image/png", 5)))
                .isEqualTo("PIXEL_LIMIT");
        assertThat(inspector.inspect(TestFiles.jpegHeader(1200, 800), "image/jpeg", 5))
                .isEqualTo(new Result.Accepted("image/jpeg", 1));
        assertThat(rejection(inspector.inspect(TestFiles.jpegHeader(65_000, 65_000), "image/jpeg", 5)))
                .isEqualTo("PIXEL_LIMIT");
    }

    @Test
    void rejectsPolyglotImage() {
        byte[] header = TestFiles.pngHeader(100, 100);
        byte[] polyglot = new byte[header.length + 9];
        System.arraycopy(header, 0, polyglot, 0, header.length);
        System.arraycopy("%PDF-1.7\n".getBytes(StandardCharsets.US_ASCII), 0, polyglot, header.length, 9);

        assertThat(rejection(inspector.inspect(polyglot, "image/png", 5))).isEqualTo("POLYGLOT");
    }
}
