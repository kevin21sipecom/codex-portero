#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${PORTERO_TEST_PROFILE:-$ROOT/.test-profile}"
TEST_HOME="$PROFILE/home"
MARKETPLACE="$PROFILE/marketplace"

rm -rf "$PROFILE"
mkdir -p "$TEST_HOME/.codex" "$MARKETPLACE/.agents/plugins" "$MARKETPLACE/plugins/codex-portero"
tar -C "$ROOT" --exclude=.git --exclude=.codegraph --exclude=.test-profile --exclude='__pycache__' --exclude='*.pyc' -cf - . | tar -C "$MARKETPLACE/plugins/codex-portero" -xf -
cp "$ROOT/tests/fixtures/marketplace.json" "$MARKETPLACE/.agents/plugins/marketplace.json"

export HOME="$TEST_HOME"
export CODEX_HOME="$TEST_HOME/.codex"
export PORTERO_CATALOG_FIXTURE="$ROOT/tests/fixtures/catalog.json"

python3 -m unittest discover -s "$ROOT/tests" -p 'test_*.py' -v
codex plugin marketplace add "$MARKETPLACE"
codex plugin add codex-portero@portero-test --json
codex plugin list --json > "$PROFILE/plugin-list.json"

CACHED_PLUGIN="$CODEX_HOME/plugins/cache/portero-test/codex-portero/0.1.0"
test -f "$CACHED_PLUGIN/.codex-plugin/plugin.json"
python3 - "$CACHED_PLUGIN/plugin.json" "$CACHED_PLUGIN/.codex-plugin/plugin.json" "$MARKETPLACE/.agents/plugins/marketplace.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    root = json.load(stream)
with open(sys.argv[2], encoding="utf-8") as stream:
    compatibility = json.load(stream)
with open(sys.argv[3], encoding="utf-8") as stream:
    marketplace = json.load(stream)
assert root["extensions"]["com.openai"]["hooks"] == "./hooks/hooks.json"
assert compatibility["hooks"] == "./hooks/hooks.json"
assert compatibility["skills"] == "./skills/"
assert root["extensions"]["com.openai"]["interface"] == compatibility["interface"]
assert root["extensions"]["com.openai"]["interface"]["displayName"] == "Codex Portero"
assert marketplace["name"] == "portero-test"
assert marketplace["interface"]["displayName"] == "Portero Test"
assert marketplace["plugins"][0]["name"] == root["name"]
PY

printf '\nIsolated profile prepared at %s\n' "$PROFILE"
printf 'Plugin inventory: %s\n' "$PROFILE/plugin-list.json"
printf 'Compatibility manifest: %s\n' "$CACHED_PLUGIN/.codex-plugin/plugin.json"
printf 'Root OpenAI hook declaration: %s\n' "$CACHED_PLUGIN/plugin.json"
printf 'CLI installation and deterministic tests verify packaging and hook logic only; they do not prove plugin-bundled hooks execute.\n'
printf 'For runtime acceptance, manually install and trust the plugin in Codex desktop, then follow README.md.\n'
