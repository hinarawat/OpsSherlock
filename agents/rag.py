"""LangChain RAG: FAISS index over markdown runbooks, local HuggingFace embeddings.

Each chunk is prefixed with its runbook title for better retrieval, and search
applies a relevance-score threshold so unrelated runbooks are filtered out.
"""
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"
_store = None


def _get_store():
    global _store
    if _store is None:
        docs = []
        for md in sorted(KB_DIR.glob("*.md")):
            title = md.stem.replace("_", " ")
            docs.append(Document(page_content=md.read_text(), metadata={"source": md.stem, "title": title}))
        chunks = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100).split_documents(docs)
        for c in chunks:  # prefix title so the embedding "knows" which runbook it is
            c.page_content = f"[Runbook: {c.metadata['title']}]\n{c.page_content}"
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        _store = FAISS.from_documents(chunks, embeddings)
    return _store


def search(query: str, k: int = 3, min_score: float = 0.3):
    """Top-k chunks with a relevance floor — returns [] if nothing is truly relevant."""
    results = _get_store().similarity_search_with_relevance_scores(query, k=k)
    return [doc for doc, score in results if score >= min_score]


def get_retriever(k: int = 3):
    """Backward-compatible retriever interface."""
    return _get_store().as_retriever(search_kwargs={"k": k})
