package ru.alfahack.credit.access.application;

public record ActorView(String actorId, String displayName, String kind, boolean disabled) {

    public boolean isActiveRepresentative() {
        return !disabled && "REPRESENTATIVE".equals(kind);
    }
}
