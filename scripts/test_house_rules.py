"""Tests for scripts/house_rules.py, against local fixture repositories only (no network)."""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import house_rules as hr  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "house_rules.py"
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def run(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, stdin=subprocess.DEVNULL,
                          env=dict(os.environ, **GIT_ENV)).stdout.decode().strip()


class Fixture(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="house-rules-test-"))
        self.addCleanup(self.cleanup)
        patch = mock.patch.dict(os.environ, {"HOUSE_RULES_CACHE": str(self.root / "cache"),
                                             "XDG_CONFIG_HOME": str(self.root / "config"), **GIT_ENV})
        patch.start()
        self.addCleanup(patch.stop)
        for name in (hr.LINK, hr.OVERRIDE, hr.RESOLVED):
            os.environ.pop(name, None)

    def cleanup(self):
        subprocess.run(["chmod", "-R", "u+w", str(self.root)], check=False, stdin=subprocess.DEVNULL)  # read-only trees
        subprocess.run(["rm", "-rf", str(self.root)], check=False, stdin=subprocess.DEVNULL)

    def source(self, name, files):
        """A bare fixture source with one commit on main holding `files`; returns its file:// URL."""
        work = self.root / "work" / name
        work.mkdir(parents=True)
        run(work, "init", "-q", "-b", "main")
        self.commit(work, files)
        bare = self.root / "remotes" / f"{name}.git"
        run(self.root, "clone", "-q", "--bare", str(work), str(bare))
        run(bare, "config", "uploadpack.allowAnySHA1InWant", "true")
        run(work, "remote", "add", "origin", str(bare))
        return f"file://{bare}"

    def commit(self, work, files):
        for path, content in files.items():
            target = Path(work) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content if isinstance(content, str) else json.dumps(content))
        run(work, "add", "-A")
        run(work, "commit", "-q", "-m", "change")
        return run(work, "rev-parse", "HEAD")

    def push(self, name, files):
        work = self.root / "work" / name
        commit = self.commit(work, files)
        run(work, "push", "-q", "origin", "main")
        return commit

    def command(self, *args, stdin=b"", cwd=None, env=None):
        proc = subprocess.run([sys.executable, "-I", str(SCRIPT), *args], input=stdin, stdin=None, capture_output=True,
                              cwd=str(cwd or self.root), env=dict(os.environ, **(env or {})))
        return proc.returncode, proc.stdout.decode(), proc.stderr.decode()

    def expire_answers(self):
        """Age every published branch answer past the reuse window, as time passing would."""
        for path in Path(hr.cache_root(), "sources").glob("**/branches/*.json"):
            record = json.loads(path.read_text())
            record["fetched"] = hr.utc(time.time() - hr.REUSE_SECONDS - 5)
            path.write_text(json.dumps(record))

    def repository(self, config=None, files=None):
        repo = self.root / "repo"
        repo.mkdir(exist_ok=True)
        run(repo, "init", "-q", "-b", "main")
        if config is not None:
            (repo / hr.CONFIG).write_text(json.dumps(config))
        for path, content in (files or {}).items():
            (repo / path).parent.mkdir(parents=True, exist_ok=True)
            (repo / path).write_text(content)
        return str(repo.resolve())

    def tour(self):
        """The design's tour: House Rules, team-rules on main and rust-settings pinned."""
        base = {"version": 1, "checks": {
            "whitespace": {"run": ["git", "diff", "--check", "{base}", "{snapshot}"], "stages": ["pre-commit", "ci"],
                           "enforced": True,
                           "paths": ["**"], "fix": "remove the whitespace"},
            "spec-docs": {"run": ["spec", "{snapshot}"], "stages": ["pre-commit", "ci"], "enforced": True, "paths": ["**"],
                          "fix": "fix the specification"}}}
        house = self.source("house-rules", {hr.RULESET: dict(base, profiles={"rust": {}, "specs": {}}),
                                            "INDEX.md": "rules\n"})
        team = self.source("team-rules", {hr.RULESET: {
            "version": 1, "budgets": {"pre-commit": {"seconds": 20, "reason": "Our pre-commit includes a slower lint."}},
            "context": ["rules/team.md"]}, "rules/team.md": "# Team\n"})
        rust = self.source("rust-settings", {hr.RULESET: {"version": 1, "profiles": {"rust": {"checks": {
            "spec-docs": {"stages": ["pre-push", "ci"], "reason": "Spec checks run at pre-push in Rust services."},
            "cargo-deny": {"run": ["cargo", "deny", "check"], "stages": ["ci"], "paths": ["Cargo.lock"],
                           "fix": "update the dependency", "reason": "Licences and advisories."}}}}}})
        pin = run(self.root / "work" / "rust-settings", "rev-parse", "HEAD")
        config = {"version": 2, "sources": [{"name": "house-rules", "url": house},
                                            {"name": "team-rules", "url": team, "ref": "main"},
                                            {"name": "rust-settings", "url": rust, "ref": pin}],
                  "profiles": ["rust", "specs"], "checks": {}}
        return config, pin


