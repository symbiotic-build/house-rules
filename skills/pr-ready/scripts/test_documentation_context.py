"""Real selector integration on small local Git snapshots; no model or network calls."""
import argparse
import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import prepare
import prompt

ROOT = Path(__file__).resolve().parents[3]
TOOL_ROOT = ROOT / "skills/spec-writing"
TOOLS = ("scripts/spec_docs.py", "scripts/runtime.json", "scripts/requirements.lock",
         "references/format-contract.json")
ASSIGNMENT = {"version": 1, "sections": ["example-demo#acceptance"]}


class DocumentationFixture:
    """Shared setup and assertions for independent test classes."""

    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.seed = Path(temporary.name)
        helper = cls()
        helper.root = cls.seed
        cls.addClassCleanup(helper.doCleanups)
        with patch.dict(os.environ, {
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }):
            helper.build_fixture()
        cls.checker = helper.checker
        cls.seed_rule_revision, cls.seed_revision = helper.rule_revision, helper.revision

    def build_fixture(self):
        self.rules, self.repo = self.root / "rules", self.root / "repo"
        for repo in (self.rules, self.repo):
            repo.mkdir()
            self.git(repo, "init", "-q", "-b", "main")
        for path in TOOLS:
            self.write(self.rules, "skills/spec-writing/" + path, (TOOL_ROOT / path).read_bytes())
        for path in ("skills/pr-ready/scripts/prompt.py", "skills/pr-ready/scripts/prepare.py", "rules/writing.md", "rules/specifications.md"):
            self.write(self.rules, path, (ROOT / path).read_bytes())
        self.rule_revision = self.commit(self.rules)
        spec = importlib.util.spec_from_file_location("_fixture_spec_docs", TOOL_ROOT / "scripts/spec_docs.py")
        self.checker = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.checker
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(self.checker)
        fixtures = TOOL_ROOT / "scripts/fixtures/miniature"
        paths = {"docs/" + name: (fixtures / name).read_bytes() for name in ("ENTITIES.json", "DOCUMENTS.json")}
        paths.update({"docs/example/" + name: (fixtures / name).read_bytes()
                      for name in ("acceptance.md", "settings.md")})
        paths["docs/example/settings.md"] += ("\n" + " ".join(["word"] * 30) + ".\n").encode()
        manifest = json.loads(paths["docs/DOCUMENTS.json"])
        manifest["documents"][0].pop("approval")
        manifest["documents"][0]["status"] = "draft"
        paths["docs/DOCUMENTS.json"] = self.checker.canonical(manifest)
        paths.update(self.checker.generate_navigation(self.checker.load_corpus(paths)))
        for path, data in paths.items():
            self.write(self.repo, path, data)
        self.revision = self.commit(self.repo)
        self.assignment_file = self.root / "assignment.json"
        self.assignment_file.write_text(json.dumps(ASSIGNMENT))

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict(os.environ, {
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.rules, self.repo = self.root / "rules", self.root / "repo"
        for name in ("rules", "repo"):
            shutil.copytree(self.seed / name, self.root / name)
        self.rule_revision, self.revision = self.seed_rule_revision, self.seed_revision
        self.assignment_file = self.root / "assignment.json"
        self.assignment_file.write_text(json.dumps(ASSIGNMENT))

    def git(self, repo, *args):
        return subprocess.run(["git", "--no-replace-objects", "-C", str(repo), *args],
                              capture_output=True, check=True, timeout=5, stdin=subprocess.DEVNULL).stdout.decode().strip()

    def write(self, repo, path, data):
        destination = repo / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data.encode() if isinstance(data, str) else data)

    def commit(self, repo):
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-qm", "Synthetic fixture")
        return self.git(repo, "rev-parse", "HEAD")

    def pack(self, assignment=ASSIGNMENT, **kwargs):
        with prompt.Commit(self.rules, self.rule_revision) as source, prompt.Commit(self.repo, self.revision) as target:
            return prompt.build_pack(source, target=target, assignment=assignment, **kwargs)

    def review(self, *, base=None, **kwargs):
        values = dict(pr=None, issue=[], spec=None, tests=None, test_prefix="PT", lens="generalist-a",
                      summary=None, format="diff", cli="codex", context_only=True,
                      assignment=self.assignment_file)
        values.update(kwargs)
        with patch.object(prepare, "HERE", self.rules / "skills/pr-ready/scripts"), \
                patch.object(prepare, "pr_context", return_value=({}, [], [], "(none)", [], [], [])):
            return prepare.review(self.repo, argparse.Namespace(**values), base or self.revision, None, self.revision)


class DocumentationReviewTests(DocumentationFixture, unittest.TestCase):
    def test_specification_rules_follow_target_in_pack_and_diff_only(self):
        self.write(self.rules, "prompts/roles/reviewer.md", "Role rules\n")
        self.write(self.rules, "prompts/lenses/generalist-a.md", "Lens instructions\n")
        self.write(self.rules, "rules/specifications.md", "Specification rules\n")
        self.rule_revision = self.commit(self.rules)
        self.write(self.repo, "AGENTS.md", "Target rules\n")
        manifest_path = self.repo / "docs/DOCUMENTS.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["inventory"].append({"path": "AGENTS.md", "kind": "other", "reason": "Synthetic target rules."})
        manifest_path.write_text(json.dumps(manifest))
        self.revision = self.commit(self.repo)
        task = self.root / "task.txt"
        for layout in ("pack", "diff", "structured"):
            with self.subTest(layout=layout):
                task.write_text("Task context\n" + ("\n# 7. Lens instructions\n" if layout == "structured" else ""))
                pack, _ = self.pack(role="reviewer", lens="generalist-a", target_base=self.revision,
                                    tasks=[(task, "review-context")])
                markers = [line for line in pack.splitlines() if line in
                           (b"Role rules", b"Lens instructions", b"Target rules", b"Specification rules")]
                self.assertEqual(markers, [b"Role rules", b"Specification rules", b"Target rules", b"Lens instructions"]
                                 if layout == "structured" else
                                 [b"Role rules", b"Lens instructions", b"Target rules", b"Specification rules"])

    def test_registered_documentation_uses_round_plan_before_each_final_lens(self):
        for folder in ("prompts", "rules"):
            shutil.copytree(ROOT / folder, self.rules / folder, dirs_exist_ok=True)
        self.write(self.rules, "skills/pr-ready/scripts/review-panel.lenses",
                   (ROOT / "skills/pr-ready/scripts/review-panel.lenses").read_bytes())
        self.rule_revision = self.commit(self.rules)
        task = self.root / "context.txt"
        lenses = ("generalist-a", "design-spec")
        compiler = self.rules / "skills/pr-ready/scripts/prompt.py"
        preparer = self.rules / "skills/pr-ready/scripts/prepare.py"
        environment = dict(os.environ, REVIEW_PYTHON=sys.executable)
        for assembly in ("one-call", "standalone"):
            with self.subTest(assembly=assembly):
                packs = []
                for lens in lenses:
                    command = [sys.executable, "-B", str(preparer), "review", str(self.repo),
                               "--base", self.revision, "--no-fetch", "--lens", lens,
                               "--reviewers", *lenses]
                    if assembly == "one-call":
                        # The service appends this context to its compiled pack.
                        task.write_text("Shared review context.\n\n# 7. Lens instructions\n")
                        command = [sys.executable, "-B", str(compiler), "--repo", str(self.rules),
                                   "--rev", self.rule_revision, "--role", "reviewer", "--lens", lens,
                                   "--target", str(self.repo), "--target-base", self.revision,
                                   "--assignment", str(self.assignment_file), "--task", str(task),
                                   "--reviewers", *lenses]
                    else:
                        command += ["--assignment", str(self.assignment_file)]
                    result = subprocess.run(command, env=environment, capture_output=True,
                                            timeout=10, stdin=subprocess.DEVNULL)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    packs.append(result.stdout.split(b"# 7. Lens instructions\n", 1))
                self.assertEqual([len(parts) for parts in packs], [2, 2])
                self.assertEqual(packs[0][0], packs[1][0])
                self.assertNotEqual(packs[0][1], packs[1][1])
                self.assertIn(b"# Complete registry", packs[0][0])
                self.assertIn(b'"id": "generalist-a"', packs[0][0])
                self.assertIn(b'"id": "design-spec"', packs[0][0])

    def test_relative_assignment_uses_callers_directory(self):
        # A conflicting target file must not replace the caller's assignment.
        (self.repo / 'assignment.json').write_text('{}')
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'skills/pr-ready/scripts/prepare.py'),
                                 'review', str(self.repo), '--base', self.revision, '--no-fetch',
                                 '--context-only', '--assignment', 'assignment.json'], cwd=self.root,
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'# Complete registry', result.stdout)

    def test_review_reuses_captured_base_for_report_documentation_and_diff(self):
        self.write(self.repo, 'rules/example.md', '- Never skip validation.\n')
        manifest_path = self.repo / 'docs/DOCUMENTS.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['inventory'].append({'path': 'rules/example.md', 'kind': 'other', 'reason': 'Synthetic rule input.'})
        manifest_path.write_text(json.dumps(manifest))
        base = self.commit(self.repo)
        self.git(self.repo, 'branch', 'comparison', base)
        self.write(self.repo, 'rules/example.md', '- Avoid skipping validation.\n')
        path = self.repo / 'docs/example/acceptance.md'
        path.write_text(path.read_text().replace('**Result:** Return', '**Result:** Report'))
        self.revision = self.commit(self.repo)
        original = prepare.git
        captures = []

        def move_base(repo, *args, **kwargs):
            result = original(repo, *args, **kwargs)
            if args[:1] == ('merge-base',):
                captures.append(result.strip())
                self.git(self.repo, 'update-ref', 'refs/heads/comparison', self.revision)
            return result

        with patch.object(prepare, 'git', side_effect=move_base):
            output = self.review(base='comparison', assignment=None)
        self.assertEqual(captures, [base])
        self.assertIn(f'Base: `{base}`;', output)
        self.assertIn('base:example-demo#test-stale-revision', output)
        self.assertIn('**Result:** Return', output)
        self.assertIn('**Result:** Report', output)
        self.assertIn('-**Result:** Return', output)
        self.assertIn('+**Result:** Report', output)

    def test_review_preparer_compares_base_and_selects_unchanged_tests(self):
        base = self.revision
        path = self.repo / 'docs/example/acceptance.md'
        path.write_text(path.read_text().replace('**Result:** Return', '**Result:** Report'))
        self.revision = self.commit(self.repo)
        output = self.review(base=base)
        self.assertIn('# Requirement changes', output)
        self.assertIn('base:example-demo#test-stale-revision', output)
        self.assertIn('**Result:** Return', output)
        self.assertIn('**Result:** Report', output)
        path.write_text(path.read_text().replace('### Requirement: stale-revision', '### Former stale-revision'))
        self.revision = self.commit(self.repo)
        with self.assertRaisesRegex(prepare.PrepareError, 'D22'):
            self.review(base=base)

    def test_review_entry_requires_actual_coverage_even_without_assignment_plan(self):
        with self.assertRaisesRegex(prepare.PrepareError, 'D26'):
            self.review(lens='security')
        self.assertIn('# Complete registry', self.review())
        self.assertIn('# Complete registry', self.review(lens='design-spec'))
        with prompt.Commit(self.rules, self.rule_revision) as source, prompt.Commit(self.repo, self.revision) as target:
            with self.assertRaisesRegex(prompt.PromptError, 'D26'):
                prompt.documentation_context(source, target, ASSIGNMENT, base=self.revision, plan=prompt.review_plan(['security']))

    def test_review_comparison_rejects_malformed_assignment_before_deriving_tests(self):
        with prompt.Commit(self.rules, self.rule_revision) as source, prompt.Commit(self.repo, self.revision) as target:
            for assignment in (b'[]', {'version': 1, 'sections': ['example-demo#acceptance'], 'required_test_reviews': [{}]}):
                with self.subTest(assignment=assignment), self.assertRaisesRegex(prompt.PromptError, 'D02'):
                    prompt.documentation_context(source, target, assignment, base=self.revision, plan=prompt.review_plan(['generalist-a']))

    def test_direct_review_compiler_requires_a_comparison_base(self):
        with self.assertRaisesRegex(prompt.PromptError, '--target-base'):
            with prompt.Commit(self.rules, self.rule_revision) as source, prompt.Commit(self.repo, self.revision) as target:
                prompt.documentation_context(source, target, ASSIGNMENT, plan=prompt.review_plan(['generalist-a']))

    def test_preparer_includes_mandatory_context_even_in_diff_mode(self):
        output = self.review()
        self.assertIn("# Complete registry", output)
        self.assertIn("Call capacity bounds documents in one native call.", output)
        self.assertIn("UTF-8 bytes", output)
        self.assertNotIn("Full document", output)
        self.assertEqual(output.count("# Complete registry"), 1)

    def test_review_without_assignment_and_without_registered_changes_has_no_context(self):
        base = self.revision
        self.write(self.repo, 'source.py', 'value = 1\n')
        self.revision = self.commit(self.repo)
        output = self.review(base=base, assignment=None)
        self.assertEqual(output.count('No registered documentation changed in this range.'), 1)
        self.assertNotIn('# Complete registry', output)

    def test_review_without_assignment_selects_changed_section_and_linked_tests(self):
        base = self.revision
        path = self.repo / 'docs/example/acceptance.md'
        path.write_text(path.read_text().replace('**Result:** Return', '**Result:** Report'))
        self.revision = self.commit(self.repo)
        output = self.review(base=base, assignment=None)
        self.assertIn('"sections": [\n      "example-demo#acceptance"\n    ]', output)
        self.assertIn('base:example-demo#test-stale-revision', output)
        self.assertIn('**Result:** Report', output)
        self.assertNotIn('No registered documentation changed', output)

    def test_explicit_assignment_still_selects_unchanged_sections(self):
        output = self.review()
        self.assertIn('# Complete registry', output)
        self.assertNotIn('No registered documentation changed', output)

    def test_derived_context_over_size_limit_names_sections_and_fails(self):
        base = self.revision
        path = self.repo / 'docs/example/acceptance.md'
        path.write_text(path.read_text().replace('**Result:** Return', '**Result:** Report'))
        self.revision = self.commit(self.repo)
        with patch.object(prepare, 'CODEX_LIMIT', 100):
            with self.assertRaisesRegex(prepare.PrepareError, 'Size guard:.*') as caught:
                self.review(base=base, assignment=None)
        self.assertIn('Documentation sections: example-demo#acceptance', str(caught.exception))

    def test_review_derives_from_merge_base_without_assigning_base_only_changes(self):
        base = self.revision
        path = self.repo / 'docs/example/acceptance.md'
        path.write_text(path.read_text().replace('**Result:** Return', '**Result:** Report'))
        changed_base = self.commit(self.repo)
        self.git(self.repo, 'checkout', '--detach', base)
        self.write(self.repo, 'source.py', 'value = 1\n')
        self.revision = self.commit(self.repo)
        output = self.review(base=changed_base, assignment=None)
        self.assertIn('No registered documentation changed in this range.', output)
        self.assertNotIn('# Complete registry', output)

    def test_python39_entry_delegates_documentation_to_configured_environment(self):
        interpreter = Path('/usr/bin/python3')
        if not interpreter.exists():
            self.skipTest('system Python is unavailable')
        version = subprocess.run([str(interpreter), '-c', 'import sys; print(sys.version_info[:2] < (3, 11))'],
                                 stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=5).stdout.strip()
        if version != b'True':
            self.skipTest('system Python does not need the tool environment bridge')
        environment = dict(os.environ, REVIEW_PYTHON=sys.executable)
        result = subprocess.run([str(interpreter), '-B', str(ROOT / 'skills/pr-ready/scripts/prepare.py'),
                                 'review', str(self.repo), '--base', self.revision, '--no-fetch', '--context-only'],
                                env=environment, stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'No registered documentation changed in this range.', result.stdout)

    def test_python39_review_service_without_tool_environment_reviews_without_documentation_pack(self):
        self.write(self.repo, 'source.py', 'value = 2\n')
        base, self.revision = self.revision, self.commit(self.repo)
        output, errors = io.StringIO(), io.StringIO()
        environment = {key: value for key, value in os.environ.items() if key != 'REVIEW_PYTHON'}
        with patch.dict(os.environ, environment, clear=True), patch.object(prepare.sys, 'version_info', (3, 9, 6)), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = prepare.main(['review', str(self.repo), '--base', base, '--no-fetch', '--rev', self.revision])
        self.assertEqual(code, 0, errors.getvalue())
        self.assertIn('Registered documentation context was not prepared', output.getvalue())
        self.assertNotIn('# Complete registry', output.getvalue())

    def test_preparer_over_budget_explicit_context_fails(self):
        self.assignment_file.write_text(json.dumps({**ASSIGNMENT, "budget_bytes": 100}))
        with self.assertRaisesRegex(prepare.PrepareError, "D25"):
            self.review()

    def test_preparer_reserves_context_before_optional_material_and_never_trims_it(self):
        baseline = self.review()
        with patch.object(prepare, "CODEX_LIMIT", len(baseline) - 50):
            with self.assertRaisesRegex(prepare.PrepareError, "Size guard"):
                self.review()
        self.assertEqual(self.review(), baseline)


