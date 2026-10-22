package ru.alfahack.credit.ports.events;

import java.util.List;

public record DeliveryReceipt(List<String> deliveredEventIds, List<String> failedEventIds) {

    public DeliveryReceipt {
        deliveredEventIds = List.copyOf(deliveredEventIds);
        failedEventIds = List.copyOf(failedEventIds);
    }
}
