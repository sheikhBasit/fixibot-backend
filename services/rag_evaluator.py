"""
RAG Evaluation System for Multimodal Mechanic Finder Chatbot
Main evaluation module with all metrics implementation
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

# NLP Metrics
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer
try:
    from bert_score import score as bert_score
    BERTSCORE_AVAILABLE = True
except ImportError:
    BERTSCORE_AVAILABLE = False
    print("⚠️  BERTScore not available. Install with: pip install bert-score transformers")

# Statistical
from scipy import stats


@dataclass
class EvaluationData:
    """Data structure for a single evaluation instance"""
    query_id: str
    query_text: str
    retrieved_doc_ids: List[str]
    relevant_doc_ids: List[str]
    similarity_scores: List[float]
    generated_text: str
    reference_text: str
    start_time: float
    end_time: float
    metadata: Optional[Dict] = None


class RetrievalMetrics:
    """Calculate retrieval performance metrics"""
    
    @staticmethod
    def top_k_accuracy(retrieved_docs: List[List[str]], 
                       relevant_docs: List[List[str]], 
                       k: int = 3) -> float:
        """
        Calculate Top-k Accuracy
        
        Args:
            retrieved_docs: List of lists of retrieved document IDs per query
            relevant_docs: List of lists of ground-truth relevant document IDs per query
            k: Number of top results to consider
            
        Returns:
            Top-k accuracy score (0-1)
        """
        correct = 0
        total = len(retrieved_docs)
        
        for retrieved, relevant in zip(retrieved_docs, relevant_docs):
            # Check if any relevant doc is in top-k retrieved
            top_k = retrieved[:k]
            if any(doc in relevant for doc in top_k):
                correct += 1
                
        return correct / total if total > 0 else 0.0
    
    @staticmethod
    def precision_at_k(retrieved_docs: List[List[str]], 
                       relevant_docs: List[List[str]], 
                       k: int = 3) -> float:
        """
        Calculate Precision@k
        
        Returns:
            Average Precision@k across all queries
        """
        precisions = []
        
        for retrieved, relevant in zip(retrieved_docs, relevant_docs):
            top_k = retrieved[:k]
            relevant_in_top_k = sum(1 for doc in top_k if doc in relevant)
            precision = relevant_in_top_k / k
            precisions.append(precision)
            
        return np.mean(precisions) if precisions else 0.0
    
    @staticmethod
    def mean_average_precision(retrieved_docs: List[List[str]], 
                                relevant_docs: List[List[str]]) -> float:
        """
        Calculate Mean Average Precision (mAP)
        
        Returns:
            mAP score across all queries
        """
        average_precisions = []
        
        for retrieved, relevant in zip(retrieved_docs, relevant_docs):
            if not relevant:
                continue
                
            precisions_at_k = []
            num_relevant_found = 0
            
            for k, doc in enumerate(retrieved, 1):
                if doc in relevant:
                    num_relevant_found += 1
                    precision_at_k = num_relevant_found / k
                    precisions_at_k.append(precision_at_k)
            
            if precisions_at_k:
                avg_precision = np.mean(precisions_at_k)
                average_precisions.append(avg_precision)
        
        return np.mean(average_precisions) if average_precisions else 0.0
    
    @staticmethod
    def recall_at_k(retrieved_docs: List[List[str]], 
                    relevant_docs: List[List[str]], 
                    k: int = 3) -> float:
        """
        Calculate Recall@k
        
        Returns:
            Average Recall@k across all queries
        """
        recalls = []
        
        for retrieved, relevant in zip(retrieved_docs, relevant_docs):
            if not relevant:
                continue
                
            top_k = retrieved[:k]
            relevant_in_top_k = sum(1 for doc in top_k if doc in relevant)
            recall = relevant_in_top_k / len(relevant)
            recalls.append(recall)
            
        return np.mean(recalls) if recalls else 0.0
    
    @staticmethod
    def mean_reciprocal_rank(retrieved_docs: List[List[str]], 
                            relevant_docs: List[List[str]]) -> float:
        """
        Calculate Mean Reciprocal Rank (MRR)
        
        Returns:
            MRR score across all queries
        """
        reciprocal_ranks = []
        
        for retrieved, relevant in zip(retrieved_docs, relevant_docs):
            for rank, doc in enumerate(retrieved, 1):
                if doc in relevant:
                    reciprocal_ranks.append(1.0 / rank)
                    break
            else:
                reciprocal_ranks.append(0.0)
        
        return np.mean(reciprocal_ranks) if reciprocal_ranks else 0.0


class ResponseQualityMetrics:
    """Calculate response quality metrics"""
    
    def __init__(self):
        self.rouge_scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=True)
        self.smoothing = SmoothingFunction().method1
    
    def calculate_bleu(self, generated_texts: List[str], 
                      reference_texts: List[str],
                      max_n: int = 4) -> Dict[str, float]:
        """
        Calculate BLEU scores (BLEU-1 to BLEU-4)
        
        Returns:
            Dictionary with BLEU-1, BLEU-2, BLEU-3, BLEU-4 scores
        """
        bleu_scores = {f'BLEU-{n}': [] for n in range(1, max_n + 1)}
        
        for generated, reference in zip(generated_texts, reference_texts):
            gen_tokens = generated.lower().split()
            ref_tokens = [reference.lower().split()]
            
            for n in range(1, max_n + 1):
                weights = tuple([1.0/n] * n + [0.0] * (max_n - n))
                score = sentence_bleu(ref_tokens, gen_tokens, 
                                     weights=weights,
                                     smoothing_function=self.smoothing)
                bleu_scores[f'BLEU-{n}'].append(score)
        
        return {key: np.mean(scores) for key, scores in bleu_scores.items()}
    
    def calculate_rouge_l(self, generated_texts: List[str], 
                         reference_texts: List[str]) -> Dict[str, float]:
        """
        Calculate ROUGE-L scores
        
        Returns:
            Dictionary with precision, recall, and F1 for ROUGE-L
        """
        rouge_scores = {'precision': [], 'recall': [], 'fmeasure': []}
        
        for generated, reference in zip(generated_texts, reference_texts):
            scores = self.rouge_scorer.score(reference, generated)
            rouge_scores['precision'].append(scores['rougeL'].precision)
            rouge_scores['recall'].append(scores['rougeL'].recall)
            rouge_scores['fmeasure'].append(scores['rougeL'].fmeasure)
        
        return {
            'ROUGE-L_Precision': np.mean(rouge_scores['precision']),
            'ROUGE-L_Recall': np.mean(rouge_scores['recall']),
            'ROUGE-L_F1': np.mean(rouge_scores['fmeasure'])
        }
    
    @staticmethod
    def calculate_bertscore(generated_texts: List[str], 
                           reference_texts: List[str],
                           model_type: str = "microsoft/deberta-base-mnli") -> Dict[str, float]:
        """
        Calculate BERTScore
        
        Args:
            model_type: Pretrained model to use. Options:
                - "microsoft/deberta-xlarge-mnli" (recommended, slow)
                - "microsoft/deberta-base-mnli" (faster)
                - "bert-base-uncased" (fastest)
        
        Returns:
            Dictionary with precision, recall, and F1 for BERTScore
        """
        if not BERTSCORE_AVAILABLE:
            print("⚠️  BERTScore not available. Skipping...")
            return {
                'BERTScore_Precision': 0.0,
                'BERTScore_Recall': 0.0,
                'BERTScore_F1': 0.0
            }
        
        P, R, F1 = bert_score(generated_texts, reference_texts, 
                              model_type=model_type, 
                              verbose=False)
        
        return {
            'BERTScore_Precision': P.mean().item(),
            'BERTScore_Recall': R.mean().item(),
            'BERTScore_F1': F1.mean().item()
        }


class LatencyMetrics:
    """Calculate latency and performance metrics"""
    
    @staticmethod
    def calculate_latencies(start_times: List[float], 
                          end_times: List[float]) -> Dict[str, float]:
        """
        Calculate comprehensive latency metrics
        
        Returns:
            Dictionary with various latency statistics
        """
        latencies = [end - start for start, end in zip(start_times, end_times)]
        
        return {
            'Avg_Latency_s': np.mean(latencies),
            'Median_Latency_s': np.median(latencies),
            'Min_Latency_s': np.min(latencies),
            'Max_Latency_s': np.max(latencies),
            'Std_Latency_s': np.std(latencies),
            'P50_Latency_s': np.percentile(latencies, 50),
            'P90_Latency_s': np.percentile(latencies, 90),
            'P95_Latency_s': np.percentile(latencies, 95),
            'P99_Latency_s': np.percentile(latencies, 99)
        }
    
    @staticmethod
    def calculate_throughput(start_times: List[float], 
                           end_times: List[float]) -> float:
        """
        Calculate queries per second
        
        Returns:
            Average throughput in queries/second
        """
        if not start_times:
            return 0.0
            
        total_time = max(end_times) - min(start_times)
        return len(start_times) / total_time if total_time > 0 else 0.0


class RAGEvaluator:
    """Main evaluator class that coordinates all metrics"""
    
    def __init__(self):
        self.retrieval_metrics = RetrievalMetrics()
        self.response_metrics = ResponseQualityMetrics()
        self.latency_metrics = LatencyMetrics()
        
    def evaluate(self, eval_data: List[EvaluationData], 
                 k_values: List[int] = [1, 3, 5],
                 calculate_bertscore: bool = True) -> pd.DataFrame:
        """
        Comprehensive evaluation of RAG system
        
        Args:
            eval_data: List of EvaluationData instances
            k_values: List of k values for top-k metrics
            calculate_bertscore: Whether to calculate BERTScore (can be slow)
            
        Returns:
            DataFrame with all evaluation metrics
        """
        print("Starting comprehensive RAG evaluation...")
        
        # Extract data
        retrieved_docs = [d.retrieved_doc_ids for d in eval_data]
        relevant_docs = [d.relevant_doc_ids for d in eval_data]
        generated_texts = [d.generated_text for d in eval_data]
        reference_texts = [d.reference_text for d in eval_data]
        start_times = [d.start_time for d in eval_data]
        end_times = [d.end_time for d in eval_data]
        
        results = {}
        
        # 1. Retrieval Metrics
        print("Calculating retrieval metrics...")
        for k in k_values:
            results[f'Top-{k}_Accuracy'] = self.retrieval_metrics.top_k_accuracy(
                retrieved_docs, relevant_docs, k)
            results[f'Precision@{k}'] = self.retrieval_metrics.precision_at_k(
                retrieved_docs, relevant_docs, k)
            results[f'Recall@{k}'] = self.retrieval_metrics.recall_at_k(
                retrieved_docs, relevant_docs, k)
        
        results['Mean_Avg_Precision'] = self.retrieval_metrics.mean_average_precision(
            retrieved_docs, relevant_docs)
        results['Mean_Reciprocal_Rank'] = self.retrieval_metrics.mean_reciprocal_rank(
            retrieved_docs, relevant_docs)
        
        # 2. Response Quality Metrics
        print("Calculating response quality metrics...")
        
        # BLEU scores
        bleu_scores = self.response_metrics.calculate_bleu(
            generated_texts, reference_texts)
        results.update(bleu_scores)
        
        # ROUGE-L scores
        rouge_scores = self.response_metrics.calculate_rouge_l(
            generated_texts, reference_texts)
        results.update(rouge_scores)
        
        # BERTScore (optional, can be slow)
        if calculate_bertscore and BERTSCORE_AVAILABLE:
            print("Calculating BERTScore (this may take a while)...")
            bert_scores = self.response_metrics.calculate_bertscore(
                generated_texts, reference_texts)
            results.update(bert_scores)
        
        # 3. Latency Metrics
        print("Calculating latency metrics...")
        latency_stats = self.latency_metrics.calculate_latencies(
            start_times, end_times)
        results.update(latency_stats)
        
        # Throughput
        results['Throughput_QPS'] = self.latency_metrics.calculate_throughput(
            start_times, end_times)
        
        # Create organized DataFrame
        df = self._organize_results(results)
        
        print("Evaluation complete!")
        return df
    
    @staticmethod
    def _organize_results(results: Dict[str, float]) -> pd.DataFrame:
        """Organize results into categorized DataFrame"""
        
        categories = {
            'Retrieval': [k for k in results.keys() if any(x in k for x in 
                         ['Top-', 'Precision@', 'Recall@', 'Mean_Avg', 'Reciprocal'])],
            'Response': [k for k in results.keys() if any(x in k for x in 
                        ['BLEU', 'ROUGE', 'BERTScore'])],
            'Latency': [k for k in results.keys() if any(x in k for x in 
                       ['Latency', 'Throughput'])]
        }
        
        data = []
        for category, metrics in categories.items():
            for metric in metrics:
                data.append({
                    'Category': category,
                    'Metric': metric,
                    'Value': results[metric]
                })
        
        df = pd.DataFrame(data)
        return df
    
    def save_results(self, df: pd.DataFrame, output_path: str):
        """Save evaluation results to CSV, JSON, and Markdown"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save as CSV
        csv_path = output_path.with_suffix('.csv')
        df.to_csv(csv_path, index=False)
        print(f"Results saved to {csv_path}")
        
        # Save as JSON
        json_path = output_path.with_suffix('.json')
        results_dict = df.set_index(['Category', 'Metric'])['Value'].to_dict()
        with open(json_path, 'w') as f:
            json.dump(results_dict, f, indent=2)
        print(f"Results saved to {json_path}")
        
        # Save formatted markdown
        md_path = output_path.with_suffix('.md')
        with open(md_path, 'w') as f:
            f.write("# RAG System Evaluation Results\n\n")
            f.write(f"**Evaluation Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for category in df['Category'].unique():
                f.write(f"## {category} Metrics\n\n")
                category_df = df[df['Category'] == category]
                f.write(category_df[['Metric', 'Value']].to_markdown(index=False))
                f.write("\n\n")
        
        print(f"Results saved to {md_path}")


# Example usage
if __name__ == "__main__":
    import time
    
    # Sample data
    eval_data = [
        EvaluationData(
            query_id="q1",
            query_text="How to fix brake problems?",
            retrieved_doc_ids=["doc1", "doc3", "doc5"],
            relevant_doc_ids=["doc1", "doc2"],
            similarity_scores=[0.95, 0.87, 0.72],
            generated_text="Check brake pads and fluid levels first.",
            reference_text="Inspect brake pads for wear and check brake fluid.",
            start_time=time.time(),
            end_time=time.time() + 1.5
        ),
    ]
    
    evaluator = RAGEvaluator()
    results_df = evaluator.evaluate(eval_data, k_values=[1, 3, 5])
    print(results_df)
    evaluator.save_results(results_df, "evaluation_results/test_eval")