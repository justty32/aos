"""spec_base - agent_spec 與 tool_spec 共用的底：例外（SpecBad、DefBad）、從檔名推名字、--compile [位置]／--dry-run 的小旗標殼、寫檔後端（文字、json、程式檔、連結；暫存檔＋改名）。

施工計劃第 0 刀（線 aos-pylib-k0-1120，設計稿 thinking/2026-11/20/aos-pylib-plan-1120/07b）：兩邊原本各寫一份的搬到這裡，編譯出的檔與輸出一字不變。
程式檔（Program）、連結（Link）、帶一層子夾的檔名，今天還沒人用；第 3、4 刀（函數抽成 fn/<名>.py、defs.extern 的連結版）才接上。
只給 aos 內部用（agent_spec、tool_spec、tools_def）；寫 agent.py／tool.py 的人不直接 import 它。
"""
import json, os


class SpecBad(Exception):
    """宣告本身寫錯（agent.py 的欄位、tool.py 的參數、metainfo 的值…）；訊息寫成怎麼改。"""


class DefBad(ValueError):
    """定義夾本身（不是宣告）不對：_metainfo.json 壞了；不宣告 FSM 時 interfaces.json 不在、或沒宣告要寫的那份檔。"""


class Program(str):
    """寫成可執行的程式檔（權限一律 755）的文字。"""


class Link(str):
    """寫成一個連結（symlink）：值＝連結裡存的目標，照字面存，不查在不在、不碰目標。"""


def prog_name(script, main_file):
    """錯誤行開頭的名字：script 是主檔（agent.py／tool.py）＝它所在的資料夾名；別的腳本（JSON 物件裡的工具 mul.py）＝檔名去副檔名。"""
    base = os.path.basename(script)
    return os.path.basename(os.path.dirname(script)) if base == main_file else os.path.splitext(base)[0]


def location(mode, rest, argv, script, usage, die):
    """--compile [位置]／--dry-run（mode）後面剩下的參數 rest → 位置；沒給＝script 所在的夾（--dry-run 也回，給要照夾算的用）。
    多給＝die("ArgumentsBad", "too many arguments: 整串 argv (usage)")；die 由叫的一方給（flags.die 與 tool_io.die 的錯誤行開頭不同）。
    其餘旗標（--static、--tooldef…）各自處理，不硬合（設計稿 07d 意見 8）。"""
    if len(rest) > (1 if mode == "--compile" else 0):
        die("ArgumentsBad", "too many arguments: %s (%s)" % (" ".join(argv), usage))
    return rest[0] if rest else os.path.dirname(script)


def _path_in(folder, name):
    parts = name.split("/") if isinstance(name, str) else []
    if not 1 <= len(parts) <= 2 or not all(p and p not in (".", "..") for p in parts):
        raise ValueError("file name %r: give a plain name, or one sub-folder and a name (like \"fn/add.py\")" % (name,))
    return os.path.join(folder, *parts), (os.path.join(folder, parts[0]) if len(parts) == 2 else None)


def write_files(folder, files, last=None):
    """files {檔名: 內容} 寫進 folder（要已經在）。內容：Link＝連結、Program＝程式檔（755）、其他 str＝文字、其餘＝JSON（縮排 2、結尾換行）。
    檔名可帶一層子夾（"fn/add.py"），子夾不在就建。
    先全部寫成同夾的暫存檔（.<名>.tmp-<pid>，連結也是暫存連結；同名殘留先清掉），最後照 last（{檔名: 次序}，沒列＝0，小的先）
    連著 os.replace：寫暫存檔時失敗＝清掉暫存檔與這次新建又空著的子夾，夾裡不變；改名時才失敗（極少）＝前面幾份已換上、每份各自完整，
    重跑就好。原檔在（os.path.exists）就把它的權限抄給新的文字與 JSON；連結不設權限。判斷在不在、清暫存一律用 lexists（斷掉的連結也算在）。
    例外照丟：OSError（folder 不是資料夾也是）、TypeError／ValueError（內容寫不成 JSON、檔名不對）。"""
    if not os.path.isdir(folder):
        raise OSError("%s is not a folder" % folder)
    last = last or {}
    plan, tmps, made, ok = [], [], [], False
    try:
        for name, value in files.items():
            path, sub = _path_in(folder, name)
            if sub is not None and not os.path.lexists(sub):
                os.mkdir(sub)
                made.append(sub)
            tmp = os.path.join(os.path.dirname(path), ".%s.tmp-%d" % (os.path.basename(path), os.getpid()))
            if os.path.lexists(tmp):                # 同一個 pid 上次沒清掉的；不清的話寫文字會順著舊的暫存連結寫到別處
                os.unlink(tmp)
            tmps.append(tmp)
            if isinstance(value, Link):
                os.symlink(str(value), tmp)
            else:
                text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n"
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(text)
                if isinstance(value, Program):
                    os.chmod(tmp, 0o755)
                elif os.path.exists(path):
                    os.chmod(tmp, os.stat(path).st_mode & 0o7777)
            plan.append((name, path, tmp))
        for name, path, tmp in sorted(plan, key=lambda p: last.get(p[0], 0)):
            os.replace(tmp, path)
        ok = True
    finally:
        for tmp in tmps:
            if os.path.lexists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        if not ok:
            for sub in reversed(made):
                try:
                    os.rmdir(sub)                   # 只刪空的：改名時才失敗、裡面已有換上的檔就留著
                except OSError:
                    pass
