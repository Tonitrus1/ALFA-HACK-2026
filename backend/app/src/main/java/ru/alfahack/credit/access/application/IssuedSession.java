package ru.alfahack.credit.access.application;

/** Новая сессия и токен cookie; токен отдаётся клиенту один раз и не логируется. */
public record IssuedSession(String token, AuthenticatedSession session) {

    @Override
    public String toString() {
        return "IssuedSession[session=" + session.actorId() + "]";
    }
}
