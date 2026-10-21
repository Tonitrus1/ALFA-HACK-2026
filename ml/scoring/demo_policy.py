from .features import validate
PRODUCTS={
 'working':{'minAmountMinor':10000000,'maxAmountMinor':500000000,'minTermMonths':3,'maxTermMonths':24,'minAgeMonths':6},
 'line':{'minAmountMinor':30000000,'maxAmountMinor':1000000000,'minTermMonths':6,'maxTermMonths':36,'minAgeMonths':12},
 'overdraft':{'minAmountMinor':5000000,'maxAmountMinor':200000000,'minTermMonths':1,'maxTermMonths':12,'minAgeMonths':12},
}
VERSION='synthetic-demo-policy-3'
def result(outcome,rule,amount=None):return {'outcome':outcome,'rule':rule,'policyVersion':VERSION,'offerAmountMinor':amount}
def precheck(statement,reference,amount,term,age=36,product='working',correction=False,explanation=''):
    try:v=validate(statement);ref=validate(reference)
    except (ValueError,KeyError,TypeError):return result('NEEDS_INFO','INVALID_DATA')
    if not correction and abs(v['revenueMinor']-ref['revenueMinor'])*5>ref['revenueMinor']:
        return result('NEEDS_INFO','REFERENCE_REVENUE_DISCREPANCY')
    if correction and explanation.strip():return result('MANUAL','RFI_EXPLANATION')
    if product not in PRODUCTS:return result('MANUAL','UNSUPPORTED_PRODUCT')
    p=PRODUCTS[product]
    if age<p['minAgeMonths'] or not p['minTermMonths']<=term<=p['maxTermMonths'] or amount<p['minAmountMinor']:
        return result('DECLINED','PRODUCT_ELIGIBILITY')
    if v['equityMinor']<0 or v['totalLiabilitiesMinor']*10>=v['totalAssetsMinor']*9:return result('DECLINED','NEGATIVE_EQUITY_OR_LEVERAGE')
    if v['revenueMinor']==0:return result('MANUAL','ZERO_REVENUE')
    return None

def after_risk(statement,amount,score,threshold,product='working',ml_error=False):
    import math
    if ml_error or score is None or not math.isfinite(score) or not 0<=score<=1:return result('MANUAL','ML_FAILURE')
    if score>=threshold:return result('MANUAL','MODEL_REVIEW_BUDGET')
    p=PRODUCTS[product];cap=min(p['maxAmountMinor'],statement['values']['revenueMinor']//4)
    if cap<p['minAmountMinor']:return result('MANUAL','CAP_BELOW_MINIMUM')
    if amount>cap:return result('ALTERNATIVE','AMOUNT_ABOVE_CAP',cap)
    return result('APPROVED','WITHIN_DEMO_RULES',amount)
