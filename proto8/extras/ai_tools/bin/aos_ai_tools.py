"""aos_ai_tools - aos-ai 不跑 agent 的命令：make（轉給 aos_ai_make）、explain（轉給 aos_ai_explain）、edit（JSON 編輯接口）、doctor（環境檢查）。

10-31 自 bin/aos-ai 拆出（行為不變）。"""
import json, os, shlex, subprocess, urllib.request
from pathlib import Path
import aos_ai_make as mk, aos_ai_explain as ex
from aos_ai_base import Fail, IMPLS, NAME_RE, child_env, clip, need, opt1, out, parse_errors, read_json, register_tool, which


def cmd_edit(root, o, pos):
    """JSON 編輯只留接口：交給 $AOS_AI_JSON_EDITOR（另一套「JSON 修改工具集」），aos-ai 只管邊界。"""
    need(pos, 2, "edit NAME 檔（相對 agents/NAME/）[給編輯器的參數...]")
    a = root.agent(pos[0])
    target = Path(root.inside(a.base / pos[1], "要改的檔"))
    if a.base.resolve() not in target.parents:
        raise Fail("PathBad", "只能改 agents/%s/ 底下的檔：%s" % (a.name, target))
    editor = os.environ.get("AOS_AI_JSON_EDITOR")
    if not editor:
        raise Fail("EditorMissing", "還沒接 JSON 修改工具（環境變數 AOS_AI_JSON_EDITOR 沒設）",
                   "先直接改檔：%s；之後接上 JSON 修改工具集" % target)
    r = subprocess.run(shlex.split(editor) + [str(target)] + pos[2:], capture_output=True, text=True, env=child_env())
    out({"ok": r.returncode == 0, "code": r.returncode, "path": str(target), "stdout": clip(r.stdout),
         "errors": parse_errors(r.stderr)})


def cmd_doctor(root, o, pos):
    url = os.environ.get("AOS_BRAIN_URL")
    reach = None
    if url:
        try:
            urllib.request.urlopen(url.rstrip("/") + "/models", timeout=3).close()
            reach = True
        except Exception:
            reach = False
    bins = {n: which(n) for n in IMPLS + ("aos-tick", "aos-ai")}
    out({"ok": all(bins[n] for n in IMPLS[:4]), "root": str(root.dir), "bins": bins,
         "brain": {"url": url, "reachable": reach, "note": None if url else "沒設 AOS_BRAIN_URL＝假腦"}})


