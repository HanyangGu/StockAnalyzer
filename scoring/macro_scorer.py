# ============================================================
# scoring/macro_scorer.py -- Macro Environment Scoring Engine
# ============================================================
# SCORING LAYER ONLY. Does not call any external API.
# Receives the standardised dict from analyzers/macro.py
# and produces a 0-100 macro score adjusted for the
# specific stock being analysed.
#
# Scoring pipeline:
#   1. Environment Score (0-100)
#      Three sub-scores from raw macro data:
#        VIX sub-score        (max 35pts)
#        Yield curve sub-score(max 35pts)
#        Market regime sub-score(max 30pts)
#
#   2. Sensitivity Multiplier (stock-specific adjustment)
#      Derived from two sources already available in fund_data:
#        Beta sensitivity   (weight 60%) -- historical market response
#        Sector sensitivity (weight 40%) -- industry-level macro exposure
#
#   3. Adjusted Macro Score
#      adjusted = 50 + (env_score - 50) × total_sensitivity
#      Clamped to [0, 100].
#      When env_score = 50 (neutral), no adjustment occurs.
#      High-sensitivity stocks are amplified in both directions.
#
# Design note:
#   All thresholds and weights are constants at the top of this
#   file, not buried in logic, for easy tuning after testing.
# ============================================================

from core.weights import (
    MACRO_VIX_MAX_PTS,
    MACRO_YIELD_MAX_PTS,
    MACRO_REGIME_MAX_PTS,
    MACRO_BETA_WEIGHT,
    MACRO_SECTOR_WEIGHT,
    MACRO_BASE_WEIGHT,
    MACRO_RAPID_VIX_SPIKE_THRESHOLD,
    MACRO_RAPID_VIX_SPIKE_PENALTY,
    MACRO_RAPID_RATE_RISE_THRESHOLD,
    MACRO_RAPID_RATE_RISE_PENALTY,
    MACRO_RAPID_RATE_FALL_BONUS,
)


# ============================================================
# Sector sensitivity table
# ============================================================
# Each sector has two sensitivity dimensions:
#   "rate" : sensitivity to interest rate changes
#            > 1.0 = hurt more by rising rates
#            < 1.0 = less affected by rate changes
#   "vix"  : sensitivity to market fear / volatility spikes
#            > 1.0 = punished more in risk-off environments
#            < 1.0 = more defensive in panics
#
# Source: standard financial theory on sector factor exposures.
# These are starting values -- adjust after testing.

SECTOR_SENSITIVITY = {
    # Rate-sensitive (duration risk, dividend compression)
    "Real Estate":            {"rate": 1.40, "vix": 1.10},
    "Utilities":              {"rate": 1.30, "vix": 0.75},
    "Financial Services":     {"rate": 1.20, "vix": 1.20},

    # Growth / cyclical (high valuation multiples compress with rates)
    "Technology":             {"rate": 1.15, "vix": 1.30},
    "Consumer Cyclical":      {"rate": 1.05, "vix": 1.20},
    "Communication Services": {"rate": 1.05, "vix": 1.10},

    # Commodity / industrial (macro cycle dependent)
    "Energy":                 {"rate": 0.90, "vix": 1.10},
    "Basic Materials":        {"rate": 0.90, "vix": 1.10},
    "Industrials":            {"rate": 1.00, "vix": 1.00},

    # Defensive (stable cash flows, less macro-sensitive)
    "Healthcare":             {"rate": 0.80, "vix": 0.70},
    "Consumer Defensive":     {"rate": 0.70, "vix": 0.60},
}

SECTOR_SENSITIVITY_DEFAULT = {"rate": 1.00, "vix": 1.00}

# Beta → sensitivity multiplier breakpoints
# (beta_upper_bound, sensitivity_value)
# Evaluated top-to-bottom; first match wins.
BETA_SENSITIVITY_BREAKPOINTS = [
    (2.50, 1.40),
    (2.00, 1.25),
    (1.50, 1.10),
    (1.00, 1.00),   # baseline
    (0.60, 0.85),
    (0.00, 0.70),
]
BETA_SENSITIVITY_DEFAULT = 1.00   # used when beta is None


