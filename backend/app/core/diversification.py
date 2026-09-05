"""Diversification metrics: pairwise return correlation, effective independent
bets, closest pair, and "least correlated to add" suggestions.

Pure math on return series in, plain dicts/tuples out — no DB, Redis, or
yfinance calls live here, mirroring change_engine.py's separation of concerns
so these formulas can be tested and stepped through in isolation.
"""

from __future__ import annotations

from statistics import mean
from typing import Sequence, TypedDict


def returns_from_closes(closes: Sequence[float]) -> list[float]:
    """Simple close-to-close returns from a chronological list of closing prices."""
    if len(closes) < 2:
        return []
    out: list[float] = []
    for prev, curr in zip(closes, closes[1:]):
        if prev:
            out.append((curr - prev) / prev)
    return out


def pearson_correlation(a: Sequence[float], b: Sequence[float]) -> float | None:
    """Pearson correlation over the trailing overlap of two return series.

    Aligns on the most recent min(len(a), len(b)) points. Returns None when
    there isn't enough overlap (fewer than 3 points) or either series has
    zero variance — correlation is undefined there, not zero.
    """
    n = min(len(a), len(b))
    if n < 3:
        return None
    a_tail = list(a[-n:])
    b_tail = list(b[-n:])
    mean_a, mean_b = mean(a_tail), mean(b_tail)
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a_tail, b_tail))
    var_a = sum((x - mean_a) ** 2 for x in a_tail)
    var_b = sum((y - mean_b) ** 2 for y in b_tail)
    if var_a == 0 or var_b == 0:
        return None
    return cov / ((var_a * var_b) ** 0.5)


class PairCorrelation(TypedDict):
    a: str
    b: str
    correlation: float


CorrelationMatrix = dict[tuple[str, str], float]


def build_correlation_matrix(returns_by_symbol: dict[str, Sequence[float]]) -> CorrelationMatrix:
    """All pairwise correlations among the given symbols (undefined pairs omitted)."""
    symbols = list(returns_by_symbol)
    matrix: CorrelationMatrix = {}
    for i, sym_a in enumerate(symbols):
        for sym_b in symbols[i + 1 :]:
            corr = pearson_correlation(returns_by_symbol[sym_a], returns_by_symbol[sym_b])
            if corr is not None:
                matrix[(sym_a, sym_b)] = corr
    return matrix


def lookup_correlation(a: str, b: str, matrix: CorrelationMatrix) -> float | None:
    """Symmetric lookup — 1.0 on the diagonal, undefined pairs return None."""
    if a == b:
        return 1.0
    return matrix.get((a, b), matrix.get((b, a)))


def average_pairwise_correlation(matrix: CorrelationMatrix) -> float | None:
    if not matrix:
        return None
    return mean(matrix.values())


def effective_independent_bets(n: int, avg_correlation: float | None) -> float:
    """Effective number of independent bets in an n-name, equal-weighted book.

    n / (1 + (n-1) * avg_correlation). Perfect correlation (1.0) collapses the
    whole book to a single bet; zero correlation gives you all n names as
    independent bets. Missing correlation data (fewer than 2 priced names)
    treats the book as fully independent rather than guessing. A slightly
    negative average correlation can push the raw ratio above n, which isn't
    meaningful — a book can't have more independent bets than names — so the
    result is capped at n.
    """
    if n <= 0:
        return 0.0
    if avg_correlation is None:
        return float(n)
    denom = 1 + (n - 1) * avg_correlation
    if denom <= 0:
        return float(n)
    return min(float(n), n / denom)


def closest_pair(matrix: CorrelationMatrix) -> PairCorrelation | None:
    """The two most-correlated names in the book (the biggest single redundancy)."""
    if not matrix:
        return None
    (sym_a, sym_b), corr = max(matrix.items(), key=lambda kv: kv[1])
    return {"a": sym_a, "b": sym_b, "correlation": corr}


def per_symbol_average_correlation(
    symbols: Sequence[str], matrix: CorrelationMatrix
) -> dict[str, float]:
    """Each symbol's average correlation to every other priced symbol in the book."""
    out: dict[str, float] = {}
    for sym in symbols:
        vals = [corr for (a, b), corr in matrix.items() if sym in (a, b)]
        if vals:
            out[sym] = mean(vals)
    return out


def adds_the_least(
    symbols: Sequence[str], matrix: CorrelationMatrix
) -> tuple[str, float] | None:
    """The held symbol with the lowest average correlation to the rest of the book —
    i.e. the one contributing the least redundant risk right now."""
    averages = per_symbol_average_correlation(symbols, matrix)
    if not averages:
        return None
    return min(averages.items(), key=lambda kv: kv[1])


def largest_sector(sector_by_symbol: dict[str, str]) -> tuple[str, float] | None:
    """The best-represented sector and its share of the book (blank sectors ignored)."""
    counts: dict[str, int] = {}
    total = 0
    for sector in sector_by_symbol.values():
        cleaned = (sector or "").strip()
        if not cleaned:
            continue
        counts[cleaned] = counts.get(cleaned, 0) + 1
        total += 1
    if not counts:
        return None
    sector, count = max(counts.items(), key=lambda kv: kv[1])
    return sector, (count / total) * 100.0


def rank_addition_candidates(
    candidate_returns: dict[str, Sequence[float]],
    held_returns: dict[str, Sequence[float]],
    limit: int = 3,
) -> list[dict]:
    """Rank symbols not already held by average correlation to the current book,
    ascending — the top of this list adds the most diversification if added.
    """
    ranked: list[dict] = []
    for symbol, returns in candidate_returns.items():
        corrs = [
            corr
            for held_returns_series in held_returns.values()
            if (corr := pearson_correlation(returns, held_returns_series)) is not None
        ]
        if corrs:
            ranked.append({"symbol": symbol, "avg_correlation": mean(corrs)})
    ranked.sort(key=lambda row: row["avg_correlation"])
    return ranked[:limit]
