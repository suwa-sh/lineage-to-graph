#!/bin/bash
# Regression test for lineage_to_md.py
#
# Usage:
#   ./test.sh           # Run tests
#   ./test.sh --update  # Update expected files

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ACTUAL_DIR="$SCRIPT_DIR/actual"
EXPECTED_DIR="$SCRIPT_DIR/expected"

# Test commands (associative array)
declare -A TEST_COMMANDS=(
  ["sample"]="python lineage_to_md.py data/sample.yml"
  ["event-driven"]="python lineage_to_md.py data/event-driven.yml"
  ["event-driven-csv"]="python lineage_to_md.py data/event-driven-csv.yml -p data/レイアウト -d data/テーブル定義"
  ["instance_example"]="python lineage_to_md.py data/instance_example.yml"
  ["instance_csv_example"]="python lineage_to_md.py data/instance_csv_example.yml -p data/レイアウト"
  ["api_example"]="python lineage_to_md.py data/api_example.yml -o data/openapi/user-api.yaml -a data/asyncapi/user-events.yaml"
  ["dynamic-fields"]="python lineage_to_md.py data/dynamic-fields.yml"
  ["etl-pipeline"]="python lineage_to_md.py data/etl-pipeline.yml"
)

# Test execution order (corresponding to README.md "個別生成" section)
TEST_ORDER=(
  "sample"
  "event-driven"
  "event-driven-csv"
  "instance_example"
  "instance_csv_example"
  "api_example"
  "dynamic-fields"
  "etl-pipeline"
)

# Check for update mode
UPDATE_MODE=false
if [[ "$1" == "--update" ]]; then
  UPDATE_MODE=true
fi

# Clean actual/ directory
rm -rf "$ACTUAL_DIR"
mkdir -p "$ACTUAL_DIR"

# Run tests
cd "$PROJECT_ROOT"
FAILED_TESTS=()
TOTAL_TESTS=${#TEST_ORDER[@]}

for test_name in "${TEST_ORDER[@]}"; do
  cmd="${TEST_COMMANDS[$test_name]} $ACTUAL_DIR/${test_name}.md"
  echo "Running: $test_name"

  # Execute command (suppress stderr)
  if ! eval "$cmd" 2>/dev/null; then
    echo "  ✗ Command failed"
    FAILED_TESTS+=("$test_name")
    continue
  fi

  if $UPDATE_MODE; then
    # Update mode: actual → expected
    cp "$ACTUAL_DIR/${test_name}.md" "$EXPECTED_DIR/${test_name}.md"
    echo "  ✓ Updated expected/${test_name}.md"
  else
    # Test mode: diff
    if diff -u "$EXPECTED_DIR/${test_name}.md" "$ACTUAL_DIR/${test_name}.md" > /dev/null 2>&1; then
      echo "  ✓ PASS"
    else
      echo "  ✗ FAIL"
      diff -u "$EXPECTED_DIR/${test_name}.md" "$ACTUAL_DIR/${test_name}.md" || true
      FAILED_TESTS+=("$test_name")
    fi
  fi
done

# Summary
echo ""
if $UPDATE_MODE; then
  echo "Updated $TOTAL_TESTS expected files"
else
  if [ ${#FAILED_TESTS[@]} -eq 0 ]; then
    echo "All tests passed ($TOTAL_TESTS/$TOTAL_TESTS)"
    exit 0
  else
    echo "Failed tests: ${FAILED_TESTS[*]}"
    echo "Total: $(($TOTAL_TESTS - ${#FAILED_TESTS[@]}))/$TOTAL_TESTS passed"
    exit 1
  fi
fi
