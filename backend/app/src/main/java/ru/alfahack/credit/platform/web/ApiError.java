package ru.alfahack.credit.platform.web;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonInclude;

/** Схема Error публичного контракта. */
@JsonInclude(JsonInclude.Include.NON_EMPTY)
public record ApiError(String code, String message, String correlationId, List<FieldError> fieldErrors) {

    public record FieldError(String field, String code, String message) {
    }
}
