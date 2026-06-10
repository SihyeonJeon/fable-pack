#!/usr/bin/env sh
set -eu

ROOT="${1:-$(pwd)}"
CLAUDE_DIR="$ROOT/.claude"
SETTINGS="$CLAUDE_DIR/settings.local.json"

mkdir -p "$CLAUDE_DIR"

python3 - "$ROOT" "$SETTINGS" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
settings_path = Path(sys.argv[2])

if settings_path.exists():
    try:
        data = json.loads(settings_path.read_text())
    except Exception:
        raise SystemExit(f"Refusing to overwrite invalid JSON: {settings_path}")
else:
    data = {}

hooks = data.setdefault("hooks", {})

def command(script):
    # Prefer $CLAUDE_PROJECT_DIR (set by Claude Code for hook commands) so the
    # entry survives repo moves and worktrees; fall back to the install root.
    rel = f"fable-pack/adapters/claude-code/hooks/{script}"
    return (
        'PACK_HOOK="${CLAUDE_PROJECT_DIR:-' + str(root) + '}/' + rel + '"; '
        'if [ -f "$PACK_HOOK" ]; then python3 "$PACK_HOOK"; fi'
    )

def set_hook(name, matcher, script):
    existing = hooks.get(name, [])
    kept = []
    for entry in existing:
        serialized = json.dumps(entry)
        if "fable-pack/adapters/claude-code/hooks" not in serialized:
            kept.append(entry)
    entry = {"hooks": [{"type": "command", "command": command(script)}]}
    if matcher is not None:
        entry["matcher"] = matcher
    kept.append(entry)
    hooks[name] = kept

set_hook("SessionStart", "*", "session_start.py")
set_hook("UserPromptSubmit", None, "user_prompt_submit.py")
set_hook("PreToolUse", "Edit|Write|MultiEdit|NotebookEdit", "pre_tool_use.py")
set_hook(
    "PostToolUse",
    "Read|Glob|Grep|LS|Edit|Write|MultiEdit|NotebookEdit|Bash|Task|Agent|TodoWrite|ExitPlanMode|EnterPlanMode|Workflow|WebSearch|WebFetch",
    "post_tool_use.py",
)
set_hook("PreCompact", "*", "pre_compact.py")
set_hook("Stop", "*", "stop.py")

settings_path.write_text(json.dumps(data, indent=2) + "\n")
print(settings_path)
PY

chmod +x "$ROOT/fable-pack/adapters/claude-code/scripts/pack"
chmod +x "$ROOT/fable-pack/adapters/claude-code/hooks/"*.py

echo "fable-pack Claude Code hooks installed."
echo "The hooks only record when the active model id contains 'fable' or FABLE_PACK_FORCE=1 is set."
