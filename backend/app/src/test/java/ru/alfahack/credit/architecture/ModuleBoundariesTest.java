package ru.alfahack.credit.architecture;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

import java.util.List;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.lang.CompositeArchRule;

/**
 * Границы модулей без Spring Modulith (backend guide, раздел 1).
 * Другой модуль доступен только через свой пакет application.
 */
@AnalyzeClasses(packages = "ru.alfahack.credit", importOptions = ImportOption.DoNotIncludeTests.class)
class ModuleBoundariesTest {

    static final List<String> MODULES = List.of(
            "access", "catalog", "applications", "consents", "documents",
            "journey", "integration", "workspace", "ml", "kb");

    static final String ROOT = "ru.alfahack.credit.";

    @ArchTest
    static final ArchRule modulesAreFreeOfCycles = slices()
            .matching("ru.alfahack.credit.(*)..")
            .should().beFreeOfCycles()
            .allowEmptyShould(true);

    @ArchTest
    static final ArchRule modulesUseOnlyApplicationLayerOfOtherModules = CompositeArchRule.of(
            MODULES.stream()
                    .map(module -> noClasses()
                            .that().resideInAPackage(ROOT + module + "..")
                            .should().dependOnClassesThat().resideInAnyPackage(
                                    MODULES.stream()
                                            .filter(other -> !other.equals(module))
                                            .flatMap(other -> List.of(
                                                    ROOT + other + ".api..",
                                                    ROOT + other + ".domain..",
                                                    ROOT + other + ".infrastructure..").stream())
                                            .toArray(String[]::new))
                            .allowEmptyShould(true)
                            .because("модуль " + module + " обращается к другим модулям только через их application"))
                    .map(ArchRule.class::cast)
                    .toList())
            .as("modules use only the application layer of other modules");

    @ArchTest
    static final ArchRule controllersDoNotUseInfrastructure = noClasses()
            .that().resideInAPackage("..api..")
            .should().dependOnClassesThat().resideInAPackage("..infrastructure..")
            .allowEmptyShould(true)
            .because("контроллеры вызывают application-сервисы, а не repositories; JPA entities не являются HTTP DTO");

    @ArchTest
    static final ArchRule domainIsIndependentOfWebAndInfrastructure = noClasses()
            .that().resideInAPackage("..domain..")
            .should().dependOnClassesThat().resideInAnyPackage(
                    "..api..", "..infrastructure..", "org.springframework.web..", "org.springframework.http..")
            .allowEmptyShould(true);

    @ArchTest
    static final ArchRule businessModulesDoNotDependOnAdapters = noClasses()
            .that().resideInAnyPackage(MODULES.stream().map(module -> ROOT + module + "..").toArray(String[]::new))
            .should().dependOnClassesThat().resideInAPackage("ru.alfahack.credit.adapters..")
            .allowEmptyShould(true)
            .because("бизнес-модули зависят только от портов; провайдер выбирает composition root");
}
