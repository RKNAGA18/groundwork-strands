import re
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class EvidenceChunk:
    chunk_id: str
    doc_name: str
    text: str
    match_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {"chunk_id": self.chunk_id, "doc_name": self.doc_name, "text": self.text, "match_score": round(self.match_score, 4)}

import math
from collections import Counter

class BM25Retriever:
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        self.avgdl = 0
        self.N = 0

    def fit(self, docs_text):
        self.N = len(docs_text)
        self.doc_freqs = []
        self.doc_len = []
        
        df = Counter()
        total_len = 0
        
        for doc in docs_text:
            words = re.findall(r'\w+', doc.lower())
            self.doc_len.append(len(words))
            total_len += len(words)
            freq = Counter(words)
            self.doc_freqs.append(freq)
            for word in freq:
                df[word] += 1
                
        self.avgdl = total_len / self.N if self.N else 0
        
        for word, freq in df.items():
            self.idf[word] = math.log(1 + (self.N - freq + 0.5) / (freq + 0.5))
            
    def get_scores(self, query):
        q_words = re.findall(r'\w+', query.lower())
        scores = [0.0] * self.N
        for idx, doc_freq in enumerate(self.doc_freqs):
            score = 0.0
            dl = self.doc_len[idx]
            for word in q_words:
                if word not in doc_freq:
                    continue
                tf = doc_freq[word]
                idf = self.idf.get(word, 0)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (dl / self.avgdl))
                score += idf * (numerator / denominator)
            scores[idx] = score
        return scores

class VectorStoreManager:
    def __init__(self): 
        self.kbs = {}
        self.retrievers = {}
    
    def create_kb(self, kb_id: str):
        if kb_id not in self.kbs: 
            self.kbs[kb_id] = []
            self.retrievers[kb_id] = BM25Retriever()
        
    def add_chunks(self, kb_id: str, chunks: List[Any]):
        self.create_kb(kb_id)
        for i, c in enumerate(chunks):
            text = getattr(c, "text", None) or (c.get("text") if isinstance(c, dict) else str(c))
            doc_name = getattr(c, "doc_name", None) or (c.get("doc_name") if isinstance(c, dict) else "doc")
            self.kbs[kb_id].append({"chunk_id": f"{doc_name}_{i}", "doc_name": str(doc_name), "text": text, "metadata": {}})
        
        # Re-fit the BM25 model for this KB
        docs_text = [item["text"] for item in self.kbs[kb_id]]
        self.retrievers[kb_id].fit(docs_text)
            
    def retrieve(self, kb_id: str, query: str, top_k: int = 3, threshold: float = 0.01) -> List[EvidenceChunk]:
        if kb_id not in self.kbs or not self.kbs[kb_id]: return []
        
        retriever = self.retrievers.get(kb_id)
        if not retriever or retriever.N == 0: return []

        scores = retriever.get_scores(query)
        scored = []
        for idx, score in enumerate(scores):
            if score >= threshold:
                scored.append((score, self.kbs[kb_id][idx]))
                
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            EvidenceChunk(chunk_id=it["chunk_id"], doc_name=it["doc_name"], text=it["text"], match_score=s) 
            for s, it in scored[:top_k]
        ]
