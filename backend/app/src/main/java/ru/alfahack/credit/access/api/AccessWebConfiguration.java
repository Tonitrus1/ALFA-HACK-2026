package ru.alfahack.credit.access.api;

import java.util.List;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import ru.alfahack.credit.access.application.SessionService;

@Configuration(proxyBeanMethods = false)
class AccessWebConfiguration implements WebMvcConfigurer {

    private final SessionService sessions;

    AccessWebConfiguration(SessionService sessions) {
        this.sessions = sessions;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(new SessionInterceptor(sessions)).addPathPatterns("/api/v1/**");
    }

    @Override
    public void addArgumentResolvers(List<HandlerMethodArgumentResolver> resolvers) {
        resolvers.add(new AuthenticatedSessionArgumentResolver());
    }
}
