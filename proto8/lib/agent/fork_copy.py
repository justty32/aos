"""fork_copy - 工具 fork 用：把一隻 agent-fsm 的 stack 裡定義宣告的東西（history、tools／llm／hooks／system 覆蓋檔）抄進新 stack，history 尾巴補上沒回的工具呼叫。

11-11 使用者「fork，也就是自身的各種東西複製一份，然後等他跑好後留下結論」；裁「一律連對話複製」、「eca不給fork。」（thinking/2026-11/11/fork-and-do-task/01-fork.md）。
只抄 interfaces.json 的 aos-agent 宣告過的檔（history 必要；tools、llm、hooks、system 有宣告、stack 裡有那份才抄），其他（goal.json、工具小格、
hook 狀態、queue、think/、stage.txt、observed）都不抄——身體從頭起、工具小格是各工具自己的帳。
history 照行原樣抄；最後一則 assistant 的 tool_calls 還沒回的補 tool 訊息（第一個沒回的＝正在跑的這次 fork，act 是一支一支照順序跑的）。
history 裡找不到叫到一半的 tool call（eca：工具來回在 CLI 裡、history 沒有這種行）＝BodyUnsupported（判法同 do_task）。
登記檔裡相對路徑的格（tools：$override、tools.*.path、tools.*.env_file；hooks：hooks.*.handler）從舊 stack 換算到新 stack；指示詞物件照原樣。
純標準庫；錯一律丟 ForkCopyBad（工具接成錯誤行）。"""
import json
import os

UNSUPPORTED = ("fork works only in an agent-fsm body, where each tool call is a line of your history "
               "(no unanswered tool call found in it); to hand work to another agent, use subagent")
OWN_CALL = ("[aos] fork: you are the copy made by this call; the original agent is waiting for your conclusion. "
            "Your task is in the next message.")
OTHER_CALL = "[aos] fork: not run in the copy (the original runs it after the fork call returns)."
KEYS = ("tools", "llm", "hooks", "system")


class ForkCopyBad(Exception):
    """抄不成：(代號, 原因)。"""
    def __init__(self, code, reason):
        self.code = code
        super().__init__(reason)


def declaration(def_folder):
    """定義 interfaces.json 的 aos-agent 宣告（物件）；沒檔、沒宣告＝InterfaceMissing，壞了＝InterfaceBad。"""
    path = os.path.join(def_folder, "interfaces.json")
    try:
        with open(path, encoding="utf-8") as f:
            value = json.load(f)
    except FileNotFoundError:
        raise ForkCopyBad("InterfaceMissing", "%s is missing" % path)
    except (OSError, ValueError) as e:
        raise ForkCopyBad("InterfaceBad", "cannot read %s: %s" % (path, e))
    decl = value.get("aos-agent") if isinstance(value, dict) else None
    if not isinstance(decl, dict):
        raise ForkCopyBad("InterfaceMissing", "%s does not declare aos-agent" % path)
    return decl


def _rel(decl, key):
    rel = decl.get(key)
    if rel is None:
        return None
    if not isinstance(rel, str) or not rel or os.path.isabs(rel) or ".." in rel.split("/"):
        raise ForkCopyBad("InterfaceBad", "aos-agent.%s must be a relative file path inside the definition" % key)
    return rel


def read_lines(path):
    """history 的每一行（原樣字串，去掉結尾換行；空行丟掉）；檔不在＝[]。"""
    try:
        with open(path, encoding="utf-8") as f:
            return [line.rstrip("\n") for line in f if line.strip()]
    except FileNotFoundError:
        return []
    except (OSError, UnicodeError) as e:
        raise ForkCopyBad("HistoryBad", "cannot read %s: %s" % (path, e))


def pending_tools(lines):
    """最後一則 assistant 的 tool_calls 裡還沒有 tool 訊息的那幾個 → 要補的 tool 訊息（第一個＝這次 fork）。讀不懂的行略過。"""
    messages = []
    for line in lines:
        try:
            m = json.loads(line)
        except ValueError:
            m = None
        messages.append(m if isinstance(m, dict) else {})
    last = max((i for i, m in enumerate(messages) if m.get("role") == "assistant"), default=None)
    if last is None or not isinstance(messages[last].get("tool_calls"), list):
        return []
    answered = {m.get("tool_call_id") for m in messages[last + 1:] if m.get("role") == "tool"}
    out = []
    for call in messages[last]["tool_calls"]:
        cid = call.get("id") if isinstance(call, dict) else None
        if not isinstance(cid, str) or cid in answered:
            continue
        out.append({"role": "tool", "tool_call_id": cid, "content": OTHER_CALL if out else OWN_CALL})
    return out


