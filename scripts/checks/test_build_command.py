"""Tests for build_command.py on synthetic shell commands."""
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_command  # noqa: E402


def rules(command):
    return [item["rule"] for item in build_command.check(command)]


class CargoTestTest(unittest.TestCase):
    def test_targeted_release_test_is_allowed(self):
        self.assertEqual(rules("cargo test --release --locked -p core --test api round_trip"), [])

    def test_lib_filter_is_allowed(self):
        self.assertEqual(rules("cargo test --release -p core --lib parse"), [])

    def test_filter_after_double_dash_is_allowed(self):
        self.assertEqual(rules("cargo test --release -p core -- parse --nocapture"), [])

    def test_bare_cargo_test_is_refused(self):
        self.assertEqual(rules("cargo test"), ["crate_wide_test", "debug_build"])

    def test_workspace_test_is_refused(self):
        self.assertEqual(rules("cargo test --workspace --release parse"), ["crate_wide_test"])

    def test_package_without_filter_is_refused(self):
        self.assertEqual(rules("cargo test --release -p core"), ["crate_wide_test"])

    def test_test_file_without_filter_is_refused(self):
        self.assertEqual(rules("cargo test --release -p core --test api"), ["crate_wide_test"])

    def test_alias_is_checked(self):
        self.assertEqual(rules("cargo t --release -p core"), ["crate_wide_test"])

    def test_harness_option_value_is_not_a_filter(self):
        for command in ("cargo test --release -p core -- --test-threads 4",
                        "cargo test --release -p core -- --skip slow", 'cargo test --release -p core ""'):
            with self.subTest(command=command):
                self.assertEqual(rules(command), ["crate_wide_test"])

    def test_compile_only_needs_no_filter(self):
        self.assertEqual(rules("cargo test --release -p core --no-run"), [])

    def test_nextest_with_filter_expression_is_allowed(self):
        self.assertEqual(rules('cargo nextest run --release -p core -E "test(parse)"'), [])

    def test_nextest_without_package_is_refused(self):
        self.assertEqual(rules("cargo nextest run --release parse"), ["crate_wide_test"])


class CargoClippyTest(unittest.TestCase):
    def test_clippy_on_one_target_is_allowed(self):
        self.assertEqual(rules("cargo clippy --release -p core --lib"), [])

    def test_workspace_clippy_is_refused(self):
        self.assertEqual(rules("cargo clippy --workspace --release"), ["crate_wide_clippy"])

    def test_all_targets_clippy_is_refused(self):
        self.assertEqual(rules("cargo clippy --release -p core --all-targets"), ["crate_wide_clippy"])

    def test_plural_or_several_clippy_targets_are_refused(self):
        for command in ("cargo clippy --release -p core --lib --bins --tests",
                        "cargo clippy --release -p core --bin a --bin b"):
            with self.subTest(command=command):
                self.assertEqual(rules(command), ["crate_wide_clippy"])


class LookupTest(unittest.TestCase):
    def test_command_lookups_run_nothing_and_pass(self):
        for command in ("command -v cargo test", "command -V cargo test", "command -pv cargo test"):
            with self.subTest(command=command):
                self.assertEqual(rules(command), [])
        self.assertEqual(rules("command cargo test --release parse"), ["crate_wide_test"])


class WorkspaceTest(unittest.TestCase):
    def test_only_a_run_across_every_crate_is_marked_workspace(self):
        for command, workspace in (("cargo test --release parse", True), ("cargo test --release --all -p core x", True),
                                   ("cargo test --release -p core", False), ("cargo clippy --release --lib", True),
                                   ("cargo clippy --release -p core --workspace --lib", True),
                                   ("cargo clippy --release -p core --all-targets", False)):
            with self.subTest(command=command):
                self.assertEqual([item["workspace"] for item in build_command.check(command)], [workspace])


class ProfileTest(unittest.TestCase):
    def test_debug_build_is_refused(self):
        self.assertEqual(rules("cargo build -p core"), ["debug_build"])

    def test_debugging_profile_is_allowed(self):
        self.assertEqual(rules("cargo build -p core --profile debugging"), [])

    def test_explicit_dev_profile_is_refused(self):
        self.assertEqual(rules("cargo run --profile=dev -p core"), ["debug_build"])

    def test_debugging_profile_name_is_configurable(self):
        self.assertEqual(build_command.check("cargo build -p core --profile dev", "dev"), [])
        self.assertEqual([item["rule"] for item in build_command.check("cargo build -p core --profile debugging",
                                                                       "dev")], ["debug_build"])
        found = build_command.check("cargo build -p core", "slow-debug")
        self.assertIn("--profile slow-debug", found[0]["message"])

    def test_unknown_profile_is_refused(self):
        self.assertEqual(rules("cargo build -p core --profile ci"), ["debug_build"])
        self.assertEqual(rules("cargo bench -p core --profile ci parse"), ["debug_build"])

    def test_short_release_flag_is_allowed(self):
        self.assertEqual(rules("cargo build -r -p core"), [])

    def test_bench_is_release_by_default(self):
        self.assertEqual(rules("cargo bench -p core parse"), [])


