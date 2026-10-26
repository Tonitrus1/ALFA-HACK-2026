package ru.alfahack.credit.platform.web;

/**
 * Прикладная ошибка со стабильным кодом (например COMPANY_CONTEXT_CHANGED).
 * Сообщение безопасно для клиента: без ПДн, токенов и деталей реализации.
 */
public class ApplicationException extends RuntimeException {

    private final ErrorKind kind;
    private final String code;

    public ApplicationException(ErrorKind kind, String code, String message) {
        super(message);
        this.kind = kind;
        this.code = code;
    }

    public ErrorKind kind() {
        return kind;
    }

    public String code() {
        return code;
    }

    public static ApplicationException notFound() {
        return new ApplicationException(ErrorKind.NOT_FOUND, "NOT_FOUND", "Ресурс не найден");
    }
}