# ============================================================
# Verdict helper
# ============================================================

def _get_macro_verdict(score: int) -> tuple:
    """Converts macro score to verdict label and emoji."""
    if score >= 70:
        return "Supportive",       "🟢"
    elif score >= 55:
        return "Mildly Supportive","🟩"
    elif score >= 45:
        return "Neutral",          "⬜"
    elif score >= 30:
        return "Headwind",         "🟥"
    else:
        return "Strong Headwind",  "🔴"


# ============================================================
# Sub-scorers (pure functions, easy to unit test)
# ============================================================

def _score_vix(vix: float | None,
               vix_change_30d: float | None) -> tuple[int, list[str]]:
    """
    VIX sub-score (max MACRO_VIX_MAX_PTS points).
    Lower VIX = less fear = more bullish environment for equities.

    Also applies a rapid-spike penalty when VIX has risen sharply
    in the past 30 days, indicating a sudden deterioration in
    market conditions even if the absolute level seems OK.
    """
    signals = []
    pts     = 0

    if vix is None:
        signals.append("VIX -- data unavailable ➡️")
        return int(MACRO_VIX_MAX_PTS * 0.5), signals   # neutral fallback

    if vix < 15:
        pts = MACRO_VIX_MAX_PTS
        signals.append(f"VIX {vix} -- very calm market, high risk appetite ✅")
    elif vix < 20:
        pts = int(MACRO_VIX_MAX_PTS * 0.80)
        signals.append(f"VIX {vix} -- normal low-fear environment ✅")
    elif vix < 25:
        pts = int(MACRO_VIX_MAX_PTS * 0.57)
        signals.append(f"VIX {vix} -- mildly elevated concern ➡️")
    elif vix < 30:
        pts = int(MACRO_VIX_MAX_PTS * 0.34)
        signals.append(f"VIX {vix} -- market stress, caution warranted ⚠️")
    elif vix < 35:
        pts = int(MACRO_VIX_MAX_PTS * 0.14)
        signals.append(f"VIX {vix} -- significant fear, risk-off environment ⚠️")
    else:
        pts = 0
        signals.append(f"VIX {vix} -- extreme fear (>35), historical panic level 🔴")

    # Rapid spike penalty: VIX surging fast is worse than a stable high VIX
    if vix_change_30d is not None and vix_change_30d > MACRO_RAPID_VIX_SPIKE_THRESHOLD:
        penalty = MACRO_RAPID_VIX_SPIKE_PENALTY
        pts     = max(0, pts - penalty)
        signals.append(
            f"VIX 30d change +{vix_change_30d:.1f}% -- rapid fear spike, "
            f"additional -{penalty}pts penalty ⚠️"
        )

    return pts, signals


