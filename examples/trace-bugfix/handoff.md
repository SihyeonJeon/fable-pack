# Handoff: project-root false-anchor bugfix (0.5.12)

Root cause: project_root's fallback walk matched any directory literally
named fable-pack or fable-disk. The user's HOME contains this repo checkout
(~/fable-pack), so every project under HOME resolved to HOME: `pack on`
wrote MODE to ~/fable-disk, and hooks (which see the correct project via
CLAUDE_PROJECT_DIR) found MODE=off there and stayed silent.

Fix: markers now verify capability — fable-pack/PACK_VERSION file for an
install, fable-disk/{trace,config} dirs for a recording disk. Resolution
order unchanged: FABLE_PACK_PROJECT_ROOT > CLAUDE_PROJECT_DIR (the
session-bound folder) > marker-verified walk > cwd. Stray ~/fable-disk
deleted. 44 tests green.