class DocumentationSnapshotTests(DocumentationFixture, unittest.TestCase):
    def test_compiler_never_acquires_unrelated_binary_blobs(self):
        self.write(self.repo, 'asset.bin', b'UNRELATED BLOB CANARY')
        self.revision = self.commit(self.repo)
        with patch.object(subprocess, 'run', wraps=subprocess.run) as run:
            pack, _ = self.pack()
        asset_oid = self.git(self.repo, 'rev-parse', 'HEAD:asset.bin').encode()
        batches = [call.kwargs.get('input', b'') for call in run.call_args_list if 'cat-file' in call.args[0]]
        self.assertTrue(batches)
        self.assertFalse(any(asset_oid in batch for batch in batches))
        lookups = [call.args[0] for call in run.call_args_list if 'ls-tree' in call.args[0] and '-rz' not in call.args[0]]
        requested = [call[-1].removeprefix(':(literal)') for call in lookups]
        expected = {prompt.COMPILER, *prompt.DOC_INPUTS, *prompt.DOC_METADATA,
                    '.agents/rules.md', 'AGENTS.md', 'rules/specifications.md'}
        self.assertEqual(set(requested), expected)
        self.assertEqual(len(requested), len(expected), 'each requested path is looked up once')
        self.assertNotIn(b'UNRELATED BLOB CANARY', pack)


    def test_commit_compiler_uses_pinned_helper_and_profile_after_live_edits(self):
        baseline = self.pack()
        for path in ("skills/spec-writing/scripts/spec_docs.py", "rules/writing.md"):
            self.write(self.rules, path, "DIRTY HELPER CANARY")
        self.write(self.repo, "docs/example/settings.md", "DIRTY HOME CANARY")
        self.assertEqual(self.pack(), baseline)
        self.commit(self.rules)
        self.commit(self.repo)
        self.assertEqual(self.pack(), baseline)

    def test_missing_pinned_helper_fails_instead_of_importing_live_tool(self):
        (self.rules / "skills/spec-writing/scripts/spec_docs.py").unlink()
        self.rule_revision = self.commit(self.rules)
        with self.assertRaisesRegex(prompt.PromptError, "missing file"):
            self.pack()

    def test_extracted_compiler_uses_matching_pinned_selector(self):
        baseline = self.pack()[0]
        extracted = self.root / "compiler.py"
        shutil.copyfile(self.rules / "skills/pr-ready/scripts/prompt.py", extracted)
        self.write(self.rules, "skills/spec-writing/scripts/spec_docs.py", "raise RuntimeError('LIVE CANARY')")
        result = subprocess.run([sys.executable, "-I", "-B", str(extracted), "--repo", str(self.rules),
                                 "--rev", self.rule_revision, "--target", str(self.repo),
                                 "--target-rev", self.revision, "--assignment", str(self.assignment_file)],
                                stdin=None, input=b"", capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, baseline)


