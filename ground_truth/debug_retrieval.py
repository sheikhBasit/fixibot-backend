import sys
import os
import asyncio
import faiss
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

# Wrapper to handle async embedding inside LangChain if needed
class FunctionalEmbeddings(Embeddings):
    def __init__(self, embed_func):
        self.func = embed_func
    def embed_documents(self, texts): return [self.func(t).tolist() for t in texts]
    def embed_query(self, text): return self.func(text).tolist()

async def inspect():
    print("🔧 DIAGNOSTIC TOOL: Inspecting Vector Store...")

    # 1. Locate Cache
    cache_dir = current_dir / ".vector_cache"
    faiss_files = list(cache_dir.glob("**/*.faiss"))
    
    if not faiss_files:
        print(f"❌ CRITICAL: No .faiss file found in {cache_dir}")
        return

    target_file = faiss_files[0]
    db_path = target_file.parent
    index_name = target_file.stem
    print(f"📂 Loaded Index: {target_file.name}")

    try:
        # 2. Load Store
        # We don't need the wrapper for the manual search test below, 
        # but FAISS loading requires *some* embedding class.
        wrapper = FunctionalEmbeddings(embed_text)
        vectorstore = FAISS.load_local(
            str(db_path), 
            embeddings=wrapper,
            allow_dangerous_deserialization=True,
            index_name=index_name
        )
        
        # 3. Check Stats
        num_docs = vectorstore.index.ntotal
        print(f"📊 Total Vectors: {num_docs}")
        
        # 4. Inspect Metadata (Checking Page Numbers!)
        print("\n🔍 --- METADATA INSPECTION ---")
        doc_dict = vectorstore.docstore._dict
        first_key = list(doc_dict.keys())[0]
        first_doc = doc_dict[first_key]
        
        print(f"Metadata Source: '{first_doc.metadata.get('source')}'")
        print(f"Metadata Page:   {first_doc.metadata.get('page')}  <-- NOTE THIS NUMBER")
        
        if "section_topic" in first_doc.metadata:
            print("✅ TOPIC ENRICHMENT: Found")
        else:
            print("⚠️ TOPIC ENRICHMENT: Not Found")

        # 5. Live Search Test
        print("\n🎯 --- LIVE SEARCH TEST ---")
        test_query = "makes this rapid clicking noise when I turn the key"
        print(f"Query: '{test_query}'")
        
        # FIX: Await the async embedding function
        print("⏳ Generating embedding...")
        emb = await embed_text(test_query)
        
        # Search
        results = vectorstore.similarity_search_with_score_by_vector(emb, k=3)
        
        print("\nResults (Score = L2 Distance, Lower is Better):")
        for i, (doc, score) in enumerate(results):
            src = doc.metadata.get("source", "N/A")
            pg = doc.metadata.get("page", "N/A")
            print(f"   {i+1}. Score: {score:.4f} | Source: {src} | Page: {pg}")
            print(f"      Text: {doc.page_content.replace(chr(10), ' ')[:80]}...")
            
            # Diagnostic for Threshold
            if score > 1.2:
                print("      ⚠️  (Would be filtered by > 1.2)")
            if score > 1.5:
                print("      ❌  (Would be filtered by > 1.5)")

    except Exception as e:
        print(f"❌ Error during inspection: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(inspect())
    