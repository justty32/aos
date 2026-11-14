# 驗證 kernel 站的份額與身分規則、設定錯誤及真信箱轉寄與拒信。
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest


KERNEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KERNEL.parents[1]))
sys.path.insert(0, str(KERNEL))
import limits_rule  # noqa: E402
from round import CfgBad  # noqa: E402

ENTRY = KERNEL / "_entry"
PROTO8 = ENTRY.parents[3]
POST = PROTO8 / "impls/aos-post/bin/aos-post"
DIRECTIVE = PROTO8 / "impls/aos-directive/bin"


class LimitsRuleTest(unittest.TestCase):
    def apply(self, cfg, specs, sender=None):
        limits_rule.load(cfg)
        body = {"procs_added": specs, "other": {"keep": [1, 2]}}
        original = copy.deepcopy(body)
        result, bad = limits_rule.apply(cfg, body, sender)
        self.assertIsNone(bad)
        self.assertEqual(body, original)
        self.assertEqual(result["other"], original["other"])
        return result["procs_added"]

    def test_inactive_keeps_same_object(self):
        body = {"procs_added": {"worker": {"limits": {"user": "root"}}}}
        for cfg in ({}, {"limits": None, "users": None}, {"groups": {"t1": 60001}}):
            with self.subTest(cfg=cfg):
                result, bad = limits_rule.apply(cfg, body, None)
                self.assertIs(result, body)
                self.assertIsNone(bad)
                self.assertFalse(limits_rule.active(cfg))

    def test_default(self):
        result = self.apply({"limits": {"default": {"cpu_s": 60}}}, {"worker": {}})
        self.assertEqual(result["worker"], {"limits": {"cpu_s": 60}})

    def test_max_clamps(self):
        result = self.apply({"limits": {"max": {"cpu_s": 100}}},
                            {"worker": {"limits": {"cpu_s": 200}}})
        self.assertEqual(result["worker"], {"limits": {"cpu_s": 100}, "limits_clamped": ["cpu_s"]})

    def test_max_fills_missing_key(self):
        result = self.apply({"limits": {"max": {"cpu_s": 100, "files": 50}}},
                            {"worker": {"limits": {"files": 10}}})
        self.assertEqual(result["worker"], {"limits": {"files": 10, "cpu_s": 100},
                                            "limits_clamped": ["cpu_s"]})

    def test_sender_identity_is_removed(self):
        result = self.apply({"users": {}},
                            {"worker": {"limits": {"user": "root", "groups": [0], "cpu_s": 5}}})
        self.assertEqual(result["worker"], {"limits": {"cpu_s": 5}})

    def test_user_pattern(self):
        result = self.apply({"users": {"sol-*": "sub:2001"}}, {"sol-T01": {}, "lead": {}})
        self.assertEqual(result["sol-T01"], {"limits": {"user": "sub:2001"}})
        self.assertEqual(result["lead"], {})

    def test_user_groups(self):
        result = self.apply({"users": {"sol-*": {"user": "sub:2001", "groups": ["t1"]}},
                             "groups": {"t1": 60001}}, {"sol-T01": {}})
        self.assertEqual(result["sol-T01"]["limits"], {"user": "sub:2001", "groups": [60001]})

    def test_by_sender_exact_match(self):
        cfg = {"limits": {"default": {"cpu_s": 60, "files": 10},
                          "by_sender": {"/a/b": {"cpu_s": 5}}}}
        for sender, seconds in (("/a/b", 5), ("/a/b/", 60), ("/other", 60), (None, 60)):
            with self.subTest(sender=sender):
                result = self.apply(cfg, {"worker": {}}, sender)
                self.assertEqual(result["worker"]["limits"], {"cpu_s": seconds, "files": 10})

    def test_exec_shorthand(self):
        for spec in ("echo hi", ["echo", "hi"]):
            with self.subTest(spec=spec):
                result = self.apply({"limits": {"default": {"cpu_s": 60}}}, {"worker": spec})
                self.assertEqual(result["worker"], {"exec": spec, "limits": {"cpu_s": 60}})
                result = self.apply({"users": {}}, {"worker": spec})
                self.assertEqual(result["worker"], spec)

    def test_empty_limits_use_default(self):
        self.assertEqual(self.apply({"limits": {}}, {"worker": {"limits": {}}})["worker"], {})
        for own in ({}, None, {"user": "root", "groups": [0]}):
            with self.subTest(own=own):
                result = self.apply({"limits": {"default": {"cpu_s": 60}}},
                                    {"worker": {"limits": own}})
                self.assertEqual(result["worker"], {"limits": {"cpu_s": 60}})

    def test_directive_is_refused(self):
        for key in ("$ref", "$env", "$other"):
            with self.subTest(key=key):
                body = {"procs_added": {"worker": {key: "proc.json"}}}
                original = copy.deepcopy(body)
                result, bad = limits_rule.apply({"users": {}}, body, None)
                self.assertIsNone(result)
                self.assertEqual(bad, ("BodyBad", "procs_added[worker] is written as a directive; a station "
                                       "with limits or users cannot check it, write the proc out in full"))
                self.assertEqual(body, original)

    def test_sender_clamped_marker_is_removed(self):
        result = self.apply({"users": {}}, {"worker": {"limits_clamped": ["files"]}})
        self.assertEqual(result["worker"], {})
        result = self.apply({"limits": {"max": {"cpu_s": 1}}},
                            {"worker": {"limits_clamped": ["files"], "limits": {"cpu_s": 2}}})
        self.assertEqual(result["worker"]["limits_clamped"], ["cpu_s"])

    def test_load_errors(self):
        shape = 'users[sol-*] must be a user string or {"user": string, "groups": [names]}'
        cases = [
            ({"limits": []}, "limits must be an object {default, max, by_sender} or null"),
            ({"limits": {"extra": {}}}, "limits.extra is not a known key (default, max, by_sender)"),
            ({"limits": {"default": []}}, "limits.default must be an object of limit keys"),
            ({"limits": {"max": {"user": 1}}},
             "limits.max.user is not a limit key (mem_mb, cpu_s, procs, file_mb, files)"),
            ({"limits": {"default": {"cpu_s": True}}}, "limits.default.cpu_s must be a positive integer"),
            ({"limits": {"by_sender": []}}, "limits.by_sender must be an object {sender: limits}"),
            ({"limits": {"by_sender": {"/a/b": []}}},
             "limits.by_sender[/a/b] must be an object of limit keys"),
            ({"limits": {"by_sender": {"/a/b": {"cpu_s": 0}}}},
             "limits.by_sender[/a/b].cpu_s must be a positive integer"),
            ({"limits": {"by_sender": {"/a/b": {"extra": 1}}}},
             "limits.by_sender[/a/b].extra is not a limit key (mem_mb, cpu_s, procs, file_mb, files)"),
            ({"users": []}, "users must be an object {name pattern: user} or null"),
            ({"users": {"sol-*": 3}}, shape),
            ({"users": {"sol-*": {}}}, shape),
            ({"users": {"sol-*": {"user": ""}}}, shape),
            ({"users": {"sol-*": {"user": "root", "extra": 1}}}, shape),
            ({"users": {"sol-*": {"user": "root", "groups": None}}}, shape),
            ({"users": {"sol-*": {"user": "root", "groups": [1]}}}, shape),
            ({"users": {"sol-*": "sub:0"}}, "users[sol-*]: sub:N needs N from 1 to 60000"),
            ({"users": {"sol-*": {"user": "root", "groups": ["t1"]}}},
             "users[sol-*].groups names t1, which is not in groups"),
            ({"groups": []}, "groups must be an object {name: number} or null"),
            ({"groups": {"t1": True}}, "groups.t1 must be an integer from 60001 to 65536"),
        ]
        for cfg, message in cases:
            with self.subTest(cfg=cfg):
                with self.assertRaises(CfgBad) as caught:
                    limits_rule.load(cfg)
                self.assertEqual(str(caught.exception), message)

    def test_nullable_optional_settings(self):
        cfg = {"limits": {"default": None, "max": None, "by_sender": None},
               "users": {"sol-*": {"user": "sub:1"}}, "groups": None}
        result = self.apply(cfg, {"sol-T01": {}})
        self.assertEqual(result["sol-T01"], {"limits": {"user": "sub:1"}})
        limits_rule.load({"limits": None, "users": None, "groups": None})

    def test_subuid_and_group_boundaries(self):
        for user in ("sub:1", "sub:60000", "root", " "):
            limits_rule.load({"users": {"*": user}})
        for suffix in ("", "01", "60001", "-1", "+1", " 1", "1 ", "1.0", "１２"):
            with self.subTest(suffix=suffix):
                with self.assertRaises(CfgBad) as caught:
                    limits_rule.load({"users": {"*": "sub:" + suffix}})
                self.assertEqual(str(caught.exception), "users[*]: sub:N needs N from 1 to 60000")
        for number in (60001, 65536):
            limits_rule.load({"groups": {"t1": number}})
        for number in (60000, 65537, False, 60001.0):
            with self.subTest(number=number):
                with self.assertRaises(CfgBad):
                    limits_rule.load({"groups": {"t1": number}})

    def test_groups_are_validated_before_users(self):
        with self.assertRaises(CfgBad) as caught:
            limits_rule.load({"groups": [], "users": []})
        self.assertEqual(str(caught.exception), "groups must be an object {name: number} or null")

    def test_unrelated_body_is_same_object(self):
        for body in (None, [1], "plain", {"procs_started": ["a"], "procs_woken": ["b"]}):
            with self.subTest(body=body):
                result, bad = limits_rule.apply({"limits": {}}, body, None)
                self.assertIs(result, body)
                self.assertIsNone(bad)

    def test_bad_body_shapes(self):
        for body, message in (
                ({"procs_added": []}, "procs_added must be an object"),
                ({"procs_added": {"worker": None}}, "procs_added[worker] must be a string, an array or an object"),
                ({"procs_added": {"worker": {"limits": []}}}, "procs_added[worker].limits must be an object or null")):
            with self.subTest(body=body):
                result, bad = limits_rule.apply({"users": {}}, body, None)
                self.assertIsNone(result)
                self.assertEqual(bad, ("BodyBad", message))

    def test_own_limits_do_not_merge_default(self):
        result = self.apply({"limits": {"default": {"cpu_s": 60}}},
                            {"worker": {"limits": {"files": 10}}})
        self.assertEqual(result["worker"], {"limits": {"files": 10}})

    def test_clamp_order_and_noninteger_values(self):
        maximum = {key: 5 for key in reversed(limits_rule.KEYS)}
        result = self.apply({"limits": {"max": maximum}}, {"worker": {}})
        self.assertEqual(result["worker"]["limits_clamped"], list(limits_rule.KEYS))
        for number in (True, "10", 10.0, None, [], {}):
            with self.subTest(number=number):
                result = self.apply({"limits": {"max": {"cpu_s": 5}}},
                                    {"worker": {"limits": {"cpu_s": number}}})
                self.assertEqual(result["worker"], {"limits": {"cpu_s": number}})

    def test_first_case_sensitive_user_match_and_group_order(self):
        cfg = {"users": {"sol-*": {"user": "first", "groups": ["t2", "t1"]}, "*": "fallback"},
               "groups": {"t1": 60001, "t2": 60002}}
        result = self.apply(cfg, {"sol-T01": {}, "Sol-T01": {}})
        self.assertEqual(result["sol-T01"]["limits"], {"user": "first", "groups": [60002, 60001]})
        self.assertEqual(result["Sol-T01"]["limits"], {"user": "fallback"})
        result = self.apply({"users": {"*": {"user": "root", "groups": []}}}, {"worker": {}})
        self.assertEqual(result["worker"]["limits"], {"user": "root"})


