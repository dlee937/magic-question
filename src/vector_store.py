"""
ChromaDB wrapper with Ollama embeddings.
Handles indexing and filtered retrieval.
"""

import json
import httpx
import chromadb
from pathlib import Path
from .config import (
    CHROMA_DIR, OLLAMA_BASE, EMBEDDING_MODEL,
    MAX_CHUNKS_RETRIEVED, SIMILARITY_THRESHOLD,
)


class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.collection = self.client.get_or_create_collection(
            name="magic_garden",
            metadata={"hnsw:space": "cosine"},
        )
        self._http = httpx.Client(timeout=30.0)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings from Ollama's nomic-embed-text."""
        embeddings = []
        for text in texts:
            resp = self._http.post(
                f"{OLLAMA_BASE}/api/embed",
                json={"model": EMBEDDING_MODEL, "input": text},
            )
            resp.raise_for_status()
            embeddings.append(resp.json()["embeddings"][0])
        return embeddings

    def index_chunks(self, chunks_dir: Path):
        """Load all chunk JSON files into ChromaDB."""
        chunk_files = sorted(chunks_dir.rglob("*.json"))
        if not chunk_files:
            print("No chunk files found!")
            return

        print(f"Indexing {len(chunk_files)} chunks...")
        ids, documents, metadatas = [], [], []

        for f in chunk_files:
            data = json.loads(f.read_text())
            ids.append(data["chunk_id"])
            documents.append(data["text"])
            # ChromaDB only accepts str/int/float/bool metadata values
            meta = {}
            for k, v in data.get("metadata", {}).items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v
            metadatas.append(meta)

        # Embed in batches of 50
        all_embeddings = []
        batch_size = 50
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            batch_embeds = self._embed(batch)
            all_embeddings.extend(batch_embeds)
            done = min(i + batch_size, len(documents))
            print(f"  Embedded {done}/{len(documents)}")

        # Upsert
        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=all_embeddings,
        )
        print(f"Done — {len(ids)} chunks indexed.")

    def retrieve(self, query: str, metadata_filters: dict | None = None,
                 n_results: int = MAX_CHUNKS_RETRIEVED) -> list[dict]:
        """Retrieve relevant chunks for a query."""
        collection_count = self.collection.count()
        if collection_count == 0:
            return []

        query_embedding = self._embed([query])[0]
        n_results = min(n_results, collection_count)

        kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }

        # Pass through pre-built ChromaDB where clause (supports $or/$and)
        if metadata_filters:
            top_keys = set(metadata_filters.keys())
            if top_keys & {"$or", "$and", "$eq", "$ne", "$gt", "$lt", "$gte", "$lte", "$in", "$nin"}:
                # Already a ChromaDB clause — pass through
                kwargs["where"] = metadata_filters
            else:
                # Flat dict — wrap each key in $eq
                conditions = [{k: {"$eq": v}} for k, v in metadata_filters.items()]
                if len(conditions) == 1:
                    kwargs["where"] = conditions[0]
                elif len(conditions) > 1:
                    kwargs["where"] = {"$and": conditions}

        try:
            results = self.collection.query(**kwargs)
        except (chromadb.errors.InvalidArgumentError, chromadb.errors.NotFoundError, ValueError):
            # Filter too restrictive — fall back to unfiltered
            kwargs.pop("where", None)
            results = self.collection.query(**kwargs)

        # Unpack and filter by similarity
        chunks = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                distance = results["distances"][0][i]
                similarity = 1 - distance
                if similarity >= SIMILARITY_THRESHOLD:
                    chunks.append({
                        "text": doc,
                        "metadata": results["metadatas"][0][i],
                        "similarity": round(similarity, 3),
                    })
        return chunks

    def count(self) -> int:
        """Return number of indexed chunks."""
        return self.collection.count()
