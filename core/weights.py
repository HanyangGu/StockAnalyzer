# ============================================================
# core/weights.py -- Centralised Weight & Threshold Config
# ============================================================
# Single source of truth for ALL scoring weights, thresholds,
# and calibration constants across the entire system.
#
# Structure:
#   1. COMPOSITE       : main dimension weights + thresholds
#   2. SENTIMENT       : sentiment sub-dimension weights
#   3. NEWS            : article scoring multipliers + calibration
#   4. ANALYST         : authority weights + consensus + targets
#   5. INSIDER         : position weights + size thresholds + decay
#   6. OPTIONS         : PCR thresholds + IV multipliers
#   7. MACRO           : macro environment scoring constants
#   8. EVENT           : event-driven reliability windows
#
# Rules:
#   - Composite weights must sum to 1.0
#   - Sentiment sub-weights must sum to 1.0
#   - Thresholds are the minimum score to count as "high"
#
# Session 5 changes:
#   - WEIGHT_MACRO: 5% → 10% (better reflects macro impact on high-Beta stocks)
#   - WEIGHT_TECHNICAL: 47% → 43%
#   - WEIGHT_SENTIMENT: 21% → 20%
#   - Added developer preset modes (INVEST / TRADE) -- not exposed to users
# ============================================================


# ============================================================
# 1. COMPOSITE DIMENSION WEIGHTS
# ============================================================
# Main investment decision: Technical + Fundamental + Sentiment + Macro
#
# MACRO_ENABLED = True  activates the Macro dimension.
# Set to False to instantly revert to 3-dimension mode (for testing).
#
# When MACRO_ENABLED = True, weights must sum to 1.0.
# When MACRO_ENABLED = False, the original 3-dim weights are used.

MACRO_ENABLED      = True

# 4-dimension weights (active when MACRO_ENABLED = True)
# Macro raised to 10% (from 5%) to better reflect macro impact on high-Beta stocks.
# Technical reduced 47%→43%, Sentiment reduced 21%→20%.
WEIGHT_TECHNICAL   = 0.43
WEIGHT_FUNDAMENTAL = 0.27
WEIGHT_SENTIMENT   = 0.20
WEIGHT_MACRO       = 0.10

# 3-dimension fallback weights (used when MACRO_ENABLED = False
# or when macro data fetch fails)
WEIGHT_TECHNICAL_3D   = 0.48
WEIGHT_FUNDAMENTAL_3D = 0.32
WEIGHT_SENTIMENT_3D   = 0.20

# ── Developer preset modes (not exposed to users) ─────────────
# Switch by temporarily reassigning the four WEIGHT_* constants above.

# Long-term investment mode
WEIGHT_TECHNICAL_INVEST   = 0.25
WEIGHT_FUNDAMENTAL_INVEST = 0.40
WEIGHT_SENTIMENT_INVEST   = 0.20
WEIGHT_MACRO_INVEST       = 0.15

# Swing trading mode
WEIGHT_TECHNICAL_TRADE   = 0.40
WEIGHT_FUNDAMENTAL_TRADE = 0.25
WEIGHT_SENTIMENT_TRADE   = 0.25
WEIGHT_MACRO_TRADE       = 0.10

# Per-dimension thresholds for quadrant decision logic.
# A score must exceed its threshold to count as "meaningfully positive".
# Technical   : spread across full 0-100, 50 = genuine neutral
# Fundamental : clusters in 40-80, 55+ signals real quality
# Sentiment   : centred at 50 by design, 60+ needed for conviction
# Macro       : centred at 50, same as sentiment
THRESHOLD_TECHNICAL   = 50
THRESHOLD_FUNDAMENTAL = 55
THRESHOLD_SENTIMENT   = 60
THRESHOLD_MACRO       = 50


# ============================================================
# 2. SENTIMENT SUB-DIMENSION WEIGHTS
# ============================================================
# Must sum to 1.0. Redistributed proportionally if a
# sub-dimension returns no data.

WEIGHT_NEWS    = 0.55
WEIGHT_ANALYST = 0.22
WEIGHT_INSIDER = 0.13
WEIGHT_OPTIONS = 0.10


# ============================================================
# 3. NEWS SENTIMENT WEIGHTS
# ============================================================

