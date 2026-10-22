package ru.alfahack.credit.access.api;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** Схема DemoLogin demo-контракта. */
record DemoLoginRequest(@NotBlank @Size(max = 256) String accountId) {
}
