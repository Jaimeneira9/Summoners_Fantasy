"""
Motor de precios dinámicos del mercado.

Variables: rendimiento reciente + demanda/oferta + momentum.
Cap: -10% / +15% diario.
Updates: post-partido y cron a medianoche.
"""

MAX_PRICE_INCREASE = 0.15
MAX_PRICE_DECREASE = 0.10


def calculate_new_price(
    current_price: float,
    recent_points: float,
    baseline_avg_points: float | None,
    ownership_count: int,
    total_rosters: int,
) -> tuple[float, float]:  # (nuevo_precio, delta_pct)
    """
    Calcula el nuevo precio de un jugador basado en rendimiento y demanda.

    Δ_rendimiento = ((recent_points - baseline) / baseline) * 0.1  [cap ±0.10]
    Δ_demanda:
      pct = ownership_count / total_rosters
      si pct > 0.60 → +(pct - 0.60) / 0.40 * 0.05  (max +5%)
      si pct < 0.20 → -(0.20 - pct) / 0.20 * 0.05  (max -5%)
      else → 0
    delta = max(-0.10, min(+0.15, Δ_rendimiento + Δ_demanda))
    nuevo_precio = round(current_price * (1 + delta), 2)
    precio mínimo absoluto: 1.0
    """
    # Δ rendimiento
    if not baseline_avg_points:
        delta_rendimiento = 0.0
    else:
        delta_rendimiento = ((recent_points - baseline_avg_points) / baseline_avg_points) * 0.1
        delta_rendimiento = max(-0.10, min(0.10, delta_rendimiento))

    # Δ demanda
    if total_rosters == 0:
        delta_demanda = 0.0
    else:
        pct = ownership_count / total_rosters
        if pct > 0.60:
            delta_demanda = (pct - 0.60) / 0.40 * 0.05
        elif pct < 0.20:
            delta_demanda = -((0.20 - pct) / 0.20 * 0.05)
        else:
            delta_demanda = 0.0

    delta = max(-0.10, min(0.15, delta_rendimiento + delta_demanda))

    new_price = max(1.0, round(current_price * (1 + delta), 2))
    return new_price, delta
