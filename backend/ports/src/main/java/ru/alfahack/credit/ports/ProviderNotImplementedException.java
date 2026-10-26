package ru.alfahack.credit.ports;

/**
 * Бросается каркасом неподключённого провайдера при попытке его выбрать.
 * Каркас никогда не возвращает успешный фиктивный результат.
 */
public class ProviderNotImplementedException extends PortException {

    public ProviderNotImplementedException(String provider) {
        super(PortErrorClass.PROVIDER_NOT_IMPLEMENTED, "Provider is not implemented: " + provider);
    }
}
