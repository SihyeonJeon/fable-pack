from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB_ROOT = ROOT / "fable-pack" / "core" / "lib"
sys.path.insert(0, str(LIB_ROOT))

import corpus  # noqa: E402
import eventlib  # noqa: E402
import tracelib  # noqa: E402
import validate  # noqa: E402


class PackSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="fable-pack-test-"))
        self.old_project = os.environ.get("FABLE_PACK_PROJECT_ROOT")
        os.environ["FABLE_PACK_PROJECT_ROOT"] = str(self.tmp)

    def tearDown(self) -> None:
        if self.old_project is None:
            os.environ.pop("FABLE_PACK_PROJECT_ROOT", None)
        else:
            os.environ["FABLE_PACK_PROJECT_ROOT"] = self.old_project
        shutil.rmtree(self.tmp)

    def test_scaffold_creates_fable_disk_trace(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="implement auth flow safely",
            grade="HEAVY",
            task_type="auth_change",
            task_id="smoke-heavy",
            model_id="fable",
            root=self.tmp,
        )
        self.assertTrue((self.tmp / "fable-disk" / "trace" / "ACTIVE").exists())
        self.assertTrue((task_path / "meta.yaml").exists())
        meta = tracelib.load_yaml(task_path / "meta.yaml")
        self.assertEqual(meta["model"]["role"], "fable_reference")

    def test_unknown_model_does_not_record(self) -> None:
        os.environ.pop("FABLE_PACK_FORCE", None)
        self.assertFalse(tracelib.should_record({"model": "claude-sonnet"}))
        self.assertTrue(tracelib.should_record({"model": "claude-fable"}))

    def test_spec_gate_fails_empty_scaffold(self) -> None:
        tracelib.scaffold_task(
            goal="add normal feature",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-standard",
            model_id="fable",
            root=self.tmp,
        )
        result = validate.validate_task("smoke-standard", self.tmp, "spec")
        self.assertFalse(result.ok)
        self.assertTrue(any("must_read" in error for error in result.errors))

    def test_context_and_observation_logging(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="inspect config",
            grade="STANDARD",
            task_type="bugfix",
            task_id="smoke-log",
            model_id="fable",
            root=self.tmp,
        )
        context = eventlib.log_context(task_path, "Read", {"file_path": "src/app.py"}, "content")
        observation = eventlib.log_observation_placeholder(task_path, context)
        self.assertEqual(context["seq"], 1)
        self.assertEqual(observation["path"], "src/app.py")

    def test_cli_start_and_corpus(self) -> None:
        script = ROOT / "fable-pack" / "adapters" / "claude-code" / "scripts" / "pack"
        env = os.environ.copy()
        env["FABLE_PACK_PROJECT_ROOT"] = str(self.tmp)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        start = subprocess.run(
            [
                sys.executable,
                str(script),
                "task",
                "start",
                "--goal",
                "add audited feature",
                "--grade",
                "STANDARD",
                "--task-type",
                "feature",
                "--id",
                "cli-smoke",
                "--model",
                "fable",
            ],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(start.returncode, 0, start.stderr)
        corpus = subprocess.run(
            [sys.executable, str(script), "corpus", "--json"],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(corpus.returncode, 0, corpus.stderr)
        self.assertIn('"task_count": 1', corpus.stdout)

    def test_model_id_from_transcript(self) -> None:
        os.environ.pop("FABLE_PACK_MODEL_ID", None)
        transcript = self.tmp / "transcript.jsonl"
        transcript.write_text(
            '{"type": "user", "message": {"role": "user", "content": "hi"}}\n'
            '{"type": "assistant", "message": {"model": "claude-fable-5", "role": "assistant"}}\n',
            encoding="utf-8",
        )
        payload = {"transcript_path": str(transcript)}
        self.assertEqual(tracelib.model_id_from_transcript(payload), "claude-fable-5")
        self.assertTrue(tracelib.should_record(payload))

    def test_placeholder_observation_does_not_satisfy_heavy_context_gate(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="rework session handling",
            grade="HEAVY",
            task_type="auth_change",
            task_id="smoke-placeholder",
            model_id="fable",
            root=self.tmp,
        )
        context_pack = tracelib.load_yaml(task_path / "context_pack.yaml")
        context_pack["must_read"] = [
            {"path": "src/app.py", "selected_by_decision_ref": "decision_events:seq=1"}
        ]
        tracelib.write_yaml(task_path / "context_pack.yaml", context_pack)
        context_event = eventlib.log_context(task_path, "Read", {"file_path": "src/app.py"}, "content")
        eventlib.log_observation_placeholder(task_path, context_event)

        result = validate.context_gate(task_path, self.tmp)
        self.assertFalse(result.ok)
        self.assertTrue(any("lacks filled observation" in error for error in result.errors))

        tracelib.append_jsonl(
            task_path / "observation_log.jsonl",
            {
                "source_event": "context_log:seq=1",
                "path": "src/app.py",
                "symbols": [],
                "extracted_facts": [{"fact": "session middleware lives here", "supports": [], "confidence": "high"}],
                "changed_task_understanding": True,
                "caused_updates": [],
            },
        )
        result = validate.context_gate(task_path, self.tmp)
        self.assertTrue(result.ok, result.errors)

    def test_command_log_redacts_secrets(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="run deploy",
            grade="STANDARD",
            task_type="ops",
            task_id="smoke-redact",
            model_id="fable",
            root=self.tmp,
        )
        event = eventlib.log_command(
            task_path,
            {"command": "export API_KEY=sk-abcdef1234567890 && curl -H 'Authorization: Bearer abcdefghijklmnopqrst'"},
        )
        self.assertNotIn("sk-abcdef1234567890", event["command"])
        self.assertNotIn("abcdefghijklmnopqrst", event["command"])
        self.assertIn("<redacted>", event["command"])

    def test_generic_phrase_uses_word_boundaries(self) -> None:
        self.assertFalse(validate.contains_generic_phrase("integration test suite covers networks module"))
        self.assertTrue(validate.contains_generic_phrase("verify it works"))
        self.assertTrue(validate.contains_generic_phrase("배포 후 동작 확인"))

    def test_korean_unicode_preserved_in_artifacts(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="결제 모듈 마이그레이션",
            grade="STANDARD",
            task_type="migration",
            task_id="smoke-korean",
            model_id="fable",
            root=self.tmp,
        )
        raw = (task_path / "input_snapshot.yaml").read_text(encoding="utf-8")
        self.assertIn("결제 모듈 마이그레이션", raw)
        events = (task_path / "decision_events.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("\\u", events.split("ts")[0])

    def _make_done_passing(self, task_path) -> None:
        """Upgrade a scaffolded trace so the (stricter) done gate passes."""
        spec = tracelib.load_yaml(task_path / "task_spec" / "final.yaml")
        spec["acceptance_criteria"] = [
            {"criterion": "tests pass", "verification": {"type": "command", "value": "python3 -m unittest"}}
        ]
        spec["risk_register"] = [
            {"id": "r-main", "risk": "regression in main flow", "severity": "high", "mitigation": "run suite"}
        ]
        tracelib.write_yaml(task_path / "task_spec" / "final.yaml", spec)
        report = tracelib.load_yaml(task_path / "verifier_report.yaml")
        report["verdict"] = "approve"
        report["acceptance_evidence"] = [
            {"criterion": "tests pass", "status": "pass", "evidence_ref": "command_log:seq=1"}
        ]
        report["risk_coverage"] = [{"risk_id": "r-main", "covered": True, "evidence_ref": "command_log:seq=1"}]
        tracelib.write_yaml(task_path / "verifier_report.yaml", report)

    def test_corpus_promote_golden(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="add audited feature",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-promote",
            model_id="fable",
            root=self.tmp,
        )
        review = tracelib.load_yaml(task_path / "human_review.yaml")
        review["rating"] = "normal"
        tracelib.write_yaml(task_path / "human_review.yaml", review)
        self._make_done_passing(task_path)
        entry = corpus.promote("smoke-promote", self.tmp)
        self.assertEqual(entry["bucket"], "fable_golden")
        dest = self.tmp / "fable-disk" / "corpus" / "fable_golden" / "smoke-promote"
        self.assertTrue((dest / "meta.yaml").exists())
        index = tracelib.read_jsonl(self.tmp / "fable-disk" / "corpus" / "index.jsonl")
        self.assertEqual(index[-1]["task_id"], "smoke-promote")
        with self.assertRaises(ValueError):
            corpus.promote("smoke-promote", self.tmp)

    def test_corpus_promote_refuses_unrated(self) -> None:
        tracelib.scaffold_task(
            goal="unrated work",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-unrated",
            model_id="fable",
            root=self.tmp,
        )
        with self.assertRaises(ValueError):
            corpus.promote("smoke-unrated", self.tmp)

    def test_cli_grade_korean_heavy_keywords(self) -> None:
        script = ROOT / "fable-pack" / "adapters" / "claude-code" / "scripts" / "pack"
        env = os.environ.copy()
        env["FABLE_PACK_PROJECT_ROOT"] = str(self.tmp)
        result = subprocess.run(
            [sys.executable, str(script), "task", "grade", "--goal", "결제 시스템 마이그레이션 진행"],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "HEAVY")

    def test_install_then_uninstall_roundtrip(self) -> None:
        project = self.tmp / "target"
        project.mkdir()
        shutil.copytree(ROOT / "fable-pack", project / "fable-pack")
        install = subprocess.run(
            ["sh", str(project / "fable-pack" / "adapters" / "claude-code" / "install.sh"), str(project)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(install.returncode, 0, install.stderr)
        settings_path = project / ".claude" / "settings.local.json"
        settings = json.loads(settings_path.read_text())
        self.assertIn("PreToolUse", settings["hooks"])
        self.assertIn("NotebookEdit", json.dumps(settings["hooks"]["PreToolUse"]))

        uninstall = subprocess.run(
            ["sh", str(project / "fable-pack" / "adapters" / "claude-code" / "uninstall.sh"), str(project)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(uninstall.returncode, 0, uninstall.stderr)
        self.assertFalse((project / "fable-pack").exists())
        settings = json.loads(settings_path.read_text())
        self.assertNotIn("hooks", settings)

    def test_project_root_uses_claude_project_dir(self) -> None:
        os.environ.pop("FABLE_PACK_PROJECT_ROOT", None)
        old = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.tmp)
        try:
            self.assertEqual(tracelib.project_root(), self.tmp.resolve())
        finally:
            if old is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old
            os.environ["FABLE_PACK_PROJECT_ROOT"] = str(self.tmp)

    def test_scaffold_creates_thinking_capture_logs(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="capture everything",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-capture",
            model_id="fable",
            root=self.tmp,
        )
        for name in ["user_prompt_log.jsonl", "orchestration_log.jsonl", "assistant_log.jsonl"]:
            self.assertTrue((task_path / name).exists(), name)

    def test_orchestration_log_keeps_plan_and_prompt_full(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="plan capture",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-orch",
            model_id="fable",
            root=self.tmp,
        )
        long_plan = "단계별 계획: " + ("아키텍처 제약을 검토한다. " * 100)
        event = eventlib.log_orchestration(task_path, "ExitPlanMode", {"plan": long_plan})
        self.assertGreater(len(event["plan_full"]), 600)
        self.assertIn("아키텍처", event["plan_full"])
        dispatch = eventlib.log_orchestration(
            task_path,
            "Task",
            {"prompt": "워커는 src/auth만 수정한다. " * 50, "description": "auth worker"},
        )
        self.assertGreater(len(dispatch["prompt_full"]), 600)
        todo = eventlib.log_orchestration(
            task_path,
            "TodoWrite",
            {"todos": [{"content": "스펙 작성", "status": "pending"}]},
        )
        self.assertEqual(todo["todos"][0]["content"], "스펙 작성")

    def test_user_prompt_and_assistant_logs(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="dialog capture",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-dialog",
            model_id="fable",
            root=self.tmp,
        )
        eventlib.log_user_prompt(task_path, "로그인 구현하되 기존 인증 흐름 깨지 마", session_id="s1")
        prompts = tracelib.read_jsonl(task_path / "user_prompt_log.jsonl")
        self.assertEqual(len(prompts), 1)
        self.assertIn("로그인", prompts[0]["prompt"])

        eventlib.log_assistant_text(task_path, "접근: 미들웨어 체인 유지, 세션 정책 재사용.")
        eventlib.log_assistant_text(task_path, "접근: 미들웨어 체인 유지, 세션 정책 재사용.")
        turns = tracelib.read_jsonl(task_path / "assistant_log.jsonl")
        self.assertEqual(len(turns), 1)

    def test_last_assistant_text_skips_thinking_and_tool_results(self) -> None:
        transcript = self.tmp / "assistant.jsonl"
        transcript.write_text(
            "\n".join(
                [
                    '{"message": {"role": "user", "content": "do the task"}}',
                    '{"message": {"role": "assistant", "model": "claude-fable-5", "content": [{"type": "thinking", "thinking": "PRIVATE"}, {"type": "text", "text": "First I will check the middleware."}, {"type": "tool_use", "name": "Read", "input": {}}]}}',
                    '{"message": {"role": "user", "content": [{"type": "tool_result", "content": "file body"}]}}',
                    '{"message": {"role": "assistant", "model": "claude-fable-5", "content": [{"type": "text", "text": "Done: middleware order preserved."}]}}',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        text = tracelib.last_assistant_text({"transcript_path": str(transcript)})
        self.assertIsNotNone(text)
        self.assertIn("middleware order preserved", text)
        self.assertIn("check the middleware", text)
        self.assertNotIn("PRIVATE", text)

    def test_plugin_manifests_are_valid(self) -> None:
        plugin = json.loads((ROOT / "fable-pack" / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(plugin["name"], "fable-pack")
        hooks = json.loads((ROOT / "fable-pack" / "hooks" / "hooks.json").read_text())
        for event in ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PreCompact", "Stop"]:
            self.assertIn(event, hooks["hooks"], event)
        serialized = json.dumps(hooks)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", serialized)
        marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual(marketplace["plugins"][0]["name"], "fable-pack")

    def test_cli_on_off_roundtrip(self) -> None:
        script = ROOT / "fable-pack" / "adapters" / "claude-code" / "scripts" / "pack"
        env = os.environ.copy()
        env["FABLE_PACK_PROJECT_ROOT"] = str(self.tmp)

        def run(*cli_args):
            return subprocess.run(
                [sys.executable, str(script), *cli_args],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )

        on = run("on")
        self.assertEqual(on.returncode, 0, on.stderr)
        self.assertIn("recording ON", on.stdout)
        # mode-only: no trace until the first Fable prompt arrives via hook
        self.assertEqual(tracelib.recording_mode(self.tmp), "on")
        self.assertFalse((self.tmp / "fable-disk" / "trace" / "ACTIVE").exists())

        started = tracelib.ensure_prompt_task(self.tmp, "잡담입니다", "claude-fable-5")
        self.assertEqual(started["grade"], "LIGHT")
        active = (self.tmp / "fable-disk" / "trace" / "ACTIVE").read_text().strip()
        meta = tracelib.load_yaml(self.tmp / "fable-disk" / "trace" / active / "meta.yaml")
        self.assertEqual(meta["task_type"], "ambient")

        again = run("on")
        self.assertIn("recording ON (mode persisted)", again.stdout)

        off = run("off")
        self.assertEqual(off.returncode, 0, off.stderr)
        self.assertIn("recording OFF", off.stdout)
        self.assertFalse((self.tmp / "fable-disk" / "trace" / "ACTIVE").exists())
        meta = tracelib.load_yaml(self.tmp / "fable-disk" / "trace" / active / "meta.yaml")
        self.assertIsNotNone(meta["timestamp_end"])
        self.assertIn("already OFF", run("off").stdout)

    def test_recording_mode_persistence(self) -> None:
        self.assertEqual(tracelib.recording_mode(self.tmp), "off")
        tracelib.set_recording_mode("on", self.tmp)
        self.assertEqual(tracelib.recording_mode(self.tmp), "on")
        tracelib.set_recording_mode("off", self.tmp)
        self.assertEqual(tracelib.recording_mode(self.tmp), "off")

    def test_ensure_prompt_task_auto_escalation(self) -> None:
        # casual prompt with no active task -> ambient LIGHT
        started = tracelib.ensure_prompt_task(self.tmp, "이 함수 뭐하는 거야?", "claude-fable-5")
        self.assertIsNotNone(started)
        self.assertEqual(started["grade"], "LIGHT")
        ambient_id = started["task_id"]

        # casual prompt with ambient active -> unchanged
        self.assertIsNone(tracelib.ensure_prompt_task(self.tmp, "고마워", "claude-fable-5"))
        self.assertEqual(tracelib.read_active(self.tmp), ambient_id)

        # slash command -> never escalates
        self.assertIsNone(tracelib.ensure_prompt_task(self.tmp, "/fable-pack:status", "claude-fable-5"))

        # work prompt -> ambient closed, gated task started
        started = tracelib.ensure_prompt_task(self.tmp, "로그인 인증 기능 구현해줘", "claude-fable-5")
        self.assertIsNotNone(started)
        self.assertEqual(started["grade"], "HEAVY")
        self.assertEqual(started["replaced_ambient"], ambient_id)
        gated_id = started["task_id"]
        self.assertEqual(tracelib.read_active(self.tmp), gated_id)
        ambient_meta = tracelib.load_yaml(self.tmp / "fable-disk" / "trace" / ambient_id / "meta.yaml")
        self.assertIsNotNone(ambient_meta["timestamp_end"])

        # next prompt with gated task active -> unchanged
        self.assertIsNone(tracelib.ensure_prompt_task(self.tmp, "그리고 기능 추가로 버그도 수정해", "claude-fable-5"))
        self.assertEqual(tracelib.read_active(self.tmp), gated_id)

    def test_estimate_grade_tiers(self) -> None:
        self.assertEqual(tracelib.estimate_grade("결제 마이그레이션"), "HEAVY")
        self.assertEqual(tracelib.estimate_grade("리팩터링 해줘"), "STANDARD")
        self.assertEqual(tracelib.estimate_grade("implement the new parser"), "STANDARD")
        self.assertEqual(tracelib.estimate_grade("what does this do?"), "LIGHT")

    def test_estimate_prompt_grade_questions_never_escalate(self) -> None:
        self.assertEqual(
            tracelib.estimate_prompt_grade("그럼 한 번 on하면, 계속 start 치는 것처럼 프롬프트 입력되고 동작한다고?"),
            "LIGHT",
        )
        self.assertEqual(tracelib.estimate_prompt_grade("이 인증 미들웨어는 어떻게 동작하는 거야?"), "LIGHT")
        self.assertEqual(tracelib.estimate_prompt_grade("로그인 인증 기능 구현해줘"), "HEAVY")
        self.assertEqual(tracelib.estimate_prompt_grade("이 파서 버그 수정해"), "STANDARD")
        self.assertEqual(
            tracelib.estimate_prompt_grade("길지만 키워드 없는 일반 대화는 아무리 길어도 그냥 잡담으로 남아야 한다 이 문장처럼"),
            "LIGHT",
        )

    def test_observation_placeholder_dedup_per_path(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="dedup check",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-dedup",
            model_id="fable",
            root=self.tmp,
        )
        first_ctx = eventlib.log_context(task_path, "Read", {"file_path": "src/app.py"})
        self.assertIsNotNone(eventlib.log_observation_placeholder(task_path, first_ctx))
        second_ctx = eventlib.log_context(task_path, "Read", {"file_path": "src/app.py"})
        self.assertIsNone(eventlib.log_observation_placeholder(task_path, second_ctx))
        observations = tracelib.read_jsonl(task_path / "observation_log.jsonl")
        self.assertEqual(len(observations), 1)

    def _hook_env(self) -> dict:
        env = os.environ.copy()
        env["FABLE_PACK_PROJECT_ROOT"] = str(self.tmp)
        env["FABLE_PACK_FORCE"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def _run_hook(self, script: str, payload: dict) -> subprocess.CompletedProcess:
        hook = ROOT / "fable-pack" / "adapters" / "claude-code" / "hooks" / script
        return subprocess.run(
            [sys.executable, str(hook)],
            input=json.dumps(payload),
            env=self._hook_env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_pre_tool_use_block_dedups_identical_errors(self) -> None:
        tracelib.set_recording_mode("on", self.tmp)
        tracelib.scaffold_task(
            goal="gated work",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-block-dedup",
            model_id="fable",
            root=self.tmp,
        )
        payload = {"tool_name": "Edit", "tool_input": {"file_path": str(self.tmp / "src" / "app.py")}}
        first = self._run_hook("pre_tool_use.py", payload)
        self.assertEqual(first.returncode, 2)
        self.assertIn("must_read is empty", first.stderr)
        second = self._run_hook("pre_tool_use.py", payload)
        self.assertEqual(second.returncode, 2)
        self.assertIn("same", second.stderr)
        self.assertNotIn("must_read is empty", second.stderr)

    def test_stop_warns_only_on_state_change(self) -> None:
        tracelib.set_recording_mode("on", self.tmp)
        task_path = tracelib.scaffold_task(
            goal="warn dedup",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-stop-dedup",
            model_id="fable",
            root=self.tmp,
        )
        eventlib.log_edit(task_path, "Edit", {"file_path": "src/app.py"}, allowed=True)
        first = self._run_hook("stop.py", {"hook_event_name": "Stop"})
        self.assertIn("done gate is not passing", first.stderr)
        second = self._run_hook("stop.py", {"hook_event_name": "Stop"})
        self.assertEqual(second.stderr.strip(), "")

    def test_post_tool_use_skips_fable_disk_reads(self) -> None:
        tracelib.set_recording_mode("on", self.tmp)
        task_path = tracelib.scaffold_task(
            goal="self-recording check",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-selfrec",
            model_id="fable",
            root=self.tmp,
        )
        disk_read = {"tool_name": "Read", "tool_input": {"file_path": str(task_path / "context_pack.yaml")}}
        result = self._run_hook("post_tool_use.py", disk_read)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(tracelib.read_jsonl(task_path / "context_log.jsonl"), [])
        normal_read = {"tool_name": "Read", "tool_input": {"file_path": str(self.tmp / "src" / "app.py")}}
        self._run_hook("post_tool_use.py", normal_read)
        events = tracelib.read_jsonl(task_path / "context_log.jsonl")
        self.assertEqual(len(events), 1)

    def test_decision_skeletons_do_not_satisfy_spec_gate(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="skeleton check",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-skeleton",
            model_id="fable",
            root=self.tmp,
        )
        events = tracelib.read_jsonl(task_path / "decision_events.jsonl")
        todo_types = {e["event_type"] for e in events if e.get("status") == "todo"}
        self.assertIn("context_selection", todo_types)
        self.assertIn("acceptance_evidence_selection", todo_types)
        result = validate.validate_task("smoke-skeleton", self.tmp, "spec")
        self.assertTrue(any("missing decision event types" in error for error in result.errors))

    def test_heavy_scaffold_includes_heavy_skeletons(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="heavy skeleton check",
            grade="HEAVY",
            task_type="auth_change",
            task_id="smoke-heavy-skel",
            model_id="fable",
            root=self.tmp,
        )
        events = tracelib.read_jsonl(task_path / "decision_events.jsonl")
        todo_types = {e["event_type"] for e in events if e.get("status") == "todo"}
        self.assertIn("architecture_boundary", todo_types)
        self.assertIn("counterfactual_boundary", todo_types)

    def test_placeholder_has_required_fill(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="fill template",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-reqfill",
            model_id="fable",
            root=self.tmp,
        )
        context = eventlib.log_context(task_path, "Read", {"file_path": "src/a.py"})
        placeholder = eventlib.log_observation_placeholder(task_path, context)
        self.assertIn("required_fill", placeholder)
        self.assertIn("extracted_facts", placeholder["required_fill"])

    def test_corpus_promote_requires_approve_verdict(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="unapproved work",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-noapprove",
            model_id="fable",
            root=self.tmp,
        )
        review = tracelib.load_yaml(task_path / "human_review.yaml")
        review["rating"] = "normal"
        tracelib.write_yaml(task_path / "human_review.yaml", review)
        with self.assertRaises(ValueError) as ctx:
            corpus.promote("smoke-noapprove", self.tmp)
        self.assertIn("approve", str(ctx.exception))

    def test_shadow_scaffold_creates_pair_structure(self) -> None:
        import compare

        tracelib.scaffold_task(
            goal="implement auth flow",
            grade="HEAVY",
            task_type="auth_change",
            task_id="smoke-shadowpair",
            model_id="fable",
            root=self.tmp,
        )
        trace_dir = compare.scaffold_shadow("smoke-shadowpair", "claude-opus-4-8", self.tmp)
        self.assertTrue((trace_dir / "input_snapshot.yaml").exists())
        self.assertTrue((trace_dir / "task_spec" / "final.yaml").exists())
        self.assertTrue((trace_dir / "decision_events.jsonl").exists())
        self.assertTrue((trace_dir.parent / "critiques.yaml").exists())
        spec = tracelib.load_yaml(trace_dir / "task_spec" / "final.yaml")
        self.assertEqual(spec["user_goal"], "implement auth flow")

    def test_rules_export_sanitizes_and_dedupes(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="rule source",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-rules",
            model_id="fable",
            root=self.tmp,
        )
        patch = {
            "task_id": "smoke-rules",
            "source": {"type": "self_review", "ref": "self_review.yaml"},
            "patches": {
                "schema": [],
                "gate_rules": [
                    {"rule_id": "r1", "condition": "auth task without middleware check", "block_message": "check middleware chain", "evidence_ref": "observation_log:seq=3"},
                    {"rule_id": "r1", "condition": "auth task without middleware check", "block_message": "check middleware chain", "evidence_ref": "observation_log:seq=3"},
                ],
                "playbook_rules": [{"rule": "export API_KEY=sk-abcdef1234567890 before deploy"}],
                "examples": [{"type": "good", "name": "secret-project-example"}],
                "invariants": [],
            },
        }
        tracelib.write_yaml(task_path / "distillation_patch.yaml", patch)
        export = corpus.export_rules(self.tmp)["fable_pack_rules_export"]
        self.assertEqual(export["source_traces"], 1)
        self.assertEqual(len(export["rules"]["gate_rules"]), 1)
        self.assertNotIn("evidence_ref", export["rules"]["gate_rules"][0])
        serialized = json.dumps(export, ensure_ascii=False)
        self.assertNotIn("sk-abcdef1234567890", serialized)
        self.assertNotIn("secret-project-example", serialized)
        with_examples = corpus.export_rules(self.tmp, include_examples=True)["fable_pack_rules_export"]
        self.assertIn("examples", with_examples["rules"])

    def test_spec_gate_requires_restated_goal(self) -> None:
        tracelib.scaffold_task(
            goal="interpretation check",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-restate",
            model_id="fable",
            root=self.tmp,
        )
        result = validate.validate_task("smoke-restate", self.tmp, "spec")
        self.assertTrue(any("restated_goal" in error for error in result.errors))

    def test_timeline_merges_streams_in_order(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="timeline check",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-timeline",
            model_id="fable",
            root=self.tmp,
        )
        eventlib.log_user_prompt(task_path, "로그인 구현해줘")
        ctx = eventlib.log_context(task_path, "Read", {"file_path": "src/auth.py"})
        eventlib.log_observation_placeholder(task_path, ctx)
        eventlib.log_edit(task_path, "Edit", {"file_path": "src/auth.py"}, allowed=True)
        eventlib.log_command(task_path, {"command": "pytest"})
        entries = tracelib.timeline("smoke-timeline", self.tmp)
        kinds = [e["kind"] for e in entries]
        for kind in ["PHASE", "PROMPT", "READ", "OBSERVE", "DECIDE", "EDIT", "RUN"]:
            self.assertIn(kind, kinds, kind)
        timestamps = [e["ts"] for e in entries]
        self.assertEqual(timestamps, sorted(timestamps))
        prompt_entries = [e for e in entries if e["kind"] == "PROMPT"]
        self.assertIn("로그인", prompt_entries[0]["summary"])
        decide_only = [e for e in tracelib.timeline("smoke-timeline", self.tmp) if e["kind"] == "DECIDE"]
        self.assertTrue(any("(todo)" in e["summary"] for e in decide_only))

    def test_done_gate_requires_approve_verdict(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="verdict check",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-verdict",
            model_id="fable",
            root=self.tmp,
        )
        self._make_done_passing(task_path)
        report = tracelib.load_yaml(task_path / "verifier_report.yaml")
        report["verdict"] = "request_changes"
        tracelib.write_yaml(task_path / "verifier_report.yaml", report)
        result = validate.done_gate(task_path, self.tmp)
        self.assertTrue(any("verdict must be approve" in error for error in result.errors))

    def test_done_gate_closes_spec_risk_loop(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="risk loop check",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-riskloop",
            model_id="fable",
            root=self.tmp,
        )
        self._make_done_passing(task_path)
        spec = tracelib.load_yaml(task_path / "task_spec" / "final.yaml")
        spec["risk_register"].append(
            {"id": "r-oauth", "risk": "OAuth callback regression", "severity": "blocking", "mitigation": "regression test"}
        )
        tracelib.write_yaml(task_path / "task_spec" / "final.yaml", spec)
        result = validate.done_gate(task_path, self.tmp)
        self.assertTrue(any("r-oauth" in error for error in result.errors))
        report = tracelib.load_yaml(task_path / "verifier_report.yaml")
        report["risk_coverage"].append({"risk_id": "r-oauth", "covered": True, "evidence_ref": "command_log:seq=2"})
        tracelib.write_yaml(task_path / "verifier_report.yaml", report)
        result = validate.done_gate(task_path, self.tmp)
        self.assertTrue(result.ok, result.errors)

    def test_contract_edit_gate_cross_checks_edit_log(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="contract check",
            grade="HEAVY",
            task_type="auth_change",
            task_id="smoke-contract",
            model_id="fable",
            root=self.tmp,
        )
        tracelib.write_yaml(task_path / "worker_contracts" / "w1.yaml", {
            "worker_contract": {
                "scope": {"allowed_files": ["src/auth/*"], "forbidden_files": ["config/secrets.yaml"]},
            }
        })
        eventlib.log_edit(task_path, "Edit", {"file_path": "src/auth/login.py"}, allowed=True)
        eventlib.log_edit(task_path, "Edit", {"file_path": "config/secrets.yaml"}, allowed=True)
        eventlib.log_edit(task_path, "Edit", {"file_path": "src/other/stray.py"}, allowed=True)
        report = {"unplanned_changes": []}
        result = validate.contract_edit_gate(task_path, self.tmp, report)
        errors = "\n".join(result.errors)
        self.assertIn("contract-forbidden file: config/secrets.yaml", errors)
        self.assertIn("outside contract allowed_files", errors)
        self.assertNotIn("src/auth/login.py", errors)
        report = {"unplanned_changes": [{"path": "src/other/stray.py", "has_decision_event": True}]}
        result = validate.contract_edit_gate(task_path, self.tmp, report)
        self.assertNotIn("stray.py", "\n".join(result.errors))

    def test_meta_records_version_triple(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="version check",
            grade="LIGHT",
            task_type="ambient",
            task_id="smoke-versions",
            model_id="fable",
            root=self.tmp,
        )
        meta = tracelib.load_yaml(task_path / "meta.yaml")
        self.assertEqual(meta["versions"]["runtime"], tracelib.PACK_VERSION)
        self.assertEqual(meta["versions"]["protocol"], tracelib.PROTOCOL_VERSION)

    def test_shadow_delta_flags_weak_coverage(self) -> None:
        import compare

        base = tracelib.scaffold_task(
            goal="implement oauth flow",
            grade="HEAVY",
            task_type="auth_change",
            task_id="smoke-weak",
            model_id="fable",
            root=self.tmp,
        )
        spec = tracelib.load_yaml(base / "task_spec" / "final.yaml")
        spec["risk_register"] = [
            {"id": "r1", "risk": "OAuth callback regression breaks login", "severity": "high", "mitigation": "regression"},
            {"id": "r2", "risk": "session expiry mismatch", "severity": "high", "mitigation": "ttl test"},
        ]
        tracelib.write_yaml(base / "task_spec" / "final.yaml", spec)
        fallback_dir = self.tmp / "fallback-trace"
        (fallback_dir / "task_spec").mkdir(parents=True)
        tracelib.write_yaml(fallback_dir / "task_spec" / "final.yaml", {
            "task_classification": {"primary_type": "auth_change"},
            "risk_register": [{"id": "x", "risk": "session expiry mismatch", "severity": "high"}],
            "non_goals": ["styling"],
            "rejected_alternatives": [{"category": "tempting_shortcut", "alternative": "skip tests"}],
            "acceptance_criteria": [{"criterion": "login works end to end"}],
            "inferred_requirements": {"functional": [{"requirement": "login"}]},
            "repo_context": {"architectural_constraints": [{"constraint": "keep middleware order"}]},
        })
        delta = compare.make_shadow_delta("smoke-weak", "claude-opus-4-8", str(fallback_dir), self.tmp)
        weak_texts = "\n".join(str(item) for item in delta["missed_by_fallback"])
        self.assertIn("OAuth callback regression", weak_texts)
        self.assertNotIn("session expiry mismatch", "\n".join(
            str(i) for i in delta["missed_by_fallback"] if str(i.get("id", "")).startswith("weak_risk_register")
        ))

    def test_project_root_ignores_lookalike_directories(self) -> None:
        os.environ.pop("FABLE_PACK_PROJECT_ROOT", None)
        old_claude = os.environ.pop("CLAUDE_PROJECT_DIR", None)
        try:
            # a directory merely NAMED fable-pack (e.g. a repo checkout in $HOME)
            # must not capture child projects
            (self.tmp / "fable-pack").mkdir()
            project = self.tmp / "some-project"
            project.mkdir()
            self.assertEqual(tracelib.project_root(project), project.resolve())

            # a real per-project install (fable-pack/PACK_VERSION) does anchor
            install_root = self.tmp / "installed-project"
            (install_root / "fable-pack").mkdir(parents=True)
            (install_root / "fable-pack" / "PACK_VERSION").write_text("0.5\n")
            subdir = install_root / "src" / "deep"
            subdir.mkdir(parents=True)
            self.assertEqual(tracelib.project_root(subdir), install_root.resolve())

            # a real recording disk (trace+config) anchors too
            disk_root_project = self.tmp / "disk-project"
            (disk_root_project / "fable-disk" / "trace").mkdir(parents=True)
            (disk_root_project / "fable-disk" / "config").mkdir(parents=True)
            inner = disk_root_project / "lib"
            inner.mkdir()
            self.assertEqual(tracelib.project_root(inner), disk_root_project.resolve())

            # CLAUDE_PROJECT_DIR (the session-bound folder) always wins
            os.environ["CLAUDE_PROJECT_DIR"] = str(project)
            self.assertEqual(tracelib.project_root(subdir), project.resolve())
        finally:
            if old_claude is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old_claude
            os.environ["FABLE_PACK_PROJECT_ROOT"] = str(self.tmp)

    def test_prompt_hook_intercepts_on_off_toggle(self) -> None:
        tracelib.ensure_disk(self.tmp)
        result = self._run_hook("user_prompt_submit.py", {"prompt": "/fable-pack:on"})
        self.assertEqual(result.returncode, 0, result.stderr)
        control = json.loads(result.stdout)
        self.assertEqual(control["decision"], "block")
        self.assertIn("recording ON", control["reason"])
        self.assertEqual(tracelib.recording_mode(self.tmp), "on")
        # toggle alone creates no trace
        self.assertFalse((self.tmp / "fable-disk" / "trace" / "ACTIVE").exists())

        # a normal prompt is NOT blocked and starts the ambient trace
        normal = self._run_hook("user_prompt_submit.py", {"prompt": "이 함수 설명해봐"})
        self.assertEqual(normal.returncode, 0, normal.stderr)
        self.assertNotIn("block", normal.stdout)
        active = (self.tmp / "fable-disk" / "trace" / "ACTIVE").read_text().strip()

        off = self._run_hook("user_prompt_submit.py", {"prompt": "/fable-pack:off"})
        control = json.loads(off.stdout)
        self.assertEqual(control["decision"], "block")
        self.assertIn(active, control["reason"])
        self.assertEqual(tracelib.recording_mode(self.tmp), "off")
        self.assertFalse((self.tmp / "fable-disk" / "trace" / "ACTIVE").exists())

    def test_malformed_string_entries_fail_gates_without_crashing(self) -> None:
        task_path = tracelib.scaffold_task(
            goal="malformed spec",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-malformed",
            model_id="fable",
            root=self.tmp,
        )
        spec = tracelib.load_yaml(task_path / "task_spec" / "final.yaml")
        spec["acceptance_criteria"] = ["tests pass", "docs updated"]
        spec["risk_register"] = ["might break login"]
        spec["rejected_alternatives"] = ["do nothing"]
        tracelib.write_yaml(task_path / "task_spec" / "final.yaml", spec)
        report = tracelib.load_yaml(task_path / "verifier_report.yaml")
        report["risk_coverage"] = ["covered everything"]
        tracelib.write_yaml(task_path / "verifier_report.yaml", report)

        spec_result = validate.spec_gate(task_path, self.tmp)
        done_result = validate.done_gate(task_path, self.tmp)
        self.assertFalse(spec_result.ok)
        self.assertFalse(done_result.ok)
        all_errors = "\n".join(spec_result.errors + done_result.errors)
        self.assertIn("acceptance_criteria[0] must be a mapping", all_errors)
        self.assertIn("risk_register[0] must be a mapping", all_errors)
        self.assertIn("risk_coverage[0] must be a mapping", all_errors)

    def test_stop_hook_survives_malformed_trace_without_traceback(self) -> None:
        tracelib.set_recording_mode("on", self.tmp)
        task_path = tracelib.scaffold_task(
            goal="crash guard",
            grade="STANDARD",
            task_type="feature",
            task_id="smoke-crashguard",
            model_id="fable",
            root=self.tmp,
        )
        spec = tracelib.load_yaml(task_path / "task_spec" / "final.yaml")
        spec["acceptance_criteria"] = ["just a string"]
        tracelib.write_yaml(task_path / "task_spec" / "final.yaml", spec)
        eventlib.log_edit(task_path, "Edit", {"file_path": "src/app.py"}, allowed=True)
        result = self._run_hook("stop.py", {"hook_event_name": "Stop"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("must be a mapping", result.stderr)

    def test_cli_refuses_non_fable_reference_trace(self) -> None:
        script = ROOT / "fable-pack" / "adapters" / "claude-code" / "scripts" / "pack"
        env = os.environ.copy()
        env["FABLE_PACK_PROJECT_ROOT"] = str(self.tmp)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "task",
                "start",
                "--goal",
                "add audited feature",
                "--grade",
                "STANDARD",
                "--task-type",
                "feature",
                "--id",
                "non-fable",
                "--model",
                "claude-sonnet",
            ],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("not Fable", result.stderr)


if __name__ == "__main__":
    unittest.main()
