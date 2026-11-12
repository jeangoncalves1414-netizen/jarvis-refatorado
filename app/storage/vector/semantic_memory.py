from __future__ import annotations

import logging
from functools import lru_cache
import time
from pathlib import Path
from typing import Any, List

logger = logging.getLogger(__name__)

_TECHNICAL_ERROR_MARKERS = (
    "sem resposta gerada pelo modelo",
    "erro ao acessar a api",
    "erro de autenticação",
    "limite de taxa",
    "api key",
    "gemini_api_key",
    "groq_api_key",
    "timeout na conexão",
    "erro de conexão com a api",
    "orquestrador não disponível",
    "não consegui falar com o núcleo",
)


# Distância cosseno máxima aceita na busca de ``user_memory`` (medida com all-MiniLM-L6-v2).
USER_MEMORY_MAX_DISTANCE = 0.45
# Coleções que guardam fatos duradouros e por isso não expiram por idade.
_NO_EXPIRY_COLLECTIONS = frozenset({"user_memory"})


@lru_cache(maxsize=1)
def embedding_function() -> Any:
    """Modelo multilíngue local; nunca baixa pesos durante um turno."""
    from app.storage.vector.multilingual_embedding import MultilingualEmbedding
    return MultilingualEmbedding()


def is_technical_error_memory(text: str) -> bool:
    """Retorna se um texto descreve uma falha operacional, não uma memória do usuário."""
    normalized = " ".join((text or "").lower().split())
    return normalized in {"sem resposta.", "sem resposta"} or any(marker in normalized for marker in _TECHNICAL_ERROR_MARKERS)

# Tenta importar ChromaDB, mas lida com falha gracefully
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("ChromaDB não disponível. Memória vetorial será desabilitada.")


