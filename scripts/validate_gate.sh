#!/usr/bin/env bash
set -euo pipefail

gate="${1:?usage: validate_gate.sh <pre-commit|pre-push|pre-pr|release>}"
python3 -m unittest discover -s tests -p 'test_*.py' -v

if command -v gentle-ai >/dev/null 2>&1; then
  gentle-ai review validate --gate "$gate"
else
  printf 'gentle-ai unavailable; native %s gate not executed\n' "$gate" >&2
fi
