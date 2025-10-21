"""
Test Script for RAG Evaluation System
Run this script to test your RAG system with sample or real data

USAGE:
    python tests/test_rag_evaluation.py --mode basic
    python tests/test_rag_evaluation.py --mode comprehensive --data-file your_data.json
    python tests/test_rag_evaluation.py --mode template
    python tests/test_rag_evaluation.py --mode compare --compare-files file1.csv file2.csv
"""

import asyncio
import json
import time
from pathlib import Path
from typing import List, Dict
import pandas as pd
import sys
sys.path.append(str(Path(__file__).parent.parent))

# Import evaluation modules
from services.rag_evaluator import EvaluationData, RAGEvaluator


class TestDataGenerator:
    """Generate test data for evaluation"""
    
    @staticmethod
    def create_sample_test_data() -> List[EvaluationData]:
        """Create sample test data for initial testing"""
        
        test_cases = [
            {
                "query_id": "test_001",
                "query_text": "Why is my car engine overheating?",
                "retrieved_doc_ids": ["manual_p45", "manual_p67", "manual_p12"],
                "relevant_doc_ids": ["manual_p45", "manual_p67"],
                "similarity_scores": [0.92, 0.85, 0.71],
                "generated_text": "Engine overheating can be caused by low coolant levels, a faulty thermostat, or a damaged water pump. First, check your coolant reservoir and ensure it's at the proper level.",
                "reference_text": "Common causes of engine overheating include insufficient coolant, malfunctioning thermostat, or water pump failure. Check coolant level first.",
                "start_time": time.time(),
                "end_time": time.time() + 1.8
            },
            {
                "query_id": "test_002",
                "query_text": "How do I change my brake pads?",
                "retrieved_doc_ids": ["manual_p89", "manual_p90", "manual_p88"],
                "relevant_doc_ids": ["manual_p89", "manual_p90", "manual_p91"],
                "similarity_scores": [0.95, 0.93, 0.88],
                "generated_text": "To change brake pads: 1) Safely lift the vehicle. 2) Remove the wheel. 3) Remove the caliper and slide out pads. 4) Install new pads. 5) Reassemble.",
                "reference_text": "Brake pad replacement: Lift vehicle, remove wheel, detach caliper, replace pads, compress piston, reinstall.",
                "start_time": time.time(),
                "end_time": time.time() + 2.1
            },
            {
                "query_id": "test_003",
                "query_text": "What does the check engine light mean?",
                "retrieved_doc_ids": ["manual_p120", "manual_p34", "manual_p121"],
                "relevant_doc_ids": ["manual_p120", "manual_p121"],
                "similarity_scores": [0.88, 0.76, 0.72],
                "generated_text": "The check engine light indicates a potential issue with your engine or emissions system. Use an OBD-II scanner to read the diagnostic code.",
                "reference_text": "Check engine light signals engine/emissions problems. Use OBD-II scanner for diagnostic codes.",
                "start_time": time.time(),
                "end_time": time.time() + 1.5
            },
            {
                "query_id": "test_004",
                "query_text": "My car won't start, what should I check?",
                "retrieved_doc_ids": ["manual_p23", "manual_p24", "manual_p56"],
                "relevant_doc_ids": ["manual_p23", "manual_p24", "manual_p25"],
                "similarity_scores": [0.91, 0.87, 0.69],
                "generated_text": "Check: 1) Dead battery - try jump starting. 2) Bad starter motor. 3) Empty fuel tank. 4) Faulty ignition switch. Start with the battery.",
                "reference_text": "No-start causes: dead battery, faulty starter, empty fuel, bad ignition. Check battery first.",
                "start_time": time.time(),
                "end_time": time.time() + 1.9
            },
            {
                "query_id": "test_005",
                "query_text": "How often should I change my oil?",
                "retrieved_doc_ids": ["manual_p15", "manual_p16", "manual_p78"],
                "relevant_doc_ids": ["manual_p15", "manual_p16"],
                "similarity_scores": [0.94, 0.91, 0.65],
                "generated_text": "Oil change intervals: 5,000-7,500 miles with conventional oil, or 7,500-10,000 miles with synthetic oil. Check your owner's manual for specific recommendations.",
                "reference_text": "Oil changes: 5,000-7,500 miles (conventional), 7,500-10,000 miles (synthetic). Consult manual.",
                "start_time": time.time(),
                "end_time": time.time() + 1.6
            }
        ]
        
        return [EvaluationData(**case) for case in test_cases]
    
    @staticmethod
    def load_from_json(json_file: str) -> List[EvaluationData]:
        """Load test data from JSON file"""
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        return [EvaluationData(**item) for item in data]
    
    @staticmethod
    def create_json_template(output_file: str = "test_data_template.json"):
        """Create a JSON template file for manual test data entry"""
        template = [
            {
                "query_id": "test_001",
                "query_text": "Your test query here",
                "retrieved_doc_ids": ["doc1", "doc2", "doc3"],
                "relevant_doc_ids": ["doc1", "doc2"],
                "similarity_scores": [0.95, 0.87, 0.72],
                "generated_text": "Your chatbot's response here",
                "reference_text": "Ground truth response here",
                "start_time": 1234567890.0,
                "end_time": 1234567891.5,
                "metadata": {
                    "vehicle_type": "car",
                    "issue_category": "engine"
                }
            }
        ]
        
        with open(output_file, 'w') as f:
            json.dump(template, f, indent=2)
        
        print(f"✅ Template created at {output_file}")
        print("📝 Edit this file with your actual test cases, then run:")
        print(f"   python tests/test_rag_evaluation.py --mode comprehensive --data-file {output_file}")


