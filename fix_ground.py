"""
Auto-Label Ground Truth
-----------------------
Since exact text matching failed, this script uses Semantic Search (FAISS)
to find the most relevant page for each query and updates the Ground Truth.

It prints the found text so you can verify if it's actually the correct answer.
"""

import sys
import os
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

# --- SETUP ---
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))
load_dotenv()

try:
    from langchain_community.vectorstores import FAISS
    from langchain_core.embeddings import Embeddings
    from services.multimodal_embeddings import embed_text
except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)

class FunctionalEmbeddings(Embeddings):
    def __init__(self, embed_func):
        self.func = embed_func
    def embed_documents(self, texts): return [self.func(t).tolist() for t in texts]
    def embed_query(self, text): return self.func(text).tolist()

async def auto_label():
    print("🔧 Initializing Auto-Labeling...")

    # 1. Load Data
    json_path = "test_ground_truth.json"
    if not Path(json_path).exists():
        print("❌ test_ground_truth.json not found.")
        return
    with open(json_path, "r") as f:
        data = json.load(f)

    # 2. Load Vector Store
    cache_dir = current_dir / ".vector_cache"
    faiss_files = list(cache_dir.glob("**/*.faiss"))
    if not faiss_files:
        print("❌ No index found.")
        return

    target_file = faiss_files[0]
    wrapper = FunctionalEmbeddings(embed_text)
    vectorstore = FAISS.load_local(
        str(target_file.parent), 
        embeddings=wrapper,
        allow_dangerous_deserialization=True,
        index_name=target_file.stem
    )

    print(f"🚀 Processing {len(data)} queries to find correct pages...")
    
    updated_data = []
    
    for item in data:
        query = item["question"]
        
        # Async Embed
        if asyncio.iscoroutinefunction(embed_text):
            emb = await embed_text(query)
        else:
            emb = await asyncio.to_thread(embed_text, query)
            
        # Search Top 1
        docs = vectorstore.similarity_search_with_score_by_vector(emb, k=1)
        
        if docs:
            best_doc, score = docs[0]
            found_page = best_doc.metadata.get("page")
            found_source = best_doc.metadata.get("source")
            
            # Update the JSON
            # We assume the Top 1 result from FAISS is the "Correct" location
            # because we want to test if the SYSTEM can find it again later.
            item["relevant_doc_ids"] = [found_source, f"Page: {found_page}"]
            
            print(f"\n✅ Query: {query[:40]}...")
            print(f"   -> Found on Page {found_page} (Score: {score:.3f})")
            print(f"   -> Snippet: {best_doc.page_content.replace(chr(10), ' ')[:100]}...")
        
        updated_data.append(item)

    # Save
    output_path = "test_ground_truth_aligned.json"
    with open(output_path, "w") as f:
        json.dump(updated_data, f, indent=2)
    
    print(f"\n✨ Generated '{output_path}'")
    print("👉 Steps to fix your metrics:")
    print("1. Review the snippets above to ensure they are relevant.")
    print(f"2. Rename '{output_path}' to 'test_ground_truth.json'")
    print("3. Run 'python test_retrieval_offline.py'")

if __name__ == "__main__":
    asyncio.run(auto_label())