class SemanticMemory:
    """Memória semântica usando ChromaDB para busca contextual."""
    
    def __init__(self, persist_dir: str = "data/vector_db", max_age_days: int = 90):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = None
        self._collections: dict[str, Any] = {}
        self.max_age_days = max_age_days
        
        if CHROMADB_AVAILABLE:
            try:
                self.client = chromadb.PersistentClient(
                    path=str(self.persist_dir),
                    settings=Settings(anonymized_telemetry=False)
                )
                logger.info(f"ChromaDB inicializado em {self.persist_dir}")
            except Exception as e:
                logger.error(f"Falha ao inicializar ChromaDB: {e}")
                self.client = None
    
    def get_or_create_collection(self, name: str) -> Any:
        """Retorna ou cria uma coleção."""
        if not self.client:
            return None
        
        if name not in self._collections:
            try:
                options: dict[str, Any] = {"name": name, "metadata": {"hnsw:space": "cosine"}}
                embedder = embedding_function()
                if embedder is not None:
                    options["embedding_function"] = embedder
                self._collections[name] = self.client.get_or_create_collection(**options)
            except Exception as e:
                logger.error(f"Falha ao criar coleção {name}: {e}")
                return None
        
        return self._collections[name]
    
    def add_memory(
        self,
        collection_name: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        importance: float = 1.0
    ) -> bool:
        """Adiciona uma memória à coleção com timestamp e importância."""
        if not self.client or is_technical_error_memory(text):
            return False
        
        collection = self.get_or_create_collection(collection_name)
        if not collection:
            return False
        
        enhanced_metadata = metadata or {}
        enhanced_metadata.update({
            "timestamp": time.time(),
            "importance": importance,
            "access_count": 0
        })
        
        try:
            collection.add(
                documents=[text],
                metadatas=[enhanced_metadata],
                ids=[f"{hash(text)}_{len(text)}_{time.time()}"]
            )
            return True
        except Exception as e:
            logger.error(f"Falha ao adicionar memória: {e}")
            return False
    
    def search_memories(
        self,
        collection_name: str,
        query: str,
        n_results: int = 5,
        filter_expired: bool = True,
        max_distance: float | None = None,
    ) -> List[dict[str, Any]]:
        """Busca memórias similares, incrementando access_count.

        ``max_distance`` descarta resultados mais distantes que o limite; ``user_memory``
        nunca expira por idade.
        """
        if not self.client:
            return []
        
        collection = self.get_or_create_collection(collection_name)
        if not collection:
            return []
        
        try:
            results = collection.query(
                query_texts=[query],
                n_results=n_results * 2  # Busca mais para filtrar depois
            )
            
            if not results or not results["documents"]:
                return []
            
            memories = []
            current_time = time.time()
            expires = filter_expired and collection_name not in _NO_EXPIRY_COLLECTIONS
            ids = (results.get("ids") or [[]])[0] or []
            
            for i, doc in enumerate(results["documents"][0]):
                metadata = (results["metadatas"][0][i] if results["metadatas"] else None) or {}
                distance = results["distances"][0][i] if results["distances"] else 0
                
                if max_distance is not None and distance > max_distance:
                    continue
                # Filtra memórias expiradas
                if expires:
                    timestamp = metadata.get("timestamp", current_time)
                    age_days = (current_time - timestamp) / 86400
                    if age_days > self.max_age_days:
                        continue
                
                memories.append({
                    "text": doc,
                    "metadata": metadata,
                    "distance": distance
                })
                
                # Incrementa access_count pelo id que o Chroma devolveu
                if i < len(ids):
                    try:
                        collection.update(
                            ids=[ids[i]],
                            metadatas=[{**metadata, "access_count": metadata.get("access_count", 0) + 1}]
                        )
                    except Exception as exc:
                        logger.debug("Falha ao atualizar access_count de %s: %s", ids[i], exc)
            
            # Ordena por relevância (distância + importância)
            memories.sort(key=lambda m: m["distance"] / (m["metadata"].get("importance", 1.0) + 0.1))
            
            return memories[:n_results]
        except Exception as e:
            logger.error(f"Falha ao buscar memórias: {e}")
            return []
    
    def delete_where(self, collection_name: str, where: dict[str, Any]) -> int:
        """Remove os itens cujo metadata casa com ``where``. Retorna quantos saíram."""
        if not self.client or not where:
            return 0
        collection = self.get_or_create_collection(collection_name)
        if not collection:
            return 0
        try:
            ids = (collection.get(where=where) or {}).get("ids") or []
            if ids:
                collection.delete(ids=ids)
            return len(ids)
        except Exception as e:
            logger.error(f"Falha ao remover memórias de {collection_name}: {e}")
            return 0

    def delete_collection(self, collection_name: str) -> bool:
        """Deleta uma coleção."""
        if not self.client:
            return False
        
        try:
            self.client.delete_collection(collection_name)
            if collection_name in self._collections:
                del self._collections[collection_name]
            return True
        except Exception as e:
            logger.error(f"Falha ao deletar coleção {collection_name}: {e}")
            return False
    
    def list_collections(self) -> List[str]:
        """Lista todas as coleções."""
        if not self.client:
            return []
        
        try:
            return [col.name for col in self.client.list_collections()]
        except Exception as e:
            logger.error(f"Falha ao listar coleções: {e}")
            return []
    
    def is_available(self) -> bool:
        """Verifica se ChromaDB está disponível."""
        return self.client is not None
    
    def cleanup_expired_memories(self, collection_name: str) -> int:
        """Remove memórias expiradas da coleção. Retorna quantidade removida."""
        if not self.client:
            return 0

    def cleanup_technical_error_memories(self, collection_names: list[str] | None = None) -> int:
        """Remove erros operacionais que tenham sido gravados por versões antigas."""
        if not self.client:
            return 0

        removed = 0
        for collection_name in collection_names or ["user_memory", "conversations", "episodic_memory"]:
            collection = self.get_or_create_collection(collection_name)
            if not collection:
                continue
            try:
                results = collection.get()
                documents = results.get("documents") or []
                ids = results.get("ids") or []
                stale_ids = [ids[index] for index, document in enumerate(documents) if is_technical_error_memory(document)]
                if stale_ids:
                    collection.delete(ids=stale_ids)
                    removed += len(stale_ids)
            except Exception as exc:
                logger.error("Falha ao limpar erros técnicos de %s: %s", collection_name, exc)
        return removed
        
        collection = self.get_or_create_collection(collection_name)
        if not collection:
            return 0
        
        try:
            results = collection.get()
            if not results or not results["ids"]:
                return 0
            
            current_time = time.time()
            expired_ids = []
            
            for i, metadata in enumerate(results["metadatas"] or []):
                timestamp = metadata.get("timestamp", current_time)
                age_days = (current_time - timestamp) / 86400
                if age_days > self.max_age_days:
                    expired_ids.append(results["ids"][i])
            
            if expired_ids:
                collection.delete(ids=expired_ids)
                logger.info(f"Removidas {len(expired_ids)} memórias expiradas de {collection_name}")
            
            return len(expired_ids)
        except Exception as e:
            logger.error(f"Falha ao limpar memórias expiradas: {e}")
            return 0
    
    def cleanup_duplicate_memories(self, collection_name: str, similarity_threshold: float = 0.95) -> int:
        """Remove memórias duplicadas baseado em similaridade. Retorna quantidade removida."""
        if not self.client:
            return 0
        
        collection = self.get_or_create_collection(collection_name)
        if not collection:
            return 0
        
        try:
            results = collection.get()
            if not results or not results["ids"]:
                return 0
            
            # Simplificado: remove duplicatas exatas pelo texto
            text_to_ids = {}
            duplicate_ids = []
            
            for i, doc in enumerate(results["documents"] or []):
                if doc in text_to_ids:
                    duplicate_ids.append(results["ids"][i])
                else:
                    text_to_ids[doc] = results["ids"][i]
            
            if duplicate_ids:
                collection.delete(ids=duplicate_ids)
                logger.info(f"Removidas {len(duplicate_ids)} memórias duplicadas de {collection_name}")
            
            return len(duplicate_ids)
        except Exception as e:
            logger.error(f"Falha ao limpar memórias duplicadas: {e}")
            return 0