class ResolutionTests(Fixture):
    def test_branch_follows_latest_commit_and_commit_stays_pinned(self):
        config, pin = self.tour()
        repo = self.repository(config)
        first = hr.resolve(repo)
        self.assertEqual([layer["source"] for layer in first["layers"]], ["fetched", "fetched", "pinned"])
        self.assertEqual(first["layers"][2]["revision"], pin)
        team_new = self.push("team-rules", {"rules/team.md": "# Team v2\n"})
        self.push("rust-settings", {"README.md": "newer\n"})
        self.expire_answers()
        second = hr.resolve(repo)
        self.assertEqual(second["layers"][1]["revision"], team_new)
        self.assertEqual(second["layers"][2]["revision"], pin)
        self.assertTrue((Path(second["layers"][1]["tree"]) / "rules/team.md").read_text().startswith("# Team v2"))

    def test_branch_answer_is_reused_within_the_window(self):
        config, _ = self.tour()
        repo = self.repository(config)
        first = hr.resolve(repo)
        self.push("team-rules", {"rules/team.md": "# Team v2\n"})
        second = hr.resolve(repo)
        self.assertEqual(second["layers"][1]["source"], "reused")
        self.assertEqual(second["layers"][1]["revision"], first["layers"][1]["revision"])

    def test_offline_uses_the_last_fetch_with_a_warning_and_stops_without_one(self):
        config, pin = self.tour()
        repo = self.repository(config)
        fetched = hr.resolve(repo)
        os.rename(str(self.root / "remotes"), str(self.root / "remotes-away"))
        self.expire_answers()
        offline = hr.resolve(repo)
        self.assertEqual([layer["source"] for layer in offline["layers"]], ["offline", "offline", "pinned"])
        self.assertEqual(offline["layers"][1]["revision"], fetched["layers"][1]["revision"])
        self.assertTrue(any(w.startswith("warning: cannot reach file://") and "team-rules main as last answered" in w
                            for w in offline["warnings"]), offline["warnings"])
        subprocess.run(["rm", "-rf", str(self.root / "cache")], check=True, stdin=subprocess.DEVNULL)
        with self.assertRaises(hr.Failure) as caught:
            hr.resolve(repo)
        self.assertIn("no earlier fetch of house-rules main is cached; run again when online", str(caught.exception))

    def test_missing_pinned_commit_and_missing_branch_name_their_layer(self):
        config, _ = self.tour()
        config["sources"][2]["ref"] = "0" * 40
        with self.assertRaises(hr.Failure) as caught:
            hr.resolve(self.repository(config))
        self.assertIn(f"rust-settings: commit {'0' * 40} not found at file://", str(caught.exception))
        config["sources"][2]["ref"] = "release"
        with self.assertRaises(hr.Failure) as caught:
            hr.resolve(self.repository(config))
        self.assertIn("rust-settings: no branch release at file://", str(caught.exception))

    def test_revision_override_replaces_house_rules_for_one_run(self):
        config, _ = self.tour()
        old = run(self.root / "work" / "house-rules", "rev-parse", "HEAD")
        self.push("house-rules", {"INDEX.md": "newer\n"})
        with mock.patch.dict(os.environ, {hr.OVERRIDE: old}):
            record = hr.resolve(self.repository(config))
        self.assertEqual(record["layers"][0]["source"], "override")
        self.assertEqual(record["layers"][0]["revision"], old)
        self.assertIn(f"warning: TEST OVERRIDE HOUSE_RULES_REVISION={old}; this run does not use house-rules main",
                      record["warnings"])

    def test_link_mode_uses_the_checkout_and_warns(self):
        config, _ = self.tour()
        repo = self.repository(config)
        checkout = self.root / "work" / "team-rules"
        (checkout / "rules/team.md").write_text("# Team, edited\n")
        self.assertEqual(hr.main(["link", str(checkout), "--url", config["sources"][1]["url"]]), 0)
        record = hr.resolve(repo)
        layer = record["layers"][1]
        self.assertEqual((layer["source"], layer["tree"], layer["link"]["dirty"]), ("link", str(checkout), True))
        self.assertIn(f"warning: LINKED team-rules -> {checkout} at {layer['revision']} with uncommitted changes; "
                      "this run does not use the fetched source", record["warnings"])
        self.assertEqual(hr.main(["unlink", str(checkout)]), 0)
        self.assertEqual(hr.resolve(repo)["layers"][1]["source"], "fetched")

    def test_link_variable_and_its_refusals(self):
        config, _ = self.tour()
        repo = self.repository(config)
        checkout = str(self.root / "work" / "house-rules")
        with mock.patch.dict(os.environ, {hr.LINK: checkout}):
            self.assertEqual(hr.resolve(repo)["layers"][0]["source"], "link")
        with mock.patch.dict(os.environ, {hr.LINK: checkout, hr.OVERRIDE: "a" * 40}):
            with self.assertRaises(hr.Failure) as caught:
                hr.resolve(repo)
        self.assertEqual((str(caught.exception), caught.exception.status),
                         ("house-rules: set HOUSE_RULES_LINK or HOUSE_RULES_REVISION, not both", 1))
        hr.write_links({config["sources"][1]["url"]: str(self.root / "gone")})
        with self.assertRaises(hr.Failure) as caught:
            hr.resolve(repo)
        self.assertIn(f"is not the root of a Git working tree; run house-rules unlink {self.root / 'gone'}",
                      str(caught.exception))

    def test_no_configuration_uses_the_global_sources_and_moves_default(self):
        fork = self.source("house-rules", {"INDEX.md": "fork rules\n"})
        repo = self.repository()
        (self.root / "config" / "house-rules").mkdir(parents=True)
        hr.global_path().write_text(json.dumps({"version": 1, "sources": [{"name": "house-rules", "url": fork}]}))
        record = hr.resolve(repo)
        self.assertEqual(record["configuration"], {"origin": "global", "commit": None})
        self.assertEqual(record["layers"][0]["url"], fork)
        self.assertEqual(os.readlink(str(hr.cache_root() / "default")), record["layers"][0]["tree"])
        self.assertEqual(hr.describe(record)[0],
                         f"house-rules: repository {repo}, configuration none (global default sources)")
        hr.global_path().unlink()
        self.assertEqual(hr.default_sources([]), ([{"name": "house-rules", "url": hr.DEFAULT_URL, "ref": "main"}],
                                                  "default"))

    def test_configuration_from_a_commit(self):
        config, _ = self.tour()
        repo = self.repository(config)
        run(repo, "add", "-A")
        run(repo, "commit", "-q", "-m", "adopt")
        (Path(repo) / hr.CONFIG).write_text(json.dumps({"version": 2, "sources": [config["sources"][0]]}))
        record = hr.resolve(repo, rev="HEAD")
        self.assertEqual(len(record["layers"]), 3)
        self.assertEqual(record["configuration"]["origin"], "commit")
        self.assertEqual(len(hr.resolve(repo)["layers"]), 1)


