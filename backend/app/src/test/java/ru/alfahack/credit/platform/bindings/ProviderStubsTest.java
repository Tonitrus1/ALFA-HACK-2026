package ru.alfahack.credit.platform.bindings;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

import ru.alfahack.credit.adapters.kafka.KafkaEventTransportAdapter;
import ru.alfahack.credit.adapters.redis.RedisCacheAdapter;
import ru.alfahack.credit.adapters.redis.RedisSessionAdapter;
import ru.alfahack.credit.adapters.s3.S3ObjectStoreAdapter;
import ru.alfahack.credit.ports.PortErrorClass;
import ru.alfahack.credit.ports.ProviderNotImplementedException;

/** Неподключённый провайдер не возвращает фиктивный результат, а отказывает при выборе. */
class ProviderStubsTest {

    @Test
    void notImplementedProvidersRefuseSelection() {
        assertNotImplemented(RedisSessionAdapter::create);
        assertNotImplemented(RedisCacheAdapter::create);
        assertNotImplemented(KafkaEventTransportAdapter::create);
        assertNotImplemented(S3ObjectStoreAdapter::create);
    }

    private static void assertNotImplemented(org.assertj.core.api.ThrowableAssert.ThrowingCallable selection) {
        assertThatThrownBy(selection)
                .isInstanceOf(ProviderNotImplementedException.class)
                .extracting("errorClass")
                .isEqualTo(PortErrorClass.PROVIDER_NOT_IMPLEMENTED);
    }
}
