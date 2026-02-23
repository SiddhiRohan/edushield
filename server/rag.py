# QuantumLeap - RAG on PDF and FAISS
from pathlib import Path
import numpy as np

# Lazy imports to avoid loading heavy deps at startup
_pdf_reader = None
_embedding_model = None
_faiss_index = None
_chunk_texts: list[str] = []


def _get_pdf_reader():
    global _pdf_reader
    if _pdf_reader is None:
        from pypdf import PdfReader
        _pdf_reader = PdfReader
    return _pdf_reader


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def extract_text_from_pdf(pdf_path: Path) -> str:
    reader = _get_pdf_reader()
    with open(pdf_path, "rb") as f:
        pdf = reader(f)
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def build_faiss_index(pdf_dir: Path, index_path: Path) -> tuple[list[str], Path]:
    """Extract text from PDFs in pdf_dir, chunk, embed, and build FAISS index. Returns (chunk_texts, index_path)."""
    global _chunk_texts
    all_chunks = []
    for pdf_file in Path(pdf_dir).glob("*.pdf"):
        try:
            text = extract_text_from_pdf(pdf_file)
            all_chunks.extend(chunk_text(text))
        except Exception as e:
            print(f"Skip {pdf_file}: {e}")
    if not all_chunks:
        all_chunks = ["No PDF content available. Add PDFs to data/pdfs/ for RAG."]
    _chunk_texts = all_chunks

    model = _get_embedding_model()
    embeddings = model.encode(all_chunks, show_progress_bar=False)
    embeddings = np.array(embeddings).astype("float32")

    import faiss
    index_path = Path(index_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    faiss.write_index(index, str(index_path))
    return _chunk_texts, index_path


def load_faiss_index(index_path: Path) -> "faiss.Index":
    import faiss
    return faiss.read_index(str(index_path))


def search_faiss(
    query: str,
    index_path: Path,
    chunk_texts: list[str] | None = None,
    top_k: int = 5,
) -> list[str]:
    """Search FAISS index with query; return top_k chunk texts. Uses in-memory chunks if provided."""
    global _chunk_texts, _faiss_index
    if not index_path or not Path(index_path).exists():
        return ["No RAG index yet. Add PDFs to data/pdfs/ and call POST /api/rag/build-index (admin)."]
    if chunk_texts is not None:
        texts = chunk_texts
    else:
        texts = _chunk_texts
    if not texts:
        return ["No RAG content indexed. Add PDFs and run build index."]
    model = _get_embedding_model()
    q_emb = model.encode([query])
    q_emb = np.array(q_emb).astype("float32")
    index = load_faiss_index(index_path)
    _, indices = index.search(q_emb, min(top_k, len(texts)))
    return [texts[i] for i in indices[0] if i < len(texts)]
