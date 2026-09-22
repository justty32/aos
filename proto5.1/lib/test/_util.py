"""aos_inst／aos_exec／aos_agent_info／aos_llm_ask 測試共用的小工具：暫存資料夾、寫檔、直接 load()、
真的把 aos-exec／aos-llm-ask 開成一個進程、寫一個 agent 資料夾。

每條測試自己一個暫存資料夾，跑完 addCleanup 收掉，不弄髒 repo。
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)
EXEC = os.path.join(os.path.dirname(LIB), "cli", "aos-exec")
LLM_ASK = os.path.join(os.path.dirname(LIB), "cli", "aos-llm-ask")
PY = sys.executable
DEFAULT_INST = os.path.join(".aos", "inst.json")

# 幾條測試要用的「外面的環境」：多幾個 AOSTEST_* 變數，其餘照繼承
OUTER = dict(os.environ, AOSTEST_OUTER="外面來的", AOSTEST_EMPTY="")


def fmt(template, **variables):
    """寫測試用的縮寫：fmt("${p}:/x", p={"$env": "PATH"}) → 完整的 $fmt 物件。"""
    return {"$fmt": dict({"$val": template}, **variables)}


class Base(unittest.TestCase):
    """有一個暫存資料夾 self.d 的測試基底。"""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="aos-proto5-exec-")
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)

    def write(self, rel, body, executable=False):
        """在 self.d 底下寫一個檔（父目錄自動建），回絕對路徑。"""
        p = os.path.join(self.d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(body)
        if executable:
            os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR)
        return p

    def inst(self, obj, rel=DEFAULT_INST):
        """寫一份 inst.json（dict 就 dump，字串就原樣寫），回絕對路徑。"""
        raw = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
        return self.write(rel, raw)

    def read(self, rel):
        with open(os.path.join(self.d, rel), encoding="utf-8") as f:
            return f.read()

    def exists(self, rel):
        return os.path.exists(os.path.join(self.d, rel))


class InstCase(Base):
    """直接在這個進程裡叫 aos_inst.load()，不開子進程（快）。"""

    def load(self, obj, env=None, rel=DEFAULT_INST):
        import aos_inst
        p = self.inst(obj, rel)
        return aos_inst.load(p, self.d, env=OUTER if env is None else env)

    def bad(self, obj, code, env=None):
        """load() 一定要丟 InstError、代號是 code；回那個例外。"""
        import aos_inst
        with self.assertRaises(aos_inst.InstError) as cm:
            self.load(obj, env=env)
        e = cm.exception
        self.assertEqual(e.code, code, str(e))
        self.assertTrue(str(e).startswith(code + ": "), str(e))
        return e


class ExecCase(Base):
    """真的把 cli/aos-exec 開成一個進程。"""

    def aos(self, *args, stdin="", env=None, timeout=60, cwd=None):
        """開一個 aos-exec 進程。env 給 dict＝整個換掉（不然繼承）。"""
        return subprocess.run([PY, EXEC] + [str(a) for a in args],
                              input=stdin, capture_output=True, text=True,
                              timeout=timeout, env=env, cwd=cwd)

    def bad(self, obj, code):
        """讀／驗階段就被擋下來的：退出碼 125、stderr 一行、開頭是代號。"""
        self.inst(obj)
        r = self.aos(self.d)
        self.assertEqual(r.returncode, 125, r.stderr)
        self.assertTrue(r.stderr.startswith("aos-exec: %s: " % code), r.stderr)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        return r


# ---------------------------------------------------------------- agent 資料夾 ----

ENGINE = {"cpu": "cpu", "model": "test-model"}   # build_request 不碰網路
TOOL_SH = {"type": "function",
           "function": {"name": "sh", "description": "跑一句 shell",
                        "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}},
                                       "required": ["cmd"]}},
           "_meta": {"argv": ["tools/bin/sh-tool"]}}


class AgentCase(Base):
    """暫存資料夾就是一個 agent 資料夾：`agent()` 把 info.json 跟指到的檔一次寫好。"""

    def agent(self, info=None, system=None, history=None, tools=None, metainfo=True):
        """寫一個 agent 資料夾，回它的絕對路徑。

        `info` 是 info.json 的內容（dict 會補上 `_metainfo` 與 `engine` 預設；字串就原樣寫）；
        `system` 是人格檔內容（dict／字串；None＝不寫）、`history` 是記憶檔內容（list／字串；None＝不寫）、
        `tools` 是 `{相對路徑: 內容}`（內容 list／字串），會自動把路徑列進 info.json 的 tools。
        """
        if isinstance(info, str):
            self.write("info.json", info)
        else:
            obj = dict(info or {})
            if metainfo and "_metainfo" not in obj:
                obj["_metainfo"] = {"_type": "llm_agent", "_version": 1}
            if "engine" not in obj:
                obj["engine"] = dict(ENGINE)
            if obj.get("engine") == ENGINE:
                self.write("cpu/info.json", json.dumps({"_metainfo": {"_type": "llm_cpu", "_version": 1},
                           "models": {"test-model": {"endpoint": "http://unused.invalid/v1", "model": "test-model"}}}))
            if tools and "tools" not in obj:
                obj["tools"] = list(tools)
            self.write("info.json", json.dumps(obj, ensure_ascii=False))
        if system is not None:
            self.write(os.path.join("prompts", "system.json"),
                       system if isinstance(system, str) else json.dumps(system, ensure_ascii=False))
        if history is not None:
            self.write(os.path.join("prompts", "history.json"),
                       history if isinstance(history, str) else json.dumps(history, ensure_ascii=False))
        for rel, body in (tools or {}).items():
            self.write(rel, body if isinstance(body, str) else json.dumps(body, ensure_ascii=False))
        return self.d

    def load(self, env=None, **kw):
        import aos_agent_info
        d = self.agent(**kw)
        return aos_agent_info.load(d, env=OUTER if env is None else env)

    def bad(self, code, env=None, **kw):
        """load() 一定要丟 AgentError、代號是 code；回那個例外。"""
        import aos_agent_info
        with self.assertRaises(aos_agent_info.AgentError) as cm:
            self.load(env=env, **kw)
        e = cm.exception
        self.assertEqual(e.code, code, str(e))
        self.assertTrue(str(e).startswith(code + ": "), str(e))
        return e

    def ask(self, *args, env=None, timeout=60, cwd=None):
        """開一個 aos-llm-ask 進程。env 給 dict＝整個換掉（不然繼承）。"""
        return subprocess.run([PY, LLM_ASK] + [str(a) for a in args],
                              capture_output=True, text=True, timeout=timeout, env=env, cwd=cwd)