def _move(value, src, dst):
    """相對路徑字串從 src 資料夾換算成相對 dst；絕對、空、指示詞物件照原樣。"""
    if isinstance(value, str) and value and not os.path.isabs(value):
        return os.path.relpath(os.path.normpath(os.path.join(src, value)), dst)
    return value


def rebase(key, value, src, dst):
    """tools／hooks 登記檔裡的相對路徑換到新位置；其他鍵（llm、system）不動。"""
    if not isinstance(value, dict):
        return value
    value = dict(value)
    if key == "tools":
        if isinstance(value.get("$override"), list):
            value["$override"] = [_move(v, src, dst) for v in value["$override"]]
        elif "$override" in value:
            value["$override"] = _move(value["$override"], src, dst)
        table = value.get("tools")
        if isinstance(table, dict):
            value["tools"] = {n: (dict(e, **{k: _move(e[k], src, dst) for k in ("path", "env_file") if k in e})
                                  if isinstance(e, dict) else e) for n, e in table.items()}
    elif key == "hooks" and isinstance(value.get("hooks"), dict):
        value["hooks"] = {n: (dict(e, handler=_move(e["handler"], src, dst)) if isinstance(e, dict) and "handler" in e else e)
                          for n, e in value["hooks"].items()}
    return value


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = os.path.join(os.path.dirname(path), ".%s.%d.tmp" % (os.path.basename(path), os.getpid()))
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def check(def_folder, src):
    """抄得了嗎：回 (history 相對路徑, {鍵: 相對路徑}, history 各行, 要補的 tool 訊息)。
    沒宣告 history＝HistoryMissing；history 裡沒有叫到一半的 tool call＝BodyUnsupported（eca，或不是從 act 叫的）。"""
    decl = declaration(def_folder)
    hist = _rel(decl, "history")
    if hist is None:
        raise ForkCopyBad("HistoryMissing", "the definition %s declares no history (aos-agent.history), so there is no conversation to copy"
                          % def_folder)
    rels = {k: _rel(decl, k) for k in KEYS}
    lines = read_lines(os.path.join(src, hist))
    filled = pending_tools(lines)
    if not filled:
        raise ForkCopyBad("BodyUnsupported", UNSUPPORTED)
    return hist, rels, lines, filled


def copy_stack(def_folder, src, dst):
    """抄 src 的宣告檔進 dst（dst 要已存在）。回 {"messages": 抄了幾則, "filled": 補了幾則 tool 訊息, "files": [抄了的覆蓋檔相對路徑]}。"""
    hist, rels, lines, filled = check(def_folder, src)
    out = {"messages": len(lines), "filled": len(filled), "files": []}
    try:
        _write(os.path.join(dst, hist), "".join(l + "\n" for l in lines)
               + "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in filled))
        for key, rel in rels.items():
            if rel is None or not os.path.isfile(os.path.join(src, rel)):
                continue
            with open(os.path.join(src, rel), encoding="utf-8") as f:
                text = f.read()
            if key in ("tools", "hooks"):
                try:
                    value = json.loads(text)
                except ValueError as e:
                    raise ForkCopyBad("InterfaceBad", "your own %s (%s) is not JSON: %s" % (key, os.path.join(src, rel), e))
                src_dir = os.path.dirname(os.path.abspath(os.path.join(src, rel)))
                dst_dir = os.path.dirname(os.path.abspath(os.path.join(dst, rel)))
                text = json.dumps(rebase(key, value, src_dir, dst_dir), ensure_ascii=False, indent=1) + "\n"
            _write(os.path.join(dst, rel), text)
            out["files"].append(rel)
    except (OSError, UnicodeError) as e:
        raise ForkCopyBad("WriteFailed", "cannot copy into %s: %s" % (dst, e))
    return out