class ConfigurationTests(Fixture):
    def refused(self, config, message):
        with self.assertRaises(hr.Failure) as caught:
            hr.repository_config(json.dumps(config))
        self.assertIn(message, str(caught.exception))

    def test_repository_configuration_refusals(self):
        source = {"name": "house-rules"}
        self.refused({"version": 2, "sources": [{"name": "team", "url": "u"}]},
                     "sources[0] must be house-rules; House Rules is always the first layer")
        self.refused({"version": 2, "sources": [source, {"name": "team", "url": "u"}, {"name": "team", "url": "v"}]},
                     "the name team is used twice")
        self.refused({"version": 2, "sources": [source, {"name": "team"}]}, "layer team needs a url")
        self.refused({"version": 2, "sources": [source, {"name": "Team", "url": "u"}]}, "lower kebab case")
        self.refused({"version": 2, "sources": [source, {"name": "house-rules", "url": "u"}]},
                     "only the first layer may be named house-rules")
        self.refused({"version": 2, "sources": [dict(source, ref="bad..ref")]}, "is not a branch name Git accepts")
        self.refused({"version": 2, "sources": [source], "checks": {"whitespace": {"enforced": False}}}, "only a layer file decides")
        self.refused({"version": 3}, "has version 3; this house-rules command knows version 2; run house-rules self-update")
        self.refused({"version": 2, "pin": "x"}, "unknown field pin")
        self.refused({"version": 2}, "sources is required")
        for value in (False, "input", {"value": "input"}, {"value": "input", "reason": " "}):
            self.refused({"version": 2, "sources": [source], "git_settings": {"core.autocrlf": value}},
                         "git_settings must map Git setting names")
        setting = {"value": "x", "reason": "r"}
        for key in ("core.attributesFile", "core.bare", "extensions.objectFormat", "include.path", "includeIf.x.path"):
            self.refused({"version": 2, "sources": [source], "git_settings": {key: setting}},
                         f"git_settings.{key}: a repository cannot set this Git setting")
        self.refused({"version": 2, "sources": [dict(source, ref="a" * 64)]},
                     "house-rules: house-rules: SHA-256 sources are not supported yet")
        whitespace = {"value": "blank-at-eol", "reason": "Trailing spaces fail everywhere."}
        self.assertEqual(hr.repository_config(json.dumps({"version": 2, "sources": [source], "git_settings": {
            "core.whitespace": whitespace, "diff.my driver.command": setting}}))["git_settings"]["core.whitespace"],
                         whitespace)
        self.assertEqual(hr.repository_config(json.dumps({"version": 2, "sources": [source]}))["sources"],
                         [{"name": "house-rules", "url": hr.DEFAULT_URL, "ref": "main"}])

    def test_layers_apply_in_order_field_by_field_with_their_labels(self):
        config, _ = self.tour()
        config["checks"] = {"whitespace": {"stages": ["ci"], "reason": "Whitespace runs in CI here."}}
        repo = self.repository(config)
        record = hr.resolve(repo)
        result = hr.effective(record, hr.repository_config(json.dumps(config)), repo)
        self.assertEqual(result["checks"]["spec-docs"]["stages"], ["pre-push", "ci"])
        self.assertEqual(result["checks"]["spec-docs"]["run"], ["spec", "{snapshot}"])
        self.assertEqual(result["layers_of"]["spec-docs"]["stages"], "rust-settings/rust")
        self.assertEqual(result["layers_of"]["spec-docs"]["run"], "house-rules")
        self.assertEqual(result["budgets"]["pre-commit"]["seconds"], 20)
        self.assertEqual([(s["key"], s["layer"], s["replaces"]) for s in result["settings"]], [
            ("budgets.pre-commit", "team-rules", None),
            ("checks.spec-docs.stages", "rust-settings/rust", "house-rules"),
            ("checks.cargo-deny", "rust-settings/rust", None),
            ("checks.whitespace.stages", "repository", "house-rules")])
        self.assertEqual([label for label, _ in result["context"]], ["team-rules"])
        self.assertIn("  checks.spec-docs.stages = [\"pre-push\", \"ci\"]  from rust-settings/rust; replaces house-rules "
                      "(reason: Spec checks run at pre-push in Rust services.)", hr.describe_settings(result["settings"]))

    def test_a_change_without_a_reason_is_refused(self):
        config, _ = self.tour()
        config["checks"] = {"spec-docs": {"stages": ["ci"]}}
        repo = self.repository(config)
        with self.assertRaises(hr.Failure) as caught:
            hr.effective(hr.resolve(repo), hr.repository_config(json.dumps(config)), repo)
        self.assertEqual(str(caught.exception), "house-rules: repository checks.spec-docs.stages: changes "
                                                "rust-settings/rust's value; add a reason")

    def test_a_layer_file_that_lists_sources_is_refused(self):
        config, _ = self.tour()
        self.push("team-rules", {hr.RULESET: {"version": 1, "sources": []}})
        repo = self.repository(config)
        with self.assertRaises(hr.Failure) as caught:
            hr.effective(hr.resolve(repo), hr.repository_config(json.dumps(config)), repo)
        self.assertEqual(str(caught.exception), "house-rules: team-rules ruleset.json: only house-rules.json lists "
                                                "sources")

    def test_an_unknown_profile_is_refused(self):
        config, _ = self.tour()
        config["profiles"] = ["rust", "haskell"]
        repo = self.repository(config)
        with self.assertRaises(hr.Failure) as caught:
            hr.effective(hr.resolve(repo), hr.repository_config(json.dumps(config)), repo)
        self.assertEqual(str(caught.exception), "house-rules: profile haskell is defined by no layer "
                                                "(house-rules, team-rules, rust-settings)")

    def test_machine_files_only_warn(self):
        config, _ = self.tour()
        repo = self.repository(config)
        record = hr.resolve(repo)
        parsed = hr.repository_config(json.dumps(config))
        home = self.root / "config" / "house-rules"
        home.mkdir(parents=True)
        hr.global_path().write_text(json.dumps({"version": 1, "budgets": {"pre-commit": {"seconds": 1}},
                                                "checks": {"whitespace": {"stages": []},
                                                           "todo-scan": {"run": ["grep", "{snapshot}"], "stages": ["pre-commit"],
                                                                         "paths": ["**"], "fix": "f", "reason": "Mine."}}}))
        result = hr.effective(record, parsed, repo, hooks=True)
        self.assertEqual(result["budgets"]["pre-commit"], {"seconds": 1})  # a budget replaces its stage's entry whole
        self.assertEqual(result["personal"], ["todo-scan"])
        self.assertFalse(result["checks"]["todo-scan"]["enforced"])
        self.assertIn("warning: global configuration check whitespace names a check of this repository; personal "
                      "checks need new names; ignored", result["warnings"])
        self.assertNotIn("todo-scan", hr.effective(record, parsed, repo)["checks"])
        hr.global_path().write_text("{not json")
        warnings = hr.effective(record, parsed, repo, hooks=True)["warnings"]
        self.assertTrue(any(w.startswith("warning: ") and "invalid JSON" in w and "ignoring the global configuration" in w
                            for w in warnings), warnings)


