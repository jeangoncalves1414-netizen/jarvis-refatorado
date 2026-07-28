"""Semantic memory using ChromaDB for long-term fact storage."""

from __future__ import annotations

import logging
import traceback
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Returns friendly error if package not installed
try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    chromadb = None


class SemanticMemory:
    """Manages long-term semantic memory using ChromaDB."""
    _instance: SemanticMemory | None = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, persist_dir: str = "data/chroma_db"):
        if self._initialized:
            return
            
        self.enabled = chromadb is not None
        self._collections: dict[str, Any] = {}
        
        if not self.enabled:
            print("[VectorDB] ChromaDB not installed. Semantic memory disabled.")
            self._initialized = True
            return

        path = Path(persist_dir)
        path.mkdir(parents=True, exist_ok=True)
        
        try:
            self.client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
            self.collection = self._get_or_create_collection("user_memories")
            total = self.collection.count()
            print(f"[VectorDB] Initialized successfully. Total memories: {total}")
        except Exception as e:
            logger.error(f"[VectorDB] Critical error initializing ChromaDB: {e}")
            logger.debug(traceback.format_exc())
            self.enabled = False
            
        self._initialized = True

    def _get_or_create_collection(self, name: str):
        """Get or create a ChromaDB collection by name (with cache)."""
        if name in self._collections:
            return self._collections[name]
        try:
            coll = self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"}
            )
            self._collections[name] = coll
            return coll
        except Exception as e:
            logger.error(f"[VectorDB] Error creating/getting collection '{name}': {e}")
            logger.debug(traceback.format_exc())
            return self.collection

    def use_collection(self, collection_name: str):
        """Change active collection to a specific agent's collection."""
        if not self.enabled:
            return
        self.collection = self._get_or_create_collection(collection_name)

    def save_memory(self, text: str, embedding: list[float], metadata: dict[str, Any] | None = None, collection_name: str | None = None) -> bool:
        """Save a new memory to vector database."""
        if not self.enabled:
            return False
            
        target = self._get_or_create_collection(collection_name) if collection_name else self.collection
        memory_id = uuid.uuid4().hex
        
        try:
            target.add(
                ids=[memory_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata or {}]
            )
            return True
        except Exception as e:
            logger.error(f"[VectorDB] Error saving memory: {e}")
            logger.debug(traceback.format_exc())
            return False

    def search_memories(self, query_embedding: list[float], top_k: int = 3, threshold: float = 1.3, collection_name: str | None = None, filter_metadata: dict[str, Any] | None = None) -> list[str]:
        """Search relevant memories using query embedding."""
        target = self._get_or_create_collection(collection_name) if collection_name else self.collection
        
        if not self.enabled or target.count() == 0:
            return []
            
        try:
            query_kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": min(top_k, target.count()),
                "include": ["documents", "distances"]
            }
            if filter_metadata:
                query_kwargs["where"] = filter_metadata

            results = target.query(**query_kwargs)
            
            memories = []
            if results["documents"] and results["distances"]:
                docs = results["documents"][0]
                distances = results["distances"][0]
                
                for doc, dist in zip(docs, distances):
                    if dist <= threshold:
                        memories.append(doc)
                        
            return memories
        except Exception as e:
            logger.error(f"[VectorDB] Error searching memories: {e}")
            logger.debug(traceback.format_exc())
            return []

    def get_collection_count(self, collection_name: str | None = None) -> int:
        """Return number of memories in a collection."""
        if not self.enabled:
            return 0
        target = self._get_or_create_collection(collection_name) if collection_name else self.collection
        try:
            return target.count()
        except Exception:
            return 0
