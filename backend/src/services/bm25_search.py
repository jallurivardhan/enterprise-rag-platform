"""BM25 keyword-based search for hybrid retrieval."""

import math
from typing import List, Dict, Tuple
from collections import Counter
import re


class BM25Search:
    """BM25 keyword-based search for hybrid retrieval."""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[Dict] = []
        self.doc_lengths: List[int] = []
        self.avg_doc_length: float = 0
        self.doc_freqs: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_term_freqs: List[Dict[str, int]] = []
    
    def tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        text = text.lower()
        tokens = re.findall(r'\b[a-z0-9]+\b', text)
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 
                      'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                      'would', 'could', 'should', 'may', 'might', 'can', 'to', 'of',
                      'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
                      'through', 'during', 'before', 'after', 'above', 'below',
                      'between', 'under', 'again', 'further', 'then', 'once', 'and',
                      'but', 'or', 'nor', 'so', 'yet', 'both', 'each', 'more', 'most',
                      'other', 'some', 'such', 'no', 'not', 'only', 'own', 'same',
                      'than', 'too', 'very', 'just', 'also', 'now', 'here', 'there',
                      'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each',
                      'few', 'more', 'most', 'other', 'some', 'such', 'this', 'that',
                      'these', 'those', 'i', 'me', 'my', 'myself', 'we', 'our', 'you',
                      'your', 'he', 'him', 'his', 'she', 'her', 'it', 'its', 'they',
                      'them', 'their', 'what', 'which', 'who', 'whom'}
        return [t for t in tokens if t not in stop_words and len(t) > 1]
    
    def index_documents(self, documents: List[Dict]):
        """Index documents for BM25 search."""
        self.documents = documents
        self.doc_term_freqs = []
        self.doc_lengths = []
        self.doc_freqs = {}
        self.idf = {}
        
        # Calculate term frequencies for each document
        for doc in documents:
            content = doc.get('content', '')
            tokens = self.tokenize(content)
            self.doc_lengths.append(len(tokens))
            
            term_freq = Counter(tokens)
            self.doc_term_freqs.append(dict(term_freq))
            
            # Update document frequencies
            for term in set(tokens):
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1
        
        # Calculate average document length
        self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0
        
        # Calculate IDF for all terms
        n_docs = len(documents)
        for term, df in self.doc_freqs.items():
            self.idf[term] = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
    
    def search(self, query: str, k: int = 10) -> List[Tuple[int, float]]:
        """Search documents and return (doc_index, score) pairs."""
        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []
        
        scores = []
        
        for idx, doc_term_freq in enumerate(self.doc_term_freqs):
            score = 0
            doc_len = self.doc_lengths[idx]
            
            for term in query_tokens:
                if term in doc_term_freq:
                    tf = doc_term_freq[term]
                    idf = self.idf.get(term, 0)
                    
                    # BM25 formula
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / self.avg_doc_length))
                    score += idf * (numerator / denominator)
            
            scores.append((idx, score))
        
        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]


# Global instance
bm25_search = BM25Search()
