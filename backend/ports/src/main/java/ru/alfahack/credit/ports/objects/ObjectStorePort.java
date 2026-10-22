package ru.alfahack.credit.ports.objects;

import java.io.InputStream;

/**
 * Хранилище файлов (S3 / ObjectStorePort). Локальный провайдер — VersionedFilesystemObjectAdapter.
 * AV-проверка и принадлежность компании ограничивают любое чтение и OCR; путь браузера и ключ бакета не раскрываются.
 */
public interface ObjectStorePort {

    ObjectRef putQuarantine(InputStream stream, long limitBytes);

    InputStream openClean(ObjectRef exactRef, ActorScope actorScope);

    ObjectRef promote(ObjectRef exactRef, ScanReceipt scanReceipt);
}
