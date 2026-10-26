package ru.alfahack.credit.integration;
import static org.assertj.core.api.Assertions.assertThat;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import ru.alfahack.credit.integration.domain.DemoPolicyV1;
import ru.alfahack.credit.integration.domain.SyntheticFraudPolicy;
class SyntheticFraudPolicyTest {
    DemoPolicyV1.Input input(long requested){return DemoPolicyV1Test.input(requested,40L,null,DemoPolicyV1Test.values(100000000,40000000,60000000,300000000),false);}
    @Test void missingRequiredProxyOrLateResultNeverApproves(){
        assertThat(SyntheticFraudPolicy.decide(input(50000000),Optional.of(.1),true,Optional.empty(),false).outcome()).isEqualTo(DemoPolicyV1.Outcome.MANUAL);
        assertThat(SyntheticFraudPolicy.decide(input(50000000),Optional.of(.1),true,Optional.of(.01),true).outcome()).isEqualTo(DemoPolicyV1.Outcome.MANUAL);
    }
    @Test void highSyntheticScoreOnlyRoutesManualAndScoresAreNotAveraged(){
        assertThat(SyntheticFraudPolicy.decide(input(50000000),Optional.of(.01),true,Optional.of(.99),false).outcome()).isEqualTo(DemoPolicyV1.Outcome.MANUAL);
        assertThat(SyntheticFraudPolicy.decide(input(50000000),Optional.of(.6),true,Optional.of(.0),false).outcome()).isEqualTo(DemoPolicyV1.Outcome.MANUAL);
    }
    @Test void disabledOrLowProxyPreservesCapFirstPolicy(){
        assertThat(SyntheticFraudPolicy.decide(input(100000000),Optional.of(.9),true,Optional.of(.1),false)).isEqualTo(DemoPolicyV1.withRisk(input(100000000),Optional.of(.9)));
        assertThat(SyntheticFraudPolicy.decide(input(50000000),Optional.of(.1),false,Optional.empty(),false)).isEqualTo(DemoPolicyV1.withRisk(input(50000000),Optional.of(.1)));
    }
}
