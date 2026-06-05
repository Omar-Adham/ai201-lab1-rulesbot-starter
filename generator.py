from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL

_client = Groq(api_key=GROQ_API_KEY)

# Chunks whose cosine distance exceeds this are treated as weak matches and
# dropped before building context. Relevant chunks for this embedding model
# typically score 0.1–0.5; values above ~0.7 are loosely related at best.
# 1.0 is a generous guard — it keeps borderline matches but discards chunks
# that are almost certainly noise, so they can't pull the answer off-track.
MAX_DISTANCE = 1.0

SYSTEM_PROMPT = (
    "You are RulesBot, an assistant that answers board game rules questions. "
    "Answer using ONLY the rule text provided in the context below. "
    "Do not draw on outside knowledge or anything you know about board games "
    "from training — even if you are confident it is correct. "
    "If the answer is not contained in the provided rule text, say so "
    "explicitly: do not guess, improvise, or fill in gaps.\n\n"
    "Every answer must state which game it comes from, citing the source in "
    "the form [Source: <Game>]. If the context contains rules from more than "
    "one game, answer for each relevant game separately and cite each one. "
    "Keep answers concise and specific to what the rules actually say."
)


def generate_response(query, retrieved_chunks):
    """
    Generate a grounded answer from retrieved rule chunks.

    TODO — Milestone 3:

    `retrieved_chunks` is the list returned by retrieve(). Each item is a dict:
      - "text"     : the chunk text
      - "game"     : the game name
      - "distance" : similarity score (you can use this to filter weak matches)

    Before writing code, talk through these with your group:
      - How will you format the chunks into a context block for the prompt?
      - What instructions will stop the model from answering beyond what the
        rules say? (Grounding is the whole point — a confident wrong answer
        is worse than an honest "I don't know.")
      - How will you surface which game each answer comes from?

    Your response should:
      1. Answer using only the retrieved context — not the model's general knowledge
      2. Make clear which game the answer comes from
      3. Say so clearly when the answer isn't in the loaded rules

    Return the response as a plain string.
    """
    if not retrieved_chunks:
        return (
            "I couldn't find anything relevant in the loaded rule books. "
            "Try rephrasing your question — or check that your ingestion pipeline is working."
        )

    # Drop weak matches so noisy chunks can't pull the model off-track.
    relevant = [c for c in retrieved_chunks if c["distance"] <= MAX_DISTANCE]
    if not relevant:
        return (
            "I couldn't find anything in the loaded rule books that answers "
            "that question. It may not be covered in the rules I have, or you "
            "might try rephrasing it."
        )

    # Format each chunk as a clearly delimited, game-labeled source block.
    # Numbering + explicit game labels help the model distinguish between
    # multiple sources and cite the right one.
    context_blocks = []
    for i, chunk in enumerate(relevant, start=1):
        context_blocks.append(
            f"[Source {i} — {chunk['game']}]\n{chunk['text']}"
        )
    context = "\n\n".join(context_blocks)

    user_message = (
        f"Context (retrieved rule text):\n\n{context}\n\n"
        f"---\n\n"
        f"Question: {query}\n\n"
        f"Answer the question using only the context above, and cite the game "
        f"you drew the answer from."
    )

    response = _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content
