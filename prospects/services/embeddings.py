from sentence_transformers import SentenceTransformer
from typing import List

# Singleton instance so the model isn't reloaded on every function call
_model = None

def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        #Lightweight model, 384 dimensional model
        _model = SentenceTransformer('all-MiniLM-l6-v2')
    return _model

def get_text_embedding(text: str) -> List[float]:
    # Generate a 384-dim vector embedding for the given text

    if not text or not text.strip():
        return []

    model = get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()