def cmd_make(root, o, pos):
    """make <inst|loop|fsm|daemon|metainfo|tool_json> [旗標] [--out 檔]；make tool 名 工具；make cell 名 格；make func 資料夾。"""
    need(pos, 1, "make inst|loop|fsm|daemon|metainfo|tool_json [旗標] [--out 檔] | make tool NAME 工具 | make cell NAME 格 | make func 資料夾")
    kind, notes = pos[0], "no-notes" not in o
    env = child_env()
    if kind in mk.GEN:
        x = mk.GEN[kind](o)
        res = {"ok": True, "kind": kind, "json": x}
        if opt1(o, "out"):
            path = root.inside(opt1(o, "out"), "--out")
            mk.write_new(path, mk.dump(x), force="force" in o)
            res["path"] = str(path)
            chk = mk.aos_json_check(which, env, path)
            if chk is not None:
                res["check"] = chk
                res["ok"] = chk["ok"]
        if notes:
            res["notes"] = mk.notes_for(x, kind)
        out(res)
    elif kind == "tool":
        need(pos, 3, "make tool NAME 工具名 --description 一句話 [--param 名:型別[:說明][:required]]... [--lang python|sh]")
        a = root.agent(pos[1])
        if not NAME_RE.match(pos[2]):
            raise Fail("NameBad", "工具名不合：%r" % pos[2], "小寫英數、_、-")
        res = {"ok": True, "name": a.name, "tool": pos[2], **mk.scaffold_tool(a.agent / "tools", pos[2], o),
               "next": "改 _entry 的 TODO；已登記進 tools.json，腦下次 think 就看得到（aos-tools ls）"}
        register_tool(a.agent, a.agent / "tools" / pos[2])
        if notes:
            res["notes"] = {**mk.notes_for(res["tool_json"], "tool_json"),
                            "_entry": "工具本體：stdin 收 arguments（JSON）、stdout 整段是結果；退非 0＝ToolFailed、整隻停（explain tool）"}
        out(res)
    elif kind == "cell":
        need(pos, 3, "make cell NAME 格名 [--exec 目標或單子JSON | --dir] [--next 下一格] [--after 前一格]")
        a = root.agent(pos[1])
        cell, fsm = pos[2], a.agent / "fsm.json"
        if not NAME_RE.match(cell):
            raise Fail("NameBad", "格名不合：%r" % cell)
        table = read_json(fsm)
        if not isinstance(table, dict) or not isinstance(table.get("states"), dict):
            raise Fail("CfgBad", "%s 不是 fsm 表" % fsm)
        if cell in table["states"]:
            raise Fail("CellExists", "已經有格 %s" % cell, "改它用 aos-json set %s#/states/%s …" % (fsm, cell))
        after = opt1(o, "after")
        if after and after not in table["states"]:
            raise Fail("CellMissing", "沒有格 %s" % after)
        made = []
        if "dir" in o:
            mk.write_new(a.agent / cell / "_entry", mk.SH_CELL.format(name=cell), mode=0o755)
            made.append(str(a.agent / cell / "_entry"))
            exe = cell
        elif opt1(o, "exec"):
            exe = mk.value(opt1(o, "exec"))
        else:
            raise Fail("ArgumentsBad", "要 --exec（目標或單子 JSON）或 --dir（起一個格資料夾）")
        nxt = opt1(o, "next") or (table["states"][after]["next"] if after else table.get("start"))
        spec = {"exec": exe, "next": nxt}
        trial = json.loads(json.dumps(table))
        trial["states"][cell] = spec
        if after:
            trial["states"][after]["next"] = cell
        mk.check_fsm(trial)                               # 先驗整張表，再交給 aos-json 改
        by = mk.aos_json_set(which, env, "%s#/states/%s" % (fsm, cell), spec)
        if after:
            mk.aos_json_set(which, env, "%s#/states/%s/next" % (fsm, after), cell)
        res = {"ok": True, "name": a.name, "cell": cell, "spec": spec, "after": after, "edited_by": by,
               "made": made, "fsm": str(fsm)}
        chk = mk.aos_json_check(which, env, fsm)
        if chk is not None:
            res["check"], res["ok"] = chk, chk["ok"]
        if notes:
            res["notes"] = {"exec": mk.NOTES["exec"], "next": "這格退 0 才換到 next；10 或失敗 state 不動（explain fsm）"}
        out(res)
    elif kind == "func":
        need(pos, 2, "make func 資料夾 [--summary 一句話] [--argv 命令 | --inst 單子JSON] [_metainfo 旗標...]")
        d = root.inside(pos[1], "函數資料夾")
        res = {"ok": True, **mk.scaffold_func(d, o), "next": "aos-ai exec %s 跑跑看" % d}
        if notes:
            res["notes"] = {"_entry": mk.NOTES["_entry"].split("；")[0] + "；這裡是可執行檔或單子（explain entry）",
                            "_metainfo": "跟 _entry 並列＝這個函數的特性，aos-exec 不讀（explain metainfo）"}
        out(res)
    else:
        raise Fail("ArgumentsBad", "make 不認得 %s；認 %s、tool、cell、func" % (kind, "、".join(mk.GEN)))



def cmd_explain(root, o, pos):
    if "here" in o:
        out(ex.here(pos[0] if pos else ".", opt1(o, "ws"), os.environ, override="dotenv-override" in o))
        return
    if not pos:
        secs = ex.sections()
        out({"ok": True, "concepts": list(secs), "how": "aos-ai explain <概念>；aos-ai explain --here [目標] 算具體值",
             "file": str(ex.CONCEPTS)})
        return
    k, text = ex.find(pos[0])
    if not k:
        raise Fail("ConceptUnknown", "沒有概念 %s" % pos[0], "aos-ai explain 列出全部：" + "、".join(ex.sections()))
    out({"ok": True, "concept": k, "text": text})
