#!/usr/bin/env python3
"""Analyze bot performance metrics and identify bottlenecks.

This script analyzes logs and metrics to show:
- Average response times
- TPS distribution
- Streaming vs non-streaming performance
- Bottleneck identification
"""

import re
import sys
import statistics


def parse_log_line(line):
    """Parse OpenRouter performance log line."""
    # OpenRouter response: 7.02s | Tokens: 331 | TPS: 47.2 | Total: 3412
    match = re.search(r'OpenRouter response: ([\d.]+)s \| Tokens: (\d+) \| TPS: ([\d.]+)', line)
    if match:
        return {
            'type': 'non_streaming',
            'response_time': float(match.group(1)),
            'tokens': int(match.group(2)),
            'tps': float(match.group(3)),
        }

    # OpenRouter stream: 9.52s | ~54 tokens | TPS: 5.7 | TTFT: 8.38s
    match = re.search(r'OpenRouter stream: ([\d.]+)s \| ~(\d+) tokens \| TPS: ([\d.]+) \| TTFT: ([\d.]+)s', line)
    if match:
        return {
            'type': 'streaming',
            'response_time': float(match.group(1)),
            'tokens': int(match.group(2)),
            'tps': float(match.group(3)),
            'ttft': float(match.group(4)),
        }

    return None


def analyze_logs(log_file_or_lines):
    """Analyze performance from logs."""

    streaming_data = []
    non_streaming_data = []

    # Read from file or stdin
    if isinstance(log_file_or_lines, str):
        with open(log_file_or_lines) as f:
            lines = f.readlines()
    else:
        lines = log_file_or_lines

    for line in lines:
        data = parse_log_line(line)
        if data:
            if data['type'] == 'streaming':
                streaming_data.append(data)
            else:
                non_streaming_data.append(data)

    return streaming_data, non_streaming_data


def print_stats(label, data, key):
    """Print statistics for a metric."""
    values = [d[key] for d in data]
    if not values:
        return

    print(f"  {label}:")
    print(f"    Average: {statistics.mean(values):.2f}")
    print(f"    Median:  {statistics.median(values):.2f}")
    print(f"    Min:     {min(values):.2f}")
    print(f"    Max:     {max(values):.2f}")
    if len(values) > 1:
        print(f"    StdDev:  {statistics.stdev(values):.2f}")


