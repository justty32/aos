"""parts - agent 資料夾裡找格（11-01 A 題，取代 bin/aos-parts）：器官（roundlib、queue、compact、act、ask_round）共用這一處。

設計：proto8/thinking/2026-10-31-parts-round.md（決定 11-01：parts 是 agent 慣例層的約定、以刪掉 aos-parts 為目標、註冊檔與固定名字共存）。
parts.json＝aos-exec 格式的槽表（C-72、N-61）：整份就是槽表（頂層不包 "parts"）；槽值是字串（轉向，相對路徑從 parts.json 的資料夾算）
  或 {".env": {名: 值}, "_entry": 路徑}（帶 env 的轉向）；endpoint/<名>、hook/<點> 是巢狀物件（{"endpoint": {"default": …}}）。
找法只寫在這裡（C-52）：parts.json 有這個槽＝`<agent>/parts.json#/槽`；沒寫＝固定名字 `<agent>/<槽>`（捷徑、真資料夾、檔都行，在就算）；
  都沒有＝None（必要的格由叫的人報 PartMissing）。登記了就用它，指到的東西壞了由 aos-exec 跑的時候自己報、不退去找固定名字。
叫格＝`aos-exec <find 回的> <agent> [子命令]`；env 交給 aos-exec 讀 `.env` key／`.env` 檔，預設不蓋環境裡已有的（N-58）、這裡不疊 env；
  要蓋就在那一跳加 aos-exec 的 `--dotenv-override`。
錯：parts.json 讀不了、不是 JSON 物件、路上碰到不是物件的（例 "hook" 寫成字串）＝raise Bad；叫的格換成自己的一行 PartsBad。"""
import json, os

FILE = "parts.json"


class Bad(Exception):
    pass


def load(agent):
    """parts.json 的內容；沒有這份檔＝{}（沒登記任何格）。"""
    p = os.path.join(agent, FILE)
    try:
        with open(p, encoding="utf-8") as f:
            reg = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise Bad("%s 讀不了或不是 JSON：%s" % (p, e))
    if not isinstance(reg, dict):
        raise Bad("%s 要是 JSON 物件（槽 → 路徑或 {\".env\", \"_entry\"}）" % p)
    return reg


def registered(agent, keys):
    node = load(agent)
    for i, k in enumerate(keys):
        if not isinstance(node, dict):
            raise Bad("%s 的 %s 要是物件（裡面放 %s）" % (os.path.join(agent, FILE), "/".join(keys[:i]), "/".join(keys[i:])))
        if k not in node:
            return False
        node = node[k]
    return True


def find(agent, slot):
    """槽（例 queue、endpoint/default、hook/pre_think）→ 給 aos-exec 的目標；沒掛＝None。"""
    keys = slot.split("/")
    if registered(agent, keys):
        return "%s#/%s" % (os.path.join(agent, FILE), "/".join(k.replace("~", "~0") for k in keys))
    fixed = os.path.join(agent, *keys)
    return fixed if os.path.lexists(fixed) else None


def endpoints(agent):
    """parts.json 的 endpoint 底下的名字與 <agent>/endpoint/ 底下的名字聯集，排序。"""
    reg = load(agent).get("endpoint")
    found = {n for n in reg if not n.startswith(".")} if isinstance(reg, dict) else set()
    try:
        found.update(n for n in os.listdir(os.path.join(agent, "endpoint")) if not n.startswith("."))
    except (FileNotFoundError, NotADirectoryError):
        pass
    return sorted(found)
