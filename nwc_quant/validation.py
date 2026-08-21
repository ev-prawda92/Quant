"""
Validation (#7) — the overfitting defense. This is what separates a quant from
someone who curve-fit the past.

Three checks:
  1. walk_forward       — performance across sequential out-of-sample folds,
                          so you see whether the edge is stable or a one-period
                          fluke.
  2. deflated_sharpe    — López de Prado's haircut: given that you effectively
                          TRIED N strategy configs, how likely is this Sharpe
                          just the best of N noisy draws? Returns a probability
                          the true Sharpe is > 0 after that correction.
  3. alpha_regression   — regress strategy returns on the benchmark; report
                          annualized alpha and its Newey-West t-stat. If the
                          "edge" is just beta to the market, alpha ~ 0.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd
from scipy.stats import norm

from .metrics import sharpe, _ann_return, _ann_vol


# ── 1. walk-forward ───────────────────────────────────────────────────────
def walk_forward(returns: pd.Series, n_splits: int = 4) -> dict:
    r = returns.dropna()
    folds = np.array_split(np.arange(len(r)), n_splits)
    rows = []
    for k, idx in enumerate(folds):
        seg = r.iloc[idx]
        rows.append({
            "fold": k + 1,
            "start": str(seg.index[0].date()),
            "end": str(seg.index[-1].date()),
            "ann_return": _ann_return(seg),
            "sharpe": sharpe(seg),
        })
    df = pd.DataFrame(rows)
    return {
        "folds": df.to_dict("records"),
        "mean_oos_sharpe": float(df["sharpe"].mean()),
        "std_oos_sharpe": float(df["sharpe"].std(ddof=0)),
        "positive_folds": int((df["sharpe"] > 0).sum()),
        "n_folds": n_splits,
    }


# ── 2. deflated Sharpe ratio ──────────────────────────────────────────────
def _expected_max_sharpe(n_trials: int, var_sr: float) -> float:
    """Expected max of N iid Sharpe estimates under a zero-true-Sharpe null
    (per-period units). López de Prado (2014)."""
    if n_trials < 2:
        return 0.0
    gamma = 0.5772156649  # Euler–Mascheroni
    z1 = norm.ppf(1 - 1.0 / n_trials)
    z2 = norm.ppf(1 - 1.0 / n_trials * np.e ** -1)
    return np.sqrt(var_sr) * ((1 - gamma) * z1 + gamma * z2)


def deflated_sharpe(returns: pd.Series, n_trials: int = 20,
                    trial_sharpes: Optional[np.ndarray] = None) -> dict:
    """
    Returns the Deflated Sharpe Ratio (a probability in [0,1]) that the true
    Sharpe exceeds the selection-adjusted benchmark. Rule of thumb: DSR > 0.95
    is the bar to take a backtested Sharpe seriously.
    """
    r = returns.dropna().values
    T = len(r)
    if T < 30:
        return {"error": "not enough observations"}

    mu, sd = r.mean(), r.std(ddof=1)
    sr_hat = mu / sd if sd else 0.0                  # per-period Sharpe
    skew = float(pd.Series(r).skew())
    kurt = float(pd.Series(r).kurt()) + 3.0          # pandas gives excess kurtosis

    # variance of the Sharpe estimator across trials
    if trial_sharpes is not None and len(trial_sharpes) > 1:
        var_sr = float(np.var(trial_sharpes, ddof=1))
    else:
        # analytic SE^2 of the Sharpe estimator under the observed moments
        var_sr = (1 - skew * sr_hat + (kurt - 1) / 4.0 * sr_hat ** 2) / (T - 1)

    sr_star = _expected_max_sharpe(n_trials, var_sr)  # benchmark to beat

    denom = np.sqrt(max(1 - skew * sr_hat + (kurt - 1) / 4.0 * sr_hat ** 2, 1e-9))
    dsr = norm.cdf(((sr_hat - sr_star) * np.sqrt(T - 1)) / denom)

    return {
        "sharpe_per_period": float(sr_hat),
        "sharpe_annualized": float(sr_hat * np.sqrt(252)),
        "benchmark_sharpe_star_ann": float(sr_star * np.sqrt(252)),
        "n_trials_assumed": n_trials,
        "deflated_sharpe_ratio": float(dsr),
        "passes_0.95": bool(dsr > 0.95),
    }


# ── 3. alpha regression vs benchmark ──────────────────────────────────────
def alpha_regression(returns: pd.Series, benchmark: pd.Series,
                     nw_lags: int = 5) -> dict:
    """
    OLS of strategy returns on benchmark returns with Newey-West (HAC) errors.
    Reports annualized alpha, beta, and the alpha t-stat. A t-stat below ~2
    means the outperformance is not statistically distinguishable from luck /
    market beta.
    """
    import statsmodels.api as sm

    df = pd.concat([returns.rename("y"), benchmark.rename("x")], axis=1).dropna()
    if len(df) < 30:
        return {"error": "not enough overlap"}

    X = sm.add_constant(df["x"].values)
    model = sm.OLS(df["y"].values, X).fit(cov_type="HAC", cov_kwds={"maxlags": nw_lags})
    alpha_daily, beta = model.params
    t_alpha = model.tvalues[0]
    return {
        "alpha_annualized": float(alpha_daily * 252),
        "alpha_tstat": float(t_alpha),
        "beta": float(beta),
        "alpha_significant_5pct": bool(abs(t_alpha) > 1.96),
        "r_squared": float(model.rsquared),
    }


@dataclass
class ValidationReport:
    walk_forward: dict
    deflated_sharpe: dict
    alpha: dict

    def verdict(self) -> str:
        wf = self.walk_forward
        ds = self.deflated_sharpe
        al = self.alpha
        checks = [
            wf.get("positive_folds", 0) >= wf.get("n_folds", 1) - 1,
            ds.get("passes_0.95", False),
            al.get("alpha_significant_5pct", False) and al.get("alpha_annualized", 0) > 0,
        ]
        passed = sum(bool(c) for c in checks)
        if passed == 3:
            return "PASS — edge is stable, survives selection haircut, and shows significant alpha."
        if passed == 2:
            return "MARGINAL — some evidence of edge; treat with caution, keep paper-trading."
        return "FAIL — no statistically defensible edge. Do not risk capital on this config."


def validate(returns: pd.Series, benchmark: pd.Series,
             n_trials: int = 20, n_splits: int = 4,
             trial_sharpes: Optional[np.ndarray] = None) -> ValidationReport:
    return ValidationReport(
        walk_forward=walk_forward(returns, n_splits=n_splits),
        deflated_sharpe=deflated_sharpe(returns, n_trials=n_trials, trial_sharpes=trial_sharpes),
        alpha=alpha_regression(returns, benchmark),
    )
