"""Foraging endpoints (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from ..database import session_scope
from ..models import ForageQueryModel, ForageStrategyModel
from ..store import ForageQueryRecord, ForageStrategyRecord, GoldStore
from .dependencies import get_store
from .schemas import (
    ForageQueryListResponse,
    ForageQueryResponse,
    ForageStrategyDetailResponse,
    ForageStrategyListResponse,
    ForageStrategyResponse,
)

router = APIRouter()


def _model_to_strategy(m: ForageStrategyModel) -> ForageStrategyRecord:
    """Convert SQLAlchemy model to dataclass."""
    providers = m.providers if isinstance(m.providers, list) else []
    return ForageStrategyRecord(
        forage_strategy_id=m.forage_strategy_id,
        claim_id=m.claim_id,
        claim_text=m.claim_text,
        mode=m.mode,
        perspective=m.perspective,
        generator_version=m.generator_version,
        generator=m.generator,
        claim_type=m.claim_type,
        providers=providers,
        context=m.context,
        source=m.source,
        fallback_reason=m.fallback_reason,
        claim_decomposition=m.claim_decomposition,
        polarity_reversal=m.polarity_reversal,
        schema_plan=m.schema_plan,
        captured_at=m.captured_at.isoformat() if m.captured_at else "",
        created_at=m.created_at.isoformat() if m.created_at else "",
    )


def _model_to_query(m: ForageQueryModel) -> ForageQueryRecord:
    """Convert SQLAlchemy model to dataclass."""
    providers = m.providers if isinstance(m.providers, list) else []
    return ForageQueryRecord(
        forage_query_id=m.forage_query_id,
        forage_strategy_id=m.forage_strategy_id,
        pool=m.pool,
        query=m.query,
        strategy=m.strategy,
        priority=m.priority,
        rank=m.rank,
        providers=providers,
        intent_label=m.intent_label,
        rationale=m.rationale,
        retrieval_role=m.retrieval_role,
        scheme=m.scheme,
        critical_question_family=m.critical_question_family,
        target_schema_need_id=m.target_schema_need_id,
        fixture_id=m.fixture_id,
        created_at=m.created_at.isoformat() if m.created_at else "",
    )


def _strategy_to_response(strategy: ForageStrategyRecord) -> ForageStrategyResponse:
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


def _query_to_response(query: ForageQueryRecord) -> ForageQueryResponse:
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
    with session_scope() as session:
        stmt = select(ForageStrategyModel)
        count_stmt = select(func.count()).select_from(ForageStrategyModel)

        if claim_id is not None:
            stmt = stmt.where(ForageStrategyModel.claim_id == claim_id)
            count_stmt = count_stmt.where(ForageStrategyModel.claim_id == claim_id)

        stmt = stmt.order_by(ForageStrategyModel.captured_at)
        stmt = stmt.offset(offset).limit(limit)

        models = session.execute(stmt).scalars().all()
        total = session.execute(count_stmt).scalar() or 0

    strategies = [_strategy_to_response(_model_to_strategy(m)) for m in models]
    return ForageStrategyListResponse(strategies=strategies, total=total)


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
    with session_scope() as session:
        stmt = select(ForageQueryModel)
        count_stmt = select(func.count()).select_from(ForageQueryModel)

        if strategy_id is not None:
            stmt = stmt.where(ForageQueryModel.forage_strategy_id == strategy_id)
            count_stmt = count_stmt.where(ForageQueryModel.forage_strategy_id == strategy_id)

        stmt = stmt.order_by(ForageQueryModel.rank)
        stmt = stmt.offset(offset).limit(limit)

        models = session.execute(stmt).scalars().all()
        total = session.execute(count_stmt).scalar() or 0

    queries = [_query_to_response(_model_to_query(m)) for m in models]
    return ForageQueryListResponse(queries=queries, total=total)
