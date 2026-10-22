package ru.alfahack.credit.adapters.s3;

import ru.alfahack.credit.ports.ProviderNotImplementedException;
import ru.alfahack.credit.ports.objects.ObjectStorePort;

/**
 * Явно отключённый каркас настоящего провайдера: SDK не подключён, успешного фиктивного
 * результата нет. Выбор этого адаптера останавливает запуск. План подключения — adapters/s3/README.md.
 */
public final class S3ObjectStoreAdapter {

    private S3ObjectStoreAdapter() {
    }

    public static ObjectStorePort create() {
        throw new ProviderNotImplementedException("S3ObjectStoreAdapter");
    }
}
