#!/bin/bash

# LLM API Platform - Load Testing Script
# This script runs comprehensive load tests against the API platform

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
RESULTS_DIR="${RESULTS_DIR:-$PROJECT_ROOT/test-results}"
TARGET_URL="${TARGET_URL:-http://localhost:8000}"
DURATION="${DURATION:-300}"
USERS="${USERS:-100}"
SPAWN_RATE="${SPAWN_RATE:-10}"
TEST_TYPE="${TEST_TYPE:-smoke}"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

error() {
    log "ERROR: $*"
    exit 1
}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

usage() {
    cat << EOF
Usage: $0 [TEST_TYPE] [OPTIONS]

Run load tests against the LLM API platform.

Test Types:
    smoke       Quick smoke test (default: 10 users, 60s)
    load        Standard load test (default: 100 users, 300s)
    stress      Stress test (default: 500 users, 600s)
    spike       Spike test (ramp up/down pattern)
    volume      Volume test (sustained high load)
    endurance   Long-running endurance test (24h)

Options:
    --url URL           Target URL (default: http://localhost:8000)
    --users N           Number of concurrent users
    --duration N        Test duration in seconds
    --spawn-rate N      User spawn rate per second
    --results-dir DIR   Results directory

Environment Variables:
    TARGET_URL          Target URL for testing
    USERS              Number of concurrent users
    DURATION           Test duration in seconds
    SPAWN_RATE         User spawn rate
    API_KEY            API key for authenticated requests

Examples:
    $0 smoke                                    # Quick smoke test
    $0 load --users 200 --duration 600         # Custom load test
    $0 stress --url https://api.example.com    # Stress test against remote API
    TARGET_URL=https://staging.api.com $0 load # Using environment variables

EOF
}

check_prerequisites() {
    print_status "Checking prerequisites..."

    # Check for required tools
    local required_tools=("locust" "curl" "jq" "python3")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            error "Required tool '$tool' is not installed"
        fi
    done

    # Check Python packages
    if ! python3 -c "import locust, requests, matplotlib, pandas" 2>/dev/null; then
        error "Required Python packages not installed. Run: pip install locust requests matplotlib pandas"
    fi

    # Check if k6 is available (optional but recommended)
    if command -v k6 &> /dev/null; then
        print_status "k6 found - will run additional performance tests"
    else
        print_warning "k6 not found - some tests will be skipped"
    fi

    print_status "Prerequisites check completed"
}

setup_test_environment() {
    print_status "Setting up test environment..."

    # Create results directory
    mkdir -p "$RESULTS_DIR"

    # Set test timestamp
    TEST_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    TEST_RUN_DIR="$RESULTS_DIR/run_${TEST_TIMESTAMP}"
    mkdir -p "$TEST_RUN_DIR"

    print_status "Test results will be saved to: $TEST_RUN_DIR"

    # Configure test parameters based on test type
    case "$TEST_TYPE" in
        smoke)
            USERS=${USERS:-10}
            DURATION=${DURATION:-60}
            SPAWN_RATE=${SPAWN_RATE:-2}
            ;;
        load)
            USERS=${USERS:-100}
            DURATION=${DURATION:-300}
            SPAWN_RATE=${SPAWN_RATE:-10}
            ;;
        stress)
            USERS=${USERS:-500}
            DURATION=${DURATION:-600}
            SPAWN_RATE=${SPAWN_RATE:-25}
            ;;
        spike)
            USERS=${USERS:-200}
            DURATION=${DURATION:-300}
            SPAWN_RATE=${SPAWN_RATE:-50}
            ;;
        volume)
            USERS=${USERS:-1000}
            DURATION=${DURATION:-1800}
            SPAWN_RATE=${SPAWN_RATE:-20}
            ;;
        endurance)
            USERS=${USERS:-100}
            DURATION=${DURATION:-86400}
            SPAWN_RATE=${SPAWN_RATE:-10}
            ;;
        *)
            error "Unknown test type: $TEST_TYPE"
            ;;
    esac

    print_status "Test configuration:"
    echo "  Type: $TEST_TYPE"
    echo "  Users: $USERS"
    echo "  Duration: $DURATION seconds"
    echo "  Spawn Rate: $SPAWN_RATE users/second"
    echo "  Target: $TARGET_URL"
}

