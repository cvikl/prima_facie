"""ChromaDB vector store for similar ticket search."""

import chromadb
from chromadb.utils import embedding_functions

# Persistent storage so embeddings survive restarts
client = chromadb.PersistentClient(path="./chroma_data")

# Multilingual model — supports Slovenian, runs locally, no API calls
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="paraphrase-multilingual-MiniLM-L12-v2"
)

collection = client.get_or_create_collection(
    name="tickets",
    embedding_function=embedding_fn,
    metadata={"hnsw:space": "cosine"},
)


def _build_text(ticket_data: dict) -> str:
    """Combine ticket fields into a single text for embedding."""
    parts = []
    if ticket_data.get("field"):
        parts.append(f"Področje: {ticket_data['field']}")
    if ticket_data.get("summary"):
        parts.append(f"Povzetek: {ticket_data['summary']}")
    if ticket_data.get("key_facts"):
        facts = "; ".join(ticket_data["key_facts"])
        parts.append(f"Dejstva: {facts}")
    return "\n".join(parts)


def add_ticket(ticket_id: int, ticket_data: dict):
    """Embed and store a ticket after processing."""
    text = _build_text(ticket_data)
    if not text.strip():
        return

    collection.upsert(
        ids=[str(ticket_id)],
        documents=[text],
        metadatas=[{
            "ticket_id": ticket_id,
            "field": ticket_data.get("field", ""),
            "summary": ticket_data.get("summary", "")[:200],
        }],
    )


def find_similar(ticket_data: dict, n_results: int = 3, exclude_id: int | None = None) -> list[dict]:
    """Find the most similar past tickets. Returns list of {id, summary, similarity}."""
    text = _build_text(ticket_data)
    if not text.strip():
        return []

    # Query more than needed so we can filter out the current ticket
    results = collection.query(
        query_texts=[text],
        n_results=n_results + 1,
    )

    similar = []
    if not results["ids"] or not results["ids"][0]:
        return []

    for i, tid in enumerate(results["ids"][0]):
        ticket_id = int(tid)
        if ticket_id == exclude_id:
            continue

        distance = results["distances"][0][i] if results["distances"] else 0
        similarity = round(1 - distance, 3)  # cosine distance → similarity
        meta = results["metadatas"][0][i] if results["metadatas"] else {}

        similar.append({
            "id": ticket_id,
            "summary": meta.get("summary", ""),
            "field": meta.get("field", ""),
            "similarity": similarity,
        })

        if len(similar) >= n_results:
            break

    return similar
