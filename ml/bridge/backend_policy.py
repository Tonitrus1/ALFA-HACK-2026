"""Acceptance-only reference of Java DemoPolicyV1. Never called by serving endpoints.

The backend remains the decision authority. Legacy scoring/demo_policy.py is retained
for historical training evidence and must not drive the integrated application.
"""
from decimal import Decimal, ROUND_HALF_UP
import math

VERSION='demo-policy-v1'

def decide(values, *, amount, product_min=10000000, product_max=500000000,
           minimum_age=6, age=40, preliminary_revenue=None, already_requested=False, score=None):
    if len(values)!=8 or any(v is None for v in values.values()):return 'NEEDS_INFO'
    revenue=values['revenueMinor']
    if not already_requested and preliminary_revenue is not None and revenue>0 and abs(preliminary_revenue-revenue)>Decimal(revenue)*Decimal('.5'):
        return 'NEEDS_INFO'
    if age is None:return 'MANUAL'
    if age<minimum_age:return 'DECLINED'
    if revenue==0:return 'MANUAL'
    assets=values['totalAssetsMinor']
    if values['equityMinor']<0:return 'DECLINED'
    if assets<=0 or (Decimal(values['totalLiabilitiesMinor'])/Decimal(assets)).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP)>=Decimal('.9'):
        return 'DECLINED'
    if score is None or not math.isfinite(score) or not 0<=score<=1:return 'MANUAL'
    cap=min(product_max,revenue//4)
    # Preserve Java priority: amount cap precedes the model-review threshold.
    if amount>cap:return 'DECLINED' if cap<product_min else 'ALTERNATIVE'
    if score>=.5:return 'MANUAL'
    return 'APPROVED'
