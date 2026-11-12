"""directive_value - 把設定檔裡一格寫成指示詞（$env／$ref，N-45）的值交給 aos-directive 解開、回解完的值；每次用到才解，不寫回任何檔。

11-10 two-machines TC（使用者：指到外面的路徑「相對、絕對、環境變數指定都可」、每次用到才解、不把解出來的值寫回任何檔）：
cli.json 的 tools 用。做法照判官（lib/aos/judge/_entry）：stdin 一份 JSON、aos-directive 印解完的一行；
相對 $ref 從 cwd 算，所以 cwd 給那份設定檔的資料夾（同 N-45「相對 $ref 從寫著它的那份檔所在的資料夾算」）。
aos-directive 自己的錯誤行照轉在 stderr（不偷讀，C-52）；這裡只說哪個檔、哪個欄、寫的是什麼、解出什麼。
錯誤用 tool_io.Error（代號＋英文原因），由呼叫者轉成自己的錯誤行。lib 最底下的共用模組，不 import py。"""
import json
import os
import subprocess

from tool_io import Error


def resolve(value, cwd, file=None):
    """value 是物件＝送 aos-directive 解（cwd 是相對 $ref 的起點），回解完的值；不是物件＝原樣回。
    file＝這格是從哪份檔讀來的（知道才給，11-12 ref-hash）：{"$ref": "#/a/b"} 取那份檔自己的 /a/b；沒給＝這種 $ref 原封不動（R1）。
    aos-directive 起不來（不在 PATH）＝CommandMissing；退非 0 或印的不是 JSON＝DirectiveBad。"""
    if not isinstance(value, dict):
        return value
    try:
        r = subprocess.run(["aos-directive"] + (["--file", os.path.abspath(file)] if file else []),
                           input=json.dumps(value, ensure_ascii=False), stdout=subprocess.PIPE, text=True, cwd=cwd)
    except OSError as e:
        raise Error("CommandMissing", "aos-directive failed to start (must be on PATH): %s" % e) from None
    if r.returncode != 0:
        raise Error("DirectiveBad", "aos-directive exited %d (its error line is above)" % r.returncode)
    try:
        return json.loads(r.stdout)
    except ValueError:
        raise Error("DirectiveBad", "aos-directive printed no JSON") from None


def resolve_path(value, cfg_file, key):
    """設定檔 cfg_file 裡 key 那格的指示詞物件 → 解完的非空字串（相對的原樣回，呼叫者照自己的基準接）。
    {"$ref": "#/a/b"}＝cfg_file 自己的 /a/b。
    解不開、解完不是非空字串＝CfgBad（指名檔、欄、寫的與解出的）；aos-directive 不在 PATH＝CommandMissing。"""
    written = json.dumps(value, ensure_ascii=False)
    try:
        got = resolve(value, os.path.dirname(os.path.abspath(cfg_file)), cfg_file)
    except Error as e:
        raise Error("CommandMissing" if e.code == "CommandMissing" else "CfgBad",
                    "%s: %s %s cannot be resolved: %s" % (cfg_file, key, written, e)) from None
    if not isinstance(got, str) or not got:
        raise Error("CfgBad", "%s: %s %s resolves to %s, which is not a non-empty path string"
                    % (cfg_file, key, written, json.dumps(got, ensure_ascii=False)))
    return got
