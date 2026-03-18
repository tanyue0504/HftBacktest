from pathlib import Path

import pandas as pd

from hft_backtest import ParquetDataset
from hft_backtest.ashare.event import (
    AshareDailyBasicEvent,
    AshareDailyEvent,
    AshareNameChangeEvent,
)


def _write_parquet(path: Path, rows: list[dict]):
    pd.DataFrame(rows).to_parquet(path, index=False)


def _to_event_ts(series: pd.Series) -> pd.Series:
    token = series.astype(str).str.replace("-", "", regex=False).str[:8]
    dt = pd.to_datetime(token, format="%Y%m%d", errors="coerce")
    return (dt.astype("int64") // 10**6).astype("int64")


def test_core_parquet_dataset_can_generate_daily_event_with_private_next_open(tmp_path: Path):
    path = tmp_path / "daily.parquet"
    rows = [
        {"ts_code": "000001.SZ", "trade_date": "20240101", "open": 10.0, "high": 11.0, "low": 9.5, "close": 10.0, "pre_close": 9.8, "change": 0.2, "pct_chg": 2.04, "vol": 1000, "amount": 10000, "_insert_time": "x"},
        {"ts_code": "000001.SZ", "trade_date": "20240102", "open": 11.0, "high": 12.0, "low": 10.5, "close": 11.5, "pre_close": 10.0, "change": 1.5, "pct_chg": 15.0, "vol": 1100, "amount": 12000, "_insert_time": "x"},
    ]
    _write_parquet(path, rows)

    next_open_map = {("000001.SZ", "20240101"): 11.0}

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        work = df.copy()
        work["_event_ts"] = _to_event_ts(work["trade_date"])
        keys = list(zip(work["ts_code"].astype(str), work["trade_date"].astype(str).str[:8]))
        work["_next_open"] = [next_open_map.get(key) for key in keys]
        return work

    ds = ParquetDataset(
        path=str(path),
        event_type=AshareDailyEvent,
        columns=["_event_ts", *AshareDailyEvent.COLUMNS],
        transform=transform,
        chunksize=1,
    )
    events = list(ds)

    assert len(events) == 2
    assert events[0].trade_date == "20240101"
    assert events[0]._next_open == 11.0
    assert events[1]._next_open is None
    assert events[0].timestamp <= events[1].timestamp


def test_event_classes_expose_explicit_columns_annotations():
    assert "ts_code" in AshareDailyEvent.__annotations__
    assert "trade_date" in AshareDailyBasicEvent.__annotations__
    assert "name" in AshareNameChangeEvent.__annotations__


def test_core_parquet_dataset_can_emit_name_change_event(tmp_path: Path):
    path = tmp_path / "name_change.parquet"
    _write_parquet(
        path,
        [
            {"ts_code": "000001.SZ", "name": "A公司", "start_date": "20240101", "end_date": None, "ann_date": "20240101", "change_reason": "rename", "_insert_time": "x"},
            {"ts_code": "000001.SZ", "name": "A股份", "start_date": "20240201", "end_date": None, "ann_date": "20240201", "change_reason": "rename", "_insert_time": "x"},
        ],
    )

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        work = df.copy()
        work["_event_ts"] = _to_event_ts(work["start_date"])
        return work

    ds = ParquetDataset(
        path=str(path),
        event_type=AshareNameChangeEvent,
        columns=["_event_ts", *AshareNameChangeEvent.COLUMNS],
        transform=transform,
        chunksize=1,
    )
    events = list(ds)

    assert len(events) == 2
    assert isinstance(events[0], AshareNameChangeEvent)
    assert events[0].name == "A公司"