class DocumentationContextTests(DocumentationFixture, unittest.TestCase):
    def test_credential_bearing_documentation_refuses_before_publication(self):
        for location in ('source', 'metadata'):
            with self.subTest(location=location):
                # Synthetic URL values only; build them at runtime so no credential is stored.
                url = 'https://example.invalid/?' + 'api_key=' + 'synthetic-canary'
                path = self.repo / ('docs/example/acceptance.md' if location == 'source' else 'docs/DOCUMENTS.json')
                original = path.read_bytes()
                if location == 'source':
                    path.write_bytes(original + f'\n[External reference]({url})\n'.encode())
                else:
                    value = json.loads(original)
                    value['documents'][0]['purpose'] += ' ' + url
                    path.write_text(json.dumps(value))
                c = self.checker.load_corpus(self.checker.Snapshot.from_git(self.repo))
                for output, data in self.checker.generate_navigation(c).items():
                    self.write(self.repo, output, data)
                self.revision = self.commit(self.repo)
                with self.assertRaisesRegex(prompt.PromptError, 'credential') as caught:
                    self.pack()
                self.assertNotIn('synthetic-canary', str(caught.exception))
                output = self.root / ('refused-' + location)
                result = subprocess.run([sys.executable, '-I', '-B', str(self.rules / 'skills/pr-ready/scripts/prompt.py'),
                    '--repo', str(self.rules), '--rev', self.rule_revision, '--target', str(self.repo),
                    '--assignment', str(self.assignment_file), '--out', str(output)],
                    stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b'')
                self.assertNotIn(b'synthetic-canary', result.stderr)
                self.assertFalse(output.exists())
                path.write_bytes(original)
                self.revision = self.commit(self.repo)


    def test_compiler_includes_registry_relevant_homes_provenance_and_exact_size(self):
        pack, manifest = self.pack()
        context = manifest["documentation"]
        self.assertIn(b"# Complete registry", pack)
        self.assertIn(b"Call capacity bounds documents in one native call.", pack)
        self.assertIn(b"# Specification rules", pack)
        self.assertIn("example.call-capacity", context["manifest"]["included"])
        self.assertEqual(context["manifest"]["baseline"], self.revision)
        self.assertEqual(context["size_bytes"], context["manifest"]["size_bytes"])
        with prompt.Commit(self.rules, self.rule_revision) as source, prompt.Commit(self.repo, self.revision) as target:
            selected = prompt.documentation_context(source, target, ASSIGNMENT)
        self.assertEqual(len(selected["content"]), context["size_bytes"])
        self.assertIn(f"({context['size_bytes']} UTF-8 bytes)".encode(), pack)
        self.assertTrue(context["warnings"], "prose warnings accompany successful preparation")
        self.assertEqual(manifest["pack"], prompt.fingerprint(pack))

    def test_compiler_requires_assignment_and_both_metadata_files(self):
        with self.assertRaisesRegex(prompt.PromptError, "explicit --assignment"):
            self.pack(None)
        (self.repo / "docs/ENTITIES.json").unlink()
        self.revision = self.commit(self.repo)
        with self.assertRaisesRegex(prompt.PromptError, "needs both"):
            self.pack()

    def test_unknown_sections_and_excessive_context_refuse_without_truncation(self):
        with self.assertRaisesRegex(prompt.PromptError, "D06"):
            self.pack({"version": 1, "sections": ["example-demo#absent"]})
        with self.assertRaisesRegex(prompt.PromptError, "D25"):
            self.pack({**ASSIGNMENT, "budget_bytes": 100})
        pack, _ = self.pack()
        self.assertIn(b"Call capacity bounds documents in one native call.", pack)

    def test_complete_registry_does_not_recursively_expand_ordinary_home_links(self):
        manifest_path = self.repo / "docs/DOCUMENTS.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["documents"][0]["sections"][0]["explanatory_dependencies"] = []
        manifest_path.write_text(json.dumps(manifest))
        corpus = self.checker.load_corpus(self.checker.Snapshot.from_git(self.repo))
        for path, data in self.checker.generate_navigation(corpus).items():
            self.write(self.repo, path, data)
        self.revision = self.commit(self.repo)
        pack, context = self.pack()
        selected = context["documentation"]["manifest"]
        self.assertIn(b'"example.call-capacity"', pack, "the registry remains complete")
        self.assertIn("example.log-group-limit", selected["included"])
        self.assertNotIn("example.call-capacity", selected["included"])
        self.assertNotIn("example-demo#settings", selected["included"])

    def test_missing_home_refuses_before_publishing_any_pack(self):
        (self.repo / "docs/example/settings.md").unlink()
        self.revision = self.commit(self.repo)
        output = self.root / "output"
        result = subprocess.run([sys.executable, "-I", "-B", str(self.rules / "skills/pr-ready/scripts/prompt.py"),
                                 "--repo", str(self.rules), "--rev", self.rule_revision, "--target", str(self.repo),
                                 "--assignment", str(self.assignment_file), "--out", str(output)],
                                stdin=None, input=b"", capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(b"D27", result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertFalse(output.exists())

    def test_assignment_json_is_checked_without_losing_duplicate_fields(self):
        for value in (b'{"version":1,"sections":[],"sections":["example-demo#acceptance"]}', b'{', b'null'):
            with self.subTest(assignment=value), self.assertRaisesRegex(prompt.PromptError, "D02"):
                self.pack(value)

    def test_complete_pack_budget_counts_rules_tasks_and_unicode_bytes(self):
        task = self.root / "task.txt"
        task.write_text("Task: \N{SNOWMAN}" * 20)
        pack, _ = self.pack(tasks=[(task, "task")])
        with self.assertRaisesRegex(prompt.PromptError, "D25 complete pack"):
            self.pack(tasks=[(task, "task")], budget_bytes=len(pack) - 1)
        self.assertEqual(self.pack(tasks=[(task, "task")], budget_bytes=len(pack))[0], pack)

    def test_panel_prepares_registered_context_once_and_stops_missing_assignment_before_dispatch(self):
        for folder in ("prompts", "rules"):
            shutil.copytree(ROOT / folder, self.rules / folder, dirs_exist_ok=True)
        for name in ("prepare.py", "review-panel.lenses"):
            self.write(self.rules, "skills/pr-ready/scripts/" + name,
                       (ROOT / "skills/pr-ready/scripts" / name).read_bytes())
        self.rule_revision = self.commit(self.rules)
        binaries = self.root / "bin"
        binaries.mkdir()
        reviewer = binaries / "codex"
        reviewer.write_text("#!/bin/sh\nwhile [ \"$1\" != '-o' ]; do shift; done\n"
                            "printf 'VERDICT: APPROVE\\n' > \"$2\"\ncat > \"$2.sent\"\n")
        reviewer.chmod(0o755)
        config = self.root / "panel.conf"
        config.write_text("a = codex synthetic-model - high\n")
        task = self.root / "task.txt"
        task.write_text("Review this synthetic documentation assignment.\n")
        output = self.root / "panels"
        environment = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ["PATH"],
                           REVIEW_HOUSE_RULES_REPO=str(self.rules), REVIEW_HOUSE_RULES_REV=self.rule_revision,
                           REVIEW_PYTHON=sys.executable, REVIEW_PANEL_CONF=str(config), REVIEW_PANEL_OUT=str(output),
                           REVIEW_BASE=self.revision, REVIEW_SPEC_ASSIGNMENT="")
        command = ["bash", str(ROOT / "skills/pr-ready/scripts/review-panel.sh")]
        read_fd, write_fd = os.pipe()
        try:
            result = subprocess.run([*command, "--assignment", str(self.assignment_file), "complete", str(self.repo),
                                     str(task), "generalist-a"], env=environment, capture_output=True, timeout=10, stdin=read_fd)
        finally:
            os.close(read_fd)
            os.close(write_fd)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        pack = (output / "complete/generalist-a.pack/pack.txt").read_bytes()
        manifest = json.loads((output / "complete/generalist-a.pack/manifest.json").read_bytes())
        self.assertEqual(pack.count(b"# Complete registry"), 1)
        self.assertEqual(manifest["pack"], prompt.fingerprint(pack))
        self.assertIn("documentation", manifest)
        self.assertFalse((output / "complete/preparer.py").exists())
        self.assertEqual(pack, (output / "complete/generalist-a.attempt-1.md.sent").read_bytes())
        failed = subprocess.run([*command, "missing", str(self.repo), str(task), "generalist-a"],
                                env=environment, capture_output=True, timeout=10, stdin=subprocess.DEVNULL)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn(b"explicit --assignment", failed.stderr)
        self.assertFalse((output / "missing/generalist-a.attempt-1.md").exists())
        self.assertFalse((output / "missing/generalist-a.pack").exists())

    def test_panel_keeps_assignment_when_file_replaced_between_compilations(self):
        for folder in ("prompts", "rules"):
            shutil.copytree(ROOT / folder, self.rules / folder, dirs_exist_ok=True)
        self.write(self.rules, "skills/pr-ready/scripts/review-panel.lenses",
                   (ROOT / "skills/pr-ready/scripts/review-panel.lenses").read_bytes())
        self.rule_revision = self.commit(self.rules)
        binaries = self.root / "bin"
        binaries.mkdir()
        replacement = json.dumps({"version": 1, "sections": ["example-demo#settings"]})
        real_git = shutil.which("git")
        wrapper = binaries / "git"
        # The first compilation closes its Git batch after building its pack.
        # Replace the assignment at that boundary, without timing or sleeps.
        wrapper.write_text("#!" + sys.executable + "\n" +
                           "import os, pathlib, subprocess, sys\n" +
                           "args = sys.argv[1:]\n" +
                           "if args[-2:] == ['cat-file', '--batch']:\n" +
                           f"    status = subprocess.call([{real_git!r}, *args])\n" +
                           f"    replacement = pathlib.Path({str(self.root / 'replacement.json')!r})\n" +
                           f"    replacement.write_text({replacement!r})\n" +
                           f"    os.replace(replacement, {str(self.assignment_file)!r})\n" +
                           "    sys.exit(status)\n" +
                           f"os.execv({real_git!r}, [{real_git!r}, *args])\n")
        wrapper.chmod(0o755)
        reviewer = binaries / "codex"
        reviewer.write_text("#!/bin/sh\nwhile [ \"$1\" != '-o' ]; do shift; done\n"
                            "printf 'VERDICT: APPROVE\\n' > \"$2\"\ncat > /dev/null\n")
        reviewer.chmod(0o755)
        config = self.root / "panel.conf"
        config.write_text("a = codex synthetic-model - high\n")
        task = self.root / "task.txt"
        task.write_text("Review the selected documentation.\n")
        output = self.root / "panels"
        environment = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ["PATH"],
                           REVIEW_HOUSE_RULES_REPO=str(self.rules), REVIEW_HOUSE_RULES_REV=self.rule_revision,
                           REVIEW_PYTHON=sys.executable, REVIEW_PANEL_CONF=str(config), REVIEW_PANEL_OUT=str(output),
                           REVIEW_BASE=self.revision)
        lenses = ("generalist-a", "correctness-security")
        result = subprocess.run(
            ["bash", str(ROOT / "skills/pr-ready/scripts/review-panel.sh"), "--assignment",
             str(self.assignment_file), "replacement", str(self.repo), str(task), *lenses],
            env=environment, capture_output=True, timeout=20, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.assignment_file.read_text(), replacement)
        packs = [output / "replacement" / (lens + ".pack") for lens in lenses]
        self.assertEqual([json.loads((pack / "manifest.json").read_bytes())["documentation"]
                          ["manifest"]["assignment"]["sections"] for pack in packs],
                         [ASSIGNMENT["sections"], ASSIGNMENT["sections"]])
        prefixes = [(pack / "pack.txt").read_bytes().split(b"# 7. Lens instructions\n", 1)[0]
                    for pack in packs]
        self.assertIn(b"# Complete registry", prefixes[0])
        self.assertEqual(prefixes[0], prefixes[1])

    def test_legacy_repository_needs_no_checker_or_assignment(self):
        shutil.rmtree(self.repo / "docs")
        self.revision = self.commit(self.repo)
        shutil.rmtree(self.rules / "skills/spec-writing")
        self.rule_revision = self.commit(self.rules)
        pack, manifest = self.pack(None)
        self.assertNotIn("documentation", manifest)
        self.assertNotIn(b"# Complete registry", pack)




if __name__ == "__main__":
    unittest.main()
