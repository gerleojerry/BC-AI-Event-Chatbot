import os
from dotenv import load_dotenv
from typing import List, Dict
from uuid import uuid4

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
# from langchain.vectorstores import Chroma
from langchain_chroma import Chroma
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain.document_loaders import Docx2txtLoader
# from langchain.document_loaders import UnstructuredWordDocumentLoader
from langchain_community.document_loaders import UnstructuredWordDocumentLoader


load_dotenv()
# -----------------------------
# 1. CONFIG
# -----------------------------
PERSIST_DIR = "./chroma_db"
DOCUMENT_COLLECTION = "document_index"
CHUNK_COLLECTION = "chunk_index"

EMBED_MODEL = "text-embedding-3-small"
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
    chunk_size=1000,
    chunk_overlap=200
)


# -----------------------------
# 3. INGESTION
# -----------------------------
def summarize_for_routing(text: str) -> str:
    """
    Create a short summary for better document-level retrieval.
    """
    prompt = f"Summarize this document in 3 concise sentences:\n\n{text}"
    return llm.invoke(prompt).content.strip()


def check_doc_exists(vectorstore, doc_id: str) -> bool:
    results = vectorstore._collection.get(
        where={"document_id": doc_id},
        limit=1
    )
    return bool(results and results.get("ids"))

def ingest_document(text: str, doc_id: str):
    """
    Ingest a document into:
    - document-level index (for routing)
    - chunk-level index (for detailed retrieval)
    """

    doc_exists = check_doc_exists(doc_store, doc_id)

    if doc_exists:
        print(f"[SKIPPED] Document {doc_id} already exists.")
        return
    print("[INGESTING] Document does not exist. Proceeding with ingestion.")

    # summary = summarize_for_routing(text)
    summary = text

    doc = Document(
        page_content=summary,
        metadata={"document_id": doc_id}
    )
    doc_store.add_documents([doc])

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

    print(f"[INGESTED] {doc_id} with {len(chunks)} chunks")


def route_to_documents(query: str, k: int = TOP_K_DOCS) -> List[str]:
    """
    Retrieve most relevant document IDs.
    """
    results = doc_store.similarity_search(query, k=k)
    doc_ids = [doc.metadata["document_id"] for doc in results]

    print(f"[ROUTER] Selected docs: {doc_ids}")
    return doc_ids


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

def answer_event_question(query: str) -> str:
    # Step 1: Route to document(s)
    doc_ids = route_to_documents(query)

    # Step 2: Retrieve chunks (filtered)
    chunks = retrieve_chunks(query, doc_ids)

    # Step 3: Generate answer
    answer = generate_answer(query, chunks)

    return answer


if __name__ == "__main__":
    root_folder = './meeting_transcript'
    dirs = os.listdir(root_folder)
    for file in dirs:
        if file.endswith('.docx'):
            file_path = os.path.join(root_folder, file)
            loader = UnstructuredWordDocumentLoader(file_path)
            data = loader.load()[0].page_content
            ingest_document(data, f"{file}")

    # question = "What does the previous industrial revolution rely on?"
    question = "How has AI Powered chat affect"
    print("\nQUESTION:", question)
    print("\nANSWER:", answer_event_question(question))