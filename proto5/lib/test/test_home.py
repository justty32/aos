"""cpu 範式的三類信封、原子放單、控制通知與開機對帳。"""
import json
from pathlib import Path
from unittest import mock

import aos_home as home
from _util import Base


class HomeCase(Base):
    def setUp(self):
        super().setUp()
        home.ensure_queue(self.d)

    def envelope(self, obj):
        raw = obj if isinstance(obj, str) else json.dumps(obj)
        return home.read_request(self.write("requests/x.json", raw))

    def test_envelope_request(self):
        env = self.envelope({"jsonrpc": "2.0", "id": None, "method": "job", "params": []})
        self.assertFalse(env.notify)
        self.assertIsNone(env.error)
        self.assertEqual(env.params, [])

    def test_envelope_notification(self):
        env = self.envelope({"jsonrpc": "2.0", "method": "unknown", "params": False})
        self.assertTrue(env.notify)
        self.assertIsNone(env.error)

    def test_parse_error(self):
        self.assertEqual(self.envelope("{").error["error"]["code"], -32700)

    def test_utf8_error(self):
        path = Path(self.d) / "requests/x.json"
        path.write_bytes(b"\xff")
        self.assertEqual(home.read_request(path).error["error"]["code"], -32700)

    def test_invalid_envelopes(self):
        for obj in ([], {}, {"jsonrpc": "1.0", "method": "x"},
                    {"jsonrpc": "2.0", "method": 1},
                    {"jsonrpc": "2.0", "method": "x", "id": True},
                    {"jsonrpc": "2.0", "method": "x", "id": []}):
            with self.subTest(obj=obj):
                env = self.envelope(obj)
                self.assertFalse(env.notify)
                self.assertEqual(env.error["error"]["code"], -32600)

    def test_invalid_retains_valid_id(self):
        self.assertEqual(self.envelope({"id": "known"}).error["id"], "known")

    def test_json_nonfinite_rejected(self):
        self.assertEqual(self.envelope('{"id":NaN}').error["error"]["code"], -32700)

    def test_error_builders(self):
        self.assertEqual(home.error_response("x", -32601, "unknown")["error"],
                         {"code": -32601, "message": "unknown"})
        self.assertEqual(home.params_error("x", "bad", ["params", "target"])["error"],
                         {"code": -32602, "message": "bad", "data": {
                             "code": "FieldTypeMismatch", "position": ["params", "target"]}})

    def test_post_no_clobber(self):
        home.post_request(self.d, "x.json", {"n": 1})
        with self.assertRaises(home.RequestExists):
            home.post_request(self.d, "x.json", {"n": 2})
        self.assertEqual(home.read_json(Path(self.d) / "requests/x.json"), {"n": 1})
        self.assertEqual(list((Path(self.d) / "requests").iterdir()),
                         [Path(self.d) / "requests/x.json"])

    def test_invalid_names(self):
        for name in ("../x.json", "x", "a\0.json", None):
            with self.subTest(name=name), self.assertRaises(home.HomeError):
                home.post_request(self.d, name, {})

    def test_state_defaults_are_independent(self):
        state = home.read_state(self.d)
        state["runs"] = 7
        self.assertEqual(home.read_state(self.d), {"current": None, "runs": 0})
        home.write_state(self.d, state)
        self.assertEqual(home.read_state(self.d), state)

    def test_state_custom_default_deepcopy(self):
        default = {"children": {}}
        home.read_state(self.d, default)["children"]["x"] = 1
        self.assertEqual(default, {"children": {}})

    def test_state_bad_utf8(self):
        (Path(self.d) / "state.json").write_bytes(b"\xff")
        with self.assertRaises(home.HomeError):
            home.read_state(self.d)

    def test_ack_two_steps_and_retry(self):
        home.write_json(Path(self.d) / "responses/x.json", {})
        home.post_request(self.d, "ack-x.json", {"jsonrpc": "2.0", "method": "ack",
                                                "params": {"name": "x.json"}})
        original = Path.unlink
        seen = []
        def unlink(path, *args, **kwargs):
            seen.append(path.name)
            if path.name == "ack-x.json":
                raise OSError("crash between ack steps")
            return original(path, *args, **kwargs)
        with mock.patch.object(Path, "unlink", unlink), self.assertRaises(OSError):
            home.scan_controls(self.d, lambda: None)
        self.assertEqual(seen, ["x.json", "ack-x.json"])
        self.assertFalse(self.exists("responses/x.json"))
        self.assertTrue(self.exists("requests/ack-x.json"))
        home.scan_controls(self.d, lambda: None)
        self.assertFalse(self.exists("requests/ack-x.json"))

    def test_ack_missing_response_noop(self):
        home.post_request(self.d, "ack-x.json", {"jsonrpc": "2.0", "method": "ack",
                                                "params": {"name": "missing.json"}})
        home.scan_controls(self.d, lambda: None)
        self.assertFalse(self.exists("requests/ack-x.json"))

    def test_stop_calls_flag(self):
        home.post_request(self.d, "stop-x.json", {"jsonrpc": "2.0", "method": "stop"})
        flag = []
        home.scan_controls(self.d, lambda: flag.append(True))
        self.assertEqual(flag, [True])
        self.assertFalse(self.exists("requests/stop-x.json"))

    def test_control_prefix_mismatch(self):
        for with_id in (False, True):
            obj = {"jsonrpc": "2.0", "method": "other"}
            if with_id:
                obj["id"] = "x"
            name = "ack-%s.json" % with_id
            home.post_request(self.d, name, obj)
            home.scan_controls(self.d, lambda: None)
            self.assertEqual(self.exists("responses/" + name), with_id)
            if with_id:
                self.assertEqual(home.read_json(Path(self.d) / "responses" / name)
                                 ["error"]["code"], -32600)

    def test_bad_ack_notification_no_response(self):
        home.post_request(self.d, "ack-x.json", {"jsonrpc": "2.0", "method": "ack",
                                                "params": {"name": "../outside.json"}})
        home.scan_controls(self.d, lambda: None)
        self.assertFalse(self.exists("responses/ack-x.json"))

    def test_bad_control_json_has_response(self):
        self.write("requests/stop-x.json", "{")
        home.scan_controls(self.d, lambda: self.fail("invalid stop"))
        self.assertEqual(home.read_json(Path(self.d) / "responses/stop-x.json")
                         ["error"]["code"], -32700)

    def test_reconcile_five_rows(self):
        current = {"name": "x.json", "id": "x", "notify": False}
        rows = [(None, True, True, ()), (current, True, False, ("interrupt", "delete_request")),
                (current, True, True, ("delete_request",)), (current, False, True, ()),
                (current, False, False, ())]
        for item, req, response, expected in rows:
            with self.subTest(item=item, req=req, response=response):
                self.assertEqual(home.reconcile_actions(item, req, response), expected)

    def test_reconcile_notification(self):
        current = {"name": "x.json", "id": None, "notify": True}
        self.assertEqual(home.reconcile_actions(current, True, False), ("delete_request",))

    def test_reconcile_writes_interrupted_and_is_idempotent(self):
        home.post_request(self.d, "x.json", {})
        current = {"name": "x.json", "id": 7, "notify": False}
        home.reconcile(self.d, current)
        home.reconcile(self.d, current)
        self.assertFalse(self.exists("requests/x.json"))
        response = home.read_json(Path(self.d) / "responses/x.json")
        self.assertEqual(response["id"], 7)
        self.assertEqual(response["error"]["data"]["code"], "Interrupted")

    def test_list_requests_excludes_controls_and_temp(self):
        for name in ("b.json", "a.json", "ack-x.json", "stop-x.json", ".x.tmp"):
            self.write("requests/" + name, "{}")
        self.assertEqual(home.list_requests(self.d), ["a.json", "b.json"])

    def test_load_info_defaults_and_directives(self):
        self.write("settings.json", '{"poll":7}')
        self.inst({"_metainfo": {"_type": "exec_cpu", "_version": 1},
                   "poll_ms": {"$ref": "settings.json", "$at": "/poll"}}, "info.json")
        info = home.load_info(self.d, "exec_cpu")
        self.assertEqual(info["poll_ms"], 7)
        self.assertEqual(info["timeout_ms"], 0)

    def test_load_info_missing_identity(self):
        self.inst({}, "info.json")
        with self.assertRaises(home.HomeError) as caught:
            home.load_info(self.d, "exec_cpu")
        self.assertEqual(caught.exception.code, "NotAHome")

    def test_load_info_rejects_option(self):
        self.inst({"_metainfo": {"_type": "exec_cpu", "_version": 1},
                   "poll_ms": {"$opt": "something", "$val": 7}}, "info.json")
        with self.assertRaises(home.HomeError) as caught:
            home.load_info(self.d, "exec_cpu")
        self.assertEqual(caught.exception.code, "UnknownOption")

    def test_load_info_rejects_bool_integer(self):
        self.inst({"_metainfo": {"_type": "exec_cpu", "_version": 1},
                   "poll_ms": True}, "info.json")
        with self.assertRaises(home.HomeError) as caught:
            home.load_info(self.d, "exec_cpu")
        self.assertEqual(caught.exception.code, "FieldTypeMismatch")