def analyze_performance(streaming_data, non_streaming_data):
    """Analyze and print performance statistics."""

    print("=" * 60)
    print("🔍 BOT PERFORMANCE ANALYSIS")
    print("=" * 60)
    print()

    # Overall stats
    total_requests = len(streaming_data) + len(non_streaming_data)
    print("📊 OVERALL STATISTICS")
    print(f"  Total Requests: {total_requests}")
    print(f"  Streaming: {len(streaming_data)} ({len(streaming_data)/total_requests*100:.1f}%)")
    print(f"  Non-Streaming: {len(non_streaming_data)} ({len(non_streaming_data)/total_requests*100:.1f}%)")
    print()

    # Streaming performance
    if streaming_data:
        print("🌊 STREAMING PERFORMANCE")
        print_stats("Response Time (seconds)", streaming_data, 'response_time')
        print_stats("TPS (tokens/second)", streaming_data, 'tps')
        print_stats("TTFT (time to first token)", streaming_data, 'ttft')
        print_stats("Token Count", streaming_data, 'tokens')
        print()

    # Non-streaming performance
    if non_streaming_data:
        print("⚡ NON-STREAMING PERFORMANCE")
        print_stats("Response Time (seconds)", non_streaming_data, 'response_time')
        print_stats("TPS (tokens/second)", non_streaming_data, 'tps')
        print_stats("Token Count", non_streaming_data, 'tokens')
        print()

    # Comparison
    if streaming_data and non_streaming_data:
        print("⚖️  STREAMING VS NON-STREAMING COMPARISON")

        stream_avg_time = statistics.mean([d['response_time'] for d in streaming_data])
        non_stream_avg_time = statistics.mean([d['response_time'] for d in non_streaming_data])
        stream_avg_tps = statistics.mean([d['tps'] for d in streaming_data])
        non_stream_avg_tps = statistics.mean([d['tps'] for d in non_streaming_data])

        print("  Avg Response Time:")
        print(f"    Streaming:     {stream_avg_time:.2f}s")
        print(f"    Non-Streaming: {non_stream_avg_time:.2f}s")
        print(f"    Difference:    {abs(stream_avg_time - non_stream_avg_time):.2f}s ({abs(stream_avg_time - non_stream_avg_time) / non_stream_avg_time * 100:.1f}%)")
        print()

        print("  Avg TPS:")
        print(f"    Streaming:     {stream_avg_tps:.1f} tokens/s")
        print(f"    Non-Streaming: {non_stream_avg_tps:.1f} tokens/s")
        print(f"    Ratio:         {non_stream_avg_tps / stream_avg_tps:.1f}x faster")
        print()

    # Bottleneck identification
    print("🚨 BOTTLENECK ANALYSIS")

    bottlenecks = []

    if streaming_data:
        avg_ttft = statistics.mean([d['ttft'] for d in streaming_data])
        avg_stream_tps = statistics.mean([d['tps'] for d in streaming_data])

        if avg_ttft > 5:
            bottlenecks.append(f"❌ CRITICAL: Streaming TTFT is {avg_ttft:.1f}s (should be < 3s)")

        if avg_stream_tps < 15:
            bottlenecks.append(f"❌ CRITICAL: Streaming TPS is {avg_stream_tps:.1f} (should be > 20)")

    if non_streaming_data:
        avg_response = statistics.mean([d['response_time'] for d in non_streaming_data])
        avg_tokens = statistics.mean([d['tokens'] for d in non_streaming_data])

        if avg_response > 10:
            bottlenecks.append(f"⚠️  WARNING: Average response time is {avg_response:.1f}s (target < 10s)")

        if avg_tokens > 600:
            bottlenecks.append(f"⚠️  WARNING: Average response is {avg_tokens:.0f} tokens (consider reducing)")

    if bottlenecks:
        for b in bottlenecks:
            print(f"  {b}")
    else:
        print("  ✅ No major bottlenecks detected!")
    print()

    # Recommendations
    print("💡 RECOMMENDATIONS")

    if streaming_data and non_streaming_data:
        if stream_avg_tps < non_stream_avg_tps * 0.5:
            print("  1. ⭐ Switch to non-streaming for short responses (< 300 tokens)")
            print("     Non-streaming is {:.1f}x faster!".format(non_stream_avg_tps / stream_avg_tps))

    if streaming_data and statistics.mean([d['ttft'] for d in streaming_data]) > 5:
        print("  2. ⭐ High TTFT detected - consider:")
        print("     - Switching OpenRouter model")
        print("     - Reducing context length")
        print("     - Using non-streaming mode")

    if non_streaming_data and statistics.mean([d['tokens'] for d in non_streaming_data]) > 500:
        print("  3. 🎯 Reduce response length:")
        print("     - Implement dynamic max_tokens")
        print("     - Use 200-400 tokens for casual chat")

    if streaming_data or non_streaming_data:
        all_data = streaming_data + non_streaming_data
        avg_time = statistics.mean([d['response_time'] for d in all_data])
        if avg_time > 8:
            print("  4. 🚀 Implement parallel TTS streaming:")
            print("     - Process sentences as they arrive")
            print("     - Estimated 60% reduction in time-to-first-audio")

    print()
    print("=" * 60)


def main():
    """Main entry point."""
    import subprocess

    # Check if input is piped
    if not sys.stdin.isatty():
        # Reading from pipe
        lines = sys.stdin.readlines()
    else:
        # Fetch from journalctl
        print("Fetching recent logs...")
        try:
            # Get last 500 lines from journalctl
            result = subprocess.run(
                ['journalctl', '-u', 'acore_bot', '-n', '500'],
                capture_output=True,
                text=True
            )
            lines = result.stdout.split('\n')
        except Exception as e:
            print(f"Error fetching logs: {e}")
            print("You can pipe logs manually:")
            print("  journalctl -u acore_bot -n 1000 | python3 scripts/analyze_performance.py")
            return 1

    streaming_data, non_streaming_data = analyze_logs(lines)

    if not streaming_data and not non_streaming_data:
        print("❌ No performance data found in logs.")
        print("Make sure the bot has processed some messages recently.")
        return 1

    analyze_performance(streaming_data, non_streaming_data)
    return 0


if __name__ == '__main__':
    sys.exit(main())
