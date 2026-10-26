package ru.alfahack.credit.platform.support;

import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;

/** Idempotency-Key: 16–128 символов (контракт). */
public final class IdempotencyKeys {

    public static final String HEADER = "Idempotency-Key";

    private IdempotencyKeys() {
    }

    public static String validate(String key) {
        if (key == null || key.length() < 16 || key.length() > 128) {
            throw new ApplicationException(
                    ErrorKind.INVALID_REQUEST, "INVALID_IDEMPOTENCY_KEY", "Не удалось подготовить действие к отправке. Обновите страницу и повторите попытку");
        }
        return key;
    }

    public static ApplicationException reused() {
        return new ApplicationException(
                ErrorKind.CONFLICT, "IDEMPOTENCY_KEY_REUSED", "Повторная отправка не соответствует предыдущему действию. Обновите данные и попробуйте снова");
    }
}
