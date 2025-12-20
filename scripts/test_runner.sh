#!/bin/bash
# Tiered Test Runner for acore_bot
# Runs tests based on tier (fast/integration/all) with proper error handling

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
cd "$(dirname "$0")/.."

echo "╔════════════════════════════════════════════════════════════════════════╗"
echo "║                ACORE BOT TIERED TEST RUNNER                            ║"
echo "╚════════════════════════════════════════════════════════════════════════╝"
echo ""

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Function to run tests with proper formatting
run_tests() {
    local tier=$1
    local marker=$2
    local description=$3

    echo ""
    echo "═══════════════════════════════════════════════════════════════════════"
    echo "  $description"
    echo "═══════════════════════════════════════════════════════════════════════"
    echo ""

    if [ "$marker" == "all" ]; then
        uv run pytest -v --tb=short
    else
        uv run pytest -m "$marker" -v --tb=short
    fi

    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        print_success "$description PASSED"
    elif [ $exit_code -eq 5 ]; then
        print_warning "$description - No tests found"
        return 0  # Don't fail if no tests exist yet
    else
        print_error "$description FAILED"
        return $exit_code
    fi

    return 0
}

# Parse command line arguments
TIER=${1:-help}

case $TIER in
    --fast|-f|fast|unit)
        print_info "Running TIER 1: Fast Unit Tests (<5s each)"
        print_info "These tests run on every commit"
        run_tests "1" "unit" "TIER 1: Unit Tests"
        ;;

    --integration|-i|integration)
        print_info "Running TIER 2: Integration Tests (5-30s)"
        print_info "These tests run on PR/merge"
        run_tests "2" "integration" "TIER 2: Integration Tests"
        ;;

    --e2e|e2e)
        print_info "Running TIER 3: End-to-End Tests (30s+)"
        print_info "These tests run pre-deploy"
        run_tests "3" "e2e" "TIER 3: E2E Tests"
        ;;

    --slow|-s|slow|benchmark)
        print_info "Running TIER 4: Performance/Benchmark Tests"
        print_info "These tests run weekly or manually"
        run_tests "4" "slow" "TIER 4: Performance Tests"
        ;;

    --all|-a|all)
        print_info "Running ALL test tiers sequentially"
        echo ""

        # Run each tier
        run_tests "1" "unit" "TIER 1: Unit Tests" || exit 1
        run_tests "2" "integration" "TIER 2: Integration Tests" || exit 1
        run_tests "3" "e2e" "TIER 3: E2E Tests" || exit 1

        # Ask before running slow tests
        echo ""
        print_warning "TIER 4 (Performance/Benchmark) tests can take a long time"
        read -p "Run TIER 4 tests? (y/N): " run_slow
        if [[ $run_slow == [yY] ]]; then
            run_tests "4" "slow" "TIER 4: Performance Tests" || exit 1
        fi
        ;;

    --coverage|-c|coverage)
        print_info "Running all tests with coverage analysis"
        echo ""
        echo "═══════════════════════════════════════════════════════════════════════"
        echo "  Full Test Suite with Coverage (70% minimum)"
        echo "═══════════════════════════════════════════════════════════════════════"
        echo ""

        uv run pytest --cov=. --cov-report=html --cov-report=term --cov-fail-under=70

        if [ $? -eq 0 ]; then
            print_success "Coverage threshold met (≥70%)"
            print_info "HTML coverage report: htmlcov/index.html"
        else
            print_error "Coverage below 70% threshold"
            exit 1
        fi
        ;;

    --watch|-w|watch)
        print_info "Running tests in watch mode (re-runs on file changes)"
        print_warning "Install pytest-watch: uv add --dev pytest-watch"
        uv run ptw -- -m unit
        ;;

    --help|-h|help|*)
        echo "Usage: $0 [OPTION]"
        echo ""
        echo "Tiered Testing Options:"
        echo "  --fast, -f, fast, unit       Run TIER 1: Fast unit tests (<5s)"
        echo "  --integration, -i            Run TIER 2: Integration tests (5-30s)"
        echo "  --e2e                        Run TIER 3: End-to-end tests (30s+)"
        echo "  --slow, -s, benchmark        Run TIER 4: Performance/benchmark tests"
        echo "  --all, -a, all               Run all test tiers"
        echo ""
        echo "Coverage & Analysis:"
        echo "  --coverage, -c, coverage     Run all tests with coverage report"
        echo ""
        echo "Development:"
        echo "  --watch, -w, watch           Run tests in watch mode (requires pytest-watch)"
        echo ""
        echo "Examples:"
        echo "  $0 --fast                    # Quick validation before commit"
        echo "  $0 --integration             # Pre-PR integration check"
        echo "  $0 --all                     # Complete test suite"
        echo "  $0 --coverage                # Coverage analysis for CI/CD"
        echo ""
        echo "Test Markers:"
        echo "  @pytest.mark.unit            Fast unit tests"
        echo "  @pytest.mark.integration     Integration tests"
        echo "  @pytest.mark.e2e             End-to-end tests"
        echo "  @pytest.mark.slow            Performance/benchmark tests"
        exit 0
        ;;
esac

echo ""
echo "╔════════════════════════════════════════════════════════════════════════╗"
echo "║                      TESTS COMPLETE                                     ║"
echo "╚════════════════════════════════════════════════════════════════════════╝"
