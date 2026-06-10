#!/usr/bin/env sh
# Removes everything fable-pack added to a project with one command:
#   sh fable-pack/adapters/claude-code/uninstall.sh [project-root] [--purge-data]
#
# Default: removes the fable-pack hook entries from .claude/settings.local.json
# and deletes the fable-pack/ directory. Recorded traces in fable-disk/ are
# kept unless --purge-data is passed.
set -eu

ROOT="$(pwd)"
PURGE_DATA=0
for arg in "$@"; do
    case "$arg" in
        --purge-data) PURGE_DATA=1 ;;
        *) ROOT="$arg" ;;
    esac
done

python3 - "$ROOT" "$PURGE_DATA" <<'PY'
import json
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
purge_data = sys.argv[2] == "1"

settings_path = root / ".claude" / "settings.local.json"
if settings_path.exists():
    try:
        data = json.loads(settings_path.read_text())
    except Exception:
        raise SystemExit(f"Refusing to edit invalid JSON: {settings_path}")
    hooks = data.get("hooks", {})
    removed = 0
    for name in list(hooks):
        kept = []
        for entry in hooks[name]:
            if "fable-pack/adapters/claude-code/hooks" in json.dumps(entry):
                removed += 1
            else:
                kept.append(entry)
        if kept:
            hooks[name] = kept
        else:
            del hooks[name]
    if not hooks and "hooks" in data:
        del data["hooks"]
    settings_path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"removed {removed} fable-pack hook entries from {settings_path}")
else:
    print(f"no settings file at {settings_path}; skipping hook removal")

pack_dir = root / "fable-pack"
if pack_dir.is_dir():
    shutil.rmtree(pack_dir)
    print(f"removed {pack_dir}")
else:
    print(f"no pack directory at {pack_dir}; skipping")

disk_dir = root / "fable-disk"
if purge_data:
    if disk_dir.is_dir():
        shutil.rmtree(disk_dir)
        print(f"removed {disk_dir}")
    else:
        print(f"no trace data at {disk_dir}; skipping")
elif disk_dir.is_dir():
    print(f"kept trace data at {disk_dir} (pass --purge-data to remove)")

print("fable-pack uninstalled.")
PY
