"""Run a set of sources concurrently. Each source is isolated; one failure never fails the run."""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

from core.models import SourceName, SourceQuery
from core.sources import SOURCES
from core.sources.base import BaseSource, SourceOutcome
from core.sources.exa import Exa


def run_sources(
    names: Iterable[SourceName],
    q: SourceQuery,
    registry: dict[SourceName, BaseSource] | None = None,
) -> list[SourceOutcome]:
    reg = registry if registry is not None else SOURCES
    selected = [reg[n] for n in names if n in reg]
    if not selected:
        return []
    with ThreadPoolExecutor(max_workers=len(selected)) as pool:
        outcomes = list(pool.map(lambda s: s.run(q), selected))
    return _news_fallback(outcomes, q, reg)


def _news_fallback(
    outcomes: list[SourceOutcome], q: SourceQuery, reg: dict[SourceName, BaseSource]
) -> list[SourceOutcome]:
    """TinyFish is the default news route; Exa news fills in only when TinyFish is down (D7).

    Fallback hits are credited to Exa, so the footer never claims TinyFish answered.
    """
    exa = reg.get(SourceName.EXA)
    tiny = next((o for o in outcomes if o.source is SourceName.TINYFISH_NEWS), None)
    if tiny is None or tiny.status == "ok" or not isinstance(exa, Exa):
        return outcomes
    news = exa.search_news(q)
    if not news:
        return outcomes
    out: list[SourceOutcome] = []
    for o in outcomes:
        if o.source is SourceName.TINYFISH_NEWS:
            detail = "; ".join(x for x in (o.detail, "exa news fallback used") if x)
            o = SourceOutcome(o.source, [], o.status, detail)
        elif o.source is SourceName.EXA:
            o = SourceOutcome(o.source, [*o.hits, *news], "ok", "people + news fallback")
        out.append(o)
    if all(o.source is not SourceName.EXA for o in out):
        out.append(SourceOutcome(SourceName.EXA, news, "ok", "news fallback"))
    return out


def split(
    outcomes: list[SourceOutcome],
) -> tuple[list[SourceName], list[SourceName], dict[str, str]]:
    """Return (contributing, unavailable, per-source status) for the output footer."""
    contributing = [o.source for o in outcomes if o.hits]
    unavailable = [o.source for o in outcomes if not o.hits]
    status = {str(o.source): o.footer.split(": ", 1)[1] for o in outcomes}
    return contributing, unavailable, status
