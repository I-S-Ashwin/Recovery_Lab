"""Bounded, assumption-based scenarios. No learned future forecasts."""
from datetime import date
from decimal import Decimal
from frozen_policy import nonnegative, money, recovery_risk


def factor(month, anchors):
    if isinstance(month, bool) or not isinstance(month, int) or month < 0:
        raise ValueError('month must be a nonnegative integer')
    previous = -1
    points = []
    for item in anchors:
        m = item['month']
        if isinstance(m, bool) or not isinstance(m, int) or m <= previous:
            raise ValueError('factor months must be strictly increasing integers')
        v = nonnegative(item['factor'], 'factor')
        if v > 1 or (points and v > points[-1][1]):
            raise ValueError('depreciation factors must be nonincreasing in [0,1]')
        points.append((m, v)); previous = m
    if not points or points[0] != (0, Decimal(1)):
        raise ValueError('factor table must start at month zero with factor one')
    if month > points[-1][0]:
        raise ValueError('unsupported horizon: extrapolation is prohibited')
    for m, v in points:
        if month == m:
            return v
    for (a, x), (b, y) in zip(points, points[1:]):
        if a < month < b:
            return x + (y-x)*Decimal(month-a)/Decimal(b-a)
    raise ValueError('unsupported horizon')


def project(reference, month, scenario, anchors):
    date.fromisoformat(reference['valuation_date'])
    low = nonnegative(reference['downside_anchor_inr'], 'downside anchor')
    mid = nonnegative(reference['median_anchor_inr'], 'median anchor')
    if low > mid:
        raise ValueError('downside anchor cannot exceed median anchor')
    shock = nonnegative(scenario['market_multiplier'], 'market multiplier')
    if shock > 1:
        raise ValueError('stress market multiplier must be in [0,1]')
    aging = factor(month, anchors)
    return {'month': month, 'valuation_date': reference['valuation_date'],
            'scenario': scenario['name'], 'aging_factor': float(aging),
            'market_multiplier': float(shock),
            'downside_value_inr': float(money(low*aging*shock)),
            'median_value_inr': float(money(mid*aging*shock)),
            'evidence_type': 'explicit_assumptions',
            'future_coverage_guaranteed': False}


def aggregate(rows):
    """Sum asset shortfalls; surplus collateral cannot offset another asset loss."""
    exposure = sum((nonnegative(r['exposure_inr'], 'exposure') for r in rows), Decimal(0))
    loss = sum((nonnegative(r['downside_shortfall_inr'], 'shortfall') for r in rows), Decimal(0))
    return {'asset_count': len(rows), 'exposure_inr': float(money(exposure)),
            'downside_shortfall_inr': float(money(loss)),
            'exposure_weighted_shortfall_ratio': float(loss/exposure) if exposure else None,
            'is_portfolio_quantile': False}


def stress_asset(reference, exposure, default_month, scenario, anchors):
    delay = scenario['recovery_delay_months']
    if isinstance(delay, bool) or not isinstance(delay, int) or delay < 0:
        raise ValueError('recovery delay must be a nonnegative integer')
    values = project(reference, default_month+delay, scenario, anchors)
    risk = recovery_risk(exposure, values['downside_value_inr'], values['median_value_inr'],
                         scenario['recovery_cost_inr'])
    return {'asset_id': reference['asset_id'], 'default_month': default_month,
            'sale_month': default_month+delay, **values, **risk}
