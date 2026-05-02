from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
import os

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
persist_directory = "chroma_db"

def load_rag_knowledge() -> Chroma:
    docs = []
    data_dir = "data"
    for filename in os.listdir(data_dir):
        if filename.endswith(".md"):
            with open(os.path.join(data_dir, filename), "r", encoding="utf-8") as f:
                content = f.read()
                docs.append(Document(page_content=content, metadata={"source": filename}))
    if os.path.exists(persist_directory):
        vectorstore = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
    else:
        vectorstore = Chroma.from_documents(docs, embeddings, persist_directory=persist_directory)
    return vectorstore

vectorstore = load_rag_knowledge()
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
