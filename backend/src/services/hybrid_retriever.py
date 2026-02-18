"""Hybrid retrieval combining vector search with BM25."""

from typing import List, Optional
import time

from src.services.bm25_search import bm25_search
from src.agents.retriever import RetrieverAgent, RetrievedChunk, RetrievalResult


class HybridRetriever:
    """Combines vector search with BM25 for better retrieval."""
    
    def __init__(self, vector_retriever: RetrieverAgent, vector_weight: float = 0.7):
        self.vector_retriever = vector_retriever
        self.vector_weight = vector_weight  # Weight for vector search (0.7 = 70% vector, 30% BM25)
        self.bm25_weight = 1 - vector_weight
        self.indexed = False
    
    def index_for_bm25(self, chunks: List[dict]):
        """Index chunks for BM25 search."""
        bm25_search.index_documents(chunks)
        self.indexed = True
    
    async def retrieve(
        self, 
        query: str, 
        k: int = 5, 
        min_score: float = 0.1
    ) -> RetrievalResult:
        """Hybrid retrieval combining vector and BM25 search."""
        start_time = time.time()
        
        # Get vector search results
        vector_results = await self.vector_retriever.retrieve(query, k=k*2, min_score=min_score)
        
        # Get BM25 results if indexed
        bm25_scores = {}
        if self.indexed and len(bm25_search.documents) > 0:
            bm25_results = bm25_search.search(query, k=k*2)
            # Normalize BM25 scores
            max_bm25 = max([s for _, s in bm25_results], default=1) or 1
            if max_bm25 > 0:
                bm25_scores = {idx: score/max_bm25 for idx, score in bm25_results}
        
        # Combine scores
        combined_chunks = []
        seen_contents = set()
        
        for chunk in vector_results.chunks:
            content_hash = hash(chunk.content[:100])
            if content_hash in seen_contents:
                continue
            seen_contents.add(content_hash)
            
            # Get BM25 score for this chunk (by matching content)
            bm25_score = 0
            if self.indexed and len(bm25_search.documents) > 0:
                for idx, doc in enumerate(bm25_search.documents):
                    if doc.get('content', '')[:100] == chunk.content[:100]:
                        bm25_score = bm25_scores.get(idx, 0)
                        break
            
            # Combined score
            combined_score = (self.vector_weight * chunk.score) + (self.bm25_weight * bm25_score)
            
            combined_chunks.append(RetrievedChunk(
                content=chunk.content,
                metadata=chunk.metadata,
                score=combined_score,
                rank=0  # Will be set after sorting
            ))
        
        # Sort by combined score and assign ranks
        combined_chunks.sort(key=lambda x: x.score, reverse=True)
        for i, chunk in enumerate(combined_chunks[:k]):
            chunk.rank = i + 1
        
        retrieval_time = (time.time() - start_time) * 1000
        
        return RetrievalResult(
            chunks=combined_chunks[:k],
            query=query,
            retrieval_time_ms=retrieval_time,
            total_candidates=len(combined_chunks)
        )


# Will be initialized with vector retriever
hybrid_retriever: Optional[HybridRetriever] = None
