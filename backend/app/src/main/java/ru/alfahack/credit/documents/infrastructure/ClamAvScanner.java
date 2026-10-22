package ru.alfahack.credit.documents.infrastructure;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import ru.alfahack.credit.documents.application.MalwareScanner;

/**
 * Клиент clamd (ClamAV) по TCP: zINSTREAM с чанками [длина uint32 BE][байты] и нулевым терминатором.
 * Ответ "stream: OK" — CLEAN, "... FOUND" — INFECTED, иначе (ошибка, лимит, сеть, нет базы) — ERROR.
 * Сигнатурная база входит в подготовленный образ scanner; сеть для обновления в runtime не нужна.
 */
@Component
class ClamAvScanner implements MalwareScanner {

    private static final int CHUNK = 64 * 1024;
    private static final int MAX_REPLY = 4096;

    private final String host;
    private final int port;
    private final int timeoutMillis;

    ClamAvScanner(
            @Value("${credit.scanner.clamd-host:scanner}") String host,
            @Value("${credit.scanner.clamd-port:3310}") int port,
            @Value("${credit.scanner.timeout:PT30S}") Duration timeout) {
        this.host = host;
        this.port = port;
        this.timeoutMillis = (int) timeout.toMillis();
    }

    @Override
    public Verdict scan(byte[] bytes) {
        String engine = version();
        try (Socket socket = connect()) {
            DataOutputStream out = new DataOutputStream(socket.getOutputStream());
            out.write("zINSTREAM\0".getBytes(StandardCharsets.US_ASCII));
            for (int offset = 0; offset < bytes.length; offset += CHUNK) {
                int length = Math.min(CHUNK, bytes.length - offset);
                out.writeInt(length);
                out.write(bytes, offset, length);
            }
            out.writeInt(0);
            out.flush();
            String reply = readReply(socket.getInputStream());
            if (reply.endsWith("OK") && !reply.contains("FOUND")) {
                return new Verdict(Outcome.CLEAN, engine, null);
            }
            if (reply.endsWith("FOUND")) {
                String signature = reply.substring(reply.indexOf(':') + 1, reply.length() - "FOUND".length()).trim();
                return new Verdict(Outcome.INFECTED, engine, signature);
            }
            return new Verdict(Outcome.ERROR, engine, "clamd: " + reply);
        } catch (IOException e) {
            return new Verdict(Outcome.ERROR, engine, "clamd unavailable: " + e.getClass().getSimpleName());
        }
    }

    /** "ClamAV 1.4.1/27456/..." — версия движка и базы сигнатур для квитанции. */
    String version() {
        try (Socket socket = connect()) {
            socket.getOutputStream().write("zVERSION\0".getBytes(StandardCharsets.US_ASCII));
            socket.getOutputStream().flush();
            String reply = readReply(socket.getInputStream());
            return reply.isBlank() ? "clamav-unknown" : reply;
        } catch (IOException e) {
            return "clamav-unavailable";
        }
    }

    private Socket connect() throws IOException {
        Socket socket = new Socket();
        socket.connect(new InetSocketAddress(host, port), timeoutMillis);
        socket.setSoTimeout(timeoutMillis);
        return socket;
    }

    private static String readReply(InputStream in) throws IOException {
        ByteArrayOutputStream reply = new ByteArrayOutputStream();
        int next;
        while ((next = in.read()) != -1 && next != 0) {
            if (reply.size() >= MAX_REPLY) {
                break;
            }
            reply.write(next);
        }
        return reply.toString(StandardCharsets.UTF_8).trim();
    }
}