# Relevance multipliers (how much an article counts toward score)
NEWS_RELEVANCE_WEIGHTS = {
    "direct":    1.0,   # explicitly about this stock
    "indirect":  0.4,   # affects sector/macro
    "unrelated": 0.0,   # no bearing on this stock
}

# Time decay by article age (days → weight)
NEWS_TIME_DECAY = [
    (3,  1.0),
    (7,  0.8),
    (14, 0.6),
    (30, 0.4),
]
NEWS_TIME_DECAY_DEFAULT = 0.2   # 30d+

# Impact-based time weight floor (major events stay relevant longer)
NEWS_TIME_WEIGHT_FLOOR = {
    "major":  0.5,
    "normal": 0.3,
    "minor":  0.0,
}

# Per-article GPT dimension multipliers
NEWS_INTENSITY_WEIGHTS   = {"strong": 1.0,  "moderate": 0.6,  "mild": 0.3}
NEWS_IMPACT_WEIGHTS      = {"major":  2.0,  "normal":   1.0,  "minor": 0.5}
NEWS_SCOPE_WEIGHTS       = {"company": 1.5, "industry": 1.0,  "macro": 0.6}
NEWS_CREDIBILITY_WEIGHTS = {"high":   1.5,  "medium":   1.0,  "low":   0.5}
NEWS_NOVELTY_WEIGHTS     = {"first":  1.5,  "followup": 0.7,  "repeat": 0.3}
NEWS_SURPRISE_WEIGHTS    = {"unexpected": 1.5, "partial": 1.0, "expected": 0.5}

# Cross-article consensus adjustment
NEWS_CONSENSUS_BOOST   = 1.2
NEWS_CONSENSUS_PENALTY = 0.8

# Score normalisation baseline (realistic average raw score, not theoretical max)
NEWS_CALIBRATION_RAW = 14.4


# ============================================================
# 4. ANALYST RATINGS WEIGHTS
# ============================================================

# Analyst firm authority multipliers (GPT-classified tiers)
ANALYST_AUTHORITY_WEIGHTS = {
    "top":     2.0,   # Goldman Sachs, Morgan Stanley, JPMorgan etc.
    "major":   1.2,   # Deutsche Bank, Barclays, UBS etc.
    "general": 0.7,   # smaller or boutique research firms
}

# Time decay by rating age (months → weight)
ANALYST_TIME_DECAY = [
    (1,  1.0),
    (3,  0.8),
    (6,  0.6),
    (12, 0.3),
]
ANALYST_TIME_DECAY_DEFAULT = 0.1

# Consensus multiplier (agreement across all analysts)
ANALYST_CONSENSUS_BOOST   = 1.15
ANALYST_CONSENSUS_PENALTY = 0.85

# Price target gap → score thresholds (upside % → points, max 20)
ANALYST_TARGET_GAP_THRESHOLDS = [
    (0.30, 20),
    (0.20, 16),
    (0.10, 10),
    (0.05,  5),
    (0.00,  2),
]

# Rating string → numeric score mapping
ANALYST_RATING_SCORES = {
    "strong buy":     2.0,
    "buy":            1.0,
    "hold":           0.0,
    "sell":          -1.0,
    "strong sell":   -2.0,
    "outperform":     1.0,
    "overweight":     1.0,
    "underperform":  -1.0,
    "underweight":   -1.0,
    "neutral":        0.0,
    "market perform": 0.0,
    "equal weight":   0.0,
    "sector perform": 0.0,
    "sector weight":  0.0,
}


# ============================================================
# 5. INSIDER TRADING WEIGHTS
# ============================================================

# Insider position level multipliers
INSIDER_POSITION_WEIGHTS = {
    "ceo":       2.0,
    "cfo":       1.8,
    "coo":       1.6,
    "president": 1.6,
    "chairman":  1.5,
    "director":  1.0,
    "vp":        0.9,
    "officer":   0.8,
    "other":     0.6,
}

# Time decay by transaction age (months → weight)
INSIDER_TIME_DECAY = [
    (1,  1.0),
    (3,  0.85),
    (6,  0.65),
    (12, 0.35),
]
INSIDER_TIME_DECAY_DEFAULT = 0.15

# Transaction size → score thresholds (USD value → points, max 20)
INSIDER_SIZE_THRESHOLDS = [
    (10_000_000, 20),
    (5_000_000,  16),
    (1_000_000,  12),
    (500_000,     8),
    (100_000,     4),
    (0,           1),
]


