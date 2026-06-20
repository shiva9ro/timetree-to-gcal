#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"

export TZ=Asia/Tokyo
exec "$project_dir/.venv/bin/python" -m time_tree_exporter sync-timetree
