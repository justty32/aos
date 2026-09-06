"""aos_llm — 跟一個「LLM 資料夾」打交道的小幫手（給 agent 或任何程式 import）。

一個 LLM 資料夾就是一個**平鋪**的資料夾：`engines.json`／`defaults.json`／`requests/`／
`results/`／`usage/`／`logs/`／`state.json` 全部直接放在它底下，`.aos/` 裡只有一句 `inst`。
要問 LLM，就往 `<dir>/requests/` 丟一個 JSON 檔，過幾格再去 `<dir>/results/` 撿同名的回覆。
**檔案就是介面**，自己寫檔完全可以；這個模組只是把「原子寫一個請求檔」跟「撿結果」包成
兩個函式，省得每個人重寫一次。只用標準函式庫。

    import aos_llm
    name = aos_llm.write_request("../llm", {"messages": [...]}, priority=3)
    ...
    answer = aos_llm.read_result("../llm", name)      # 還沒好就回 None

寫檔一律先寫 `<檔名>.tmp` 再 rename：`.tmp` 不是 `.json` 結尾，派工員不會撿到半個檔。
"""
import datetime
import json
import os

__all__ = ["home_of", "read_json", "write_json", "write_json_atomic", "stamp",
           "write_request", "read_result"]


def home_of(world_dir):
    """LLM 資料夾 → 東西放在哪（現在就是它自己，平鋪；換佈局只要改這裡）。"""
    return os.path.abspath(world_dir)


def read_json(path, default):
    """讀一個 JSON 檔；不在、空的、讀不成都回 default（不丟例外）。"""
    if not os.path.isfile(path):
        return default
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
    except OSError:
        return default
    if not text:
        return default
    try:
        return json.loads(text)
    except ValueError:
        return default


def write_json(path, obj):
    """就地寫一個 JSON 檔（沒有的資料夾自己建）。"""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_json_atomic(path, obj):
    """原子寫：先寫 `<path>.tmp` 再 rename，讀的人不會看到半個檔。"""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def stamp():
    """時間戳到微秒，拿來當檔名：`20260906-134500-123456`。"""
    now = datetime.datetime.now()
    return "%s-%06d" % (now.strftime("%Y%m%d-%H%M%S"), now.microsecond)


def write_request(world_dir, body, priority=None, engine=None, name=None):
    """把一包 body 寫成請求檔丟進 `<dir>/requests/`，回請求檔名。

    `body` 的頂層鍵原樣就是 chat/completions 的欄位（messages、tools、temperature…）。
    `priority`／`engine` **有給才寫進去**，沒給就留白讓那個 LLM 資料夾用自己的預設。
    `name` 不給＝純時間戳；給了而且不是 `.json` 結尾就當**前綴**（`<前綴>-<時間戳>.json`）；
    給了完整的 `xxx.json` 就原樣用。
    """
    req = dict(body or {})
    if priority is not None:
        req["priority"] = priority
    if engine:
        req["engine"] = engine
    if not name:
        name = stamp() + ".json"
    elif not name.endswith(".json"):
        name = "%s-%s.json" % (name, stamp())
    box = os.path.join(home_of(world_dir), "requests")
    os.makedirs(box, exist_ok=True)
    write_json_atomic(os.path.join(box, name), req)
    return name


def read_result(world_dir, request_name, remove=True):
    """撿 `<dir>/results/<request_name>`；還沒出現就回 None。

    撿到就回整包（一個 dict）；讀不成 JSON 物件的回 `{"error": "結果檔讀不成 JSON"}`
    ——反正對叫的人來說都是「這趟不算」。`remove=True`（預設）拿走就把結果檔刪掉。
    """
    if not request_name:
        return None
    path = os.path.join(home_of(world_dir), "results", request_name)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return None
    try:
        answer = json.loads(text)
        if not isinstance(answer, dict):
            raise ValueError("結果不是一個 JSON 物件")
    except ValueError:
        answer = {"error": "結果檔讀不成 JSON"}
    if remove:
        try:
            os.remove(path)
        except OSError:
            pass
    return answer