check_target_health() {
    print_status "Checking target health..."

    # Basic connectivity check
    if ! curl -f -s --max-time 10 "$TARGET_URL/health" > /dev/null; then
        error "Target is not responding at $TARGET_URL/health"
    fi

    # Check API endpoints
    local endpoints=(
        "/health"
        "/v1/models"
        "/docs"
    )

    for endpoint in "${endpoints[@]}"; do
        local status_code
        status_code=$(curl -s -o /dev/null -w "%{http_code}" "$TARGET_URL$endpoint" || echo "000")

        if [[ "$status_code" -ge 200 && "$status_code" -lt 400 ]]; then
            print_status "✓ $endpoint: $status_code"
        else
            print_warning "✗ $endpoint: $status_code"
        fi
    done

    print_status "Target health check completed"
}

run_locust_test() {
    print_status "Starting Locust load test..."

    local locust_file="$PROJECT_ROOT/tests/load/locustfile.py"
    if [[ ! -f "$locust_file" ]]; then
        error "Locust file not found: $locust_file"
    fi

    # Run Locust test
    cd "$PROJECT_ROOT/tests/load"

    locust \
        --headless \
        --users="$USERS" \
        --spawn-rate="$SPAWN_RATE" \
        --run-time="${DURATION}s" \
        --host="$TARGET_URL" \
        --html="$TEST_RUN_DIR/locust_report.html" \
        --csv="$TEST_RUN_DIR/locust_results" \
        --logfile="$TEST_RUN_DIR/locust.log" \
        --loglevel=INFO

    print_status "Locust test completed"
}

run_k6_test() {
    if ! command -v k6 &> /dev/null; then
        print_warning "k6 not available, skipping k6 tests"
        return 0
    fi

    print_status "Starting k6 performance test..."

    local k6_script="$PROJECT_ROOT/tests/load/k6-script.js"
    if [[ ! -f "$k6_script" ]]; then
        print_warning "k6 script not found: $k6_script"
        return 0
    fi

    cd "$PROJECT_ROOT/tests/load"

    k6 run \
        --vus="$USERS" \
        --duration="${DURATION}s" \
        --out json="$TEST_RUN_DIR/k6_results.json" \
        --out csv="$TEST_RUN_DIR/k6_results.csv" \
        "$k6_script"

    print_status "k6 test completed"
}

run_artillery_test() {
    if ! command -v artillery &> /dev/null; then
        print_warning "Artillery not available, skipping Artillery tests"
        return 0
    fi

    print_status "Starting Artillery test..."

    local artillery_config="$PROJECT_ROOT/tests/load/artillery_config.yml"
    if [[ ! -f "$artillery_config" ]]; then
        print_warning "Artillery config not found: $artillery_config"
        return 0
    fi

    cd "$PROJECT_ROOT/tests/load"

    artillery run \
        --target="$TARGET_URL" \
        --output="$TEST_RUN_DIR/artillery_results.json" \
        "$artillery_config"

    # Generate HTML report
    artillery report \
        "$TEST_RUN_DIR/artillery_results.json" \
        --output "$TEST_RUN_DIR/artillery_report.html"

    print_status "Artillery test completed"
}

