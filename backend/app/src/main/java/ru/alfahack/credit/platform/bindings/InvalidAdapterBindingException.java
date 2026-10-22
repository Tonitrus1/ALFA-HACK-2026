package ru.alfahack.credit.platform.bindings;

/** Ошибка конфигурации провайдеров; останавливает запуск приложения. */
public class InvalidAdapterBindingException extends RuntimeException {

    public InvalidAdapterBindingException(String message) {
        super(message);
    }
}