async def run_basic_test():
    """Run basic evaluation test with sample data"""
    
    print("="*70)
    print("RAG SYSTEM EVALUATION - BASIC TEST")
    print("="*70)
    print()
    
    # Generate test data
    print("Loading test data...")
    test_data = TestDataGenerator.create_sample_test_data()
    print(f"✅ Loaded {len(test_data)} test cases")
    print()
    
    # Initialize evaluator
    evaluator = RAGEvaluator()
    
    # Run evaluation
    print("Running evaluation...")
    results_df = evaluator.evaluate(
        test_data, 
        k_values=[1, 3, 5],
        calculate_bertscore=False  # Set to True if you have bert-score installed
    )
    
    # Display results
    print()
    print("="*70)
    print("EVALUATION RESULTS")
    print("="*70)
    print()
    
    # Group by category
    for category in results_df['Category'].unique():
        print(f"\n{category} Metrics:")
        print("-" * 70)
        category_df = results_df[results_df['Category'] == category]
        
        for _, row in category_df.iterrows():
            metric = row['Metric']
            value = row['Value']
            print(f"  {metric:.<50} {value:.4f}")
    
    print()
    print("="*70)
    
    # Save results
    output_dir = Path("evaluation_results")
    output_dir.mkdir(exist_ok=True)
    
    evaluator.save_results(results_df, "evaluation_results/basic_test_eval")
    
    return results_df


async def run_comprehensive_test(test_data_file: str = None):
    """Run comprehensive evaluation with custom test data"""
    
    print("="*70)
    print("RAG SYSTEM EVALUATION - COMPREHENSIVE TEST")
    print("="*70)
    print()
    
    # Load test data
    if test_data_file and Path(test_data_file).exists():
        print(f"Loading test data from {test_data_file}...")
        test_data = TestDataGenerator.load_from_json(test_data_file)
    else:
        print("Using sample test data...")
        test_data = TestDataGenerator.create_sample_test_data()
    
    print(f"✅ Loaded {len(test_data)} test cases")
    print()
    
    # Initialize evaluator
    evaluator = RAGEvaluator()
    
    # Run evaluation
    print("Running comprehensive evaluation...")
    print()
    
    results_df = evaluator.evaluate(
        test_data,
        k_values=[1, 3, 5],
        calculate_bertscore=False  # Set to True if you want BERTScore
    )
    
    # Detailed results
    print()
    print("="*70)
    print("COMPREHENSIVE EVALUATION RESULTS")
    print("="*70)
    print()
    print(results_df.to_string(index=False))
    
    # Save results
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"evaluation_results/comprehensive_eval_{timestamp}"
    evaluator.save_results(results_df, output_path)
    
    print()
    print("="*70)
    print(f"✅ Results saved to: {output_path}")
    print("="*70)
    
    return results_df


def compare_evaluations(eval_files: List[str]):
    """Compare multiple evaluation results"""
    
    print("="*70)
    print("EVALUATION COMPARISON")
    print("="*70)
    print()
    
    # Load all evaluations
    dfs = []
    labels = []
    
    for file_path in eval_files:
        if not Path(file_path).exists():
            print(f"⚠️  File not found: {file_path}")
            continue
        df = pd.read_csv(file_path)
        dfs.append(df)
        labels.append(Path(file_path).stem)
    
    if len(dfs) < 2:
        print("❌ Need at least 2 valid files to compare")
        return
    
    # Create comparison DataFrame
    comparison_data = []
    
    for metric in dfs[0]['Metric'].unique():
        row = {'Metric': metric}
        for i, (df, label) in enumerate(zip(dfs, labels)):
            value = df[df['Metric'] == metric]['Value'].values
            if len(value) > 0:
                row[label] = value[0]
        comparison_data.append(row)
    
    comparison_df = pd.DataFrame(comparison_data)
    
    # Calculate improvements
    if len(dfs) >= 2:
        baseline = labels[0]
        for label in labels[1:]:
            comparison_df[f'{label}_vs_{baseline}_improvement_%'] = (
                (comparison_df[label] - comparison_df[baseline]) / 
                comparison_df[baseline] * 100
            )
    
    print(comparison_df.to_string(index=False))
    
    # Save comparison
    comparison_df.to_csv("evaluation_results/comparison.csv", index=False)
    print()
    print("✅ Comparison saved to: evaluation_results/comparison.csv")
    
    return comparison_df


# CLI Interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG System Evaluation Test")
    parser.add_argument(
        "--mode",
        choices=["basic", "comprehensive", "compare", "template"],
        default="basic",
        help="Evaluation mode"
    )
    parser.add_argument(
        "--data-file",
        type=str,
        help="Path to test data JSON file"
    )
    parser.add_argument(
        "--compare-files",
        nargs="+",
        help="CSV files to compare (for compare mode)"
    )
    parser.add_argument(
        "--no-bertscore",
        action="store_true",
        help="Skip BERTScore calculation (faster)"
    )
    
    args = parser.parse_args()
    
    if args.mode == "template":
        # Create template file
        TestDataGenerator.create_json_template()
        
    elif args.mode == "basic":
        # Run basic test
        asyncio.run(run_basic_test())
        
    elif args.mode == "comprehensive":
        # Run comprehensive test
        asyncio.run(run_comprehensive_test(args.data_file))
        
    elif args.mode == "compare":
        # Compare evaluations
        if not args.compare_files or len(args.compare_files) < 2:
            print("❌ Error: Need at least 2 files to compare")
            print("Usage: --mode compare --compare-files file1.csv file2.csv")
        else:
            compare_evaluations(args.compare_files)