class OtherToolsTest(unittest.TestCase):
    def test_whole_ctest_suite_is_refused(self):
        self.assertEqual(rules("ctest --output-on-failure"), ["whole_suite"])

    def test_selected_ctest_is_allowed(self):
        self.assertEqual(rules("ctest -R parser"), [])

    def test_make_test_target_is_refused(self):
        self.assertEqual(rules("make -j4 test"), ["whole_suite"])

    def test_ninja_check_target_is_refused(self):
        self.assertEqual(rules("ninja -C build check"), ["whole_suite"])

    def test_cmake_build_test_target_is_refused(self):
        self.assertEqual(rules("cmake --build build --target test"), ["whole_suite"])

    def test_cmake_test_target_among_several_is_refused(self):
        for command in ("cmake --build build --target core test", "cmake --build build --target=core test"):
            with self.subTest(command=command):
                self.assertEqual(rules(command), ["whole_suite"])

    def test_plain_make_build_is_allowed(self):
        self.assertEqual(rules("make -j4"), [])


class ReadOnlyTest(unittest.TestCase):
    def test_read_only_calls_are_allowed(self):
        for command in ("cargo metadata --format-version 1", "cargo test --help", "cargo --version",
                        "cargo tree -p core", "ctest -N", "make -n test", "ninja -t targets",
                        "cargo test --release -p core -- --list", "git status", "ls target"):
            with self.subTest(command=command):
                self.assertEqual(rules(command), [])


class ShellTest(unittest.TestCase):
    def test_each_command_of_a_compound_line_is_checked(self):
        self.assertEqual(rules("git status && cargo test --workspace --release parse"), ["crate_wide_test"])

    def test_environment_and_wrappers_are_skipped(self):
        self.assertEqual(rules("RUSTFLAGS=-Dwarnings timeout 600 nice -n 5 cargo test -p core"),
                         ["crate_wide_test", "debug_build"])

    def test_shell_string_is_checked(self):
        self.assertEqual(rules('bash -c "cd build && ctest"'), ["whole_suite"])

    def test_line_continuation_joins_one_command(self):
        self.assertEqual(rules("cargo test --release -p core \\\n  --test api round_trip"), [])
        found = build_command.check("ls\ncargo test \\\n  --release -p core")
        self.assertEqual([(item["rule"], item["line"]) for item in found], [("crate_wide_test", 2)])

    def test_subshell_and_redirection_are_not_filters(self):
        for command in ("(cargo test --release -p core); echo done", "cargo test --release -p core 2>&1 | tail",
                        "cargo test --release -p core > test.log", "x=$(cargo test --release -p core)"):
            with self.subTest(command=command):
                self.assertEqual(rules(command), ["crate_wide_test"])

    def test_separator_inside_quotes_is_kept(self):
        self.assertEqual(rules('cargo test --release -p core "a;b"'), [])

    def test_toolchain_selector_is_skipped(self):
        self.assertEqual(rules("cargo +nightly test --release -p core parse"), [])

    def test_refusal_names_the_command_and_line(self):
        found = build_command.check("ls\ncargo build")
        self.assertEqual(found[0]["line"], 2)
        self.assertEqual(found[0]["command"], "cargo build")


class CommandLineTest(unittest.TestCase):
    def run_check(self, text):
        return subprocess.run([sys.executable, "-B", str(HERE / "build_command.py")], input=text,
                              stdin=None, capture_output=True, text=True)

    def test_exit_status_is_zero_when_allowed_and_two_when_refused(self):
        self.assertEqual(self.run_check("cargo test --release -p core parse\n").returncode, 0)
        self.assertEqual(self.run_check("cargo test\n").returncode, 2)

    def test_unbalanced_quote_exits_one(self):
        self.assertEqual(self.run_check('cargo test "parse\n').returncode, 1)


if __name__ == "__main__":
    unittest.main()
