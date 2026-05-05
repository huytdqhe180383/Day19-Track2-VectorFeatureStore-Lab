"""Hybrid memory agent for cooking-recipe retrieval.

POC only: builds context string from episodic memories (Qdrant + BM25/RRF)
and user-state features (Feast online store).
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure Feast metrics files are written in workspace (Windows-safe).
_PROM_DIR = Path(__file__).resolve().parent / ".prom_metrics"
_PROM_DIR.mkdir(exist_ok=True)
os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", str(_PROM_DIR))

from fastembed import TextEmbedding
from feast import FeatureStore
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from rank_bm25 import BM25Okapi

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384


class HybridMemoryAgent:
    def __init__(self, collection: str = "bonus_recipe_memory", top_k: int = 3, rrf_k: int = 60) -> None:
        self.collection = collection
        self.top_k = top_k
        self.rrf_k = rrf_k
        self.embedder = TextEmbedding(model_name=EMBED_MODEL)
        self.client = self._init_qdrant()
        self._ensure_collection()
        self.feature_store = FeatureStore(repo_path=str(Path(__file__).resolve().parent.parent / "app" / "feast_repo"))

    def _init_qdrant(self) -> QdrantClient:
        mode = os.getenv("QDRANT_MODE", "server")
        if mode == "server":
            try:
                return QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
            except Exception:
                return QdrantClient(":memory:")
        return QdrantClient(":memory:")

    def _ensure_collection(self) -> None:
        existing = {c.name for c in self.client.get_collections().collections}
        if self.collection not in existing:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
            )

    @staticmethod
    def _chunk(text: str, max_chars: int = 220) -> list[str]:
        pieces = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
        chunks: list[str] = []
        for piece in pieces:
            if len(piece) <= max_chars:
                chunks.append(piece)
                continue
            words = piece.split()
            cur: list[str] = []
            for w in words:
                nxt = (" ".join(cur + [w])).strip()
                if len(nxt) > max_chars and cur:
                    chunks.append(" ".join(cur))
                    cur = [w]
                else:
                    cur.append(w)
            if cur:
                chunks.append(" ".join(cur))
        return chunks or [text.strip()]

    def remember(self, text: str, user_id: str = "u_001") -> None:
        chunks = self._chunk(text)
        vectors = list(self.embedder.embed(chunks))
        now = datetime.now(timezone.utc).isoformat()
        points = [
            PointStruct(
                id=uuid.uuid4().hex,
                vector=v.tolist(),
                payload={"user_id": user_id, "text": c, "added_at": now},
            )
            for c, v in zip(chunks, vectors)
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def _all_user_points(self, user_id: str) -> list:
        points, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]),
            limit=1000,
            with_payload=True,
            with_vectors=False,
        )
        return points

    @staticmethod
    def _tok(text: str) -> list[str]:
        return text.lower().split()

    def _keyword_hits(self, query: str, user_id: str, limit: int) -> list[tuple[str, str]]:
        pts = self._all_user_points(user_id)
        if not pts:
            return []
        texts = [str(p.payload.get("text", "")) for p in pts]
        bm25 = BM25Okapi([self._tok(t) for t in texts])
        scores = bm25.get_scores(self._tok(query))
        ranked = sorted(range(len(scores)), key=lambda i: -scores[i])[:limit]
        return [(str(pts[i].id), texts[i]) for i in ranked]

    def _semantic_hits(self, query: str, user_id: str, limit: int) -> list[tuple[str, str]]:
        qv = next(self.embedder.embed([query])).tolist()
        res = self.client.query_points(
            collection_name=self.collection,
            query=qv,
            limit=limit,
            query_filter=Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]),
        )
        return [(str(p.id), str(p.payload.get("text", ""))) for p in res.points]

    def _hybrid(self, query: str, user_id: str) -> list[str]:
        depth = max(self.top_k * 4, 20)
        kw = self._keyword_hits(query, user_id, depth)
        sem = self._semantic_hits(query, user_id, depth)
        scores: dict[str, float] = {}
        text_by_id: dict[str, str] = {}
        for hits in (kw, sem):
            for rank, (doc_id, txt) in enumerate(hits, start=1):
                scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (self.rrf_k + rank)
                text_by_id.setdefault(doc_id, txt)
        ordered = sorted(scores.items(), key=lambda kv: -kv[1])[: self.top_k]
        return [text_by_id[doc_id] for doc_id, _ in ordered]

    def _profile(self, user_id: str) -> dict[str, str]:
        feats = [
            "user_profile_features:reading_speed_wpm",
            "user_profile_features:preferred_language",
            "user_profile_features:topic_affinity",
            "query_velocity_features:queries_last_hour",
            "query_velocity_features:distinct_topics_24h",
        ]
        data = self.feature_store.get_online_features(features=feats, entity_rows=[{"user_id": user_id}]).to_dict()

        def get0(k: str, d: str | int) -> str:
            vals = data.get(k)
            if not vals:
                return str(d)
            return str(vals[0])

        return {
            "reading_speed_wpm": get0("reading_speed_wpm", "n/a"),
            "preferred_language": get0("preferred_language", "vi"),
            "topic_affinity": get0("topic_affinity", "cooking"),
            "queries_last_hour": get0("queries_last_hour", 0),
            "distinct_topics_24h": get0("distinct_topics_24h", 0),
        }

    def recall(self, query: str, user_id: str = "u_001") -> str:
        top_memories = self._hybrid(query, user_id)
        profile = self._profile(user_id)
        memories_text = "(no episodic memory found)" if not top_memories else "\n".join(f"- {m}" for m in top_memories)
        return (
            f"User: {user_id}\n"
            f"Profile: language={profile['preferred_language']}, "
            f"reading_speed_wpm={profile['reading_speed_wpm']}, "
            f"topic_affinity={profile['topic_affinity']}\n"
            f"Recent activity: queries_last_hour={profile['queries_last_hour']}, "
            f"distinct_topics_24h={profile['distinct_topics_24h']}\n"
            f"Query: {query}\n"
            f"Top memories:\n{memories_text}"
        )
