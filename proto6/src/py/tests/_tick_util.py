"""aos-tick 系列測試共用：表與任務的縮寫、CAT_REC、TickCase 基底與 check_record()。"""
import importlib.util
import json
import os
import shlex
import subprocess

from _util import Base, LIB, PY
from aos_tick_record import read_record


HERE = os.path.dirname(os.path.abspath(__file__))
TICK = os.path.join(os.path.dirname(HERE), "bin", "aos-tick")
SPEC = os.path.join(HERE, "..", "..", "..", "spec", "protocol")

CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}


def table(*tasks):
    return {"_metainfo": {"_type": "aos-tasks", "_version": 1}, "tasks": list(tasks)}


POSIX = {"_type": "posix", "_version": 1}


def task(tid, argv, **extra):
    """一項任務，`_metainfo`、`id`、`argv` 都填好（使用者 2026-10-01：`kind` 不必填；裁定 2026-10-01：`_metainfo` 可省）。"""
    return dict({"_metainfo": POSIX, "id": tid, "argv": argv}, **extra)


def sh(tid, script, **extra):
    return task(tid, ["sh", "-c", script], **extra)


# 使用者 2026-10-01：沒有 AOS_TICK_RECORD，任務從 $AOS_TICK_CWD/<dirname>/tick/current/ 找紀錄；
# dirname 照 AOS_DIRNAME 三態（沒設＝.aos、空字串＝直接在工作資料夾下、其他＝那個名字）。
# 第九批（2026-10-01）拆檔：record.json 用 $ref 指向 ran.json 等，任務用 aos_tick_record.read_record() 印展開後的完整紀錄
CAT_REC = ('d=${AOS_DIRNAME-.aos}; %s -c "import sys, json; sys.path.insert(0, sys.argv[1]); '
           'import aos_tick_record as r; print(json.dumps(r.read_record(sys.argv[2])))" %s '
           '"$AOS_TICK_CWD/${d:+$d/}tick/current"' % (shlex.quote(PY), shlex.quote(LIB)))


class TickCase(Base):

    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.d, ".aos"))

    def tasks(self, *items):
        self.write(".aos/tasks.json", json.dumps(table(*items), ensure_ascii=False))

    def tick(self, *args, env=None):
        e = dict(CLEAN_ENV, **(env or {}))
        args = args or (self.d,)
        return subprocess.run([PY, TICK] + list(args), capture_output=True, text=True, env=e, timeout=30)

    def rec(self, name="current", cwd="", dirname=".aos"):
        """展開後的完整紀錄（第九批：`<cwd>/<dirname>/tick/<name>/record.json` 加上它 $ref 的檔）。"""
        return read_record(os.path.join(self.d, cwd, dirname, "tick", name))

    def snap(self, rel):
        """一格紀錄資料夾裡每個檔的原文（{檔名: 內容}）；資料夾不在回 None。"""
        p = os.path.join(self.d, rel)
        if not os.path.isdir(p):
            return None
        return {n: self.read(os.path.join(rel, n)) for n in sorted(os.listdir(p))}


def check_record(case, rec, raw=False):
    """跨欄位規則（跟 spec 的 validate.py 共用 record_rules.py）＋（有 jsonschema 時）tick-record schema。
    raw＝傳進來的是 record.json 本體，只驗 schema 的 RecordFile。"""
    if raw:
        return _check_schema(rec, raw=True)
    if rec.get("ended"):
        case.assertEqual(rec["exit"], 0)                  # 寫得到收尾就是 0，任務成敗不影響
    else:
        case.assertNotIn("exit", rec)
        case.assertNotIn("skipped", rec)               # skipped 跟 blocked_before 一樣收尾才寫
    case.assertNotIn({"exit": 0}, [{k: v for k, v in t.items() if k == "exit"} for t in rec["tasks"]])
    case.assertEqual(_record_rules().record_errors(rec), [])
    _check_schema(rec)


def _record_rules():
    spec = importlib.util.spec_from_file_location("record_rules", os.path.join(SPEC, "examples", "messages", "record_rules.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _check_schema(rec, raw=False):
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except ImportError:
        return
    sd = os.path.join(SPEC, "schemas")
    res = {}
    for n in ("common.schema.json", "tick-record.schema.json"):
        with open(os.path.join(sd, n), encoding="utf-8") as f:
            res[n] = Resource.from_contents(json.load(f))
    reg = Registry().with_resources(res.items())
    schema = res["tick-record.schema.json"].contents
    if raw:                                            # 第九批：record.json 本體（ran／tasks／hooks 是 $ref）
        schema = {"$ref": "tick-record.schema.json#/$defs/RecordFile"}
    Draft202012Validator(schema, registry=reg).validate(rec)
