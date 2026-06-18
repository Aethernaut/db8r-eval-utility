"""Foraging endpoints (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..store import GoldStore
from .dependencies import get_store
from .schemas import (
    ForageQueryListResponse,
    ForageQueryResponse,
    ForageStrategyDetailResponse,
    ForageStrategyListResponse,
    ForageStrategyResponse,
)

router = APIRouter()


def _strategy_to_response(strategy) -> ForageStrategyResponse:
    """Convert ForageStrategyRecord to response model."""
    return ForageStrategyResponse(
        forage_strategy_id=strategy.forage_strategy_id,
        claim_id=strategy.claim_id,
        claim_text=strategy.claim_text,
        mode=strategy.mode,
        perspective=strategy.perspective,
        generator_version=strategy.generator_version,
        generator=strategy.generator,
        claim_type=strategy.claim_type,
        providers=strategy.providers,
        context=strategy.context,
        source=strategy.source,
        fallback_reason=strategy.fallback_reason,
        claim_decomposition=strategy.claim_decomposition,
        polarity_reversal=strategy.polarity_reversal,
        schema_plan=strategy.schema_plan,
        captured_at=strategy.captured_at,
        created_at=strategy.created_at,
    )


def _query_to_response(query) -> ForageQueryResponse:
    """Convert ForageQueryRecord to response model."""
    return ForageQueryResponse(
        forage_query_id=query.forage_query_id,
        forage_strategy_id=query.forage_strategy_id,
        pool=query.pool,
        query=query.query,
        strategy=query.strategy,
        priority=query.priority,
        rank=query.rank,
        providers=query.providers,
        intent_label=query.intent_label,
        rationale=query.rationale,
        retrieval_role=query.retrieval_role,
        scheme=query.scheme,
        critical_question_family=query.critical_question_family,
        target_schema_need_id=query.target_schema_need_id,
        fixture_id=query.fixture_id,
        created_at=query.created_at,
    )


@router.get("/strategies", response_model=ForageStrategyListResponse)
def list_strategies(
    claim_id: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    store: GoldStore = Depends(get_store),
) -> ForageStrategyListResponse:
    """List forage strategies."""
    # Get all strategies from store
    with store._connect() as conn:
        if claim_id:
            rows = conn.execute(
                "SELECT * FROM forage_strategy WHERE claim_id = ? ORDER BY captured_at LIMIT ? OFFSET ?",
                (claim_id, limit, offset),
            ).fetchall()
            count_row = conn.execute(
                "SELECT COUNT(*) FROM forage_strategy WHERE claim_id = ?", (claim_id,)
            ).fetchone()
        else:
            rows = conn.execute(
                "SELECT * FROM forage_strategy ORDER BY captured_at LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            count_row = conn.execute("SELECT COUNT(*) FROM forage_strategy").fetchone()

    import json

    strategies = []
    for row in rows:
        d = dict(row)
        d["providers"] = json.loads(d["providers"]) if d["providers"] else []
        d["context"] = json.loads(d["context"]) if d["context"] else None
        d["claim_decomposition"] = json.loads(d["claim_decomposition"]) if d["claim_decomposition"] else None
        d["polarity_reversal"] = json.loads(d["polarity_reversal"]) if d["polarity_reversal"] else None
        d["schema_plan"] = json.loads(d["schema_plan"]) if d["schema_plan"] else None

        from ..store import ForageStrategyRecord

        strategies.append(_strategy_to_response(ForageStrategyRecord(**d)))

    return ForageStrategyListResponse(strategies=strategies, total=count_row[0])


@router.get("/strategies/{strategy_id}", response_model=ForageStrategyDetailResponse)
def get_strategy(
    strategy_id: str,
    store: GoldStore = Depends(get_store),
) -> ForageStrategyDetailResponse:
    """Get forage strategy with queries."""
    strategy = store.get_forage_strategy(strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    queries = store.get_queries_for_strategy(strategy_id)

    return ForageStrategyDetailResponse(
        forage_strategy_id=strategy.forage_strategy_id,
        claim_id=strategy.claim_id,
        claim_text=strategy.claim_text,
        mode=strategy.mode,
        perspective=strategy.perspective,
        generator_version=strategy.generator_version,
        generator=strategy.generator,
        claim_type=strategy.claim_type,
        providers=strategy.providers,
        context=strategy.context,
        source=strategy.source,
        fallback_reason=strategy.fallback_reason,
        claim_decomposition=strategy.claim_decomposition,
        polarity_reversal=strategy.polarity_reversal,
        schema_plan=strategy.schema_plan,
        captured_at=strategy.captured_at,
        created_at=strategy.created_at,
        queries=[_query_to_response(q) for q in queries],
    )


@router.get("/queries", response_model=ForageQueryListResponse)
def list_queries(
    strategy_id: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    store: GoldStore = Depends(get_store),
) -> ForageQueryListResponse:
    """List forage queries."""
    import json

    with store._connect() as conn:
        if strategy_id:
            rows = conn.execute(
                "SELECT * FROM forage_query WHERE forage_strategy_id = ? ORDER BY rank LIMIT ? OFFSET ?",
                (strategy_id, limit, offset),
            ).fetchall()
            count_row = conn.execute(
                "SELECT COUNT(*) FROM forage_query WHERE forage_strategy_id = ?", (strategy_id,)
            ).fetchone()
        else:
            rows = conn.execute(
                "SELECT * FROM forage_query ORDER BY created_at LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            count_row = conn.execute("SELECT COUNT(*) FROM forage_query").fetchone()

    queries = []
    for row in rows:
        d = dict(row)
        d["providers"] = json.loads(d["providers"]) if d["providers"] else []

        from ..store import ForageQueryRecord

        queries.append(_query_to_response(ForageQueryRecord(**d)))

    return ForageQueryListResponse(queries=queries, total=count_row[0])
