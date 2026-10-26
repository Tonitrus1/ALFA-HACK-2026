package ru.alfahack.credit.access.api;

import org.springframework.core.MethodParameter;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.context.request.RequestAttributes;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;

import ru.alfahack.credit.access.application.AuthenticatedSession;
import ru.alfahack.credit.platform.web.ApplicationException;
import ru.alfahack.credit.platform.web.ErrorKind;

/** Передаёт проверенную сессию в параметр контроллера типа {@link AuthenticatedSession}. */
class AuthenticatedSessionArgumentResolver implements HandlerMethodArgumentResolver {

    @Override
    public boolean supportsParameter(MethodParameter parameter) {
        return AuthenticatedSession.class.equals(parameter.getParameterType());
    }

    @Override
    public Object resolveArgument(
            MethodParameter parameter,
            ModelAndViewContainer mavContainer,
            NativeWebRequest webRequest,
            WebDataBinderFactory binderFactory) {
        Object session = webRequest.getAttribute(SessionInterceptor.ATTRIBUTE, RequestAttributes.SCOPE_REQUEST);
        if (session == null) {
            throw new ApplicationException(ErrorKind.UNAUTHENTICATED, "UNAUTHENTICATED", "Требуется вход");
        }
        return session;
    }
}