def _score_yield_curve(treasury_10y: float | None,
                       treasury_3m:  float | None,
                       yield_spread: float | None,
                       yield_curve:  str,
                       rate_trend_30d:  float | None,
                       rate_direction:  str) -> tuple[int, list[str]]:
    """
    Yield curve sub-score (max MACRO_YIELD_MAX_PTS points).

    Two components:
      A. Curve shape (normal / flat / inverted)
         Inverted curve has historically preceded recessions,
         but with a 12-18 month lag, so we penalise moderately
         rather than catastrophically.

      B. Rate trend adjustment
         Rapidly rising rates compress equity valuations (especially
         growth stocks). Rapidly falling rates suggest easing --
         generally positive for equities medium-term.
    """
    signals = []
    pts     = 0

    # -- A. Curve shape -----------------------------------
    if yield_spread is None:
        pts = int(MACRO_YIELD_MAX_PTS * 0.5)
        signals.append("Yield curve -- data unavailable ➡️")
    elif yield_curve == "normal":
        pts = MACRO_YIELD_MAX_PTS
        signals.append(
            f"Yield curve normal (+{yield_spread:.2f}pp) -- "
            f"healthy term premium, no recession signal ✅"
        )
    elif yield_curve == "flat":
        pts = int(MACRO_YIELD_MAX_PTS * 0.51)
        signals.append(
            f"Yield curve flat ({yield_spread:+.2f}pp) -- "
            f"slowdown concern but not inverted ➡️"
        )
    else:   # inverted
        pts = int(MACRO_YIELD_MAX_PTS * 0.23)
        signals.append(
            f"Yield curve inverted ({yield_spread:+.2f}pp) -- "
            f"historical recession predictor (12-18 month lag) ⚠️"
        )

    # 10Y level context (absolute rate level matters for valuations)
    if treasury_10y is not None:
        if treasury_10y > 5.0:
            signals.append(f"10Y yield {treasury_10y}% -- very high, significant valuation headwind ⚠️")
        elif treasury_10y > 4.5:
            signals.append(f"10Y yield {treasury_10y}% -- elevated, pressure on growth multiples ⚠️")
        elif treasury_10y > 4.0:
            signals.append(f"10Y yield {treasury_10y}% -- above neutral, mild headwind ➡️")
        elif treasury_10y > 3.0:
            signals.append(f"10Y yield {treasury_10y}% -- moderate, manageable for equities ✅")
        else:
            signals.append(f"10Y yield {treasury_10y}% -- low rates, supportive for equity valuations ✅")

    # -- B. Rate trend adjustment -------------------------
    if rate_trend_30d is not None:
        if rate_trend_30d > MACRO_RAPID_RATE_RISE_THRESHOLD:
            pts = max(0, pts + MACRO_RAPID_RATE_RISE_PENALTY)   # penalty is negative
            signals.append(
                f"10Y rate rising +{rate_trend_30d:.2f}pp in 30d -- "
                f"rapid tightening, valuation headwind {MACRO_RAPID_RATE_RISE_PENALTY}pts ⚠️"
            )
        elif rate_trend_30d < -MACRO_RAPID_RATE_RISE_THRESHOLD:
            pts = min(MACRO_YIELD_MAX_PTS, pts + MACRO_RAPID_RATE_FALL_BONUS)
            signals.append(
                f"10Y rate falling {rate_trend_30d:.2f}pp in 30d -- "
                f"easing conditions, equity tailwind +{MACRO_RAPID_RATE_FALL_BONUS}pts ✅"
            )
        else:
            signals.append(f"10Y rate trend stable ({rate_trend_30d:+.2f}pp in 30d) ➡️")

    return pts, signals


def _score_market_regime(sp500_trend_30d: float | None,
                          market_regime:   str) -> tuple[int, list[str]]:
    """
    Market regime sub-score (max MACRO_REGIME_MAX_PTS points).
    S&P 500 30-day trend as proxy for broad risk appetite.
    """
    signals = []

    if sp500_trend_30d is None:
        signals.append("S&P 500 trend -- data unavailable ➡️")
        return int(MACRO_REGIME_MAX_PTS * 0.5), signals

    if sp500_trend_30d > 7:
        pts = MACRO_REGIME_MAX_PTS
        signals.append(f"S&P 500 +{sp500_trend_30d:.1f}% (30d) -- strong risk-on, broad market rally ✅")
    elif sp500_trend_30d > 3:
        pts = int(MACRO_REGIME_MAX_PTS * 0.73)
        signals.append(f"S&P 500 +{sp500_trend_30d:.1f}% (30d) -- positive market regime ✅")
    elif sp500_trend_30d > 0:
        pts = int(MACRO_REGIME_MAX_PTS * 0.47)
        signals.append(f"S&P 500 +{sp500_trend_30d:.1f}% (30d) -- mild positive drift ➡️")
    elif sp500_trend_30d > -3:
        pts = int(MACRO_REGIME_MAX_PTS * 0.27)
        signals.append(f"S&P 500 {sp500_trend_30d:.1f}% (30d) -- mild weakness, cautious ⚠️")
    elif sp500_trend_30d > -7:
        pts = int(MACRO_REGIME_MAX_PTS * 0.10)
        signals.append(f"S&P 500 {sp500_trend_30d:.1f}% (30d) -- notable selloff, risk-off ⚠️")
    else:
        pts = 0
        signals.append(f"S&P 500 {sp500_trend_30d:.1f}% (30d) -- severe market decline 🔴")

    return pts, signals


