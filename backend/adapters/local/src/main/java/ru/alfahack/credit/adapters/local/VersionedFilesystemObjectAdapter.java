package ru.alfahack.credit.adapters.local;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.UncheckedIOException;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.UUID;
import java.util.regex.Pattern;

import ru.alfahack.credit.ports.PortErrorClass;
import ru.alfahack.credit.ports.PortException;
import ru.alfahack.credit.ports.objects.ActorScope;
import ru.alfahack.credit.ports.objects.ObjectRef;
import ru.alfahack.credit.ports.objects.ObjectStorePort;
import ru.alfahack.credit.ports.objects.ScanReceipt;
import ru.alfahack.credit.ports.objects.ScanStatus;

/**
 * Неизменяемые версии файлов в постоянных томах quarantine/ и clean/. Путь строится только из UUID объекта
 * и номера версии — путь браузера или имя файла не используются. Чтение clean-версии сверяет размер и SHA-256.
 * Принадлежность компании и AV-статус в метаданных проверяет владелец документов до вызова openClean.
 * Ограничение: не S3 API, не общий многоузловой том, нет управляемой долговечности.
 */
public class VersionedFilesystemObjectAdapter implements ObjectStorePort {

    private static final Pattern OBJECT_ID = Pattern.compile("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$");
    private static final int BUFFER = 64 * 1024;

    private final Path quarantine;
    private final Path clean;

    public VersionedFilesystemObjectAdapter(Path root) {
        try {
            Path base = root.toAbsolutePath().normalize();
            this.quarantine = Files.createDirectories(base.resolve("quarantine"));
            this.clean = Files.createDirectories(base.resolve("clean"));
        } catch (IOException e) {
            throw new UncheckedIOException("Object store root is not writable", e);
        }
    }

    /** Потоково пишет байты в карантин; превышение лимита удаляет частичный файл и даёт INVALID_INPUT. */
    @Override
    public ObjectRef putQuarantine(InputStream stream, long limitBytes) {
        String objectId = UUID.randomUUID().toString();
        Path target = path(quarantine, objectId, 1);
        Path partial = target.resolveSibling(target.getFileName() + ".part");
        MessageDigest sha256 = sha256();
        long size = 0;
        try {
            Files.createDirectories(target.getParent());
            try (InputStream in = new DigestInputStream(stream, sha256);
                 OutputStream out = Files.newOutputStream(partial, StandardOpenOption.CREATE_NEW)) {
                byte[] buffer = new byte[BUFFER];
                int read;
                while ((read = in.read(buffer)) != -1) {
                    size += read;
                    if (size > limitBytes) {
                        throw new PortException(PortErrorClass.INVALID_INPUT, "Object exceeds size limit");
                    }
                    out.write(buffer, 0, read);
                }
            }
            move(partial, target);
        } catch (IOException e) {
            deleteQuietly(partial);
            throw new PortException(PortErrorClass.UNAVAILABLE, "Object store write failed", e);
        } catch (RuntimeException e) {
            deleteQuietly(partial);
            throw e;
        }
        return new ObjectRef(objectId, 1, HexFormat.of().formatHex(sha256.digest()), size, null,
                ScanStatus.QUARANTINED);
    }

    /** Копирует точную карантинную версию в clean только по CLEAN-квитанции той же версии и того же хеша. */
    @Override
    public ObjectRef promote(ObjectRef exactRef, ScanReceipt scanReceipt) {
        requireObjectId(exactRef.objectId());
        boolean matches = scanReceipt.result() == ScanStatus.CLEAN
                && scanReceipt.objectId().equals(exactRef.objectId())
                && scanReceipt.version() == exactRef.version()
                && scanReceipt.sha256().equals(exactRef.sha256());
        if (!matches) {
            throw new PortException(PortErrorClass.FORBIDDEN, "Scan receipt does not allow promotion");
        }
        Path source = path(quarantine, exactRef.objectId(), exactRef.version());
        Path target = path(clean, exactRef.objectId(), exactRef.version());
        try {
            verify(source, exactRef);
            if (!Files.exists(target)) {
                Files.createDirectories(target.getParent());
                Path partial = target.resolveSibling(target.getFileName() + ".part");
                Files.copy(source, partial, StandardCopyOption.REPLACE_EXISTING);
                move(partial, target);
            }
            verify(target, exactRef);
        } catch (IOException e) {
            throw new PortException(PortErrorClass.UNAVAILABLE, "Object store promote failed", e);
        }
        return new ObjectRef(exactRef.objectId(), exactRef.version(), exactRef.sha256(), exactRef.size(),
                exactRef.mediaType(), ScanStatus.CLEAN);
    }

    /** Только clean-версия с совпадающими размером и SHA-256; иначе VERSION_CONFLICT/NOT_FOUND. */
    @Override
    public InputStream openClean(ObjectRef exactRef, ActorScope actorScope) {
        if (actorScope == null || actorScope.companyId() == null) {
            throw new PortException(PortErrorClass.FORBIDDEN, "Actor scope is required");
        }
        requireObjectId(exactRef.objectId());
        if (exactRef.scanStatus() != ScanStatus.CLEAN) {
            throw new PortException(PortErrorClass.FORBIDDEN, "Object is not clean");
        }
        Path file = path(clean, exactRef.objectId(), exactRef.version());
        try {
            verify(file, exactRef);
            return Files.newInputStream(file);
        } catch (IOException e) {
            throw new PortException(PortErrorClass.UNAVAILABLE, "Object store read failed", e);
        }
    }

    private void verify(Path file, ObjectRef exactRef) throws IOException {
        if (!Files.isRegularFile(file)) {
            throw new PortException(PortErrorClass.NOT_FOUND, "Object version not found");
        }
        if (Files.size(file) != exactRef.size() || !sha256Hex(file).equals(exactRef.sha256())) {
            throw new PortException(PortErrorClass.VERSION_CONFLICT, "Object digest mismatch");
        }
    }

    private static Path path(Path area, String objectId, long version) {
        requireObjectId(objectId);
        if (version < 1) {
            throw new PortException(PortErrorClass.INVALID_INPUT, "Invalid object version");
        }
        Path resolved = area.resolve(objectId.substring(0, 2)).resolve(objectId).resolve("v" + version).normalize();
        if (!resolved.startsWith(area)) {
            throw new PortException(PortErrorClass.INVALID_INPUT, "Invalid object path");
        }
        return resolved;
    }

    private static void requireObjectId(String objectId) {
        if (objectId == null || !OBJECT_ID.matcher(objectId).matches()) {
            throw new PortException(PortErrorClass.INVALID_INPUT, "Invalid object id");
        }
    }

    private static void move(Path from, Path to) throws IOException {
        try {
            Files.move(from, to, StandardCopyOption.ATOMIC_MOVE);
        } catch (AtomicMoveNotSupportedException e) {
            Files.move(from, to);
        }
    }

    private static String sha256Hex(Path file) throws IOException {
        MessageDigest digest = sha256();
        try (InputStream in = new DigestInputStream(Files.newInputStream(file), digest)) {
            in.transferTo(OutputStream.nullOutputStream());
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is not available", e);
        }
    }

    private static void deleteQuietly(Path file) {
        try {
            Files.deleteIfExists(file);
        } catch (IOException ignored) {
            // частичный файл в карантине без метаданных не читается
        }
    }
}
