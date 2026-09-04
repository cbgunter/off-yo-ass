from oya.domain.baselines import Baseline, BuildingBaseline, compute_baseline


def test_building_when_history_is_short():
    result = compute_baseline(today=52.0, history=[50.0] * 12)
    assert isinstance(result, BuildingBaseline)
    assert result.days == 12
    assert result.needed == 30
    assert result.today == 52.0


def test_building_when_today_is_missing():
    result = compute_baseline(today=None, history=[50.0] * 40)
    assert isinstance(result, BuildingBaseline)
    assert result.today is None


def test_real_baseline_once_enough_history():
    result = compute_baseline(today=55.0, history=[50.0] * 30)
    assert isinstance(result, Baseline)
    assert result.average == 50.0
    assert result.delta == 5.0
    assert result.days == 30


def test_delta_pct():
    result = compute_baseline(today=60.0, history=[50.0] * 30)
    assert isinstance(result, Baseline)
    assert result.delta_pct == 20.0


def test_delta_pct_is_none_when_average_is_zero():
    result = compute_baseline(today=1.0, history=[0.0] * 30)
    assert isinstance(result, Baseline)
    assert result.delta_pct is None


def test_custom_min_days_boundary():
    # Exactly at the custom threshold counts as enough.
    assert isinstance(compute_baseline(today=1.0, history=[1.0] * 7, min_days=7), Baseline)
    # One short of it does not.
    assert isinstance(compute_baseline(today=1.0, history=[1.0] * 6, min_days=7), BuildingBaseline)
