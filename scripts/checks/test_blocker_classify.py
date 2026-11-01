"""Tests for blocker_classify.py on synthetic failure records and texts."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blocker_classify  # noqa: E402


def classify(**record):
    result = blocker_classify.classify(record)
    return result["class"], result["operator_only"]


class ProviderRecordTest(unittest.TestCase):
    def test_empty_balance_is_operator_only(self):
        self.assertEqual(classify(status=402, provider_message="Insufficient Balance (request_id: r1)"),
                         ("balance", True))

    def test_status_402_alone_is_a_balance_blocker(self):
        self.assertEqual(classify(status=402), ("balance", True))

    def test_status_given_as_digits_is_read(self):
        self.assertEqual(classify(status="401"), ("credential", True))

    def test_throttle_that_asks_for_a_top_up_is_a_balance_blocker(self):
        message = ("Too many requests. Your concurrency limit of 5 is based on your remaining balance. "
                   "Please top up your balance to restore your concurrency.")
        self.assertEqual(classify(status=429, code="invalid_request_error", provider_message=message),
                         ("balance", True))

    def test_plain_throttle_is_not_operator_only(self):
        self.assertEqual(classify(status=429, code="429", provider_message="Too many requests"),
                         ("rate_limit", False))

    def test_weekly_usage_limit_is_a_quota_blocker(self):
        message = "You've reached your weekly usage limit. Purchase extra usage or upgrade your plan."
        self.assertEqual(classify(status=429, provider_message=message), ("quota", True))

    def test_policy_code_with_a_hardware_key_message_is_a_credential_blocker(self):
        message = "This response cannot be shown: the session was not authenticated with an authorized hardware key."
        result = blocker_classify.classify({"status": 200, "code": "cyber_policy", "provider_message": message,
                                            "route": "beta_responses"})
        self.assertEqual((result["class"], result["operator_only"]), ("credential", True))
        self.assertEqual(result["action"], "Sign in to beta_responses again with an authorized hardware key, "
                                           "then tell the agent the session is authenticated.")

    def test_operator_only_text_in_a_later_field_wins_over_an_ordinary_one(self):
        record = {"provider_message": "Too many requests", "failure": {"reason": "Please top up your balance"}}
        result = blocker_classify.classify(record)
        self.assertEqual((result["class"], result["field"]), ("balance", "reason"))

    def test_policy_code_alone_is_a_refusal(self):
        self.assertEqual(classify(status=200, code="cyber_policy"), ("policy_refusal", False))

    def test_forbidden_status_is_a_permission_blocker(self):
        self.assertEqual(classify(status=403), ("permission", True))

    def test_missing_permission_message_is_operator_only(self):
        self.assertEqual(classify(provider_message="Resource not accessible by integration"),
                         ("permission", True))

    def test_suspended_account_is_operator_only(self):
        self.assertEqual(classify(provider_message="Your account has been suspended."), ("account", True))

    def test_server_error_is_not_operator_only(self):
        self.assertEqual(classify(status=503), ("provider_error", False))

    def test_unmatched_record_is_unknown(self):
        self.assertEqual(classify(status=200, code="other"), ("unknown", False))

    def test_action_names_the_route(self):
        result = blocker_classify.classify({"status": 402, "route": "alpha_chat"})
        self.assertEqual(result["action"], "Top up the alpha_chat account balance, then tell the agent the "
                                           "balance is restored.")


class JobRecordTest(unittest.TestCase):
    def test_runtime_limit_category_is_a_timeout(self):
        self.assertEqual(classify(category="runtime_limit"), ("timeout", False))

    def test_nested_failure_with_reason_text(self):
        record = {"failure": {"category": "refusal", "reason": "provider refused the request (cyber_policy)"}}
        self.assertEqual(blocker_classify.classify(record)["class"], "policy_refusal")

    def test_wrapped_job_record(self):
        record = {"job": "j1", "record": {"failure": {"category": "model", "reason": "agent exited with status 1"}}}
        self.assertEqual(blocker_classify.classify(record)["class"], "job_failure")


class TextTest(unittest.TestCase):
    def test_request_to_sign_in_again_is_a_credential_blocker(self):
        self.assertEqual(classify(text="please reauthenticate the beta account"), ("credential", True))

    def test_creating_a_credential_is_a_protected_asset_action(self):
        self.assertEqual(classify(text="Create a new API key for alpha to unblock the job."),
                         ("protected_asset", True))

    def test_bare_number_402_in_text_is_not_a_balance_blocker(self):
        self.assertEqual(classify(text="the run used 402 jobs"), ("none", False))

    def test_text_naming_no_blocker_is_none(self):
        self.assertEqual(classify(text="keep the import running overnight"), ("none", False))


class InputTest(unittest.TestCase):
    def run_check(self, text):
        result = subprocess.run([sys.executable, "-B", str(HERE / "blocker_classify.py")], input=text,
                                stdin=None, capture_output=True, text=True)
        return result.returncode, [json.loads(line) for line in result.stdout.splitlines()]

    def test_json_lines_exit_two_when_any_record_is_operator_only(self):
        status, results = self.run_check('{"status": 429, "provider_message": "Too many requests"}\n'
                                         '{"status": 402}\n')
        self.assertEqual(status, 2)
        self.assertEqual([item["class"] for item in results], ["rate_limit", "balance"])
        self.assertEqual([item["index"] for item in results], [0, 1])

    def test_json_array_exits_zero_when_none_is_operator_only(self):
        status, results = self.run_check('[{"status": 503}, {"category": "runtime_limit"}]')
        self.assertEqual(status, 0)
        self.assertEqual(len(results), 2)

    def test_plain_text_is_one_record(self):
        status, results = self.run_check("The hardware-key gate blocks the beta jobs.\n")
        self.assertEqual(status, 2)
        self.assertEqual(results[0]["class"], "credential")


if __name__ == "__main__":
    unittest.main()
