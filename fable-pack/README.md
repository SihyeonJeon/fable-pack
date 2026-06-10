# fable-pack

`fable-pack` is a personal workflow tool that persists the engineering
decision record of Claude Code sessions — specifications, context-selection
rationale, rejected alternatives, acceptance criteria, verification
evidence — as structured project documents, and enforces quality gates that
block implementation edits until those documents are written. The output
serves code review, audit, retrospectives, and onboarding.

It records decision artifacts, not private chain of thought.

## What It Creates

Runtime data is written to the target project root:

```text
fable-disk/
  trace/
    ACTIVE
    <task-id>/
      meta.yaml
      input_snapshot.yaml
      repo_snapshot.yaml
      context_log.jsonl        # reads, searches, web lookups, session/compaction events
      observation_log.jsonl
      decision_events.jsonl
      edit_log.jsonl
      command_log.jsonl
      user_prompt_log.jsonl    # raw user goals, follow-ups, corrections
      orchestration_log.jsonl  # plans (ExitPlanMode), todo decompositions, subagent dispatch prompts
      assistant_log.jsonl      # visible assistant turn text (never private chain of thought)
      context_pack.yaml
      task_spec/
      worker_contracts/
      verifier_report.yaml
      handoff.md
      shadow/
      counterfactuals/
  corpus/
```

The pack code stays inside `fable-pack/`. Removing `fable-pack/` disables the
hooks. Existing `fable-disk/` trace data remains available unless you delete it.

## Claude Code Install

### Option A: global plugin (recommended)

Installs once, enforces in every project you open. From any Claude Code
session:

```text
/plugin marketplace add SihyeonJeon/fable-pack
/plugin install fable-pack@fable-pack-marketplace
```

(For a local checkout, pass the checkout path to `marketplace add` instead.)

Hooks resolve the target project via `CLAUDE_PROJECT_DIR`, so `fable-disk/`
is still written to whichever project you are working in. Slash commands:
`/fable-pack:start`, `/fable-pack:status`, `/fable-pack:done`,
`/fable-pack:promote`. Remove with `/plugin uninstall fable-pack`.

### Option B: per-project install

From the target project root:

```sh
sh fable-pack/adapters/claude-code/install.sh
```

The installer writes guarded hook commands to `.claude/settings.local.json`.
Those commands no-op if `fable-pack/` is later removed.

## Uninstall

From the target project root:

```sh
sh fable-pack/adapters/claude-code/uninstall.sh
```

This removes the hook entries from `.claude/settings.local.json` and deletes
`fable-pack/`. Recorded traces in `fable-disk/` are kept; add `--purge-data`
to remove them too.

## Token Cost & Security

Recording runs entirely in harness-side hook processes and costs zero model
tokens. Only behavior-changing signals enter agent context (session status
line, one escalation notice, gate errors), and identical gate errors are
never re-injected — a hash of the error list gates re-printing, so new
errors always surface in full. Re-reads do not duplicate observation
placeholders, and agent reads/writes of `fable-disk/` itself are excluded
from context logs (no self-recording loop).

All data stays in local plain files under the target project's
`fable-disk/` — no network, no telemetry. Secret-shaped values
(`sk-…`, `ghp_…`, `AKIA…`, JWTs, `Bearer …`, `KEY=value`) are redacted
before writing; thinking blocks are never extracted from transcripts;
bypassed traces are audit-marked and barred from the golden corpus. See the
root README for the full statement.

## Fable-Only Enforcement

Hooks record and block only when the active model id contains `fable`.

Sources checked, in order:

- `FABLE_PACK_MODEL_ID` (explicit override)
- the session transcript (`transcript_path` from the hook payload; reflects
  live `/model` switches — this is the primary live-session source)
- `CLAUDE_CODE_MODEL`
- `CLAUDE_MODEL`
- `ANTHROPIC_MODEL`
- hook payload model fields

If the model id is unknown or does not contain `fable`, hooks no-op. For smoke
tests only, set `FABLE_PACK_FORCE=1`.

`pack task start` also refuses to create a reference trace unless the resolved
model is Fable. Use `--model fable` only when Claude Code is pinned to
`/model fable`; use `--allow-non-fable` only for explicit shadow traces.

## Basic Use

```sh
fable-pack/adapters/claude-code/scripts/pack task start \
  --goal "implement login without breaking current auth flows" \
  --grade HEAVY \
  --task-type auth_change \
  --model fable
```

Before implementation, fill:

- `context_pack.yaml`
- `task_spec/final.yaml`
- `decision_events.jsonl`
- `observation_log.jsonl`

Then run:

```sh
fable-pack/adapters/claude-code/scripts/pack validate --gate spec
fable-pack/adapters/claude-code/scripts/pack validate --gate context
```

Close the trace only after verifier evidence is complete:

```sh
fable-pack/adapters/claude-code/scripts/pack task done
```

After human review (`human_review.yaml` rating set), promote the trace into
the corpus:

```sh
fable-pack/adapters/claude-code/scripts/pack corpus promote --task-id <task-id>
```

Ratings `exemplary`/`normal` go to `corpus/fable_golden/` (corpus quality gate
must pass); `flawed` goes to `corpus/flawed_examples/` as a negative example.

## Design Limits

No local file can force Claude Code hooks merely by existing. Level 2
enforcement requires Claude Code to load the hook commands. The installer is the
minimal one-time bridge. The active hook commands are self-contained and safe to
leave behind because they no-op when this directory is absent.
