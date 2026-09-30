#!/usr/bin/env bash
# Quick-start launcher from workspace root
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/case-study-4/start.sh" "$@"
