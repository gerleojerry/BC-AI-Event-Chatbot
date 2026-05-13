import os
from dotenv import load_dotenv
from typing import List, Dict
from uuid import uuid4

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.vectorstores import Chroma
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter


load_dotenv()
# -----------------------------
# 1. CONFIG
# -----------------------------
PERSIST_DIR = "./chroma_db"
DOCUMENT_COLLECTION = "document_index"
CHUNK_COLLECTION = "chunk_index"

EMBED_MODEL = "text-embedding-3-large"
LLM_MODEL = "gpt-5.4-nano-2026-03-17"

# Retrieval settings
TOP_K_DOCS = 1        # try 2 for ambiguous queries
TOP_K_CHUNKS = 3


# -----------------------------
# 2. INIT MODELS & STORES
# -----------------------------
embeddings = OpenAIEmbeddings(model=EMBED_MODEL)
llm = ChatOpenAI(model=LLM_MODEL, temperature=0)

doc_store = Chroma(
    collection_name=DOCUMENT_COLLECTION,
    embedding_function=embeddings,
    persist_directory=PERSIST_DIR
)

chunk_store = Chroma(
    collection_name=CHUNK_COLLECTION,
    embedding_function=embeddings,
    persist_directory=PERSIST_DIR
)

# Better chunking
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100
)


# -----------------------------
# 3. INGESTION
# -----------------------------
def summarize_for_routing(text: str) -> str:
    """
    Create a short summary for better document-level retrieval.
    """
    prompt = f"Summarize this document in 3 concise lines:\n\n{text}"
    return llm.invoke(prompt).content.strip()


def ingest_document(text: str, doc_id: str):
    """
    Ingest a document into:
    - document-level index (for routing)
    - chunk-level index (for detailed retrieval)
    """

    # --- Step 1: Create routing summary (IMPORTANT)
    summary = summarize_for_routing(text)

    doc = Document(
        page_content=summary,
        metadata={"document_id": doc_id}
    )
    doc_store.add_documents([doc])

    # --- Step 2: Chunk the full document
    chunks = splitter.split_text(text)

    chunk_docs: List[Document] = []
    for i, chunk in enumerate(chunks):
        chunk_docs.append(
            Document(
                page_content=chunk,
                metadata={
                    "document_id": doc_id,
                    "chunk_index": i
                }
            )
        )

    chunk_store.add_documents(chunk_docs)

    # Persist to disk
    doc_store.persist()
    chunk_store.persist()

    print(f"[INGESTED] {doc_id} with {len(chunks)} chunks")


# -----------------------------
# 4. ROUTING
# -----------------------------
def route_to_documents(query: str, k: int = TOP_K_DOCS) -> List[str]:
    """
    Retrieve most relevant document IDs.
    """
    results = doc_store.similarity_search(query, k=k)
    doc_ids = [doc.metadata["document_id"] for doc in results]

    print(f"[ROUTER] Selected docs: {doc_ids}")
    return doc_ids


# -----------------------------
# 5. FILTERED RETRIEVAL
# -----------------------------
def retrieve_chunks(query: str, doc_ids: List[str], k: int = TOP_K_CHUNKS) -> List[str]:
    """
    Retrieve chunks ONLY from selected documents.
    """
    all_chunks = []

    for doc_id in doc_ids:
        results = chunk_store.similarity_search(
            query,
            k=k,
            filter={"document_id": doc_id}   # 🔥 strict filtering
        )
        all_chunks.extend([r.page_content for r in results])

    return all_chunks


# -----------------------------
# 6. GENERATION
# -----------------------------
def generate_answer(query: str, context_chunks: List[str]) -> str:
    context = "\n\n".join(context_chunks)

    prompt = f"""
You are a precise assistant. Answer ONLY using the provided context.
If the answer is not in the context, say "I don't know".

Question:
{query}

Context:
{context}

Answer:
"""
    response = llm.invoke(prompt)
    return response.content.strip()


# -----------------------------
# 7. FULL PIPELINE
# -----------------------------
def ask(query: str) -> str:
    # Step 1: Route to document(s)
    doc_ids = route_to_documents(query)

    # Step 2: Retrieve chunks (filtered)
    chunks = retrieve_chunks(query, doc_ids)

    # Step 3: Generate answer
    answer = generate_answer(query, chunks)

    return answer


# -----------------------------
# 8. EXAMPLE
# -----------------------------
if __name__ == "__main__":
    doc1 = """
    Loan eligibility requires:
    - valid government ID
    - proof of income
    - minimum credit score of 650
    """

    doc2 = """
    Loan repayment terms:
    - duration: up to 24 months
    - monthly installment required
    - late payment attracts penalty
    """

    ingest_document(doc1, "doc_1")
    ingest_document(doc2, "doc_2")

    question = "What do I need to qualify for a loan?"
    print("\nQUESTION:", question)
    print("\nANSWER:", ask(question))