package ru.alfahack.credit.ports.objects;

import java.io.InputStream;

/**
 * Хранилище файлов (S3 / ObjectStorePort). Локальный провайдер — VersionedFilesystemObjectAdapter.
 * AV-проверка и принадлежность компании ограничивают любое чтение и OCR; путь браузера и ключ бакета не раскрываются.
 */
public interface ObjectStorePort {

    ObjectRef putQuarantine(InputStream stream, long limitBytes);

    InputStream openClean(ObjectRef exactRef, ActorScope actorScope);

    /**
     * Чтение карантинной версии только для сканера/проверки структуры (в каталоге сканер читает том
     * quarantine напрямую; метод добавлен для in-process сканера и требует подтверждения в P01).
     */
    InputStream openQuarantine(ObjectRef exactRef);

    ObjectRef promote(ObjectRef exactRef, ScanReceipt scanReceipt);
}
