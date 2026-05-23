#!/usr/bin/env bash
set -euo pipefail

# py2kdm end-to-end regression script with JSON Schema validation.
#
# Run from the py2kdm root directory.
#
# Flow:
#   extractor
#     -> architecture recovery
#     -> pre-review agents
#     -> JSON Schema validation
#     -> pass-through reviewed JSON
#     -> JSON Schema validation
#     -> post-review agents
#     -> JSON Schema validation
#     -> KDM generation
#     -> sanity checks over the KDM XMI
#
# The pass-through reviewed JSON is used only for regression/CI purposes.
# It does not replace human GUI review.

CONFIG_PATH="configs/pymape_hierarchical.json"
OUTPUT_DIR="outputs/pymape_hierarchical"
PYTHON_BIN="${PYTHON:-python}"

INTERMEDIATE_JSON="${OUTPUT_DIR}/python_model.json"
ARCHITECTURE_JSON="${OUTPUT_DIR}/python_model.architecture.json"
AI_ARCHITECTURE_JSON="${OUTPUT_DIR}/python_model.ai_architecture.json"
REVIEWED_JSON="${OUTPUT_DIR}/python_model.reviewed_architecture.json"
AI_CHECKED_JSON="${OUTPUT_DIR}/python_model.reviewed.ai_checked.json"
KDM_XMI="${OUTPUT_DIR}/model.reviewed.kdm.xmi"

CLEAN=false
USE_EXISTING_REVIEWED=false

usage() {
  cat <<EOF
Usage:
  bash scripts/e2e_regression.sh [options]

Options:
  --config PATH              Pipeline config path.
                             Default: configs/pymape_hierarchical.json

  --output-dir PATH          Output directory.
                             Default: outputs/pymape_hierarchical

  --clean                    Remove generated output files before running.

  --use-existing-reviewed    Do not create a pass-through reviewed JSON.
                             Use the existing reviewed JSON exported from the GUI.

  -h, --help                 Show this help message.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      INTERMEDIATE_JSON="${OUTPUT_DIR}/python_model.json"
      ARCHITECTURE_JSON="${OUTPUT_DIR}/python_model.architecture.json"
      AI_ARCHITECTURE_JSON="${OUTPUT_DIR}/python_model.ai_architecture.json"
      REVIEWED_JSON="${OUTPUT_DIR}/python_model.reviewed_architecture.json"
      AI_CHECKED_JSON="${OUTPUT_DIR}/python_model.reviewed.ai_checked.json"
      KDM_XMI="${OUTPUT_DIR}/model.reviewed.kdm.xmi"
      shift 2
      ;;
    --clean)
      CLEAN=true
      shift
      ;;
    --use-existing-reviewed)
      USE_EXISTING_REVIEWED=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

print_step() {
  echo
  echo "========================================================================"
  echo "$1"
  echo "========================================================================"
}

assert_file_exists() {
  local file="$1"

  if [[ ! -f "$file" ]]; then
    echo "ERROR: Expected file does not exist: $file" >&2
    exit 1
  fi
}

json_check() {
  local file="$1"
  local expression="$2"
  local description="$3"

  "$PYTHON_BIN" - "$file" "$expression" "$description" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
expression = sys.argv[2]
description = sys.argv[3]

with path.open("r", encoding="utf-8") as handle:
    data = json.load(handle)

namespace = {"data": data}

try:
    result = eval(expression, {}, namespace)
except Exception as exc:
    print(f"ERROR: JSON check failed while evaluating: {description}", file=sys.stderr)
    print(f"Expression: {expression}", file=sys.stderr)
    print(f"Exception: {exc}", file=sys.stderr)
    sys.exit(1)

if not result:
    print(f"ERROR: JSON check failed: {description}", file=sys.stderr)
    print(f"Expression: {expression}", file=sys.stderr)
    sys.exit(1)

print(f"OK: {description}")
PY
}

schema_check() {
  local file="$1"
  local model_type="$2"
  local description="$3"

  if [[ ! -f "scripts/validate_json_schema.py" ]]; then
    echo "ERROR: Schema validator not found: scripts/validate_json_schema.py" >&2
    exit 1
  fi

  "$PYTHON_BIN" scripts/validate_json_schema.py \
    --input "$file" \
    --type "$model_type"

  echo "OK: $description"
}

if [[ "$CLEAN" == true ]]; then
  print_step "Cleaning generated artifacts"
  rm -f "$INTERMEDIATE_JSON" \
        "$ARCHITECTURE_JSON" \
        "$AI_ARCHITECTURE_JSON" \
        "$AI_CHECKED_JSON" \
        "$KDM_XMI"

  if [[ "$USE_EXISTING_REVIEWED" == false ]]; then
    rm -f "$REVIEWED_JSON"
  fi
