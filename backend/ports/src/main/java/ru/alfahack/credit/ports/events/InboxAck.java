package ru.alfahack.credit.ports.events;

/** AckAfterInboxCommit: подтверждение отдаётся только после commit inbox. */
public record InboxAck(String eventId, boolean duplicate) {
}