class CommandTests(Fixture):
    def test_urls_key_the_cache_as_written_and_carry_no_credentials(self):
        self.assertEqual(hr.source_folder("git@github.com:owner/rules.git").name,
                         __import__("hashlib").sha256(b"git@github.com:owner/rules.git").hexdigest())
        self.assertNotEqual(hr.source_folder("alice@host:rules.git"), hr.source_folder("bob@host:rules.git"))
        self.assertNotEqual(hr.source_folder("https://example.com/rules"), hr.source_folder("https://example.com/rules/"))
        source = {"name": "house-rules"}
        for url in ("https://token@github.com/owner/rules", "http://user:pw@host/rules", "ssh://git:pw@host/rules"):
            with self.assertRaises(hr.Failure) as caught:
                hr.repository_config(json.dumps({"version": 2, "sources": [source, {"name": "team", "url": url}]}))
            self.assertIn("the URL of team carries credentials; use a Git credential helper", str(caught.exception))
        self.assertEqual(hr.repository_config(json.dumps({"version": 2, "sources": [
            source, {"name": "team", "url": "ssh://git@host/rules"}]}))["sources"][1]["url"], "ssh://git@host/rules")

    def test_text_form_of_the_tour(self):
        config, pin = self.tour()
        repo = self.repository(config)
        lines = hr.describe(hr.resolve(repo))
        self.assertEqual(lines[0], f"house-rules: repository {repo}, configuration house-rules.json (working tree)")
        house = config["sources"][0]["url"]
        self.assertRegex(lines[1], rf"^house-rules: layer house-rules   {house} ref main -> [0-9a-f]{{40}} \(fetched "
                                   r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\)$")
        self.assertRegex(lines[3], rf"^house-rules: layer rust-settings {config['sources'][2]['url']} ref {pin} "
                                   r"\(pinned, fetched \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\)$")
        self.assertEqual(lines[4], "house-rules: profiles rust, specs")

    def test_init_writes_detected_profiles_once(self):
        repo = self.repository(files={"Cargo.toml": "", "docs/ENTITIES.json": "{}", "package.json": "{}"})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(hr.main(["init", "--repo", repo]), 0)
        self.assertEqual(json.loads((Path(repo) / hr.CONFIG).read_text()),
                         {"version": 2, "sources": [{"name": "house-rules", "ref": "main"}], "profiles": ["rust", "specs"], "checks": {}})
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(hr.main(["init", "--repo", repo]), 1)

    def test_exec_hook_runs_the_resolved_script_with_the_record_and_input(self):
        script = "import json, os, sys\nprint(json.loads(os.environ['HOUSE_RULES_RESOLVED'])['layers'][0]['revision'])\n" \
                 "print(sys.stdin.read())\n"
        house = self.source("house-rules", {"scripts/show.py": script})
        repo = self.repository({"version": 2, "sources": [{"name": "house-rules", "url": house}]})
        revision = run(self.root / "work" / "house-rules", "rev-parse", "HEAD")
        hook_input = json.dumps({"cwd": repo, "session_id": "s"})
        proc = subprocess.run([sys.executable, "-I", str(SCRIPT), "exec", "--hook", "scripts/show.py"],
                              input=hook_input.encode(), stdin=None, capture_output=True, cwd=str(self.root), env=os.environ)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.decode().splitlines(), [revision, hook_input])

    def test_failed_resolution_in_a_hook_falls_back_to_the_default_tree(self):
        house = self.source("house-rules", {"scripts/show.py": "print('rules from', __file__)\n"})
        (self.root / "config" / "house-rules").mkdir(parents=True)
        hr.global_path().write_text(json.dumps({"version": 1, "sources": [{"name": "house-rules", "url": house}]}))
        tree = hr.resolve(None)["layers"][0]["tree"]
        repo = self.repository({"version": 2, "sources": [{"name": "house-rules", "url": house, "ref": "gone"}]})
        command = [sys.executable, "-I", str(SCRIPT), "exec", "--hook", "scripts/show.py"]
        proc = subprocess.run(command, input=json.dumps({"cwd": repo}).encode(), stdin=None, capture_output=True,
                              env=os.environ)
        lines = proc.stdout.decode().splitlines()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(lines[0].startswith("HOUSE RULES HOOK ERROR: house-rules: house-rules: no branch gone at file://"))
        self.assertIn(f"The House Rules below are the global default's ({tree}), not this repository's resolved rules, "
                      "and this repository's custom layers are missing.", lines[0])
        self.assertEqual(lines[1], f"rules from {tree}/scripts/show.py")

    def test_cache_prune_removes_only_unused_unheld_and_expired_entries(self):
        config, _ = self.tour()
        record = hr.resolve(self.repository(config))
        named, pinned = Path(record["layers"][1]["tree"]), Path(record["layers"][2]["tree"])
        old, held, recent = (named.parent / (digit * 40) for digit in "123")
        team = hr.source_folder(config["sources"][1]["url"])
        partial = team / ".partial-x"
        for folder in (old, held, recent, partial):
            folder.mkdir()
        for folder in (old, held, recent):
            Path(str(folder) + ".fetched").write_text(hr.utc() + "\n")  # placed, as a fetch leaves them
        now = time.time()
        Path(str(held) + ".used").touch()
        for path, age in ((old, 8), (held, 8), (Path(str(held) + ".used"), 8), (recent, 0.1), (partial, 2)):
            os.utime(str(path), (now - age * 86_400,) * 2)
        os.utime(str(pinned) + ".used", (now - 8 * 86_400,) * 2)
        os.utime(str(named) + ".used", (now - 8 * 86_400,) * 2)  # only its branch record keeps it
        house_record = hr.answer_path(config["sources"][0]["url"], "branch", "main")
        os.utime(str(house_record), (now - 31 * 86_400,) * 2)  # expired: House Rules' tree loses its protection
        house_tree = Path(record["layers"][0]["tree"])
        os.utime(str(house_tree) + ".used", (now - 8 * 86_400,) * 2)
        self.assertEqual({path for path, _, _ in hr.prune_plan(now)},
                         {house_record, old, held, pinned, house_tree, partial})
        with contextlib.redirect_stdout(io.StringIO()):
            hr.main(["cache", "prune", "--dry-run"])
        self.assertTrue(old.exists() and house_record.exists())
        with contextlib.redirect_stdout(io.StringIO()):
            hr.main(["cache", "prune"])
        self.assertFalse(any(p.exists() for p in (old, held, partial, pinned, house_tree, house_record,
                                                   Path(str(old) + ".fetched"), Path(str(pinned) + ".used"))))
        self.assertTrue(recent.exists() and named.exists())
        self.assertTrue((hr.cache_root() / "revisions").is_dir())

    def test_one_run_variables_win_over_links_json(self):
        config, _ = self.tour()
        repo = self.repository(config)
        hr.write_links({config["sources"][0]["url"]: str(self.root / "work" / "house-rules")})
        old = run(self.root / "work" / "house-rules", "rev-parse", "HEAD")
        with mock.patch.dict(os.environ, {hr.OVERRIDE: old}):
            self.assertEqual(hr.resolve(repo)["layers"][0]["source"], "override")
        self.assertEqual(hr.resolve(repo)["layers"][0]["source"], "link")

    def test_hook_deadline_uses_the_last_answer_and_names_the_wait(self):
        import fcntl
        config, _ = self.tour()
        repo = self.repository(config)
        first = hr.resolve(repo)
        folder = hr.source_folder(config["sources"][1]["url"])
        descriptor = os.open(str(folder / "lock"), os.O_RDWR)
        fcntl.flock(descriptor, fcntl.LOCK_EX)  # another resolver holds the source
        try:
            self.expire_answers()
            record = hr.resolve(repo, deadline=hr.Deadline(0.3))
        finally:
            os.close(descriptor)
        self.assertEqual(record["layers"][1]["source"], "offline")
        self.assertEqual(record["layers"][1]["revision"], first["layers"][1]["revision"])
        self.assertTrue(any(w.startswith(f"warning: the remote did not answer within {hr.HOOK_SECONDS} s; using "
                                         "team-rules main as last answered") for w in record["warnings"]), record["warnings"])

    def test_a_refused_fetch_fails_and_keeps_the_previous_answer(self):
        config, _ = self.tour()
        repo = self.repository(config)
        first = hr.resolve(repo)["layers"][1]["revision"]
        newer = self.push("team-rules", {"rules/team.md": "# Team v2\n"})
        self.expire_answers()
        shim = self.root / "bin"
        shim.mkdir()
        real = subprocess.run(["sh", "-c", "command -v git"], capture_output=True, text=True, check=True,
                              stdin=subprocess.DEVNULL).stdout.strip()
        (shim / "git").write_text(f'#!/bin/sh\ncase "$*" in *fetch*{newer}*) echo "fatal: refused" >&2; exit 128;; esac\n'
                                  f'exec {real} "$@"\n')  # the server refuses to send the commit it named
        (shim / "git").chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"}):
            with self.assertRaises(hr.Failure) as caught:
                hr.resolve(repo)
        self.assertIn(f"team-rules: {config['sources'][1]['url']} names {newer} for main but cannot send it "
                      "(fatal: refused)", str(caught.exception))
        self.assertEqual(hr.read_answer(config["sources"][1]["url"], "branch", "main")["revision"], first)

    def test_the_record_lists_custom_context_and_first_fetch_times(self):
        config, _ = self.tour()
        record = hr.resolve(self.repository(config))
        self.assertEqual(record["context"], [{"layer": "team-rules", "path": "rules/team.md"}])
        tree = Path(record["layers"][2]["tree"])
        stamp = Path(str(tree) + ".fetched").read_text().strip()
        os.utime(str(tree), (time.time() + 3600,) * 2)  # the folder's time no longer decides
        self.assertEqual(hr.resolve(self.repository(config))["layers"][2]["fetched"], stamp)

