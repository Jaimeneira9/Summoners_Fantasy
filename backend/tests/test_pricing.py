from market.pricing import MAX_PRICE_INCREASE, MAX_PRICE_DECREASE, calculate_new_price


def test_outperforming_increases_price():
    new_price, delta = calculate_new_price(100.0, recent_points=50.0, baseline_avg_points=30.0, ownership_count=1, total_rosters=10)
    assert new_price > 100.0


def test_underperforming_decreases_price():
    new_price, delta = calculate_new_price(100.0, recent_points=10.0, baseline_avg_points=30.0, ownership_count=1, total_rosters=10)
    assert new_price < 100.0


def test_cap_positive():
    new_price, delta = calculate_new_price(100.0, recent_points=999.0, baseline_avg_points=1.0, ownership_count=10, total_rosters=10)
    assert new_price == round(100.0 * (1 + MAX_PRICE_INCREASE), 2)


def test_cap_negative():
    new_price, delta = calculate_new_price(100.0, recent_points=0.0, baseline_avg_points=999.0, ownership_count=0, total_rosters=10)
    assert new_price == round(100.0 * (1 - MAX_PRICE_DECREASE), 2)


def test_equilibrium_no_change():
    # performance_factor=0, ownership entre 20%-60% → demanda=0, delta=0 → sin cambio
    new_price, delta = calculate_new_price(100.0, recent_points=30.0, baseline_avg_points=30.0, ownership_count=4, total_rosters=10)
    assert new_price == 100.0
    assert delta == 0.0


def test_zero_baseline_no_crash():
    new_price, delta = calculate_new_price(100.0, recent_points=50.0, baseline_avg_points=0.0, ownership_count=1, total_rosters=10)
    assert isinstance(new_price, float)
    assert isinstance(delta, float)


def test_high_ownership_increases_price():
    # ownership >60% dispara delta_demanda positivo
    new_high, _ = calculate_new_price(100.0, recent_points=30.0, baseline_avg_points=30.0, ownership_count=9, total_rosters=10)
    new_neutral, _ = calculate_new_price(100.0, recent_points=30.0, baseline_avg_points=30.0, ownership_count=4, total_rosters=10)
    assert new_high > new_neutral


def test_low_ownership_decreases_price():
    # ownership <20% dispara delta_demanda negativo
    new_low, _ = calculate_new_price(100.0, recent_points=30.0, baseline_avg_points=30.0, ownership_count=1, total_rosters=10)
    new_neutral, _ = calculate_new_price(100.0, recent_points=30.0, baseline_avg_points=30.0, ownership_count=4, total_rosters=10)
    assert new_low < new_neutral


def test_result_is_rounded_to_two_decimals():
    new_price, _ = calculate_new_price(100.0, recent_points=35.0, baseline_avg_points=30.0, ownership_count=3, total_rosters=10)
    assert new_price == round(new_price, 2)


def test_returns_tuple():
    result = calculate_new_price(100.0, recent_points=30.0, baseline_avg_points=30.0, ownership_count=4, total_rosters=10)
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_minimum_price_floor():
    # Precio actual muy bajo, caída máxima no puede bajar de 1.0
    new_price, _ = calculate_new_price(1.0, recent_points=0.0, baseline_avg_points=999.0, ownership_count=0, total_rosters=10)
    assert new_price >= 1.0
