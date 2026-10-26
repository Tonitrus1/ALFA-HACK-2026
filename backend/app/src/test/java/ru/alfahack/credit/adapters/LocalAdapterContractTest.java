package ru.alfahack.credit.adapters;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.List;
import java.util.stream.Stream;

import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import ru.alfahack.credit.adapters.local.BoundedLocalCacheAdapter;
import ru.alfahack.credit.adapters.local.PostgresOutboxTransportAdapter;
import ru.alfahack.credit.adapters.local.VersionedFilesystemObjectAdapter;
import ru.alfahack.credit.ports.PortErrorClass;
import ru.alfahack.credit.ports.PortException;
import ru.alfahack.credit.ports.cache.CacheLookup;
import ru.alfahack.credit.ports.events.DeliveryReceipt;
import ru.alfahack.credit.ports.events.EventEnvelope;
import ru.alfahack.credit.ports.events.InboxAck;
import ru.alfahack.credit.ports.events.OutboxBatch;
import ru.alfahack.credit.ports.objects.ActorScope;
import ru.alfahack.credit.ports.objects.ObjectRef;
import ru.alfahack.credit.ports.objects.ScanReceipt;
import ru.alfahack.credit.ports.objects.ScanStatus;

/** Общие контрактные случаи портов для локальных адаптеров (technology-adapters.json: contractCases). */
class LocalAdapterContractTest {

    static final Instant NOW = Instant.parse("2026-10-22T12:00:00Z");

    static PortErrorClass errorOf(Runnable action) {
        try {
            action.run();
        } catch (PortException e) {
            return e.errorClass();
        }
        throw new AssertionError("PortException expected");
    }

    @Nested
    class Cache {

        @Test
        void ttlExpires() {
            BoundedLocalCacheAdapter cache = new BoundedLocalCacheAdapter(10);
            cache.put("company-a:products:v1", 1, bytes("x"), NOW.plusSeconds(60));

            assertThat(cache.get("company-a:products:v1", 1, NOW)).isInstanceOf(CacheLookup.Hit.class);
            assertThat(cache.get("company-a:products:v1", 1, NOW.plusSeconds(60))).isInstanceOf(CacheLookup.Miss.class);
        }

        @Test
        void sizeIsBounded() {
            BoundedLocalCacheAdapter cache = new BoundedLocalCacheAdapter(2);
            cache.put("k1", 1, bytes("1"), NOW.plusSeconds(60));
            cache.put("k2", 1, bytes("2"), NOW.plusSeconds(60));
            cache.put("k3", 1, bytes("3"), NOW.plusSeconds(60));

            assertThat(cache.size()).isEqualTo(2);
            assertThat(cache.get("k1", 1, NOW)).isInstanceOf(CacheLookup.Miss.class);
        }

        @Test
        void versionMismatchIsMiss() {
            BoundedLocalCacheAdapter cache = new BoundedLocalCacheAdapter(10);
            cache.put("k", 1, bytes("old"), NOW.plusSeconds(60));

            assertThat(cache.get("k", 2, NOW)).isInstanceOf(CacheLookup.Miss.class);
        }

        @Test
        void tenantKeysDoNotCollide() {
            BoundedLocalCacheAdapter cache = new BoundedLocalCacheAdapter(10);
            cache.put("company-a:x", 1, bytes("a"), NOW.plusSeconds(60));

            assertThat(cache.get("company-b:x", 1, NOW)).isInstanceOf(CacheLookup.Miss.class);
        }

        @Test
        void storedValueIsCopied() {
            BoundedLocalCacheAdapter cache = new BoundedLocalCacheAdapter(10);
            byte[] value = bytes("abc");
            cache.put("k", 1, value, NOW.plusSeconds(60));
            value[0] = 'z';

            assertThat(((CacheLookup.Hit) cache.get("k", 1, NOW)).value()).isEqualTo(bytes("abc"));
        }
    }

    @Nested
    class Objects {

        @TempDir
        Path root;

        final ActorScope scope = new ActorScope("representative-a", "company-a");

        ObjectRef putAndPromote(VersionedFilesystemObjectAdapter store, String content) {
            ObjectRef quarantined = store.putQuarantine(stream(content), 1024);
            return store.promote(quarantined, clean(quarantined));
        }

        @Test
        void quarantineThenPromoteThenRead() throws Exception {
            VersionedFilesystemObjectAdapter store = new VersionedFilesystemObjectAdapter(root);
            ObjectRef quarantined = store.putQuarantine(stream("отчёт"), 1024);

            assertThat(quarantined.scanStatus()).isEqualTo(ScanStatus.QUARANTINED);
            assertThat(quarantined.size()).isEqualTo("отчёт".getBytes(StandardCharsets.UTF_8).length);
            assertThat(errorOf(() -> store.openClean(quarantined, scope))).isEqualTo(PortErrorClass.FORBIDDEN);

            ObjectRef cleanRef = store.promote(quarantined, clean(quarantined));
            try (InputStream in = store.openClean(cleanRef, scope)) {
                assertThat(new String(in.readAllBytes(), StandardCharsets.UTF_8)).isEqualTo("отчёт");
            }
        }

