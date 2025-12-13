import sys
import pickle
import os
from pathlib import Path

# Setup paths
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent
sys.path.append(str(src_dir))

from langchain_community.vectorstores import FAISS
# Import Embeddings Wrapper (needed to load your specific index)
from langchain_core.embeddings import Embeddings
from services.multimodal_embeddings import embed_text

class FunctionalEmbeddings(Embeddings):
    def __init__(self, embed_func):
        self.func = embed_func
    def embed_documents(self, texts):
        return [self.func(t).tolist() for t in texts]
    def embed_query(self, text):
        return self.func(text).tolist()

def check_pages():
    print("🔧 Loading Vector Store for Inspection...")
    
    # 1. Find Cache
    cache_dir = src_dir / ".vector_cache"
    if not cache_dir.exists():
        print(f"❌ Cache not found at {cache_dir}")
        return

    # 2. Find Index File
    faiss_files = list(cache_dir.glob("*.faiss")) or list(cache_dir.glob("*/*.faiss"))
    if not faiss_files:
        print("❌ No .faiss index found.")
        return
        
    target_file = faiss_files[0]
    db_path = target_file.parent
    index_name = target_file.stem
    print(f"📂 Loaded Index: {index_name}")

    # 3. Load Vectorstore
    embedding_wrapper = FunctionalEmbeddings(embed_text)
    vectorstore = FAISS.load_local(
        str(db_path), 
        embeddings=embedding_wrapper,
        allow_dangerous_deserialization=True,
        index_name=index_name
    )

    # 4. RUN TEST QUERIES
    queries = [
        "My car won't start",
        "Check engine light blinking",
        "Black smoke from exhaust"
    ]

    print("\n" + "="*50)
    for q in queries:
        print(f"🔎 Query: '{q}'")
        results = vectorstore.similarity_search(q, k=2)
        
        for i, doc in enumerate(results):
            print(f"   Rank {i+1}: Page {doc.metadata.get('page')} | Source: {doc.metadata.get('source')}")
            # print(f"   Preview: {doc.page_content[:100]}...") # Optional: Un-comment to see text
        print("-" * 30)

if __name__ == "__main__":
    check_pages()

# import pytest
# import asyncio
# from pathlib import Path
# from services.data_extractor import DataExtractor
# from services.rag_evaluator import EvaluationData
# from services.data_extractor import EnhancedRAGEvaluator

# @pytest.fixture
# async def sample_data():
#     extractor = DataExtractor()
#     data = await extractor.extract_chat_data(days=7)  # Get last 7 days of data
#     return data

# @pytest.mark.asyncio
# async def test_rag_evaluation_with_real_data(sample_data):
#     """Test RAG evaluation with real chat data"""
    
#     # Convert to evaluation format
#     eval_data = [
#         EvaluationData(
#             query=item["query"],
#             generated_text=item["generated_text"],
#             reference_text=item["reference_text"],
#             retrieved_context=item["retrieved_context"]
#         )
#         for item in sample_data
#     ]
    
#     evaluator = EnhancedRAGEvaluator()
#     results = evaluator.evaluate(eval_data)
    
#     # Save results
#     Path("evaluation_results").mkdir(exist_ok=True)
#     results.to_csv("evaluation_results/test_results.csv", index=False)
    
#     # Validate results
#     assert not results.empty, "No evaluation results generated"
#     assert all(0 <= score <= 1 for score in results["Score"]), "Invalid score range"
    
#     # Print summary
#     print("\n=== Evaluation Results ===")
#     print(results.to_string(index=False))

# if __name__ == "__main__":
#     pytest.main([__file__, "-v"])