# ============================================================
# Sensitivity calculators
# ============================================================

def _get_beta_sensitivity(beta: float | None) -> tuple[float, str]:
    """
    Maps beta to a sensitivity multiplier.
    Returns (multiplier, signal_string).
    """
    if beta is None:
        return BETA_SENSITIVITY_DEFAULT, "Beta unknown -- using baseline sensitivity ➡️"

    for upper_bound, multiplier in BETA_SENSITIVITY_BREAKPOINTS:
        if beta >= upper_bound:
            direction = "amplified" if multiplier > 1.0 else ("reduced" if multiplier < 1.0 else "baseline")
            return multiplier, f"Beta {beta} → sensitivity ×{multiplier} ({direction} macro impact) ➡️"

    # beta below all breakpoints (very defensive)
    return 0.70, f"Beta {beta} (very low) → sensitivity ×0.70 (minimal macro exposure) ✅"


def _get_sector_sensitivity(sector: str | None,
                             rate_direction: str,
                             vix_trend: str) -> tuple[float, str]:
    """
    Maps sector to a sensitivity multiplier, weighted by
    which macro signal (rate or vix) is currently dominant.

    Logic:
      - If rates are moving fast (tightening/easing) → rate dimension dominates (70%)
      - If VIX is trending (rising/falling) → vix dimension dominates (70%)
      - Otherwise → equal weighting (50/50)
    """
    sens = SECTOR_SENSITIVITY.get(sector, SECTOR_SENSITIVITY_DEFAULT)

    rate_dominant = rate_direction in ("tightening", "easing")
    vix_dominant  = vix_trend in ("rising", "falling")

    if rate_dominant and not vix_dominant:
        rate_w, vix_w = 0.70, 0.30
    elif vix_dominant and not rate_dominant:
        rate_w, vix_w = 0.30, 0.70
    else:
        rate_w, vix_w = 0.50, 0.50

    multiplier = round(
        sens["rate"] * rate_w + sens["vix"] * vix_w,
        3
    )

    sector_label = sector or "Unknown"
    return (
        multiplier,
        f"Sector '{sector_label}' → sensitivity ×{multiplier} "
        f"(rate×{sens['rate']} @ {int(rate_w*100)}%, "
        f"vix×{sens['vix']} @ {int(vix_w*100)}%) ➡️"
    )


# ============================================================
# Master scoring function
# ============================================================

