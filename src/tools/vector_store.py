import os
import logging
from typing import List, Dict, Optional, Any
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)

class VectorStoreManager:
    """
    Manages the ChromaDB vector store for Semantic RAG.
    """
    
    def __init__(self, persist_directory: str = "/app/data/chroma_db"):
        self.persist_directory = persist_directory
        self._client = None
        self._collection = None
        
        # Ensure directory exists
        if not os.path.exists(persist_directory):
            os.makedirs(persist_directory, exist_ok=True)
            
        try:
            # Initialize Client
            self._client = chromadb.PersistentClient(path=persist_directory)
            
            # Default Embedding Function (all-MiniLM-L6-v2)
            # This downloads the model on first use (~80MB)
            self._embedding_fn = embedding_functions.DefaultEmbeddingFunction()
            
            # Get or Create Collection
            self._collection = self._client.get_or_create_collection(
                name="rag_knowledge_base",
                embedding_function=self._embedding_fn,
                metadata={"hnsw:space": "cosine"} # Cosine similarity
            )
            logger.info(f"Vector Store initialized at {persist_directory}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Vector Store: {e}")
            self._client = None

    def add_documents(self, documents: List[Dict[str, Any]]):
        """
        Adds documents to the vector store.
        Args:
            documents: List of dicts with keys: 'id', 'text', 'metadata'
        """
        if not self._collection or not documents:
            return

        ids = [doc["id"] for doc in documents]
        texts = [doc["text"] for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]

        try:
            # Chroma handles batching, but we can do small batches if needed.
            # For now, pass all.
            self._collection.upsert(
                ids=ids,
                documents=texts,
                metadatas=metadatas
            )
            logger.info(f"Upserted {len(documents)} docs to Vector Store")
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")

    def query_similar(self, query_text: str, n_results: int = 5) -> List[Dict]:
        """
        Semantic search.
        """
        if not self._collection:
            return []
            
        try:
            results = self._collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            
            # Flatten results structure
            # results['ids'][0], results['documents'][0], results['metadatas'][0], results['distances'][0]
            if not results['ids']:
                return []
                
            flat_results = []
            for i in range(len(results['ids'][0])):
                flat_results.append({
                    "id": results['ids'][0][i],
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i]
                })
            return flat_results
            
        except Exception as e:
            logger.error(f"Vector Query failed: {e}")
            return []

    def delete_documents(self, ids: List[str]):
        if not self._collection: return
        try:
            self._collection.delete(ids=ids)
        except Exception as e:
            logger.error(f"Failed to delete docs: {e}")

    def count(self):
        if not self._collection: return 0
        return self._collection.count()
