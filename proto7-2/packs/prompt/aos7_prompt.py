"""prompt 組裝、折疊與展開（spec.md）。"""
import argparse
import copy
import functools
import hashlib
import json
import os
import re
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(HERE)), "lib")]
import aos_directives as ad  # noqa: E402
from aos7_fs import write_json  # noqa: E402
BAD_DIRECTIVES = {"UnknownDirective", "DirectiveValueTypeMismatch", "FormatVariableInvalid",
                  "UnknownFormatVariable", "UnknownOption", "OptionConflict"}
MESSAGE_OPTS = {"append": {"val": "required", "alone": True},
                "clear": {"val": "forbidden", "alone": True}}
FILE_OPTS = {k: {"val": "required", "alone": True} for k in ("file", "tail", "latest")}
MARKER = re.compile(r"ref://([0-9a-fA-F]{64}) 已折疊 ([0-9]+) 字，預覽：\n")
class PromptError(Exception):
    """帶回條分類的輸入或未知錯誤。"""
    def __init__(self, outcome, code, why):
        """保存分類、代號與白話。"""
        super().__init__(why)
        self.outcome, self.code, self.why = outcome, code, why
def boundary(fn):
    """將函式庫及檔案例外轉成公開錯誤。"""
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        """守住公開函式的錯誤邊界。"""
        try:
            return fn(*args, **kwargs)
        except ad.DirectiveError as e:
            raise PromptError("bad" if e.code in BAD_DIRECTIVES else "unknown", e.code, e.msg) from e
        except (OSError, UnicodeError, RecursionError) as e:
            raise PromptError("unknown", type(e).__name__, str(e)) from e
        except ValueError as e:
            raise PromptError("bad", "ValueInvalid", str(e)) from e
    return wrapped
def require(ok, why, outcome="bad", code="InvalidShape"):
    """拒絕不符合形狀的值。"""
    if not ok:
        raise PromptError(outcome, code, why)
def path_at(node, path):
    """相對路徑從 node 起算。"""
    return os.path.join(node, path)
def read_text(path):
    """讀 UTF-8，保留原本行尾。"""
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()
def read_json(path):
    """讀 JSON，語法錯誤歸 unknown。"""
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as e:
        raise PromptError("unknown", "ReferenceJsonInvalid", str(e)) from e
def located(value, ctx, pos):
    """解值並保留實體文件及位置。"""
    return ad.resolve_located(value, ctx, pos)
def option(value, pos, table):
    """依宿主選項表驗名字與值規則。"""
    opt = ad.split_option(value)
    return next(iter(ad.option_names(opt.opt, opt.has_val, pos, table))), opt.val
def segment(value, ctx, pos, node):
    """將一段文字或讀檔選項解成文字。"""
    value, ctx, pos = located(value, ctx, pos)
    if isinstance(value, str):
        return value
    require(ad.is_option_object(value), "content 每段要是字串或讀檔選項")
    name, raw = option(value, pos, FILE_OPTS)
    path = located(raw, ctx, pos + ["$val"]).value
    require(isinstance(path, str), "讀檔選項的 $val 要是路徑字串")
    path = path_at(node, path)
    if name == "file":
        return read_text(path)
    n = located(value.get("n", 40 if name == "tail" else 5), ctx, pos + ["n"]).value
    require(type(n) is int and n > 0, "n 要是正整數")
    if name == "tail":
        return "".join(re.findall(r"[^\n]*\n|[^\n]+$", read_text(path))[-n:])
    with os.scandir(path) as entries:
        names = sorted((e.name for e in entries if not e.name.startswith(".") and e.name.endswith(".md") and e.is_file()), reverse=True)
    return "\n\n".join("### " + x + "\n" + read_text(os.path.join(path, x)) for x in names[:n])
def content(value, ctx, pos, node):
    """解出單段或多段，保留折疊前的分段。"""
    value, ctx, pos = located(value, ctx, pos)
    if isinstance(value, list):
        return [segment(v, ctx, pos + [str(i)], node) for i, v in enumerate(value)]
    return [segment(value, ctx, pos, node)]
def messages(value, ctx, pos, node, result, chain=()):
    """遞迴組裝訊息，循環只看目前陣列鏈。"""
    value, ctx, pos = located(value, ctx, pos)
    require(isinstance(value, list), "messages／append 解完要是陣列")
    ident = (ctx.doc.ident, tuple(pos))
    require(ident not in chain, "append 陣列繞回自己", "unknown", "ReferenceCycle")
    for i, raw in enumerate(value):
        item, child, at = located(raw, ctx, pos + [str(i)])
        if ad.is_option_object(item):
            name, val = option(item, at, MESSAGE_OPTS)
            if name == "clear":
                result.clear()
            else:
                messages(val, child, at + ["$val"], node, result, chain + (ident,))
            continue
        require(isinstance(item, dict) and set(item) == {"role", "content"}, "訊息只准 role 與 content")
        role = located(item["role"], child, at + ["role"]).value
        require(isinstance(role, str) and bool(role), "role 要是非空字串")
        result.append((role, content(item["content"], child, at + ["content"], node)))