class RoundOneTests(Fixture):
    """Defects Warden's round 1 on the resolver found, one test each."""

    def test_resolve_refuses_an_unknown_profile_on_the_command_line(self):
        config, _ = self.tour()
        config["profiles"] = ["rust", "haskell"]
        code, _, err = self.command("resolve", "--repo", self.repository(config))
        self.assertEqual((code, err.strip().splitlines()[-1]),
                         (2, "house-rules: profile haskell is defined by no layer (house-rules, team-rules, rust-settings)"))

    def test_invalid_check_entries_are_refused_and_bad_personal_checks_warn(self):
        config, _ = self.tour()
        for checks, message in (({"lint": {}}, "check lint has no run"),
                                ({"lint": {"run": ["x"], "stages": ["merge"], "paths": ["**"], "fix": "f",
                                           "reason": "r"}}, "stages has the wrong type or value"),
                                ({"whitespace": {"colour": "red", "reason": "r"}}, "unknown check field colour")):
            config["checks"] = checks
            with self.assertRaises(hr.Failure) as caught:
                hr.resolve(self.repository(config))
            self.assertIn(message, str(caught.exception))
        config["checks"] = {}
        repo = self.repository(config)
        (self.root / "config" / "house-rules").mkdir(parents=True)
        hr.global_path().write_text(json.dumps({"version": 1, "checks": {"mine": {"run": ["x"], "reason": "r"}}}))
        result = hr.effective(hr.resolve(repo), hr.repository_config(json.dumps(config)), repo, hooks=True)
        self.assertNotIn("mine", result["checks"])
        self.assertTrue(any("global configuration check mine is not usable" in w for w in result["warnings"]))

    def test_a_sha1_source_is_fetched_whatever_the_personal_default_format(self):
        config, pin = self.tour()
        home = self.root / "home-config"
        home.write_text("[init]\n\tdefaultObjectFormat = sha256\n")
        with mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(home)}):
            layer = hr.resolve(self.repository(config))["layers"][2]
        self.assertEqual(layer["revision"], pin)

    def test_a_branch_name_with_a_unicode_line_separator_resolves(self):
        config, _ = self.tour()
        branch = "team rules"
        work = self.root / "work" / "team-rules"
        run(work, "push", "-q", "origin", f"main:refs/heads/{branch}")
        config["sources"][1]["ref"] = branch
        record = hr.resolve(self.repository(config))
        self.assertEqual(record["layers"][1]["revision"], run(work, "rev-parse", "HEAD"))

    def test_branch_records_for_slashed_names_are_one_file_each(self):
        config, _ = self.tour()
        work = self.root / "work" / "team-rules"
        for branch in ("a", "a.json/b", "feature/x"):
            run(work, "push", "-q", "origin", f"main:refs/heads/{branch}")
            config["sources"][1]["ref"] = branch
            hr.resolve(self.repository(config))
        folder = hr.source_folder(config["sources"][1]["url"]) / "branches"
        self.assertEqual(sorted(p.name for p in folder.iterdir() if not p.name.startswith(".")),
                         sorted(f"{hr.digest(b)}.json" for b in ("a", "a.json/b", "feature/x")))
        self.assertEqual(sorted(name for _, _, name, *_ in hr.answers(folder.parent)), ["a", "a.json/b", "feature/x"])

    def test_another_spelling_of_a_url_is_another_source(self):
        config, _ = self.tour()
        repo = self.repository(config)
        hr.resolve(repo)
        os.rename(str(self.root / "remotes"), str(self.root / "remotes-away"))
        self.expire_answers()
        config["sources"][1]["url"] += "/"  # the same repository, spelled with a trailing slash: no shared answer
        with self.assertRaises(hr.Failure) as caught:
            hr.resolve(self.repository(config))
        self.assertIn("no earlier fetch of team-rules main is cached", str(caught.exception))

    def test_house_rules_profiles_need_reasons_too(self):
        config, _ = self.tour()
        ruleset = json.loads((self.root / "work" / "house-rules" / hr.RULESET).read_text())
        ruleset["profiles"]["rust"] = {"checks": {"spec-docs": {"stages": ["ci"]}}}
        self.push("house-rules", {hr.RULESET: ruleset})
        with self.assertRaises(hr.Failure) as caught:
            hr.resolve(self.repository(config))
        self.assertEqual(str(caught.exception), "house-rules: house-rules/rust checks.spec-docs.stages: changes "
                                                "house-rules's value; add a reason")

    def test_an_explicit_repository_wins_over_inherited_git_bindings(self):
        config, _ = self.tour()
        chosen = self.repository(config)
        other = self.root / "other"
        other.mkdir()
        run(other, "init", "-q", "-b", "main")
        with mock.patch.dict(os.environ, {"GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other)}):
            self.assertEqual(hr.find_repository(chosen), chosen)
            self.assertEqual(len(hr.resolve(chosen)["layers"]), 3)

    def test_expected_errors_are_messages_not_tracebacks(self):
        code, _, err = self.command("resolve", "--repo", str(self.root / "nowhere"))
        self.assertEqual((code, "Traceback" in err), (1, False))
        (self.root / "config" / "house-rules").mkdir(parents=True)
        hr.links_path().write_text('{"version": 1, "links": [{"key": 1}]}')
        code, _, err = self.command("cache", "list")
        self.assertEqual((code, "Traceback" in err), (2, False))
        self.assertIn("is not a links file", err)
        code, _, err = self.command("exec", "--hook", "scripts/x.py", stdin=json.dumps({"cwd": "/no/such"}).encode())
        self.assertEqual((code, "Traceback" in err), (0, False))

    def test_link_refuses_a_bare_repository(self):
        bare = self.root / "remotes" / "bare.git"
        bare.parent.mkdir(parents=True, exist_ok=True)
        run(self.root, "init", "-q", "--bare", str(bare))
        code, _, err = self.command("link", str(bare), "--url", "https://example.com/team/rules")
        self.assertEqual(code, 1)
        self.assertIn("is not the root of a Git working tree", err)

    def test_exec_prints_resolution_warnings(self):
        house = self.source("house-rules", {"scripts/show.py": "print('ran')\n"})
        repo = self.repository({"version": 2, "sources": [{"name": "house-rules", "url": house}]})
        checkout = self.root / "work" / "house-rules"
        code, out, err = self.command("exec", "--repo", repo, "scripts/show.py", env={hr.LINK: str(checkout)})
        self.assertEqual((code, out), (0, "ran\n"))
        self.assertIn(f"warning: LINKED house-rules -> {checkout}", err)

    def test_context_and_exec_paths_stay_inside_their_trees(self):
        outside = self.root / "outside.md"
        outside.write_text("# not the layer's\n")
        config, _ = self.tour()
        work = self.root / "work" / "team-rules"
        os.symlink(str(outside), str(work / "rules" / "escape.md"))
        self.push("team-rules", {hr.RULESET: {"version": 1, "context": ["rules/escape.md"]}})
        with self.assertRaises(hr.Failure) as caught:
            hr.resolve(self.repository(config))
        self.assertIn("context file rules/escape.md is not a file inside the layer", str(caught.exception))
        house = self.source("house-rules-2", {"scripts/show.py": "print('ran')\n"})
        repo = self.repository({"version": 2, "sources": [{"name": "house-rules", "url": house}]})
        for path in (str(self.root / "outside.md"), "../outside.md"):
            code, _, err = self.command("exec", "--repo", repo, path)
            self.assertEqual(code, 1, err)

    def test_init_refuses_profiles_resolution_would_reject(self):
        repo = self.repository()
        for profiles in (["Rust"], ["rust", "rust"]):
            code, _, _ = self.command("init", "--repo", repo, *[a for p in profiles for a in ("--profile", p)])
            self.assertEqual(code, 2)
            self.assertFalse((Path(repo) / hr.CONFIG).exists())

    def test_usage_errors_exit_1(self):
        self.assertEqual(self.command("no-such-command")[0], 1)
        self.assertEqual(self.command("exec")[0], 1)

    def test_a_linked_layer_keeps_its_configured_ref_kind(self):
        config, pin = self.tour()
        hr.write_links({config["sources"][2]["url"]: str(self.root / "work" / "rust-settings")})
        layer = hr.resolve(self.repository(config))["layers"][2]
        self.assertEqual((layer["source"], layer["ref_kind"]), ("link", "commit"))
        self.assertIn(f"ref {pin} link ", hr.describe_layer(layer, 13))

    def test_hook_fallback_passes_no_inherited_resolution(self):
        script = "import os\nprint(os.environ.get('HOUSE_RULES_RESOLVED', 'none'))\n"
        house = self.source("house-rules", {"scripts/show.py": script})
        (self.root / "config" / "house-rules").mkdir(parents=True)
        hr.global_path().write_text(json.dumps({"version": 1, "sources": [{"name": "house-rules", "url": house}]}))
        hr.resolve(None)
        repo = self.repository({"version": 2, "sources": [{"name": "house-rules", "url": house, "ref": "gone"}]})
        code, out, _ = self.command("exec", "--hook", "scripts/show.py", stdin=json.dumps({"cwd": repo}).encode(),
                                    env={hr.RESOLVED: '{"version": 1, "layers": []}'})
        self.assertEqual(out.splitlines()[-1], "none")

    def test_a_linked_global_default_moves_default_and_an_obstruction_fails(self):
        house = self.source("house-rules", {"INDEX.md": "rules\n"})
        (self.root / "config" / "house-rules").mkdir(parents=True)
        hr.global_path().write_text(json.dumps({"version": 1, "sources": [{"name": "house-rules", "url": house}]}))
        hr.resolve(None)
        checkout = str(self.root / "work" / "house-rules")
        hr.write_links({house: checkout})
        hr.resolve(None)
        self.assertEqual(os.readlink(str(hr.cache_root() / "default")), checkout)
        (hr.cache_root() / "default").unlink()
        (hr.cache_root() / "default").mkdir()
        with self.assertRaises(hr.Failure) as caught:
            hr.resolve(None)
        self.assertIn("is not a symbolic link; move it away", str(caught.exception))

    def test_a_use_that_cannot_be_recorded_fails(self):
        config, _ = self.tour()
        repo = self.repository(config)
        tree = Path(hr.resolve(repo)["layers"][2]["tree"])
        marker = Path(str(tree) + ".used")
        marker.unlink()
        marker.mkdir()  # nothing can open it as the marker file
        with self.assertRaises(hr.Failure) as caught:
            hr.resolve(repo)
        self.assertIn(f"cannot record the use of {tree}", str(caught.exception))

    def test_prune_rechecks_a_tree_used_after_planning_and_never_leaves_half_a_tree(self):
        config, _ = self.tour()
        tree = Path(hr.resolve(self.repository(config))["layers"][2]["tree"])
        old = time.time() - 8 * 86_400
        os.utime(str(tree) + ".used", (old, old))
        planned = [path for path, _, _ in hr.prune_plan()]
        self.assertIn(tree, planned)
        hr.mark_used(tree)  # another run used it after the plan
        self.assertEqual(hr.prune_tree(tree), ("keep", "used or named again"))
        os.utime(str(tree) + ".used", (old, old))
        with mock.patch.object(hr.shutil, "rmtree", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                hr.prune_tree(tree)
        self.assertFalse(tree.exists())  # renamed away before deletion started
        self.assertTrue(any(p.name.startswith(".removing-") for p in tree.parent.iterdir()))
        layer = hr.resolve(self.repository(config))["layers"][2]
        self.assertTrue((Path(layer["tree"]) / hr.RULESET).is_file())  # fetched again, whole

    def test_init_never_overwrites_a_file_created_meanwhile(self):
        path = Path(self.repository()) / hr.CONFIG
        path.write_text("theirs\n")  # another writer created it after init's first check
        with self.assertRaises(hr.Failure):
            hr.create_once(path, "ours\n")
        self.assertEqual(path.read_text(), "theirs\n")

    def test_a_failed_cleanup_of_a_fetch_repository_is_reported(self):
        config, pin = self.tour()
        with mock.patch.object(hr.shutil, "rmtree", side_effect=OSError(13, "Permission denied")):
            with self.assertRaises(hr.Failure) as caught:
                hr.resolve(self.repository(config))
        self.assertIn("cannot remove the temporary fetch repository", str(caught.exception))
        subprocess.run(["rm", "-rf", str(self.root / "cache")], check=True, stdin=subprocess.DEVNULL)
        shim = self.root / "bin"
        shim.mkdir()
        real = subprocess.run(["sh", "-c", "command -v git"], capture_output=True, text=True, check=True,
                              stdin=subprocess.DEVNULL).stdout.strip()
        (shim / "git").write_text(f'#!/bin/sh\ncase "$*" in *" fetch "*) echo "fatal: refused" >&2; exit 128;; esac\n'
                                  f'exec {real} "$@"\n')  # every fetch fails
        (shim / "git").chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"}), \
                mock.patch.object(hr.shutil, "rmtree", side_effect=OSError(13, "Permission denied")):
            with self.assertRaises(hr.Failure) as caught:
                hr.resolve(self.repository(config))
        self.assertIn("; the fetch had failed first: fatal: refused", str(caught.exception))  # the first cause stays


class RoundTwoTests(Fixture):
    """The design's round 2, the lead's decisions on it and the operator's answers, one test each."""

    def tag(self, name, ref, annotated=True):
        work = self.root / "work" / name
        run(work, *(["tag", "-a", "-m", ref, ref] if annotated else ["tag", ref]))
        run(work, "push", "-q", "origin", f"refs/tags/{ref}")

    def test_a_release_tag_resolves_once_and_never_moves(self):
        config, _ = self.tour()
        work = self.root / "work" / "team-rules"
        released = run(work, "rev-parse", "HEAD")
        self.tag("team-rules", "v1.4.0")
        config["sources"][1]["ref"] = "v1.4.0"
        repo = self.repository(config)
        first = hr.resolve(repo)["layers"][1]
        self.assertEqual((first["ref_kind"], first["source"], first["revision"]), ("tag", "fetched", released))
        self.push("team-rules", {"rules/team.md": "# Team v2\n"})
        run(work, "tag", "-f", "-a", "-m", "moved", "v1.4.0")
        run(work, "push", "-q", "-f", "origin", "refs/tags/v1.4.0")
        again = hr.resolve(repo)["layers"][1]
        self.assertEqual((again["source"], again["revision"]), ("pinned", released))  # never asked again
        self.assertRegex(hr.describe_layer(again, 10), rf"ref v1.4.0 -> {released} \(pinned, fetched ")
        config["sources"][1]["ref"] = "v9.9.9"
        with self.assertRaises(hr.Failure) as caught:
            hr.resolve(self.repository(config))
        self.assertIn("team-rules: no release tag v9.9.9 at file://", str(caught.exception))
        self.assertEqual(hr.ref_kind("v1"), "branch")  # a range is not a release tag

    def test_a_lightweight_tag_and_an_offline_tag_without_a_record(self):
        config, _ = self.tour()
        self.tag("team-rules", "v2.0.0", annotated=False)
        config["sources"][1]["ref"] = "v2.0.0"
        layer = hr.resolve(self.repository(config))["layers"][1]
        self.assertEqual(layer["revision"], run(self.root / "work" / "team-rules", "rev-parse", "HEAD"))
        os.rename(str(self.root / "remotes"), str(self.root / "remotes-away"))
        self.assertEqual(hr.resolve(self.repository(config))["layers"][1]["source"], "pinned")
        config["sources"][1]["ref"] = "v2.0.1"
        with self.assertRaises(hr.Failure) as caught:
            hr.resolve(self.repository(config))
        self.assertIn("no earlier fetch of team-rules v2.0.1 is cached; run again when online", str(caught.exception))

    def test_hooks_read_the_staged_and_the_pushed_configuration(self):
        script = "import json, os, sys\nr = json.loads(os.environ['HOUSE_RULES_RESOLVED'])\n" \
                 "print(r['configuration']['origin'], len(r['layers']))\nprint(sys.stdin.read(), end='')\n"
        config, _ = self.tour()
        self.push("house-rules", {"scripts/show.py": script})
        repo = self.repository(config)
        run(repo, "add", hr.CONFIG)
        run(repo, "commit", "-q", "-m", "adopt")
        pushed = run(repo, "rev-parse", "HEAD")
        (Path(repo) / hr.CONFIG).write_text("{not json")  # an unstaged edit never decides a hook
        code, out, err = self.command("exec", "--origin", "index", "scripts/show.py", cwd=repo)
        self.assertEqual((code, out), (0, "index 3\n"), err)
        lines = f"refs/heads/main {pushed} refs/heads/main {'0' * 40}\n"
        code, out, err = self.command("exec", "--origin", "push", "scripts/show.py", cwd=repo, stdin=lines.encode())
        self.assertEqual((code, out), (0, f"commit 3\n{lines}"), err)
        os.rename(str(self.root / "remotes"), str(self.root / "remotes-away"))  # nothing may need the network
        subprocess.run(["rm", "-rf", str(self.root / "cache")], check=True, stdin=subprocess.DEVNULL)
        code, out, err = self.command("exec", "--origin", "push", "scripts/show.py", cwd=repo,
                                      stdin=f"(delete) {'0' * 40} refs/heads/old {pushed}\n".encode())
        self.assertEqual((code, out), (0, "nothing to check: the push only deletes references\n"), err)

    def test_a_command_naming_its_layer_changes_with_the_layer(self):
        config, _ = self.tour()
        run_layer = ["{python}", "{layer}/scripts/lint.py", "{snapshot}"]
        lint = {"run": run_layer, "stages": ["ci"], "paths": ["**"], "fix": "fix it"}
        self.push("team-rules", {hr.RULESET: {"version": 1, "checks": {"lint": lint}}})
        self.push("rust-settings", {hr.RULESET: {"version": 1, "checks": {"lint": {"run": run_layer}}}})
        config["sources"][2]["ref"] = run(self.root / "work" / "rust-settings", "rev-parse", "HEAD")
        with self.assertRaises(hr.Failure) as caught:  # the same text runs rust-settings' script: a change
            hr.resolve(self.repository(config))
        self.assertEqual(str(caught.exception), "house-rules: rust-settings checks.lint.run: changes team-rules's value; "
                                                "add a reason")

    def test_a_hook_fallback_tells_its_script(self):
        house = self.source("house-rules", {"scripts/show.py": "import os\nprint(os.environ.get('HOUSE_RULES_FALLBACK'))\n"})
        (self.root / "config" / "house-rules").mkdir(parents=True)
        hr.global_path().write_text(json.dumps({"version": 1, "sources": [{"name": "house-rules", "url": house}]}))
        hr.resolve(None)
        repo = self.repository({"version": 2, "sources": [{"name": "house-rules", "url": house, "ref": "gone"}]})
        code, out, _ = self.command("exec", "--hook", "scripts/show.py", stdin=json.dumps({"cwd": repo}).encode())
        self.assertEqual(code, 0)
        self.assertTrue(out.splitlines()[-1].startswith("house-rules: house-rules: no branch gone at "), out)

    def test_a_hook_passes_its_deadline_to_the_script(self):
        house = self.source("house-rules", {"scripts/show.py": "import os\nprint(os.environ['HOUSE_RULES_DEADLINE'])\n"})
        repo = self.repository({"version": 2, "sources": [{"name": "house-rules", "url": house}]})
        started = time.time()
        code, out, err = self.command("exec", "--hook", "scripts/show.py", stdin=json.dumps({"cwd": repo}).encode())
        self.assertEqual(code, 0, err)
        self.assertLessEqual(abs(float(out) - (started + hr.HOOK_SECONDS)), 2)

    def test_prune_keeps_a_record_used_after_planning(self):
        config, _ = self.tour()
        repo = self.repository(config)
        hr.resolve(repo)
        record = hr.answer_path(config["sources"][1]["url"], "branch", "main")
        old = time.time() - 31 * 86_400
        os.utime(str(record), (old, old))
        source = next(source for path, _, source in hr.prune_plan() if path == record)
        os.utime(str(record), None)  # a resolution used it after the plan
        self.assertEqual(hr.prune_record(record, source), ("keep", "used again"))
        self.assertTrue(record.exists())
        os.utime(str(record), (old, old))
        self.assertEqual(hr.prune_record(record, source), ("remove", None))

    def test_a_cache_that_cannot_be_written_names_the_repair(self):
        config, _ = self.tour()
        cache = hr.cache_root()
        cache.mkdir(parents=True)
        cache.chmod(0o500)
        self.addCleanup(cache.chmod, 0o700)
        with self.assertRaises(hr.Failure) as caught:
            hr.resolve(self.repository(config))
        self.assertIn(f"house-rules: cannot write the cache {cache} (", str(caught.exception))
        self.assertIn("; free space, make it writable or set HOUSE_RULES_CACHE", str(caught.exception))
        self.assertEqual(list(cache.iterdir()), [])

    def test_cache_list_names_sources_records_and_links(self):
        config, _ = self.tour()
        hr.resolve(self.repository(config))
        checkout = str(self.root / "work" / "team-rules")
        hr.write_links({config["sources"][1]["url"]: checkout})
        code, out, _ = self.command("cache", "list")
        self.assertEqual(code, 0)
        self.assertRegex(out, rf"{re.escape(config['sources'][1]['url'])}\n  branch main -> [0-9a-f]{{40}} \(fetched "
                              rf"[^)]*\)\n  linked to {re.escape(checkout)}\n")  # the link sits under its source



class RoundThreeTests(Fixture):
    """The design's round 3, the lead's simplifications and the ruleset format, one test each."""

    def test_house_rules_ruleset_starts_with_the_index_always_load_list(self):
        repo = Path(__file__).resolve().parents[1]
        index = (repo / "INDEX.md").read_text().split("## Always load", 1)[1].split("\n## ", 1)[0]
        listed = __import__("re").findall(r"\]\((rules/[^)]+\.md)\)", index)
        context = hr.ruleset((repo / hr.RULESET).read_bytes(), hr.RULESET)["top"]["context"]
        self.assertTrue(listed, "INDEX.md lists no always-load rules")
        self.assertEqual(context[:len(listed)], listed)
        self.assertTrue(all((repo / path).is_file() for path in context), context)

    def test_profiles_apply_after_the_top_level_and_budgets_replace_per_stage(self):
        config, _ = self.tour()
        self.push("team-rules", {hr.RULESET: {"version": 1, "context": ["rules/team.md"],
                                              "budgets": {"pre-commit": {"seconds": 20, "reason": "Slow lint."}},
                                              "profiles": {"rust": {"context": ["rules/rust.md"], "budgets": {
                                                  "pre-commit": {"seconds": 30, "reason": "Rust lint."}}}}},
                                 "rules/rust.md": "# Rust\n"})
        repo = self.repository(config)
        record = hr.resolve(repo)
        self.assertEqual([(item["layer"], item["path"]) for item in record["context"]],
                         [("team-rules", "rules/team.md"), ("team-rules/rust", "rules/rust.md")])
        result = hr.effective(record, hr.repository_config(json.dumps(config)), repo)
        self.assertEqual(result["budgets"]["pre-commit"], {"seconds": 30, "reason": "Rust lint."})
        self.push("team-rules", {hr.RULESET: {"version": 1, "profiles": {"rust": {"budgets": {
            "pre-commit": {"seconds": 30}}}}, "budgets": {"pre-commit": {"seconds": 20, "reason": "Slow lint."}}}})
        self.expire_answers()
        with self.assertRaises(hr.Failure) as caught:
            hr.resolve(repo)
        self.assertEqual(str(caught.exception), "house-rules: team-rules/rust budgets.pre-commit: changes team-rules's "
                                                "value; add a reason")

    def test_a_tree_is_ready_with_its_first_fetch_time_and_never_replaced(self):
        config, pin = self.tour()
        real = os.rename
        seen = []

        def rename(source, target):
            if Path(target).parent == hr.cache_root() / "revisions":
                seen.append(Path(target + ".fetched").is_file())
            return real(source, target)
        with mock.patch.object(hr.os, "rename", side_effect=rename):
            record = hr.resolve(self.repository(config))
        self.assertTrue(seen and all(seen), seen)  # .fetched exists before every tree is renamed into place
        tree = Path(record["layers"][2]["tree"])
        stamp = Path(str(tree) + ".fetched").read_text()
        subprocess.run(["chmod", "-R", "u+w", str(tree)], check=True, stdin=subprocess.DEVNULL)
        subprocess.run(["rm", "-rf", str(tree)], check=True, stdin=subprocess.DEVNULL)  # an interrupted fetch
        self.assertIsNone(hr.fetch_commit(config["sources"][2]["url"], pin))  # left .fetched; the next one completes
        self.assertEqual(Path(str(tree) + ".fetched").read_text(), stamp)
        (tree / "marker").write_text("the existing tree\n")
        self.assertIsNone(hr.fetch_commit(config["sources"][2]["url"], pin))
        self.assertTrue((tree / "marker").is_file())  # an existing tree is never replaced

    def test_a_record_over_64_kib_is_refused_naming_the_layer(self):
        config, _ = self.tour()
        names = [f"rules/{'x' * 60}-{n}.md" for n in range(1200)]
        self.push("team-rules", {hr.RULESET: {"version": 1, "context": names}, **{name: "# r\n" for name in names}})
        with self.assertRaises(hr.Failure) as caught:
            hr.resolve(self.repository(config))
        self.assertRegex(str(caught.exception), r"^house-rules: the record for this run is \d+ bytes, over the 64 KiB "
                                                r"limit; team-rules lists the most context files \(1200\)$")


if __name__ == "__main__":
    unittest.main()
