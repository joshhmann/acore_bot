#!/usr/bin/env python3
"""Performance profiling script for acore_bot.

This script provides tools for profiling the bot's performance to identify bottlenecks.

Usage:
    # Profile with py-spy (requires separate installation: pip install py-spy)
    sudo py-spy record -o profile.svg --pid <bot_pid>

    # Profile with cProfile (built-in)
    python scripts/profile_performance.py --mode cprofile --duration 60

    # Memory profiling
    python scripts/profile_performance.py --mode memory --duration 60
"""

import argparse
import cProfile
import io
import pstats
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def profile_with_cprofile(duration_seconds: int):
    """Profile bot execution with cProfile.

    Args:
        duration_seconds: How long to profile
    """
    print(f"Starting cProfile profiling for {duration_seconds} seconds...")

    profiler = cProfile.Profile()
    profiler.enable()

    # Import and run bot
    try:

        # Note: This would need the bot to be structured to run for a specific duration
        # For now, this is a template - actual implementation depends on bot structure
        print("Note: Actual bot profiling requires bot to be running")
        print("Use py-spy for live profiling instead:")
        print("  sudo py-spy record -o profile.svg --pid $(pgrep -f main.py)")

    except KeyboardInterrupt:
        pass
    finally:
        profiler.disable()

        # Generate report
        output = io.StringIO()
        stats = pstats.Stats(profiler, stream=output)

        # Sort by cumulative time
        stats.sort_stats("cumulative")
        stats.print_stats(50)  # Top 50 functions

        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = Path(f"profile_report_{timestamp}.txt")

        with open(report_file, "w") as f:
            f.write(output.getvalue())

        print(f"\nProfile report saved to: {report_file}")
        print("\nTop 10 functions by cumulative time:")
        stats.print_stats(10)


def profile_memory():
    """Generate memory profiling instructions."""
    print("Memory Profiling Guide")
    print("=" * 60)
    print()
    print("1. Install memory_profiler:")
    print("   pip install memory-profiler")
    print()
    print("2. Add @profile decorator to functions you want to profile")
    print()
    print("3. Run with:")
    print("   python -m memory_profiler main.py")
    print()
    print("4. For line-by-line memory usage:")
    print("   mprof run main.py")
    print("   mprof plot")
    print()
    print("5. For memory over time (running bot):")
    print("   # In one terminal:")
    print("   mprof run --python main.py")
    print("   # In another terminal (after some time):")
    print("   mprof plot")
    print()


def analyze_existing_profile(profile_file: str):
    """Analyze an existing .prof file.

    Args:
        profile_file: Path to .prof file
    """
    if not Path(profile_file).exists():
        print(f"Error: Profile file not found: {profile_file}")
        return

    stats = pstats.Stats(profile_file)

    print("\n" + "=" * 60)
    print("PROFILE ANALYSIS")
    print("=" * 60)

    # Top functions by cumulative time
    print("\nTop 20 functions by cumulative time:")
    print("-" * 60)
    stats.sort_stats("cumulative")
    stats.print_stats(20)

    # Top functions by time spent in function itself
    print("\nTop 20 functions by internal time:")
    print("-" * 60)
    stats.sort_stats("time")
    stats.print_stats(20)

    # Most called functions
    print("\nTop 20 most called functions:")
    print("-" * 60)
    stats.sort_stats("calls")
    stats.print_stats(20)


def print_profiling_guide():
    """Print comprehensive profiling guide."""
    guide = """
    ╔══════════════════════════════════════════════════════════════════╗
    ║           ACORE BOT PERFORMANCE PROFILING GUIDE                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    
    RECOMMENDED APPROACH: py-spy (Low Overhead, Production-Safe)
    ────────────────────────────────────────────────────────────────────
    
    1. Install py-spy:
       pip install py-spy
       
    2. Start your bot normally:
       python main.py
       
    3. In another terminal, find the bot's process ID:
       pgrep -f main.py
       
    4. Start profiling (requires sudo):
       sudo py-spy record -o profile.svg --pid <PID> --duration 60
       
    5. Generate flamegraph for 5 minutes:
       sudo py-spy record -o flamegraph.svg --pid <PID> --duration 300
       
    6. Open the SVG file in a browser to analyze
    
    
    ALTERNATIVE: cProfile (Built-in, Higher Overhead)
    ────────────────────────────────────────────────────────────────────
    
    For specific function profiling, add to your code:
    
        import cProfile
        import pstats
        
        profiler = cProfile.Profile()
        profiler.enable()
        
        # Your code here
        await some_function()
        
        profiler.disable()
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        stats.print_stats(20)
    
    
    MEMORY PROFILING
    ────────────────────────────────────────────────────────────────────
    
    1. Install memory_profiler:
       pip install memory-profiler
       
    2. Track memory over time:
       mprof run python main.py
       # Let it run for a while, then Ctrl+C
       mprof plot  # Generates memory usage graph
       
    3. For specific function memory usage, add decorator:
       @profile
       def my_function():
           pass
       
       Then run: python -m memory_profiler main.py
    
    
    ANALYZING BOTTLENECKS
    ────────────────────────────────────────────────────────────────────
    
    Look for:
    1. Functions with high cumulative time (hot paths)
    2. Functions called many times (optimization opportunities)
    3. Blocking I/O operations (convert to async)
    4. Memory growth over time (potential leaks)
    
    Common bottlenecks in this codebase:
    - LLM API calls (should use caching/deduplication)
    - File I/O (should use async file operations)
    - Large data structure iterations (consider generators)
    - Synchronous HTTP requests (use aiohttp)
    
    
    METRICS DASHBOARD
    ────────────────────────────────────────────────────────────────────
    
    The bot includes a built-in metrics service. Check:
    
        from services.metrics import MetricsService
        stats = metrics_service.get_summary()
        
    Response time percentiles:
        stats['response_times']['p95']  # 95th percentile
        stats['response_times']['p99']  # 99th percentile
        
    Cache hit rates:
        stats['cache_stats']['history_cache']['hit_rate']
        
    Deduplication stats:
        stats['cache_stats']['deduplication']
    
    
    BENCHMARK BEFORE/AFTER
    ────────────────────────────────────────────────────────────────────
    
    1. Run profiling BEFORE optimization
    2. Note the top bottlenecks and their times
    3. Implement optimization
    4. Run profiling AFTER optimization
    5. Compare the results
    
    Example benchmarking script in scripts/benchmark_optimizations.py
    
    ╔══════════════════════════════════════════════════════════════════╗
    ║  For questions, see: docs/PERFORMANCE.md                         ║
    ╚══════════════════════════════════════════════════════════════════╝
    """
    print(guide)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Performance profiling tools for acore_bot"
    )
    parser.add_argument(
        "--mode",
        choices=["guide", "cprofile", "memory", "analyze"],
        default="guide",
        help="Profiling mode",
    )
    parser.add_argument(
        "--duration", type=int, default=60, help="Duration in seconds for profiling"
    )
    parser.add_argument(
        "--profile-file", type=str, help="Path to existing .prof file to analyze"
    )

    args = parser.parse_args()

    if args.mode == "guide":
        print_profiling_guide()
    elif args.mode == "cprofile":
        profile_with_cprofile(args.duration)
    elif args.mode == "memory":
        profile_memory()
    elif args.mode == "analyze":
        if not args.profile_file:
            print("Error: --profile-file required for analyze mode")
            sys.exit(1)
        analyze_existing_profile(args.profile_file)


if __name__ == "__main__":
    main()
