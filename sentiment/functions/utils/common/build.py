import pandas as pd
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

def build_vector_store(csv_path, embeddings, limit_rows=300):
    """Loads historical sentiment CSV, processes and indexes records into a FAISS database."""
    print(f"Loading dataset: {csv_path}...")
    df = pd.read_csv(csv_path)
    df = df.dropna(subset=["Sentence", "Sentiment"])
    
    df_subset = df.head(limit_rows)
    print(f"Indexing {len(df_subset)} records into FAISS vector database...")
    
    documents = [
        Document(page_content=row["Sentence"], metadata={"sentiment": row["Sentiment"]})
        for _, row in df_subset.iterrows()
    ]
    
    db = FAISS.from_documents(documents, embeddings)
    print("[+] FAISS Local Vector Store created successfully!")
    return db