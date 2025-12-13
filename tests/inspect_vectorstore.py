"""
Inspector Script: Check what is actually inside your FAISS Vector Store.
"""
import sys
import pickle
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

# 1. Setup
load_dotenv()
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))

try:
    from services.multimodal_embeddings import embed_text
except ImportError:
    print("❌ Could not import services. Run from project root.")
    sys.exit(1)

class FunctionalEmbeddings(Embeddings):
    def __init__(self, embed_func):
        self.func = embed_func
    def embed_documents(self, texts): return [self.func(t).tolist() for t in texts]
    def embed_query(self, text): return self.func(text).tolist()

def inspect():
    print("🔍 Inspecting Vector Store...")
    
    # Locate Cache
    cache_dir = project_root / ".vector_cache"
    if not cache_dir.exists():
        print(f"❌ Cache directory not found at {cache_dir}")
        return

    # Find Index
    faiss_files = list(cache_dir.glob("*.faiss")) + list(cache_dir.glob("*/*.faiss"))
    if not faiss_files:
        print("❌ No .faiss index found.")
        return

    target_file = faiss_files[0]
    index_name = target_file.stem
    db_path = target_file.parent
    
    print(f"📂 Loading Index: {index_name}")
    print(f"📂 Path: {db_path}")

    # Load
    embedding_wrapper = FunctionalEmbeddings(embed_text)
    vectorstore = FAISS.load_local(
        str(db_path), 
        embeddings=embedding_wrapper,
        allow_dangerous_deserialization=True,
        index_name=index_name
    )

    # Inspect Documents
    print("\n📊 Database Content Preview:")
    docs = vectorstore.docstore._dict
    print(f"   Total Documents/Chunks: {len(docs)}")
    
    print("\n🧐 First 5 Documents Metadata (Use these IDs for your Ground Truth):")
    count = 0
    for k, v in docs.items():
        # metadata usually contains 'source' or 'file_path'
        meta = v.metadata
        source = meta.get('source', 'UNKNOWN')
        page = meta.get('page', '?')
        print(f"   [{count+1}] Source: '{source}' | Page: {page} | ID Key: {k}")
        count += 1
        if count >= 5: break

    print("\n✅ ACTION: Update your 'test_ground_truth.json' 'relevant_doc_ids' to match the 'Source' shown above exactly.")

if __name__ == "__main__":
    inspect()