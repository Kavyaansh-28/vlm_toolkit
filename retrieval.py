"""Small, inspectable TF-IDF RAG implementation."""
from __future__ import annotations
from functools import lru_cache
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from ingestion import load_documents

class RajasthanRetriever:
    def __init__(self, documents=None):
        self.documents = documents if documents is not None else load_documents()
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), lowercase=True)
        corpus = [f"{d['title']} {d['destination']} {d['category']} {d['text']}" for d in self.documents]
        self.matrix = self.vectorizer.fit_transform(corpus) if corpus else None

    def search(self, query, destination=None, category=None, top_k=5):
        if not query or not query.strip() or self.matrix is None: return []
        candidates = [(i, d) for i, d in enumerate(self.documents)
                      if (not destination or d["destination"].lower() == destination.lower())
                      and (not category or d["category"].lower() == category.lower())]
        if not candidates: return []
        q = self.vectorizer.transform([query])
        scores = cosine_similarity(q, self.matrix[[i for i, _ in candidates]]).ravel()
        rows = []
        for score, (_, doc) in sorted(zip(scores, candidates), reverse=True, key=lambda x: x[0]):
            if score > 0:
                rows.append({**doc, "score": round(float(score), 3)})
        return rows[:max(1, min(top_k, 10))]

@lru_cache(maxsize=1)
def get_retriever(): return RajasthanRetriever()

def retrieve_knowledge(query, destination=None, category=None, top_k=5):
    return get_retriever().search(query, destination, category, top_k)
