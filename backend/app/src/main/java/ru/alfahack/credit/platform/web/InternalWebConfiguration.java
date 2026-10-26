package ru.alfahack.credit.platform.web;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration(proxyBeanMethods = false)
class InternalWebConfiguration implements WebMvcConfigurer {

    private final ServiceIdentityProperties properties;

    InternalWebConfiguration(ServiceIdentityProperties properties) {
        this.properties = properties;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(new ServiceIdentityInterceptor(properties)).addPathPatterns("/internal/**");
    }
}