fi

print_step "Running pipeline with pre-review agents"

"$PYTHON_BIN" run_pipeline.py \
  --config "$CONFIG_PATH" \
  --with-agents pre-review \
  --skip-kdm

print_step "Checking pre-review outputs"

assert_file_exists "$INTERMEDIATE_JSON"
assert_file_exists "$ARCHITECTURE_JSON"
assert_file_exists "$AI_ARCHITECTURE_JSON"

json_check "$INTERMEDIATE_JSON" "'projectName' in data" "intermediate JSON has projectName"
json_check "$ARCHITECTURE_JSON" "'structure_model' in data" "architecture JSON has structure_model"
json_check "$AI_ARCHITECTURE_JSON" "'ai_enrichment' in data" "AI architecture JSON has ai_enrichment"
json_check "$AI_ARCHITECTURE_JSON" "data.get('ai_enrichment', {}).get('summary', {}).get('suggestions', 0) >= 1" "pre-review agents produced suggestions"

print_step "Validating pre-review JSON artifacts against schemas"

schema_check "$INTERMEDIATE_JSON" "python" "intermediate JSON validates against python_model.schema.json"
schema_check "$ARCHITECTURE_JSON" "architecture" "architecture JSON validates against architecture_model.schema.json"
schema_check "$AI_ARCHITECTURE_JSON" "ai-architecture" "AI architecture JSON validates against ai_architecture_model.schema.json"

if [[ "$USE_EXISTING_REVIEWED" == true ]]; then
  print_step "Using existing reviewed JSON"
  assert_file_exists "$REVIEWED_JSON"
else
  print_step "Creating pass-through reviewed JSON for regression"

  "$PYTHON_BIN" - "$AI_ARCHITECTURE_JSON" "$REVIEWED_JSON" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])

with source.open("r", encoding="utf-8") as handle:
    data = json.load(handle)

data["architecture_review"] = {
    "status": "reviewed",
    "source": "e2e_regression_pass_through",
    "decision": "approved_without_manual_changes",
    "note": (
        "This reviewed JSON was generated automatically for end-to-end "
        "regression testing. It does not replace manual GUI review."
    ),
    "created_at": datetime.now(timezone.utc).isoformat(),
}

target.parent.mkdir(parents=True, exist_ok=True)

with target.open("w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2, ensure_ascii=False)

print(f"Created pass-through reviewed JSON: {target}")
PY
fi

print_step "Validating reviewed JSON against schema"

schema_check "$REVIEWED_JSON" "reviewed" "reviewed JSON validates against reviewed_architecture_model.schema.json"

print_step "Running post-review agents"

"$PYTHON_BIN" kdm_architecture_agents/main.py \
  --mode post-review \
  --input "$REVIEWED_JSON" \
  --output "$AI_CHECKED_JSON"

assert_file_exists "$AI_CHECKED_JSON"

json_check "$AI_CHECKED_JSON" "'post_review_ai_check' in data" "AI-checked JSON has post_review_ai_check"
json_check "$AI_CHECKED_JSON" "data.get('post_review_ai_check', {}).get('summary', {}).get('kdm_ready') is True" "AI-checked JSON is KDM-ready"

print_step "Validating AI-checked JSON against schema"

schema_check "$AI_CHECKED_JSON" "ai-checked" "AI-checked JSON validates against ai_checked_architecture_model.schema.json"

print_step "Generating reviewed KDM"

"$PYTHON_BIN" kdm_pyecore_generator/main.py \
  --input "$AI_CHECKED_JSON" \
  --output "$KDM_XMI"

assert_file_exists "$KDM_XMI"

print_step "Checking KDM XMI content"

if ! grep -q "Adaptive System Domain" "$KDM_XMI"; then
  echo "ERROR: KDM XMI does not contain Adaptive System Domain." >&2
  exit 1
fi

if ! grep -q "StructureModel" "$KDM_XMI"; then
  echo "ERROR: KDM XMI does not contain StructureModel." >&2
  exit 1
fi

if ! grep -q "Control Loop" "$KDM_XMI"; then
  echo "ERROR: KDM XMI does not contain Control Loop." >&2
  exit 1
fi

print_step "E2E regression completed successfully"

echo "Generated artifacts:"
echo "- Intermediate JSON: $INTERMEDIATE_JSON"
echo "- Architecture JSON: $ARCHITECTURE_JSON"
echo "- AI Architecture JSON: $AI_ARCHITECTURE_JSON"
echo "- Reviewed JSON: $REVIEWED_JSON"
echo "- AI-checked JSON: $AI_CHECKED_JSON"
echo "- KDM XMI: $KDM_XMI"
