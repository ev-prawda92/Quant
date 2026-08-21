"""Central configuration for the quant engine."""
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class EngineConfig:
    # ── Universe / data (#1) ──
    # A real quant strategy ranks a BROAD cross-section, not a 12-name watchlist.
    # Breadth is where the edge comes from (Grinold: IR ≈ IC * sqrt(breadth)).
    universe_size: int = 100          # synthetic universe size for the demo
    start: str = "2015-01-01"
    end: str = "2025-12-31"
    trading_days_per_year: int = 252

    # ── Rebalance (#2) ──
    rebalance_freq: str = "ME"        # month-end (pandas offset alias)

    # ── Factors (#3) ──
    # Weights for the composite. Keep simple/equal to start — clever weighting
    # is the #1 place quant strategies overfit.
    factor_weights: Dict[str, float] = field(default_factory=lambda: {
        "momentum": 1.0,
        "value": 1.0,
        "quality": 1.0,
        "low_vol": 0.5,
        "reversal": 0.5,
    })
    winsorize_pct: float = 0.02       # clip extreme z-scores at 2%/98%

    # ── Portfolio construction (#5) ──
    long_only: bool = True            # a $3,500 Robinhood account can't short cheaply
    top_quantile: float = 0.2         # long the best 20% of the cross-section
    bottom_quantile: float = 0.2      # (used only if long_only=False)
    max_position_weight: float = 0.05 # cap any single name at 5% (Dalio rule echo)
    sector_neutral: bool = True       # don't let the bet become "just long tech"
    target_annual_vol: float = 0.10   # scale exposure to ~10% annualized vol

    # ── Costs (#6) ──
    commission_bps: float = 1.0       # per-side commission (bps of traded notional)
    spread_bps: float = 5.0           # half-spread / slippage assumption (bps)

    # ── Validation (#7) ──
    walk_forward_splits: int = 4
    n_strategy_trials: int = 20       # how many configs you effectively tried
                                      # (feeds the deflated Sharpe haircut)

    seed: int = 42


DEFAULT = EngineConfig()
