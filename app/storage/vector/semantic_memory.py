from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, List

logger = logging.getLogger(__name__)

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
                self._collections[name] = self.client.get_or_create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"}
                )
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
        if not self.client:
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
        filter_expired: bool = True
    ) -> List[dict[str, Any]]:
        """Busca memórias similares, incrementando access_count."""
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
            
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0
                
                # Filtra memórias expiradas
                if filter_expired:
                    timestamp = metadata.get("timestamp", current_time)
                    age_days = (current_time - timestamp) / 86400
                    if age_days > self.max_age_days:
                        continue
                
                memories.append({
                    "text": doc,
                    "metadata": metadata,
                    "distance": distance
                })
                
                # Incrementa access_count
                if metadata.get("id"):
                    try:
                        collection.update(
                            ids=[metadata["id"]],
                            metadatas=[{**metadata, "access_count": metadata.get("access_count", 0) + 1}]
                        )
                    except Exception:
                        pass
            
            # Ordena por relevância (distância + importância)
            memories.sort(key=lambda m: m["distance"] / (m["metadata"].get("importance", 1.0) + 0.1))
            
            return memories[:n_results]
        except Exception as e:
            logger.error(f"Falha ao buscar memórias: {e}")
            return []
    
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
