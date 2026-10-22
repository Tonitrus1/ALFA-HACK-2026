package ru.alfahack.credit.integration.domain;
import java.util.List;
import java.util.Optional;
/** Explicit manual-review overlay; existing early gates/cap-first Risk policy stay authoritative. */
public final class SyntheticFraudPolicy {
    public static final String VERSION="demo-policy-v1+synthetic-fraud-manual-v1";
    public static final double MANUAL_THRESHOLD=0.8942151833349473;
    private SyntheticFraudPolicy(){}
    public static DemoPolicyV1.Decision decide(DemoPolicyV1.Input input,Optional<Double> risk,
            boolean required,Optional<Double> fraud,boolean deadlineExceeded){
        var early=DemoPolicyV1.beforeRisk(input);
        if(early.isPresent())return early.get();
        if(risk.isEmpty())return DemoPolicyV1.withRisk(input,risk);
        if(required && (deadlineExceeded || fraud.isEmpty() || !Double.isFinite(fraud.get())
                || fraud.get()<0 || fraud.get()>1 || fraud.get()>=MANUAL_THRESHOLD)) {
            return new DemoPolicyV1.Decision(DemoPolicyV1.Outcome.MANUAL,
                List.of(fraud.isEmpty()||deadlineExceeded?"SYNTHETIC_PROXY_UNAVAILABLE":"SYNTHETIC_PROXY_MANUAL"),
                "Заявка передана на дополнительную проверку",null,null,List.of());
        }
        return DemoPolicyV1.withRisk(input,risk);
    }
}
