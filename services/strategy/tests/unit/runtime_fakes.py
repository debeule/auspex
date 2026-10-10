import io
from collections.abc import Callable
from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pandas as pd
from auspex_backtesting.market_sim import (
    CostModel,
    CostParameters,
    CurrencyConverter,
    FillModel,
    PriceSnapshotStore,
)
from minio.error import S3Error

from auspex_strategy.abc import AsOfContext, Strategy
from auspex_strategy.models import (
    CorroborationRecord,
    Direction,
    FixedDays,
    HoldingRule,
    InputSource,
    IntentRationale,
    StrategyParameters,
    SubscriptionType,
    TradeIntent,
    Trigger,
)
from auspex_strategy.registry import RegistryEntry
from auspex_strategy.runtime import CorroboratedSignal, PaperBroker, StrategySlot

COST_PARAMS = CostParameters(
    usd_min_commission=1.00,
    ibkr_rate_per_share=0.005,
    spread_bps=50.0,
    tob_rate=0.0035,
    borrow_fee_annual_pct=3.0,
    fx_fee_rate=0.0003,
)

Decide = Callable[[Strategy, AsOfContext, Trigger], list[TradeIntent]]


def ohlcv(rows: dict[str, tuple[float, float, float, float]]) -> pd.DataFrame:
    """rows maps ISO date -> (open, high, low, close), in the stored PriceFetcher schema."""
    idx = pd.DatetimeIndex(list(rows), tz="UTC", name="date")
    return pd.DataFrame(
        {
            "open": [r[0] for r in rows.values()],
            "high": [r[1] for r in rows.values()],
            "low": [r[2] for r in rows.values()],
            "close": [r[3] for r in rows.values()],
            "volume": [100_000.0] * len(rows),
        },
        index=idx,
    )


def flat_bars(start: date, end: date, price: float) -> dict[str, tuple[float, float, float, float]]:
    days = pd.bdate_range(start, end)
    return {d.date().isoformat(): (price, price, price, price) for d in days}


def price_store(snapshots: dict[str, pd.DataFrame]) -> PriceSnapshotStore:
    def get_object(bucket: str, key: str) -> MagicMock:
        ticker = key.removesuffix(".parquet")
        if ticker not in snapshots:
            raise S3Error(MagicMock(), "NoSuchKey", "The specified key does not exist.", "/", "", "")
        buf = io.BytesIO()
        snapshots[ticker].to_parquet(buf)
        response = MagicMock()
        response.read.return_value = buf.getvalue()
        return response

    minio = MagicMock()
    minio.get_object.side_effect = get_object
    return PriceSnapshotStore(minio_client=minio)


def broker(objects: object, snapshots: dict[str, pd.DataFrame]) -> PaperBroker:
    prices = price_store(snapshots)
    return PaperBroker(
        objects,  # type: ignore[arg-type]
        fills=FillModel(prices),
        costs=CostModel(COST_PARAMS),
        fx=CurrencyConverter(prices),
    )


def strategy_class(
    name: str,
    *,
    decide: Decide,
    inputs: frozenset[InputSource] = frozenset({InputSource.CORROBORATION_STORE}),
    hypothesis_id: str = "h1",
) -> type[Strategy]:
    class _Synthetic(Strategy):
        @property
        def subscriptions(self) -> frozenset[SubscriptionType]:
            return frozenset({SubscriptionType.CORROBORATION_NEW})

        @property
        def declared_inputs(self) -> frozenset[InputSource]:
            return inputs

        def decide(self, context: AsOfContext, trigger: Trigger) -> list[TradeIntent]:
            return decide(self, context, trigger)

        @classmethod
        def parameters(cls) -> StrategyParameters:
            return StrategyParameters(raw={})

    _Synthetic.name = name
    _Synthetic.version = "1.0"
    _Synthetic.hypothesis_id = hypothesis_id
    _Synthetic.description = f"synthetic {name}"
    return _Synthetic


def slot(
    name: str,
    status: str,
    decide: Decide,
    *,
    inputs: frozenset[InputSource] = frozenset({InputSource.CORROBORATION_STORE}),
    known_at_delay_days: int = 1,
) -> StrategySlot:
    cls = strategy_class(name, decide=decide, inputs=inputs)
    entry = RegistryEntry(
        name=name,
        module="tests.unit.runtime_fakes",
        class_name=cls.__name__,
        version="1.0",
        hypothesis_id="h1",
        status=status,
        parameters_file=None,
        strategy_class=cls,
    )
    return StrategySlot(entry=entry, known_at_delay_days=known_at_delay_days)


_TWENTY_DAYS = FixedDays(20)


def long_on_trigger(ticker: str = "SRPT", holding_rule: HoldingRule = _TWENTY_DAYS) -> Decide:
    """A decide() that goes long `ticker` once per triggering corroboration."""

    def decide(self: Strategy, context: AsOfContext, trigger: Trigger) -> list[TradeIntent]:
        record = trigger.payload
        assert isinstance(record, CorroborationRecord)
        return [
            TradeIntent(
                ticker=ticker,
                direction=Direction.LONG,
                conviction=0.5,
                holding_rule=holding_rule,
                exit_conditions=(),
                rationale=IntentRationale(
                    corroboration_id=record.entity_key,
                    entity_key=record.entity_key,
                    as_of=context.as_of,
                    source_types=record.source_types,
                    directionality="positive",
                    confidence_scores=(0.9,),
                ),
                strategy_name=self.name,
                strategy_version=self.version,
                hypothesis_id=self.hypothesis_id,
                as_of=context.as_of,
            )
        ]

    return decide


def crash(self: Strategy, context: AsOfContext, trigger: Trigger) -> list[TradeIntent]:
    raise RuntimeError("strategy bug")


def record(entity_key: str, corroborated_at: datetime, ticker: str = "SRPT") -> CorroborationRecord:
    return CorroborationRecord(
        entity_key=entity_key,
        ticker=ticker,
        corroborated_at=corroborated_at,
        source_count=2,
        source_types=frozenset({"biorxiv", "clinicaltrials"}),
        participant_event_ids=(f"{entity_key}-a", f"{entity_key}-b"),
    )


def signal(
    entity_key: str,
    corroborated_at: datetime,
    first_detected_at: datetime | None = None,
) -> CorroboratedSignal:
    return CorroboratedSignal(
        entity_key=entity_key,
        participants_hash=f"hash-{entity_key}",
        participant_event_ids=(f"{entity_key}-a", f"{entity_key}-b"),
        distinct_source_count=2,
        corroborated_at=corroborated_at,
        first_detected_at=first_detected_at or corroborated_at,
    )


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)  # type: ignore[misc]