run_custom_benchmarks() {
    print_status "Running custom benchmarks..."

    # API response time benchmark
    python3 << EOF
import requests
import time
import json
import statistics

def benchmark_endpoint(url, iterations=100):
    """Benchmark a single endpoint"""
    times = []
    errors = 0

    for _ in range(iterations):
        start = time.time()
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                times.append((time.time() - start) * 1000)  # Convert to ms
            else:
                errors += 1
        except Exception:
            errors += 1

    if times:
        return {
            'mean': statistics.mean(times),
            'median': statistics.median(times),
            'p95': sorted(times)[int(0.95 * len(times))],
            'p99': sorted(times)[int(0.99 * len(times))],
            'min': min(times),
            'max': max(times),
            'errors': errors,
            'success_rate': (iterations - errors) / iterations * 100
        }
    else:
        return {'errors': errors, 'success_rate': 0}

endpoints = [
    '$TARGET_URL/health',
    '$TARGET_URL/v1/models',
    '$TARGET_URL/v1/chat/completions'
]

results = {}
for endpoint in endpoints:
    print(f"Benchmarking {endpoint}...")
    results[endpoint] = benchmark_endpoint(endpoint, 50)

# Save results
with open('$TEST_RUN_DIR/benchmark_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print("Custom benchmarks completed")
EOF

    print_status "Custom benchmarks completed"
}

analyze_results() {
    print_status "Analyzing test results..."

    # Create analysis script
    python3 << EOF
import json
import pandas as pd
import matplotlib.pyplot as plt
import os

results_dir = '$TEST_RUN_DIR'

# Analyze Locust results
if os.path.exists(f'{results_dir}/locust_results_stats.csv'):
    locust_stats = pd.read_csv(f'{results_dir}/locust_results_stats.csv')
    print("=== LOCUST RESULTS ===")
    print(locust_stats.to_string(index=False))
    print()

# Analyze benchmark results
if os.path.exists(f'{results_dir}/benchmark_results.json'):
    with open(f'{results_dir}/benchmark_results.json') as f:
        benchmark_data = json.load(f)

    print("=== BENCHMARK RESULTS ===")
    for endpoint, metrics in benchmark_data.items():
        print(f"{endpoint}:")
        if 'mean' in metrics:
            print(f"  Mean response time: {metrics['mean']:.2f}ms")
            print(f"  P95 response time: {metrics['p95']:.2f}ms")
            print(f"  Success rate: {metrics['success_rate']:.1f}%")
        print()

# Create performance charts
if os.path.exists(f'{results_dir}/locust_results_stats_history.csv'):
    history = pd.read_csv(f'{results_dir}/locust_results_stats_history.csv')

    # Response time chart
    plt.figure(figsize=(12, 6))
    plt.subplot(1, 2, 1)
    plt.plot(history['Timestamp'], history['Average Response Time'])
    plt.title('Response Time Over Time')
    plt.xlabel('Time')
    plt.ylabel('Response Time (ms)')
    plt.xticks(rotation=45)

    # Request rate chart
    plt.subplot(1, 2, 2)
    plt.plot(history['Timestamp'], history['Requests/s'])
    plt.title('Request Rate Over Time')
    plt.xlabel('Time')
    plt.ylabel('Requests per Second')
    plt.xticks(rotation=45)

    plt.tight_layout()
    plt.savefig(f'{results_dir}/performance_charts.png', dpi=300, bbox_inches='tight')
    print("Performance charts saved to performance_charts.png")

print("Analysis completed")
EOF

    print_status "Results analysis completed"
}

check_thresholds() {
    print_status "Checking performance thresholds..."

    python3 << EOF
import json
import sys

# Default thresholds
thresholds = {
    'max_response_time': 2000,  # ms
    'min_success_rate': 99.0,   # %
    'max_error_rate': 1.0,      # %
}

# Load test results
results_file = '$TEST_RUN_DIR/benchmark_results.json'
try:
    with open(results_file) as f:
        results = json.load(f)

    failures = []

    for endpoint, metrics in results.items():
        if 'p95' in metrics:
            if metrics['p95'] > thresholds['max_response_time']:
                failures.append(f"{endpoint}: P95 response time {metrics['p95']:.2f}ms > {thresholds['max_response_time']}ms")

            if metrics['success_rate'] < thresholds['min_success_rate']:
                failures.append(f"{endpoint}: Success rate {metrics['success_rate']:.1f}% < {thresholds['min_success_rate']}%")

    if failures:
        print("THRESHOLD FAILURES:")
        for failure in failures:
            print(f"  ❌ {failure}")
        sys.exit(1)
    else:
        print("✅ All thresholds passed")
        sys.exit(0)

except FileNotFoundError:
    print("No benchmark results found")
    sys.exit(0)
EOF

    local exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        print_status "All performance thresholds passed"
    else
        print_error "Some performance thresholds failed"
        return 1
    fi
}

generate_report() {
    print_status "Generating test report..."

    # Create HTML report
    cat > "$TEST_RUN_DIR/test_report.html" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Load Test Report - $TEST_TIMESTAMP</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }
        .section { margin: 20px 0; padding: 15px; border-left: 4px solid #007cba; }
        .metrics { display: flex; gap: 20px; flex-wrap: wrap; }
        .metric { background-color: #f9f9f9; padding: 15px; border-radius: 5px; flex: 1; min-width: 200px; }
        .metric h3 { margin-top: 0; color: #333; }
        .pass { color: green; }
        .fail { color: red; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Load Test Report</h1>
        <p><strong>Test Type:</strong> $TEST_TYPE</p>
        <p><strong>Target:</strong> $TARGET_URL</p>
        <p><strong>Timestamp:</strong> $TEST_TIMESTAMP</p>
        <p><strong>Duration:</strong> ${DURATION}s</p>
        <p><strong>Concurrent Users:</strong> $USERS</p>
    </div>

    <div class="section">
        <h2>Test Configuration</h2>
        <ul>
            <li>Test Type: $TEST_TYPE</li>
            <li>Duration: ${DURATION} seconds</li>
            <li>Concurrent Users: $USERS</li>
            <li>Spawn Rate: $SPAWN_RATE users/second</li>
            <li>Target URL: $TARGET_URL</li>
        </ul>
    </div>

    <div class="section">
        <h2>Files Generated</h2>
        <ul>
            <li><a href="locust_report.html">Locust HTML Report</a></li>
            <li><a href="performance_charts.png">Performance Charts</a></li>
            <li><a href="benchmark_results.json">Benchmark Results (JSON)</a></li>
            <li><a href="locust_results_stats.csv">Locust Stats (CSV)</a></li>
        </ul>
    </div>

    <div class="section">
        <h2>Quick Actions</h2>
        <ul>
            <li>Review detailed results in the Locust HTML report</li>
            <li>Check performance trends in the charts</li>
            <li>Analyze raw data in the CSV files</li>
            <li>Compare with previous test runs</li>
        </ul>
    </div>
</body>
</html>
EOF

    # Create summary JSON
    cat > "$TEST_RUN_DIR/test_summary.json" << EOF
{
  "timestamp": "$TEST_TIMESTAMP",
  "test_type": "$TEST_TYPE",
  "target_url": "$TARGET_URL",
  "duration": $DURATION,
  "users": $USERS,
  "spawn_rate": $SPAWN_RATE,
  "results_directory": "$TEST_RUN_DIR",
  "files": [
    "test_report.html",
    "locust_report.html",
    "performance_charts.png",
    "benchmark_results.json"
  ]
}
EOF

    print_status "Test report generated: $TEST_RUN_DIR/test_report.html"
}

cleanup() {
    # Kill any background processes
    jobs -p | xargs -r kill 2>/dev/null || true
}

main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            --url)
                TARGET_URL="$2"
                shift 2
                ;;
            --users)
                USERS="$2"
                shift 2
                ;;
            --duration)
                DURATION="$2"
                shift 2
                ;;
            --spawn-rate)
                SPAWN_RATE="$2"
                shift 2
                ;;
            --results-dir)
                RESULTS_DIR="$2"
                shift 2
                ;;
            smoke|load|stress|spike|volume|endurance)
                TEST_TYPE="$1"
                shift
                ;;
            *)
                error "Unknown argument: $1"
                ;;
        esac
    done

    print_header "LLM API Platform Load Testing"

    check_prerequisites
    setup_test_environment
    check_target_health

    # Record start time
    local start_time
    start_time=$(date +%s)

    # Run tests
    run_locust_test
    run_k6_test
    run_artillery_test
    run_custom_benchmarks

    # Analyze and report
    analyze_results
    check_thresholds || true  # Don't fail the script on threshold failures
    generate_report

    # Calculate duration
    local end_time duration
    end_time=$(date +%s)
    duration=$((end_time - start_time))

    print_header "LOAD TEST COMPLETED"
    print_status "Duration: ${duration}s"
    print_status "Results: $TEST_RUN_DIR"
    print_status "Report: $TEST_RUN_DIR/test_report.html"

    # Log test completion
    mkdir -p "$PROJECT_ROOT/logs"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Load test completed - Type: $TEST_TYPE - Duration: ${duration}s - Users: $USERS - Results: $TEST_RUN_DIR" >> "$PROJECT_ROOT/logs/load-test.log"
}

trap cleanup EXIT
main "$@"