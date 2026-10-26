package ru.alfahack.credit.access.api;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** Схема SelectCompany публичного контракта. */
record SelectCompanyRequest(@NotBlank @Size(max = 256) String companyId) {
}