        @Test
        void unsafeFileIsNeverPromoted() {
            VersionedFilesystemObjectAdapter store = new VersionedFilesystemObjectAdapter(root);
            ObjectRef quarantined = store.putQuarantine(stream("virus"), 1024);
            ScanReceipt rejected = new ScanReceipt(
                    quarantined.objectId(), quarantined.version(), quarantined.sha256(), ScanStatus.REJECTED);

            assertThat(errorOf(() -> store.promote(quarantined, rejected))).isEqualTo(PortErrorClass.FORBIDDEN);
            ScanReceipt otherHash = new ScanReceipt(quarantined.objectId(), 1, "0".repeat(64), ScanStatus.CLEAN);
            assertThat(errorOf(() -> store.promote(quarantined, otherHash))).isEqualTo(PortErrorClass.FORBIDDEN);
        }

        @Test
        void oversizeIsRejectedWithoutLeftovers() throws Exception {
            VersionedFilesystemObjectAdapter store = new VersionedFilesystemObjectAdapter(root);

            assertThat(errorOf(() -> store.putQuarantine(stream("x".repeat(2048)), 1024)))
                    .isEqualTo(PortErrorClass.INVALID_INPUT);
            try (Stream<Path> files = Files.walk(root)) {
                assertThat(files.filter(Files::isRegularFile).toList()).isEmpty();
            }
        }

        @Test
        void pathTraversalIsRejected() {
            VersionedFilesystemObjectAdapter store = new VersionedFilesystemObjectAdapter(root);
            ObjectRef traversal = new ObjectRef("../../etc/passwd", 1, "0".repeat(64), 1, null, ScanStatus.CLEAN);

            assertThat(errorOf(() -> store.openClean(traversal, scope))).isEqualTo(PortErrorClass.INVALID_INPUT);
        }

        @Test
        void digestMismatchIsDetected() throws Exception {
            VersionedFilesystemObjectAdapter store = new VersionedFilesystemObjectAdapter(root);
            ObjectRef cleanRef = putAndPromote(store, "original");
            try (Stream<Path> files = Files.walk(root.resolve("clean"))) {
                Path stored = files.filter(Files::isRegularFile).findFirst().orElseThrow();
                Files.writeString(stored, "tampered");
            }

            assertThat(errorOf(() -> store.openClean(cleanRef, scope))).isEqualTo(PortErrorClass.VERSION_CONFLICT);
        }

        @Test
        void staleReferenceIsNotFound() {
            VersionedFilesystemObjectAdapter store = new VersionedFilesystemObjectAdapter(root);
            ObjectRef cleanRef = putAndPromote(store, "v1");
            ObjectRef stale = new ObjectRef(cleanRef.objectId(), 2, cleanRef.sha256(), cleanRef.size(), null,
                    ScanStatus.CLEAN);

            assertThat(errorOf(() -> store.openClean(stale, scope))).isEqualTo(PortErrorClass.NOT_FOUND);
        }

        @Test
        void filesSurviveRestart() throws Exception {
            ObjectRef cleanRef = putAndPromote(new VersionedFilesystemObjectAdapter(root), "durable");

            try (InputStream in = new VersionedFilesystemObjectAdapter(root).openClean(cleanRef, scope)) {
                assertThat(new String(in.readAllBytes(), StandardCharsets.UTF_8)).isEqualTo("durable");
            }
        }

        @Test
        void deniedWithoutTenantScope() {
            VersionedFilesystemObjectAdapter store = new VersionedFilesystemObjectAdapter(root);
            ObjectRef cleanRef = putAndPromote(store, "x");

            assertThat(errorOf(() -> store.openClean(cleanRef, new ActorScope("a", null))))
                    .isEqualTo(PortErrorClass.FORBIDDEN);
        }

        ScanReceipt clean(ObjectRef ref) {
            return new ScanReceipt(ref.objectId(), ref.version(), ref.sha256(), ScanStatus.CLEAN);
        }
    }

    @Nested
    class Events {

        static EventEnvelope envelope(String id) {
            return new EventEnvelope(id, "SubmissionRequested", "app-1", 2, "trace", "{}");
        }

        @Test
        void dispatchReportsDeliveredAndFailed() {
            PostgresOutboxTransportAdapter transport = new PostgresOutboxTransportAdapter(event -> {
                if (event.eventId().equals("poison")) {
                    throw new IllegalStateException("handler failed");
                }
                return new InboxAck(event.eventId(), false);
            });

            DeliveryReceipt receipt = transport.dispatch(new OutboxBatch(List.of(envelope("e1"), envelope("poison"))));

            assertThat(receipt.deliveredEventIds()).containsExactly("e1");
            assertThat(receipt.failedEventIds()).containsExactly("poison");
        }

        @Test
        void consumeReturnsAckAfterSink() {
            PostgresOutboxTransportAdapter transport =
                    new PostgresOutboxTransportAdapter(event -> new InboxAck(event.eventId(), true));

            assertThat(transport.consume(envelope("e2"))).isEqualTo(new InboxAck("e2", true));
        }
    }

    static byte[] bytes(String value) {
        return value.getBytes(StandardCharsets.UTF_8);
    }

    static InputStream stream(String value) {
        return new ByteArrayInputStream(bytes(value));
    }
}
