#!/bin/bash
set -e

# The inputs are passed as positional arguments from action.yml
REPO=$1
BASE=$2
HEAD=$3
LOG_FILE=$4
MODEL_PROVIDER=$5
MODEL_NAME=$6

echo "Running QAOps Fault Localizer..."

fault-localizer \
  --repo "$REPO" \
  --base "$BASE" \
  --head "$HEAD" \
  --log-file "$LOG_FILE" \
  --model-provider "$MODEL_PROVIDER" \
  --model-name "$MODEL_NAME" \
  --auto-revert
