#!/bin/bash
# Run all optimization tests

echo "╔════════════════════════════════════════════════════════════════════════╗"
echo "║          OPTIMIZATION TESTING SUITE                                    ║"
echo "╚════════════════════════════════════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")/.."

echo "Select test to run:"
echo ""
echo "  1) Quick validation tests (no API calls)"
echo "  2) Pipeline timing tests (measures LLM + TTS)"
echo "  3) Full benchmark (compares baseline vs optimized)"
echo "  4) Run all tests"
echo ""
read -p "Enter choice [1-4]: " choice

case $choice in
    1)
        echo ""
        echo "Running validation tests..."
        echo ""
        uv run python scripts/test_optimizations.py
        ;;
    2)
        echo ""
        echo "Running pipeline timing tests..."
        echo "⚠️  This will make real API calls to OpenRouter"
        echo ""
        read -p "Continue? (y/N): " confirm
        if [[ $confirm == [yY] ]]; then
            uv run python scripts/test_pipeline_timing.py
        else
            echo "Cancelled"
        fi
        ;;
    3)
        echo ""
        echo "Running full benchmark..."
        echo "⚠️  This will make many API calls to OpenRouter"
        echo ""
        read -p "Continue? (y/N): " confirm
        if [[ $confirm == [yY] ]]; then
            uv run python scripts/benchmark_optimizations.py
        else
            echo "Cancelled"
        fi
        ;;
    4)
        echo ""
        echo "Running ALL tests..."
        echo ""
        echo "═══════════════════════════════════════════════════════════════════════"
        echo "TEST 1: Validation Tests"
        echo "═══════════════════════════════════════════════════════════════════════"
        uv run python scripts/test_optimizations.py <<< "n"

        echo ""
        echo "═══════════════════════════════════════════════════════════════════════"
        echo "TEST 2: Pipeline Timing (requires API calls)"
        echo "═══════════════════════════════════════════════════════════════════════"
        read -p "Run pipeline timing tests? (y/N): " confirm1
        if [[ $confirm1 == [yY] ]]; then
            uv run python scripts/test_pipeline_timing.py
        fi

        echo ""
        echo "═══════════════════════════════════════════════════════════════════════"
        echo "TEST 3: Full Benchmark (requires many API calls)"
        echo "═══════════════════════════════════════════════════════════════════════"
        read -p "Run full benchmark? (y/N): " confirm2
        if [[ $confirm2 == [yY] ]]; then
            uv run python scripts/benchmark_optimizations.py
        fi
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "╔════════════════════════════════════════════════════════════════════════╗"
echo "║          TESTS COMPLETE                                                 ║"
echo "╚════════════════════════════════════════════════════════════════════════╝"
