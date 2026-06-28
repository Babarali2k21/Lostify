#!/usr/bin/env bash
# Package mock Lambda functions into zip files for AWS upload
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAMBDA_DIR="$SCRIPT_DIR/lambda"
OUT_DIR="$SCRIPT_DIR/dist"

mkdir -p "$OUT_DIR"

pack() {
  local name=$1
  local src_dir=$2
  local tmp
  tmp=$(mktemp -d)
  cp "$LAMBDA_DIR/common.py" "$tmp/"
  cp "$src_dir/handler.py" "$tmp/"
  (cd "$tmp" && zip -q "$OUT_DIR/${name}.zip" common.py handler.py)
  rm -rf "$tmp"
  echo "Created $OUT_DIR/${name}.zip"
}

pack "lostify-create-claim"  "$LAMBDA_DIR/create_claim"
pack "lostify-reserve-item"  "$LAMBDA_DIR/reserve_item"
pack "lostify-recover-item"  "$LAMBDA_DIR/recover_item"
pack "lostify-release-item"  "$LAMBDA_DIR/release_item"
pack "lostify-send-notification" "$LAMBDA_DIR/send_notification"

echo ""
echo "Upload each zip to AWS Lambda (Python 3.12, handler: handler.handler)"
echo "Zip files are in: $OUT_DIR"
