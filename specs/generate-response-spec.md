# Spec: `generate_response()`

**File:** `generator.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Given a user query and a list of retrieved rule chunks, generate a response that directly answers the question using only the retrieved text as context. The response must be grounded — it should not draw on the model's general knowledge of board games, only on what was retrieved.

---

## Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | `str` | The user's original question |
| `retrieved_chunks` | `list[dict]` | Ranked list of chunks from `retrieve()`, each with `"text"`, `"game"`, and `"distance"` |

**Output:** `str`

A plain string containing the response to show the user. The response should:
- Answer the question using only the retrieved rule text
- Identify which game the answer comes from
- Acknowledge clearly when the answer is not found in the loaded rules

Returns a fallback string (not an error) when `retrieved_chunks` is empty.

---

## Design Decisions

*Complete the fields below before writing any code. Use your AI tool in Plan or Ask mode to help you reason through what belongs here — but the decisions are yours.*

---

### Context formatting

*How will you format the retrieved chunks before passing them to the LLM? Describe the structure — not the code. Consider: will you label chunks by game? Include distance scores? Separate chunks with delimiters?*

```
Each chunk becomes its own numbered, game-labeled block:

  [Source 1 — Pandemic]
  <chunk text>

  [Source 2 — Monopoly]
  <chunk text>

Blocks are separated by blank lines, and the whole context is delimited from
the question with a "---" line. Decisions:
  - Label each block with the game so the model can cite the right source and
    keep multi-game results straight (research on multi-document prompting
    shows explicit source labels reduce cross-source confusion).
  - Number the sources to give the model a clean handle for citation.
  - Do NOT include distance scores — they are an internal relevance signal,
    not something the model should reason about or surface to the user.
```

---

### System prompt — grounding instruction

*Write the exact system prompt instruction you will use to prevent the model from answering beyond the retrieved text. This is the most important design decision in this function.*

```
"Answer using ONLY the rule text provided in the context below. Do not draw on
outside knowledge or anything you know about board games from training — even
if you are confident it is correct. If the answer is not contained in the
provided rule text, say so explicitly: do not guess, improvise, or fill in
gaps."

Note: this is phrased as a prohibited behavior ("do not draw on outside
knowledge") rather than a desired outcome ("be accurate"), because behavior-
prohibiting instructions give the model less room to sidestep grounding.
Pressure-testing it with the AI tool surfaced the "even if you are confident
it is correct" clause and the explicit "do not fill in gaps", which were added
to close the loophole where a model rationalizes adding training knowledge.
```

---

### System prompt — citation instruction

*Write the exact instruction you will use to tell the model to identify which game its answer comes from.*

```
"Every answer must state which game it comes from, citing the source in the
form [Source: <Game>]. If the context contains rules from more than one game,
answer for each relevant game separately and cite each one."

This gives a fixed citation format the user can verify against the rulebook,
and explicitly handles the multi-game case (e.g. "how do you win?") so the
model splits its answer per game rather than blurring them together.
```

---

### Fallback behavior

*What should the response say when the answer isn't found in the loaded rule books? Write the exact fallback message.*

```
Two layers:

1. retrieved_chunks is empty (retrieval returned nothing / empty collection):
   "I couldn't find anything relevant in the loaded rule books. Try rephrasing
    your question — or check that your ingestion pipeline is working."

2. chunks came back but all are weak matches (every distance > 1.0):
   "I couldn't find anything in the loaded rule books that answers that
    question. It may not be covered in the rules I have, or you might try
    rephrasing it."

Beyond these code-level fallbacks, the grounding instruction tells the model to
say the answer isn't in the rules when borderline chunks don't actually contain
it — so there are three points where an honest "I don't know" can surface.
```

---

### Handling low-relevance chunks

*`retrieved_chunks` may include chunks with high distance scores (weak relevance). Will you filter these out before building context, pass them all in, or handle them another way? What are the tradeoffs?*

```
Filter with a generous guard: drop any chunk whose distance > 1.0 (MAX_DISTANCE)
before building context. If everything is filtered out, return the weak-match
fallback above.

Tradeoffs:
  - A cutoff stops obvious noise (a Catan question dragging in an unrelated Risk
    chunk) from diluting the context and tempting the model off-topic.
  - The threshold is deliberately loose (1.0, where relevant chunks score
    0.1–0.5 and observed top matches sat ~0.37–0.47). A tight cutoff would risk
    discarding the only chunk that actually holds the answer.
  - The grounding instruction is the real backstop: even if a borderline chunk
    slips through, the model is told to answer only from it or say it can't.
```

---

### Message structure

*Describe how you will structure the messages list for the API call — what goes in the system message vs. the user message?*

```
Two messages:
  - system : the persistent role + grounding + citation rules (SYSTEM_PROMPT).
    These are behavior constraints that apply to every query, so they belong in
    the system role where the model weights them most heavily.
  - user   : the per-query payload — the formatted, labeled context blocks,
    a "---" delimiter, then the actual question, plus a short reminder to
    answer only from the context and cite the game.

temperature is set low (0.2) to keep answers deterministic and close to the
source text rather than creative. Return response.choices[0].message.content
as a plain string.
```

---

## Implementation Notes

*Fill this in after implementing and testing.*

**Test query and response:**

```
Query: How do you get out of Jail in Monopoly?
Response: (pending) — code is implemented and the module imports cleanly, but
  end-to-end generation needs a real GROQ_API_KEY in .env (currently still set
  to the placeholder "your_key_here"). Retrieval for this query already returns
  the correct Monopoly chunks (top dist 0.367, including the "...pay the $50
  fine / rolled doubles" rule), so once the key is added the grounded answer
  should cite [Source: Monopoly] and describe pay $50 / roll doubles / Get Out
  of Jail Free card.
Correctly grounded? [verify after adding key]
Cited the right game? [verify after adding key]
```

**One thing you changed from your original spec after seeing the actual output:**

```
Added the "even if you are confident it is correct" clause to the grounding
instruction after pressure-testing the draft — without it, a strong model can
rationalize supplementing thin retrieved text with training knowledge it
"knows" is right, which is exactly the grounding failure this function exists
to prevent.
```
