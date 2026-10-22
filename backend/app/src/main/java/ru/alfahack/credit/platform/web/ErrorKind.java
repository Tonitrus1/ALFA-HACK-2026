package ru.alfahack.credit.platform.web;

import org.springframework.http.HttpStatus;

/** Класс прикладной ошибки и его HTTP-статус из публичного контракта. */
public enum ErrorKind {

    INVALID_REQUEST(HttpStatus.BAD_REQUEST),
    UNAUTHENTICATED(HttpStatus.UNAUTHORIZED),
    FORBIDDEN(HttpStatus.FORBIDDEN),
    NOT_FOUND(HttpStatus.NOT_FOUND),
    CONFLICT(HttpStatus.CONFLICT),
    UNPROCESSABLE(HttpStatus.UNPROCESSABLE_CONTENT),
    UNAVAILABLE(HttpStatus.SERVICE_UNAVAILABLE);

    private final HttpStatus status;

    ErrorKind(HttpStatus status) {
        this.status = status;
    }

    public HttpStatus status() {
        return status;
    }
}
