package ru.alfahack.credit.documents.application;

import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;
import ru.alfahack.credit.ports.PortException;

final class DocumentErrors {

    private DocumentErrors() {
    }

    static ApplicationException conflict(String code, String message) {
        return new ApplicationException(ErrorKind.CONFLICT, code, message);
    }

    static ApplicationException unprocessable(String code, String message) {
        return new ApplicationException(ErrorKind.UNPROCESSABLE, code, message);
    }

    static ApplicationException forbidden(String code, String message) {
        return new ApplicationException(ErrorKind.FORBIDDEN, code, message);
    }

    static ApplicationException fromPort(PortException e) {
        return switch (e.errorClass()) {
            case INVALID_INPUT -> unprocessable("FILE_REJECTED", "Файл не принят");
            case NOT_FOUND -> ApplicationException.notFound();
            case VERSION_CONFLICT -> conflict("OBJECT_VERSION_CONFLICT", "Версия файла изменилась");
            case FORBIDDEN -> forbidden("FILE_NOT_AVAILABLE", "Файл недоступен");
            default -> new ApplicationException(
                    ErrorKind.UNAVAILABLE, "FILE_STORE_UNAVAILABLE", "Хранилище файлов временно недоступно");
        };
    }
}
