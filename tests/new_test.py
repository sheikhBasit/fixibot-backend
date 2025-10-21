import pytest
import asyncio
from pathlib import Path
from services.data_extractor import DataExtractor
from services.rag_evaluator import EvaluationData
from services.data_extractor import EnhancedRAGEvaluator

@pytest.fixture
async def sample_data():
    extractor = DataExtractor()
    data = await extractor.extract_chat_data(days=7)  # Get last 7 days of data
    return data

@pytest.mark.asyncio
async def test_rag_evaluation_with_real_data(sample_data):
    """Test RAG evaluation with real chat data"""
    
    # Convert to evaluation format
    eval_data = [
        EvaluationData(
            query=item["query"],
            generated_text=item["generated_text"],
            reference_text=item["reference_text"],
            retrieved_context=item["retrieved_context"]
        )
        for item in sample_data
    ]
    
    evaluator = EnhancedRAGEvaluator()
    results = evaluator.evaluate(eval_data)
    
    # Save results
    Path("evaluation_results").mkdir(exist_ok=True)
    results.to_csv("evaluation_results/test_results.csv", index=False)
    
    # Validate results
    assert not results.empty, "No evaluation results generated"
    assert all(0 <= score <= 1 for score in results["Score"]), "Invalid score range"
    
    # Print summary
    print("\n=== Evaluation Results ===")
    print(results.to_string(index=False))

if __name__ == "__main__":
    pytest.main([__file__, "-v"])