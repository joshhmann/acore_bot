#!/usr/bin/env python3
"""Benchmark script to measure actual performance improvements.

This script makes real API calls to compare optimized vs non-optimized performance.
"""
import asyncio
import time
import statistics
from pathlib import Path
import sys
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from services.response_optimizer import ResponseOptimizer
from services.openrouter import OpenRouterService


# Benchmark test queries
BENCHMARK_QUERIES = [
    # Format: (query, expected_type, description)
    ("hi", "greeting", "Simple greeting"),
    ("hello there", "greeting", "Greeting with extra word"),
    ("what time is it?", "simple_question", "Simple time question"),
    ("who are you?", "simple_question", "Identity question"),
    ("explain how machine learning works", "complex_question", "Complex explanation"),
    ("tell me about quantum computing", "complex_question", "Technical topic"),
]


class PerformanceBenchmark:
    """Benchmark harness for testing optimizations."""

    def __init__(self):
        """Initialize benchmark."""
        self.results = []
        self.llm = None

    async def initialize(self):
        """Initialize LLM service."""
        if Config.LLM_PROVIDER != "openrouter":
            raise ValueError("Benchmark only works with OpenRouter")

        self.llm = OpenRouterService(
            api_key=Config.OPENROUTER_API_KEY,
            model=Config.OPENROUTER_MODEL,
            max_tokens=Config.OLLAMA_MAX_TOKENS or 1000,
        )
        await self.llm.initialize()
        print(f"✓ Initialized OpenRouter with model: {Config.OPENROUTER_MODEL}")

    async def benchmark_query(
        self,
        query: str,
        use_optimization: bool,
        query_type: str,
        description: str
    ) -> dict:
        """Benchmark a single query.

        Args:
            query: Query text
            use_optimization: Whether to use dynamic token optimization
            query_type: Expected query type
            description: Human-readable description

        Returns:
            Dict with benchmark results
        """
        # Determine max_tokens
        if use_optimization:
            optimal_tokens, reasoning = ResponseOptimizer.estimate_optimal_tokens(query)
        else:
            optimal_tokens = Config.OLLAMA_MAX_TOKENS or 1000
            reasoning = "Default allocation"

        # Make request
        messages = [{"role": "user", "content": query}]
        system_prompt = "You are a helpful AI assistant. Be concise and direct."

        start_time = time.time()

        try:
            response = await self.llm.chat(
                messages,
                system_prompt=system_prompt,
                max_tokens=optimal_tokens
            )

            duration = time.time() - start_time

            # Calculate metrics
            response_length = len(response)
            word_count = len(response.split())
            tokens_generated = self.llm.total_tokens_generated  # Approximate

            result = {
                'query': query,
                'query_type': query_type,
                'description': description,
                'optimized': use_optimization,
                'max_tokens': optimal_tokens,
                'reasoning': reasoning,
                'duration_ms': duration * 1000,
                'duration_s': duration,
                'response_length': response_length,
                'word_count': word_count,
                'response': response[:100] + "..." if len(response) > 100 else response,
                'tps': self.llm.last_tps,
                'timestamp': datetime.now().isoformat(),
            }

            return result

        except Exception as e:
            return {
                'query': query,
                'query_type': query_type,
                'description': description,
                'optimized': use_optimization,
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
            }

    async def run_benchmark(self, num_iterations: int = 1):
        """Run complete benchmark suite.

        Args:
            num_iterations: Number of times to run each query
        """
        print("\n" + "="*80)
        print("PERFORMANCE BENCHMARK")
        print("="*80)
        print(f"\nIterations per query: {num_iterations}")
        print(f"Total queries: {len(BENCHMARK_QUERIES) * 2 * num_iterations}")
        print(f"Provider: {Config.LLM_PROVIDER}")
        print(f"Model: {Config.OPENROUTER_MODEL}\n")

        all_results = []

        for iteration in range(num_iterations):
            print(f"\n{'─'*80}")
            print(f"Iteration {iteration + 1}/{num_iterations}")
            print(f"{'─'*80}\n")

            for query, expected_type, description in BENCHMARK_QUERIES:
                # Test WITHOUT optimization
                print(f"Testing: {description} (baseline)...", end=" ", flush=True)
                result_baseline = await self.benchmark_query(
                    query, False, expected_type, description
                )
                all_results.append(result_baseline)

                if 'error' in result_baseline:
                    print(f"❌ Error: {result_baseline['error']}")
                else:
                    print(f"✓ {result_baseline['duration_ms']:.0f}ms")

                await asyncio.sleep(0.5)  # Rate limit protection

                # Test WITH optimization
                print(f"Testing: {description} (optimized)...", end=" ", flush=True)
                result_optimized = await self.benchmark_query(
                    query, True, expected_type, description
                )
                all_results.append(result_optimized)

                if 'error' in result_optimized:
                    print(f"❌ Error: {result_optimized['error']}")
                else:
                    improvement = (
                        (result_baseline['duration_ms'] - result_optimized['duration_ms'])
                        / result_baseline['duration_ms'] * 100
                    )
                    print(f"✓ {result_optimized['duration_ms']:.0f}ms ({improvement:+.1f}%)")

                await asyncio.sleep(0.5)  # Rate limit protection

        self.results = all_results
        return all_results

    def analyze_results(self):
        """Analyze and print benchmark results."""
        if not self.results:
            print("No results to analyze")
            return

        # Filter out errors
        valid_results = [r for r in self.results if 'error' not in r]

        if not valid_results:
            print("All queries failed")
            return

        print("\n" + "="*80)
        print("BENCHMARK RESULTS")
        print("="*80)

        # Group by query type
        by_type = {}
        for result in valid_results:
            qtype = result['query_type']
            if qtype not in by_type:
                by_type[qtype] = {'baseline': [], 'optimized': []}

            if result['optimized']:
                by_type[qtype]['optimized'].append(result)
            else:
                by_type[qtype]['baseline'].append(result)

        # Calculate statistics by query type
        print("\n" + "─"*80)
        print("By Query Type:")
        print("─"*80)

        for qtype, results in sorted(by_type.items()):
            if not results['baseline'] or not results['optimized']:
                continue

            baseline_times = [r['duration_ms'] for r in results['baseline']]
            optimized_times = [r['duration_ms'] for r in results['optimized']]

            avg_baseline = statistics.mean(baseline_times)
            avg_optimized = statistics.mean(optimized_times)
            improvement = (avg_baseline - avg_optimized) / avg_baseline * 100

            baseline_tokens = statistics.mean([r['max_tokens'] for r in results['baseline']])
            optimized_tokens = statistics.mean([r['max_tokens'] for r in results['optimized']])

            print(f"\n{qtype.upper().replace('_', ' ')}:")
            print(f"  Baseline:  {avg_baseline:7.0f}ms | {baseline_tokens:4.0f} max tokens")
            print(f"  Optimized: {avg_optimized:7.0f}ms | {optimized_tokens:4.0f} max tokens")
            print(f"  Improvement: {improvement:+.1f}% ({avg_baseline - avg_optimized:.0f}ms saved)")

        # Overall statistics
        print("\n" + "─"*80)
        print("Overall Performance:")
        print("─"*80)

        baseline_all = [r['duration_ms'] for r in valid_results if not r['optimized']]
        optimized_all = [r['duration_ms'] for r in valid_results if r['optimized']]

        if baseline_all and optimized_all:
            avg_baseline_all = statistics.mean(baseline_all)
            avg_optimized_all = statistics.mean(optimized_all)
            overall_improvement = (avg_baseline_all - avg_optimized_all) / avg_baseline_all * 100

            print(f"\nAverage baseline:  {avg_baseline_all:.0f}ms")
            print(f"Average optimized: {avg_optimized_all:.0f}ms")
            print(f"Overall improvement: {overall_improvement:+.1f}%")

        # Token efficiency
        print("\n" + "─"*80)
        print("Token Efficiency:")
        print("─"*80)

        baseline_tokens_all = [r['max_tokens'] for r in valid_results if not r['optimized']]
        optimized_tokens_all = [r['max_tokens'] for r in valid_results if r['optimized']]

        if baseline_tokens_all and optimized_tokens_all:
            avg_baseline_tokens = statistics.mean(baseline_tokens_all)
            avg_optimized_tokens = statistics.mean(optimized_tokens_all)
            token_reduction = (avg_baseline_tokens - avg_optimized_tokens) / avg_baseline_tokens * 100

            print(f"\nAverage baseline tokens:  {avg_baseline_tokens:.0f}")
            print(f"Average optimized tokens: {avg_optimized_tokens:.0f}")
            print(f"Token reduction: {token_reduction:.1f}%")

    def save_results(self, filename: str = None):
        """Save results to JSON file.

        Args:
            filename: Optional filename, defaults to timestamped name
        """
        if not self.results:
            print("No results to save")
            return

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_results_{timestamp}.json"

        output_dir = Path(__file__).parent.parent / "data" / "benchmarks"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / filename

        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'config': {
                    'provider': Config.LLM_PROVIDER,
                    'model': Config.OPENROUTER_MODEL,
                    'streaming_threshold': Config.STREAMING_TOKEN_THRESHOLD,
                    'default_max_tokens': Config.OLLAMA_MAX_TOKENS or 1000,
                },
                'results': self.results,
            }, f, indent=2)

        print(f"\n✓ Results saved to: {output_file}")

    async def cleanup(self):
        """Clean up resources."""
        if self.llm:
            await self.llm.close()


async def main():
    """Main benchmark runner."""
    benchmark = PerformanceBenchmark()

    try:
        # Initialize
        await benchmark.initialize()

        # Get iterations count
        print("\nHow many iterations per query? (default: 1): ", end="", flush=True)
        try:
            iterations_input = input().strip()
            iterations = int(iterations_input) if iterations_input else 1
        except ValueError:
            iterations = 1

        # Run benchmark
        await benchmark.run_benchmark(num_iterations=iterations)

        # Analyze results
        benchmark.analyze_results()

        # Save results
        benchmark.save_results()

        print("\n" + "="*80)
        print("BENCHMARK COMPLETE")
        print("="*80)

    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
    except Exception as e:
        print(f"\n\nError during benchmark: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await benchmark.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