def score_macro(macro_data: dict,
                fund_data:  dict | None = None) -> dict:
    """
    Produces the final macro score adjusted for this specific stock.

    Args:
        macro_data : output of analyzers/macro.py fetch_macro_data()
        fund_data  : output of analyzers/fundamental.py (for beta + sector)
                     Pass None to skip stock-specific sensitivity adjustment.

    Returns:
    {
      "score":        int    0-100, stock-adjusted macro score
      "env_score":    int    0-100, raw environment score (pre-adjustment)
      "verdict":      str
      "icon":         str    emoji
      "sensitivity":  float  total sensitivity multiplier applied
      "beta_used":    float | None
      "sector_used":  str | None
      "signals":      list[str]   for dropdown display
      "raw":          dict        raw macro data snapshot
      "available":    bool        False if data_quality == "failed"
    }
    """
    # ── Availability check ────────────────────────────────────
    if macro_data.get("data_quality") == "failed":
        return {
            "score":       None,
            "env_score":   None,
            "verdict":     "Data unavailable",
            "icon":        "➡️",
            "sensitivity": 1.0,
            "beta_used":   None,
            "sector_used": None,
            "signals":     ["Macro data could not be fetched -- dimension excluded from composite score."],
            "raw":         macro_data,
            "available":   False,
        }

    signals = []

    # ── Step 1: Environment sub-scores ────────────────────────
    vix_pts,    vix_sigs    = _score_vix(
        macro_data.get("vix"),
        macro_data.get("vix_change_30d"),
    )
    yield_pts,  yield_sigs  = _score_yield_curve(
        macro_data.get("treasury_10y"),
        macro_data.get("treasury_3m"),
        macro_data.get("yield_spread"),
        macro_data.get("yield_curve", "unknown"),
        macro_data.get("rate_trend_30d"),
        macro_data.get("rate_direction", "unknown"),
    )
    regime_pts, regime_sigs = _score_market_regime(
        macro_data.get("sp500_trend_30d"),
        macro_data.get("market_regime", "unknown"),
    )

    env_score = max(0, min(100,
        vix_pts + yield_pts + regime_pts
    ))

    signals += vix_sigs + yield_sigs + regime_sigs

    # Partial data note
    if macro_data.get("data_quality") == "partial":
        missing = macro_data.get("missing_fields", [])
        signals.append(f"Note: partial macro data (missing: {', '.join(missing)}) -- some signals estimated ➡️")

    # ── Step 2: Stock-specific sensitivity ───────────────────
    beta        = None
    sector      = None
    beta_sens   = BETA_SENSITIVITY_DEFAULT
    sector_sens = 1.00

    if fund_data and not fund_data.get("error"):
        beta   = fund_data.get("beta")
        sector = fund_data.get("sector")

    beta_sens,   beta_sig   = _get_beta_sensitivity(beta)
    sector_sens, sector_sig = _get_sector_sensitivity(
        sector,
        macro_data.get("rate_direction", "unknown"),
        macro_data.get("vix_trend",      "unknown"),
    )
    signals.append(beta_sig)
    signals.append(sector_sig)

    # Combine: beta × 0.55 + sector × 0.35 + base 0.10
    # The base component (1.0 × 0.10) anchors the multiplier closer to 1.0,
    # reducing amplification at extreme beta/sector combinations and
    # partially compensating for double-counting between the two factors.
    total_sensitivity = round(
        beta_sens   * MACRO_BETA_WEIGHT +
        sector_sens * MACRO_SECTOR_WEIGHT +
        1.0         * MACRO_BASE_WEIGHT,
        3
    )
    signals.append(
        f"Combined sensitivity ×{total_sensitivity} "
        f"(beta ×{MACRO_BETA_WEIGHT} + sector ×{MACRO_SECTOR_WEIGHT} "
        f"+ base ×{MACRO_BASE_WEIGHT} weighting)"
    )

    # ── Step 3: Adjusted macro score ─────────────────────────
    # Formula: adjusted = 50 + (env - 50) × sensitivity
    # When env = 50 (neutral), adjustment = 0.
    # When env > 50 (good), high-sensitivity stocks benefit more.
    # When env < 50 (bad),  high-sensitivity stocks are punished more.
    adjusted_score = round(50 + (env_score - 50) * total_sensitivity)
    adjusted_score = max(0, min(100, adjusted_score))

    verdict, icon = _get_macro_verdict(adjusted_score)

    return {
        "score":       adjusted_score,
        "env_score":   env_score,
        "verdict":     verdict,
        "icon":        icon,
        "sensitivity": total_sensitivity,
        "beta_used":   beta,
        "sector_used": sector,
        "signals":     signals,
        "raw": {
            "vix":             macro_data.get("vix"),
            "vix_30d_avg":     macro_data.get("vix_30d_avg"),
            "vix_trend":       macro_data.get("vix_trend"),
            "treasury_10y":    macro_data.get("treasury_10y"),
            "treasury_3m":     macro_data.get("treasury_3m"),
            "yield_spread":    macro_data.get("yield_spread"),
            "yield_curve":     macro_data.get("yield_curve"),
            "rate_direction":  macro_data.get("rate_direction"),
            "sp500_trend_30d": macro_data.get("sp500_trend_30d"),
            "market_regime":   macro_data.get("market_regime"),
            "data_quality":    macro_data.get("data_quality"),
        },
        "available": True,
    }