# ============================================================
# 6. OPTIONS SENTIMENT WEIGHTS
# ============================================================

# PCR baseline (equity market historical average, not 1.0)
OPTIONS_PCR_BASELINE = 0.7

# IV thresholds for confidence multiplier
OPTIONS_IV_HIGH     = 0.60   # >60% → high uncertainty
OPTIONS_IV_MODERATE = 0.35   # 35-60% → moderate

# IV confidence multipliers (dampens signal when market is uncertain)
OPTIONS_IV_MULT_HIGH     = 0.70
OPTIONS_IV_MULT_MODERATE = 0.85
OPTIONS_IV_MULT_LOW      = 1.00

# PCR volume → score thresholds (PCR value → points, max 35)
OPTIONS_PCR_VOL_THRESHOLDS = [
    (0.40, 35),
    (0.55, 28),
    (0.70, 20),
    (0.90, 12),
    (1.10,  6),
    (1.40,  2),
]

# PCR open interest → score thresholds (PCR value → points, max 25)
OPTIONS_PCR_OI_THRESHOLDS = [
    (0.50, 25),
    (0.70, 20),
    (0.90, 14),
    (1.10,  8),
    (1.30,  3),
    (9999,  0),
]


# ============================================================
# 7. MACRO ENVIRONMENT WEIGHTS
# ============================================================
# Controls the macro scoring engine in scoring/macro_scorer.py.
# All point values refer to the sub-score maximums that sum to 100.

# Sub-score maximums (must sum to 100)
MACRO_VIX_MAX_PTS    = 35   # VIX fear gauge
MACRO_YIELD_MAX_PTS  = 35   # yield curve shape + rate trend
MACRO_REGIME_MAX_PTS = 30   # S&P 500 30-day trend (market regime)

# Sensitivity multiplier composition
# Beta is empirical (actual market response), sector is categorical.
# Beta weight slightly reduced (0.60→0.55) and sector (0.40→0.35),
# with a fixed 0.10 base to reduce double-counting between the two.
# Note: Beta and Sector sensitivity have partial overlap (high-Beta stocks
# tend to be in high-sensitivity sectors). This is a known approximation.
MACRO_BETA_WEIGHT   = 0.55
MACRO_SECTOR_WEIGHT = 0.35
MACRO_BASE_WEIGHT   = 0.10   # fixed baseline, reduces amplification at extremes

# VIX rapid spike: if VIX rises >X% in 30 days, apply penalty pts
MACRO_RAPID_VIX_SPIKE_THRESHOLD = 40.0   # % VIX rise in 30d
MACRO_RAPID_VIX_SPIKE_PENALTY   = 8      # pts deducted from VIX sub-score

# Rate trend: absolute change in 10Y yield in pp over 30 days
# e.g. 4.0% → 4.5% = +0.50pp change
MACRO_RAPID_RATE_RISE_THRESHOLD = 0.40   # pp rise triggers penalty
MACRO_RAPID_RATE_RISE_PENALTY   = -8     # pts added (negative = penalty)
MACRO_RAPID_RATE_FALL_BONUS     = 5      # pts added when rates fall fast


# ============================================================
# 8. EVENT-DRIVEN WEIGHTS
# ============================================================
# Controls the event reliability layer in scoring/event_scorer.py.
#
# Reliability coefficients per time window.
# 1.0 = full signal reliability (no event distortion)
# 0.5 = severely dampened (post-earnings shock)
#
# These values override the hardcoded defaults in event_scorer.py,
# making them easy to tune without touching scoring logic.

EVENT_WINDOW_RELIABILITY = {
    "POST_EARNINGS_SHOCK":   0.50,   # 0-1 days after earnings
    "PRE_EARNINGS_IMMINENT": 0.65,   # 1-3 days before earnings
    "PRE_EARNINGS_NEAR":     0.80,   # 4-7 days before earnings
    "PRE_EARNINGS_WATCH":    0.90,   # 8-14 days before earnings
    "POST_EARNINGS_DIGEST":  0.85,   # 2-5 days after earnings
    "NORMAL":                1.00,   # no imminent event
}

# EPS surprise thresholds for beat/miss classification
# Positive = beat, negative = miss (as % of estimate)
EVENT_SURPRISE_BEAT_THRESHOLD =  5.0   # >5% above estimate = beat
EVENT_SURPRISE_MISS_THRESHOLD = -5.0   # >5% below estimate = miss