class LimitsStationTest(unittest.TestCase):
    def setUp(self):
        self.fixture()

    def fixture(self, **policy):
        scratch = os.environ.get("KERNEL_TEST_TMP", "/tmp")
        self.root = Path(subprocess.check_output(
            ["mktemp", "-d", str(Path(scratch) / "limits-test.XXXXXX")], text=True).strip())
        self.addCleanup(shutil.rmtree, self.root)
        self.stack = self.root / "stack"
        self.daemon = self.root / "daemon"
        self.stack.mkdir()
        self.daemon.mkdir()
        self.requests = self.stack / "requests"
        self.ctl = self.daemon / "procs_requests"
        self.sender = self.root / "sender"
        self.policy = self.root / "kernel.json"
        self.policy.write_text(json.dumps(policy))
        self.env = dict(os.environ, AOS_STACK=str(self.stack), AOS_DAEMON=str(self.daemon),
                        PYTHONDONTWRITEBYTECODE="1",
                        PATH=os.pathsep.join([str(POST.parent), str(DIRECTIVE), os.environ["PATH"]]))
        self.env.pop("AOS_CLOCK", None)
        self.env.pop("AOS_KERNEL", None)
        for box in (self.requests, self.ctl, self.sender):
            self.post("init", box)

    def post(self, *args, body=None):
        result = subprocess.run([str(POST), *map(str, args)],
                                input="" if body is None else json.dumps(body),
                                text=True, capture_output=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def kernel(self):
        return subprocess.run([sys.executable, str(ENTRY), str(self.policy)],
                              text=True, capture_output=True, env=self.env)

    def forward(self, cfg, body):
        self.policy.write_text(json.dumps(cfg))
        name = self.post("send", self.requests, "request", body=body)
        result = self.kernel()
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads((self.ctl / "new" / name / "letter.json").read_text())["body"]

    def test_no_policy_forwards_unchanged(self):
        body = {"procs_added": {"worker": "echo hi"}, "other": [1]}
        self.assertEqual(self.forward({}, body), body)

    def test_default_is_forwarded(self):
        result = self.forward({"limits": {"default": {"cpu_s": 60}}}, {"procs_added": {"worker": {}}})
        self.assertEqual(result["procs_added"]["worker"], {"limits": {"cpu_s": 60}})

    def test_clamp_is_forwarded(self):
        result = self.forward({"limits": {"max": {"cpu_s": 100}}},
                              {"procs_added": {"worker": {"limits": {"cpu_s": 200}}}})
        self.assertEqual(result["procs_added"]["worker"],
                         {"limits": {"cpu_s": 100}, "limits_clamped": ["cpu_s"]})

    def test_identity_and_groups_are_forwarded(self):
        result = self.forward({"users": {"sol-*": {"user": "sub:2001", "groups": ["t1"]}},
                               "groups": {"t1": 60001}},
                              {"procs_added": {"sol-T01": {"limits": {"user": "root", "groups": [0]}}}})
        self.assertEqual(result["procs_added"]["sol-T01"],
                         {"limits": {"user": "sub:2001", "groups": [60001]}})

    def test_directive_refusal_reaches_sender_not_daemon(self):
        self.policy.write_text(json.dumps({"users": {}}))
        name = self.post("send", "--reply-to", self.sender, self.requests, "request",
                         body={"procs_added": {"worker": {"$ref": "proc.json"}}})
        result = self.kernel()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list((self.ctl / "new").iterdir()), [])
        replies = list((self.sender / "new").iterdir())
        self.assertEqual(len(replies), 1)
        reply = json.loads((replies[0] / "letter.json").read_text())
        self.assertEqual(reply["in_reply_to"], name)
        self.assertEqual(reply["body"], {"applied": False, "error": {
            "code": "BodyBad", "msg": "procs_added[worker] is written as a directive; a station with limits "
            "or users cannot check it, write the proc out in full"}})


if __name__ == "__main__":
    unittest.main()
