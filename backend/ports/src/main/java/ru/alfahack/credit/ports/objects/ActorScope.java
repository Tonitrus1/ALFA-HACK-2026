package ru.alfahack.credit.ports.objects;

/** tenantScope вычисляет сервер, а не клиент. */
public record ActorScope(String actorId, String companyId) {
}
