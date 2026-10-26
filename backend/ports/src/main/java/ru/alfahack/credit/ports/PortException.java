package ru.alfahack.credit.ports;

import java.util.Objects;

/**
 * Ошибка порта. Сообщение не должно содержать connection string, текст запроса или секреты.
 */
public class PortException extends RuntimeException {

    private final PortErrorClass errorClass;

    public PortException(PortErrorClass errorClass, String message) {
        super(message);
        this.errorClass = Objects.requireNonNull(errorClass, "errorClass");
    }

    public PortException(PortErrorClass errorClass, String message, Throwable cause) {
        super(message, cause);
        this.errorClass = Objects.requireNonNull(errorClass, "errorClass");
    }

    public PortErrorClass errorClass() {
        return errorClass;
    }
}
