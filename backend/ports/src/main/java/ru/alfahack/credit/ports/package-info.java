/**
 * Порты технологических способностей backend (docs/architecture/contracts/technology-adapters.json).
 * Бизнес-модули зависят только от этих интерфейсов; реализация выбирается один раз в composition root.
 * Сигнатуры повторяют каталог; поля DTO уточняются контрактным PR (P01/P25), а не правкой адаптера.
 */
package ru.alfahack.credit.ports;
