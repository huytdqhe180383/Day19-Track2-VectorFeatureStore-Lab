# Hybrid Memory POC for Cooking Recipes (VN-first)

Contributors: solo

## 1) Architecture Diagram

```mermaid
flowchart LR
    U[User Query] --> O[Orchestrator: HybridMemoryAgent.recall]
    O --> V1[Vector Retriever
    Qdrant + FastEmbed
    user_id filter]
    O --> K1[Keyword Retriever
    BM25 over user memory chunks]
    O --> RRF[RRF Fusion k=60]

    subgraph Episodic Memory Path
      IN[remember(text)] --> CH[Chunker]
      CH --> EM[Embed chunks]
      EM --> QD[(Qdrant collection:
      bonus_recipe_memory)]
    end

    subgraph Feature Store Path
      EV[Profile/activity events] --> FP[(Parquet offline)]
      FP --> FA[feast apply]
      FA --> FM[materialize-incremental]
      FM --> FO[(Feast online store)]
    end

    QD --> V1
    O --> FO
    RRF --> C[Context Assembler
    profile + activity + top memories]
    FO --> C
    C --> A[Final answer context
    for downstream LLM]
```

The POC is intentionally small: no real LLM call, only context assembly. The design goal is to prove that retrieval quality improves when episodic memory and user-state features are joined at recall time.

## 2) Decision 1 - Chunking Strategy

Chosen approach: sentence-first chunking with soft size cap (~220 chars), then fallback split by words for long sentences.

Tradeoff:
- Retrieval quality: sentence chunks preserve recipe steps (for example, "xao hanh tim" + "do nuoc dung") better than per-conversation blobs, so semantic recall is less noisy.
- Storage cost: finer chunks increase vector count. A recipe paragraph of 600 chars may become 3-4 vectors instead of 1.
- Context window: smaller chunks reduce wasted tokens in final prompt, but may lose cross-step dependencies if split too aggressively.

Why this fits cooking retrieval: recipe notes often contain compact instruction units (ingredients, prep, cook). Sentence-level chunks map naturally to those units. A pure per-message chunk was considered but rejected because multi-recipe notes become too broad and hurt top-k precision.

## 3) Decision 2 - Feature Schema

Chosen pattern: tabular online features in Feast, embeddings only in vector store.

Entity and feature set:
- `user_id` -> `reading_speed_wpm`, `preferred_language`, `topic_affinity`
- `user_id` -> `queries_last_hour`, `distinct_topics_24h`
- (existing lab view also has `doc_id` popularity features; not required for this POC recall path)

TTL policy:
- Profile view: 30 days (slow-changing)
- Query velocity view: 1 hour (fresh behavioral signal)

Tradeoff:
- Tabular features are fast, interpretable, and easy to reason about for routing/prompt style.
- Embedding-as-feature-view was considered for latent preferences, but rejected in this POC because lifecycle differs: profile updates in coarse cadence while episodic memory requires frequent upserts/re-index-like behavior.

This split keeps responsibilities clean: Feast = durable, query-time numeric/categorical signals; Qdrant = searchable personal memory.

## 4) Decision 3 - Freshness Strategy

Chosen multi-cadence freshness:
- Sub-second to near-real-time for `remember(...)` writes to Qdrant.
- Minute-level for query-activity features via periodic materialization.
- Daily (or slower) for stable profile features.

Three use cases:
1. "What did I save about pho broth just now?" -> requires near-real-time episodic write visibility.
2. "What am I focusing on lately?" -> recent activity is enough with minute-level refresh; sub-second is unnecessary.
3. "How should you explain this to me?" (language, reading speed) -> profile can be daily without harming UX.

Tradeoff: uniform sub-second freshness for all features would increase pipeline complexity and cost (stream infra for attributes that barely change). Uniform daily batch would be too stale for active-session memory recall. Mixed freshness is the pragmatic middle.

## 5) Explicit Rejection of an Alternative

Rejected option: storing episodic memory in Feast as embedding-like feature columns.

Reason: Feast is excellent for point lookups and historical joins, but not optimized for ANN retrieval and hybrid lexical-semantic ranking. Episodic memory retrieval needs top-k nearest-neighbor semantics plus filtered vector search. Qdrant handles that naturally, while Feast remains ideal for profile/activity snapshots.

## 6) Vietnamese Context Considerations

1. Code-switching (vi/en mix): cooking users often mix terms like "meal prep", "air fryer", "umami", "nuoc mam". Embedding model choice must tolerate mixed-language tokens.
2. Phonetic/telex typos: queries like "nuoc dung pho" vs "nuoc duwng" can degrade BM25. Hybrid recall mitigates this by letting semantic retriever recover when lexical match fails.
3. Tokenizer compromise: this POC uses whitespace tokenization for simplicity (aligned with lab baseline), but production should evaluate Vietnamese-aware tokenizers (`pyvi`, `underthesea`) because syllable boundaries and compounds affect keyword ranking quality.

## 7) Link to Lab Concepts

- RRF hybrid retrieval: same concept as NB2, now applied to personal cooking memory.
- TTL in feature views: profile vs velocity lifecycles follow NB4 patterns.
- Streaming mindset: query velocity is modeled as fast-changing behavior.
- PIT relevance: if this assistant were used for training personalization models, historical features should be joined with PIT discipline to avoid leakage.

## 8) What This POC Does Not Handle Yet

- No encryption-at-rest or key management for private memories.
- No authenticated multi-user isolation beyond payload filter (`user_id`).
- No memory edit/delete API (only append).
- No long-term consolidation (duplicate memories are not merged).
- No production-grade observability/SLO dashboards.

Despite these limits, the POC demonstrates the key architecture judgment: split episodic memory search and stable behavior features, then assemble both into one retrieval context before the generation step.
