# Spec: `retrieve()`

**File:** `retriever.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Given a user's natural language query, find the most relevant chunks from the vector store using semantic similarity search. Return them ranked by relevance so that `generate_response()` can use them as context.

---

## Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | The user's natural language question |
| `n_results` | `int` | Maximum number of chunks to return (default: `N_RESULTS` from `config.py`) |

**Output:** `list[dict]`

Each dict in the returned list must contain exactly these keys:

| Key | Type | Description |
|-----|------|-------------|
| `"text"` | `str` | The chunk text |
| `"game"` | `str` | The game name this chunk came from |
| `"distance"` | `float` | Cosine distance score — lower means more similar to the query |

Results should be ordered from most to least relevant (lowest to highest distance). Returns an empty list `[]` if the collection contains no documents.

---

## Design Decisions

*Complete the fields below before writing any code. Use your AI tool in Plan or Ask mode to help you reason through what belongs here — but the decisions are yours.*

---

### Query approach

*Describe how you will use `_collection.query()` to find relevant chunks. What arguments will you pass, and why?*

```
Call _collection.query() with three arguments:
  - query_texts=[query]  : a list holding the single user question. ChromaDB
    embeds it with the same all-MiniLM-L6-v2 model used at ingestion, so the
    query and the stored chunks live in the same vector space.
  - n_results=n_results  : how many of the closest chunks to return (default 3
    from config.N_RESULTS).
  - include=["documents", "metadatas", "distances"] : we need all three — the
    chunk text to feed the LLM, the metadata to know which game it came from,
    and the distance to judge relevance.
ChromaDB returns the chunks sorted nearest-first (lowest cosine distance).
```

---

### Return structure

*Sketch out what one item in your return list looks like as a concrete example. Where does each field come from in the query results?*

```
A list of dicts, one per retrieved chunk, e.g.:

  {
    "text": "When a 7 is rolled, no one collects resources. The player ...",
    "game": "Catan",
    "distance": 0.142,
  }

Field sources (after indexing into [0] for the single query):
  - "text"     <- results["documents"][0][i]
  - "game"     <- results["metadatas"][0][i]["game"]
  - "distance" <- results["distances"][0][i]

Built by zipping the three parallel lists together so each dict lines up with
one chunk. Order is preserved, so the list stays sorted lowest-distance first.
```

---

### Handling the nested result structure

*`_collection.query()` returns nested lists. Describe what index you need to access to get the actual list of results for a single query, and why the nesting exists.*

```
query() supports batching — you can pass many query strings at once, so it
returns one inner list of results per query. The shape is:

  results["documents"]  -> [ [doc, doc, doc] ]   # outer list = one per query
  results["metadatas"]  -> [ [meta, meta, meta] ]
  results["distances"]  -> [ [dist, dist, dist] ]

We pass exactly one query, so our results are at index [0] of each key:
  results["documents"][0], results["metadatas"][0], results["distances"][0].

Forgetting the [0] is the classic bug — you'd iterate over a length-1 outer
list instead of the actual chunks.
```

---

### Relevance threshold

*Will you filter out results above a certain distance score, or return all `n_results` regardless of how relevant they are? What are the tradeoffs of each approach?*

```
retrieve() returns all n_results without filtering. Relevance filtering is
deferred to the generation step (generator.py drops chunks with distance >
1.0 before building context).

Reasoning / tradeoffs:
  - Keeping retrieve() unopinionated makes it reusable and easy to debug — you
    can always see the raw ranked results and their distances.
  - A hard threshold inside retrieve() risks returning an empty list for a
    valid question whose best chunk happens to sit just above the cutoff, which
    is worse than handing a borderline chunk to a strongly-grounded LLM that
    can itself say "not in the rules."
  - The cost of not filtering here: occasionally a weak chunk is passed along,
    but grounding + the generator's distance guard handle that downstream.
```

---

### Edge cases

*How does your implementation behave when: (a) the collection is empty, (b) the query matches no chunks well, (c) the query matches chunks from multiple games?*

```
(a) Empty collection: guarded at the top — if _collection.count() == 0 we
    return [] immediately, so query() is never called against an empty index.
(b) No good match: query() still returns the n closest chunks, just with high
    distances. retrieve() returns them as-is; the generator filters weak ones
    and/or the grounded LLM reports the answer isn't in the rules.
(c) Multiple games: entirely fine and expected for broad questions like
    "how do you win?". Chunks from different games come back interleaved by
    distance, each tagged with its own "game" field, and generation cites each.
```

---

## Implementation Notes

*Fill this in after implementing, before moving to Milestone 3.*

**Test query and top result returned:**

```
Query: What happens when you run out of disease cubes in Pandemic?
Top result game: Pandemic
Distance score: 0.373
Does it make sense? Yes — all three top results were Pandemic chunks, and the
top one is the loss-condition rule ("...any color of disease cubes runs out").
The Monopoly query likewise returned only Monopoly chunks (top dist 0.367), so
the game-routing via semantic search is working without any keyword matching.
```

**One thing about the query results that surprised you:**

```
Distances were higher than the lab's example numbers (~0.37–0.47 vs. the 0.14
in the walkthrough). The cause is the character-based chunker: many chunks
start mid-sentence (e.g. "iately if: the outbreak marker reaches 8..."), which
adds noise to the embedding and pushes distances up. Retrieval still ranks the
right game first, but it's a concrete illustration of how chunk boundaries
affect embedding quality — a sentence-aware splitter would tighten these scores.
```
