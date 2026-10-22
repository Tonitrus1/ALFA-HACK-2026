package ru.alfahack.credit.documents.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.function.Function;

import org.junit.jupiter.api.Test;

import ru.alfahack.credit.documents.application.MalwareScanner.Outcome;
import ru.alfahack.credit.documents.application.MalwareScanner.Verdict;
import ru.alfahack.credit.support.TestFiles;

/** Протокол clamd (zVERSION, zINSTREAM) против локального TCP-сервера с ответами ClamAV. */
class ClamAvScannerTest {

    /** Минимальный clamd: читает команду и поток чанков, отвечает функцией от полученных байтов. */
    static final class FakeClamd implements AutoCloseable {

        final ServerSocket server;
        final Thread thread;

        FakeClamd(Function<byte[], String> reply) throws IOException {
            server = new ServerSocket(0);
            thread = new Thread(() -> {
                while (!server.isClosed()) {
                    try (Socket socket = server.accept()) {
                        DataInputStream in = new DataInputStream(socket.getInputStream());
                        String command = readCommand(in);
                        String answer;
                        if (command.equals("zVERSION")) {
                            answer = "ClamAV 1.4.1/27456/Tue Oct 21 08:00:00 2026";
                        } else {
                            ByteArrayOutputStream data = new ByteArrayOutputStream();
                            int length;
                            while ((length = in.readInt()) > 0) {
                                data.write(in.readNBytes(length));
                            }
                            answer = reply.apply(data.toByteArray());
                        }
                        socket.getOutputStream().write((answer + "\0").getBytes(StandardCharsets.UTF_8));
                    } catch (IOException ignored) {
                        // сервер закрыт
                    }
                }
            });
            thread.setDaemon(true);
            thread.start();
        }

        int port() {
            return server.getLocalPort();
        }

        @Override
        public void close() throws IOException {
            server.close();
        }

        static String readCommand(InputStream in) throws IOException {
            ByteArrayOutputStream command = new ByteArrayOutputStream();
            int next;
            while ((next = in.read()) > 0) {
                command.write(next);
            }
            return command.toString(StandardCharsets.US_ASCII);
        }
    }

    static String clamdReply(byte[] data) {
        String content = new String(data, StandardCharsets.ISO_8859_1);
        if (content.contains("EICAR-STANDARD-ANTIVIRUS-TEST-FILE")) {
            return "stream: Eicar-Signature FOUND";
        }
        if (content.contains("BROKEN")) {
            return "INSTREAM size limit exceeded. ERROR";
        }
        return "stream: OK";
    }

    ClamAvScanner scanner(int port) {
        return new ClamAvScanner("127.0.0.1", port, Duration.ofSeconds(5));
    }

    @Test
    void cleanStreamIsClean() throws Exception {
        try (FakeClamd clamd = new FakeClamd(ClamAvScannerTest::clamdReply)) {
            byte[] big = new byte[200_000];
            Verdict verdict = scanner(clamd.port()).scan(big);

            assertThat(verdict.outcome()).isEqualTo(Outcome.CLEAN);
            assertThat(verdict.engineVersion()).startsWith("ClamAV 1.4.1/27456");
        }
    }

    @Test
    void eicarIsInfected() throws Exception {
        try (FakeClamd clamd = new FakeClamd(ClamAvScannerTest::clamdReply)) {
            Verdict verdict = scanner(clamd.port()).scan(TestFiles.EICAR.getBytes(StandardCharsets.US_ASCII));

            assertThat(verdict.outcome()).isEqualTo(Outcome.INFECTED);
            assertThat(verdict.detail()).isEqualTo("Eicar-Signature");
        }
    }

    @Test
    void engineErrorIsNotClean() throws Exception {
        try (FakeClamd clamd = new FakeClamd(ClamAvScannerTest::clamdReply)) {
            assertThat(scanner(clamd.port()).scan("BROKEN".getBytes(StandardCharsets.US_ASCII)).outcome())
                    .isEqualTo(Outcome.ERROR);
        }
    }

    @Test
    void unavailableDaemonIsError() throws Exception {
        int port;
        try (ServerSocket probe = new ServerSocket(0)) {
            port = probe.getLocalPort();
        }
        Verdict verdict = scanner(port).scan(new byte[] {1, 2, 3});

        assertThat(verdict.outcome()).isEqualTo(Outcome.ERROR);
        assertThat(verdict.engineVersion()).isEqualTo("clamav-unavailable");
    }
}
