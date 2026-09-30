"""身分先行（inst.md〈先決定身分，切完才解析〉〈頂層整份指示詞〉）。"""
import json
import os
import pwd

from aos_inst import (InstError, find_inst, grant_only, load_plan_obj, lookup_uid, raw_user,
                      read_snapshot, snapshot_from_bytes)
from tests.util import ME, TmpCase

MY_NAME = pwd.getpwuid(ME).pw_name


class RawUser(TmpCase):
    def snap(self, obj):
        self.write("inst.json", obj)
        return read_snapshot(find_inst(self.dir))

    def test_literal_values(self):
        self.assertEqual(raw_user(self.snap({"user": "bob", "argv": ["x"]})), "bob")
        self.assertEqual(raw_user(self.snap({"user": 0, "argv": ["x"]})), 0)
        self.assertIsNone(raw_user(self.snap({"user": "", "argv": ["x"]})))
        self.assertIsNone(raw_user(self.snap({"argv": ["x"]})))
        self.assertIsNone(raw_user(self.snap([1])))

    def test_not_expanded_and_invalid(self):
        for bad in (True, -1, 1.5, None, ["a"], {"$env": "USER"}, {"$opt": "x"}):
            with self.assertRaises(InstError) as cm:
                raw_user(self.snap({"user": bad, "argv": ["x"]}))
            self.assertEqual(cm.exception.code, "UserInvalid", bad)

    def test_raw_user_read_even_beside_top_ref(self):
        # 原始頂層字面：頂層是 $ref 指示詞時一樣讀它旁邊的 user
        self.assertEqual(raw_user(self.snap({"$ref": "x.json", "user": "bob"})), "bob")

    def test_snapshot_from_bytes(self):
        s = snapshot_from_bytes(find_inst(self.write("a.json", {"argv": ["x"]})), b'{"user":3}')
        self.assertEqual(raw_user(s), 3)
        with self.assertRaises(InstError) as cm:
            snapshot_from_bytes(s.source, b"\xff")
        self.assertEqual(cm.exception.code, "JsonSyntax")


class Lookup(TmpCase):
    def test_lookup(self):
        self.assertEqual(lookup_uid(None), ME)
        self.assertEqual(lookup_uid("", inherited_uid=42), 42)
        self.assertEqual(lookup_uid(MY_NAME), ME)
        self.assertEqual(lookup_uid(12345), 12345)
        with self.assertRaises(InstError) as cm:
            lookup_uid("no-such-user-aos-inst-test")
        self.assertEqual(cm.exception.code, "UserInvalid")


class IdentityFirst(TmpCase):
    def test_user_checked_before_directives(self):
        # user 不合法時，不會先去讀 $ref（否則會報 ReferenceReadFailed）
        self.assertCode("UserInvalid", {"user": True, "argv": {"$ref": "missing.json"}})

    def test_unknown_account_is_user_invalid(self):
        self.assertCode("UserInvalid", {"user": "no-such-user-aos-inst-test", "argv": ["x"]})

    def test_not_granted(self):
        self.assertCode("UserNotGranted", {"user": ME + 1, "argv": ["x"]})

    def test_authorize_runs_before_ref_read_and_env(self):
        calls = []

        def authorize(user, uid, snap):
            calls.append((user, uid))
            self.write("later.json", ["from-ref"])      # 授權（切身分）之後才出現的檔
            env["WHO"] = "switched"                     # 切身分後的環境
            return uid
        env = {}
        plan = self.plan({"user": MY_NAME, "argv": {"$ref": "later.json"},
                          "envs": {"W": {"$env": "WHO"}}}, env=env, authorize=authorize)
        self.assertEqual(calls, [(MY_NAME, ME)])
        self.assertEqual(plan.argv, ["from-ref"])
        self.assertEqual(plan.envs, {"W": "switched"})
        self.assertEqual((plan.uid, plan.user), (ME, MY_NAME))

    def test_inherited_uid_passed_to_authorize(self):
        seen = []
        self.plan({"argv": ["x"]}, authorize=lambda u, uid, s: seen.append((u, uid)) or ME,
                  inherited_uid=777)
        self.assertEqual(seen, [(None, 777)])

    def test_top_ref_user_mismatch(self):
        self.write("real.json", {"user": ME + 1, "argv": ["x"]})
        self.assertCode("UserMismatch", {"$ref": "real.json"})

    def test_top_ref_user_same_identity_by_name(self):
        self.write("real.json", {"user": MY_NAME, "argv": ["x"]})
        plan = self.plan({"$ref": "real.json", "user": ME})
        self.assertEqual((plan.uid, plan.user), (ME, MY_NAME))

    def test_top_ref_user_invalid(self):
        self.write("real.json", {"user": {"$env": "USER"}, "argv": ["x"]})
        self.assertCode("UserInvalid", {"$ref": "real.json"})

    def test_top_ref_without_user_keeps_identity(self):
        self.write("real.json", {"argv": ["x"]})
        self.assertEqual(self.plan({"$ref": "real.json"}).uid, ME)

    def test_source_changed(self):
        def authorize(user, uid, snap):
            self.write("inst.json", {"argv": ["y"]})    # 授權後來源被改
            return uid
        self.assertCode("SourceChanged", {"argv": ["x"]}, authorize=authorize)

    def test_source_vanished(self):
        def authorize(user, uid, snap):
            os.unlink(self.path("inst.json"))
            return uid
        self.assertCode("SourceChanged", {"argv": ["x"]}, authorize=authorize)

    def test_source_check_optional(self):
        def authorize(user, uid, snap):
            self.write("inst.json", {"argv": ["y"]})
            return uid
        # 不比對時用的是快照，不是改過的檔
        plan = self.plan({"argv": ["x"]}, authorize=authorize, verify_source=False)
        self.assertEqual(plan.argv, ["x"])


class FromObject(TmpCase):
    def test_task_item_superset(self):
        item = {"id": "t1", "kind": "system", "group": "g", "needs": ["a"], "_note": 1,
                "user": "", "argv": ["x", {"$ref": "", "$at": "/id"}], "cwd": "w"}
        plan = load_plan_obj(item, self.dir, grant_only([ME]), env={}, create_dirs=False,
                             label="tasks.json#/tasks/0")
        self.assertEqual(plan.argv, ["x", "t1"])
        self.assertEqual(plan.cwd, self.path("w"))
        self.assertEqual(plan.extra, {"id": "t1", "kind": "system", "group": "g", "needs": ["a"],
                                      "_note": 1})
        self.assertEqual(plan.source, "tasks.json#/tasks/0")
        json.dumps(plan.to_json())

    def test_obj_identity_first(self):
        with self.assertRaises(InstError) as cm:
            load_plan_obj({"user": ME + 1, "argv": ["x"]}, self.dir, grant_only([ME]))
        self.assertEqual(cm.exception.code, "UserNotGranted")