@boundary
def render(node, prompt_path, max_chars=None, out=None):
    """先解完讀完，才寫 ref，回請求與回條。"""
    require(os.path.isdir(node), "node 要是已存在的資料夾")
    refs_dir = os.path.realpath(path_at(node, "refs"))
    require(out is None or not os.path.realpath(path_at(node, out)).startswith(refs_dir + os.sep),
            "--out 不能寫進 <node>/refs/（那裡放折疊的原文）")
    path = path_at(node, prompt_path)
    raw = read_json(path)
    require(isinstance(raw, dict) and "messages" in raw and not set(raw) - {"messages", "model", "max_chars", "note"},
            "prompt 要是物件、有 messages，且只准 messages／model／max_chars／note")
    ctx = ad.Context(ad.Document(path, raw), base_dir=node, env=os.environ)
    values = {k: located(v, ctx, [k]) for k, v in raw.items() if k != "messages"}
    model = values["model"].value if "model" in values else "chatgpt-gpt-6-sol-high"
    limit = values["max_chars"].value if "max_chars" in values else 6000
    require(isinstance(model, str), "model 要是字串")
    require(type(limit) is int and limit >= 0, "max_chars 要是非負整數")
    if max_chars is not None:
        limit = max_chars
    require(type(limit) is int and limit >= 0, "max_chars 要是非負整數")
    rows, refs, output = [], {}, []
    messages(raw["messages"], ctx, ["messages"], node, rows)
    require(bool(rows), "訊息表不能是空的")
    full = sum(len("\n\n".join(parts)) for _, parts in rows)
    for role, parts in rows:
        folded = []
        for text in parts:
            if limit and len(text) > limit:
                sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
                refs[sha] = {"v": 1, "sha": sha, "chars": len(text), "text": text}
                text = f"ref://{sha} 已折疊 {len(text)} 字，預覽：\n" + text[:200]
            folded.append(text)
        output.append({"role": role, "content": "\n\n".join(folded)})
    pending = []
    for sha, ref in refs.items():
        dest = path_at(node, "refs/" + sha + ".json")
        try:
            old = read_json(dest)
        except (OSError, PromptError):
            old = None
        if old != ref:
            pending.append((dest, ref))
    for dest, ref in pending:
        write_json(dest, ref)
    chars = sum(len(m["content"]) for m in output)
    return {"litellm": {"model": model, "messages": output}}, dict(
        v=1, outcome="rendered", messages=len(output), chars=chars, tokens_est=(chars + 2) // 3,
        chars_full=full, tokens_est_full=(full + 2) // 3, folded=list(refs), out=None)
def ref_text(node, sha, chars=None):
    """讀取並驗 ref 的原文、雜湊及字數。"""
    ref = read_json(path_at(node, "refs/" + sha + ".json"))
    text = ref.get("text") if isinstance(ref, dict) else None
    require(isinstance(text, str) and hashlib.sha256(text.encode("utf-8")).hexdigest() == sha
            and type(ref.get("chars")) is int and ref["chars"] == len(text)
            and (chars is None or str(len(text)) == chars), "ref 內容或字數對不上", "unknown", "RefMismatch")
    return text
@boundary
def expand_text(node, s):
    """從左往右展開完整標記，不重掃換回的原文。"""
    require(os.path.isdir(node) and isinstance(s, str), "node 或文字不合", "unknown")
    pieces, start = [], 0
    for match in MARKER.finditer(s):
        if match.start() < start:
            continue
        text = ref_text(node, match[1], match[2])
        end = match.end() + len(text[:200])
        require(s[match.end():end] == text[:200], "ref 預覽對不上", "unknown", "RefMismatch")
        pieces.extend((s[start:match.start()], text))
        start = end
    return "".join(pieces) + s[start:]
@boundary
def expand_request(node, request_dict):
    """複製請求並展開每個 content。"""
    result = copy.deepcopy(request_dict)
    llm = result.get("litellm") if isinstance(result, dict) else None
    require(os.path.isdir(node) and isinstance(llm, dict) and isinstance(llm.get("model"), str)
            and isinstance(llm.get("messages"), list), "請求要有 litellm.model 字串與 litellm.messages 陣列")
    for item in llm["messages"]:
        require(isinstance(item, dict) and isinstance(item.get("role"), str) and item["role"]
                and isinstance(item.get("content"), str), "每則訊息要有非空 role 與字串 content")
        item["content"] = expand_text(node, item["content"])
    return result

def main(argv=None):
    """執行 render／expand，錯誤回 2 或 3。"""
    ap = argparse.ArgumentParser(prog="aos7-prompt")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("render")
    p.add_argument("node"); p.add_argument("prompt")
    p.add_argument("--out"); p.add_argument("--max-chars", type=int)
    p = sub.add_parser("expand")
    p.add_argument("node"); p.add_argument("source")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return e.code
    try:
        if a.cmd == "render":
            req, receipt = render(a.node, a.prompt, a.max_chars, a.out)
            if a.out is not None:
                write_json(path_at(a.node, a.out), req)
                receipt["out"] = a.out
            else:
                print(json.dumps(req, ensure_ascii=False, indent=1))
            try:   # 請求已提交；回條印不出來不改變結果
                print(json.dumps(receipt, ensure_ascii=False), file=sys.stdout if a.out is not None else sys.stderr)
            except OSError:
                pass
        else:
            require(os.path.isdir(a.node), "node 要是已存在的資料夾")
            if a.source.startswith("ref://"):
                require(bool(re.fullmatch(r"ref://[0-9a-fA-F]{64}", a.source)), "ref 格式不合", "unknown")
                print(ref_text(a.node, a.source[6:]), end="")
            else:
                print(json.dumps(expand_request(a.node, read_json(path_at(a.node, a.source))), ensure_ascii=False, indent=1))
        return 0
    except (OSError, UnicodeError) as e:
        error = PromptError("unknown", type(e).__name__, str(e))
    except ValueError as e:
        error = PromptError("bad", "ValueInvalid", str(e))
    except PromptError as e:
        error = e
    print(json.dumps(dict(v=1, outcome=error.outcome, code=error.code, why=error.why), ensure_ascii=False), file=sys.stderr)
    return 2 if error.outcome == "bad" else 3
