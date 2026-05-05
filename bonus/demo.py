"""Demo for bonus HybridMemoryAgent using cooking-recipe memories."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parent.parent
FEAST_DIR = ROOT / "app" / "feast_repo"
FEAST_DATA = FEAST_DIR / "data"
PROM_DIR = ROOT / "bonus" / ".prom_metrics"
PROM_DIR.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", str(PROM_DIR))
os.environ.setdefault("QDRANT_MODE", "server")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")


def _prepare_feature_data() -> None:
    FEAST_DATA.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    pl.DataFrame(
        {
            "user_id": ["u_001", "u_002", "u_003"],
            "reading_speed_wpm": [210, 170, 240],
            "preferred_language": ["vi", "vi", "en"],
            "topic_affinity": ["vietnamese_cooking", "quick_meals", "baking"],
            "event_timestamp": [now, now - timedelta(hours=2), now - timedelta(hours=6)],
        }
    ).write_parquet(FEAST_DATA / "user_profile.parquet")

    pl.DataFrame(
        {
            "doc_id": ["recipe_001", "recipe_002", "recipe_003"],
            "click_count_24h": [120, 95, 80],
            "ctr_7d": [0.42, 0.35, 0.31],
            "avg_dwell_seconds": [54.0, 49.5, 45.2],
            "event_timestamp": [now, now - timedelta(minutes=10), now - timedelta(minutes=30)],
        }
    ).write_parquet(FEAST_DATA / "item_popularity.parquet")

    pl.DataFrame(
        {
            "user_id": ["u_001", "u_002", "u_003"],
            "queries_last_hour": [7, 2, 3],
            "distinct_topics_24h": [3, 1, 2],
            "event_timestamp": [now, now - timedelta(minutes=15), now - timedelta(minutes=20)],
        }
    ).write_parquet(FEAST_DATA / "query_velocity.parquet")


def _run(cmd: list[str], cwd: Path) -> None:
    env = os.environ.copy()
    env["PROMETHEUS_MULTIPROC_DIR"] = str(PROM_DIR)
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")


def _feast_bootstrap() -> None:
    feast_bin = Path(sys.executable).with_name("feast.exe")
    if not feast_bin.exists():
        feast_bin = Path(sys.executable).with_name("feast")
    _run([str(feast_bin), "apply"], FEAST_DIR)
    end_dt = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")
    _run([str(feast_bin), "materialize-incremental", end_dt], FEAST_DIR)


def main() -> int:
    _prepare_feature_data()
    _feast_bootstrap()

    from agent import HybridMemoryAgent

    agent = HybridMemoryAgent()
    memories = [
        "Pho bo: nuoc dung ngon can nuong hanh gung truoc, ham xuong bo 4-6 gio, nho hot bot de nuoc trong.",
        "Bun bo Hue: sa te tu ot va xa tao mui cay, mam ruoc can loc ky truoc khi cho vao noi nuoc.",
        "Com ga hoi an: uop ga voi toi gung nghe, nuoc luoc ga dung nau com de com vang va thom.",
        "Meal prep 3 ngay: ca hoi ap chao, rau luoc, gao lut; uu tien it dau mo va de can bang dinh duong.",
        "Canh chua ca: me + dua + ca chua tao vi chua thanh; them rau om ngo gai cuoi de giu mui.",
        "Kho quet an voi rau cu luoc: ty le nuoc mam duong 2:1, them tieu va hanh phi de day vi.",
    ]
    for m in memories:
        agent.remember(m, user_id="u_001")

    queries = [
        "Toi da luu cong thuc gi ve pho bo?",
        "Goi y mon nen nau tiep theo cho toi",
        "Gan day toi dang quan tam mon nao?",
        "Co ghi chu nao ve nuoc dung ham xuong thom va trong?",
        "Tom tat nhanh thuc don meal-prep lanh manh cho toi",
    ]

    for i, q in enumerate(queries, start=1):
        print(f"\n=== Query {i} ===")
        print(agent.recall(q, user_id="u_001"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
