"""slash - agent-fsm 的 /status、/usage、/exit（線 eca-aos-templates-1125b，使用者 11-25「18.要認」；/clear 在 compact.py）：idle 收信時認，不叫腦、不跑 before_queue／after_queue，回一則「[aos] slash: …」。

跟 /clear 一樣（thinking/2026-11/21/api-agent-clear-1121.md「替使用者定的」）：內容去頭尾空白剛好是這幾個字的信一定自己一批，這一問一答記進 history
（user 那封帶 aos.letter、assistant 帶 aos.answer_to 與 aos.slash），listen 照信名配得到回答。這裡只算回答的字與 /exit 要叫的指令；寫 history、收信由 idle 做。
替使用者定的（11-25，eca-aos 轉的推薦）見 thinking/2026-11/25/api-agent-slash-1125.md：
  /status＝從 stack 拼：身體、model（定義的 llm.json 疊 stack 那份）、reasoning_effort、history 則數、goal、compact.json 的 phase、冷卻、queue 裡等著的信數；
  /usage ＝只報手上有的：observed.jsonl 裡每次問腦的 usage 加總與最後一次、context 讀數（aos.agentlib.context_use）；llm kernel 沒有額度介面，明說沒有；
  /exit  ＝停下（aos-agent ctl stop --target 自己 --no-wait），不是睡：兩種都不會因為來信就自己起來，stop 連 daemon 重啟也不會把它叫醒（sleep 會），
           比較像「離開」；回答說怎麼再起（aos-agent ctl start），信照樣排在 queue 等。"""
import json
import os

from aos.agentlib import context_use, cooldown, goal_state
from aos.declared_files import declared_files

COMMANDS = ("/status", "/usage", "/exit")
OBSERVED = "observed.jsonl"


def which(content):
    """這封是不是 /status、/usage、/exit（去頭尾空白後剛好是；後面帶字＝一般題目）。回那個字或 None。"""
    if not isinstance(content, str):
        return None
    word = content.strip()
    return word if word in COMMANDS else None


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def llm_settings(cd, stack):
    """腦設定＝定義的 llm（interfaces.json 宣告的）疊 stack 那份，同 brain.py；讀不到＝{}。"""
    files = declared_files(cd)
    if "llm" not in files:
        return {}
    cfg = _read_json(os.path.join(cd, files["llm"]))
    cfg.update(_read_json(os.path.join(stack, files["llm"])))
    return cfg


def _count_rows(path):
    try:
        with open(path, encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return 0


def _queue_waiting(stack):
    n = 0
    for stage in ("new", "cur"):
        try:
            n += sum(1 for name in os.listdir(os.path.join(stack, "queue", stage)) if not name.startswith("."))
        except OSError:
            pass
    return n


def _short(text, n=80):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n - 3] + "..."


def status(cd, stack, compact_state):
    """/status 的回答字（不含 [aos] slash: 前綴）。compact_state＝compact.state(stack)。queue 數不含這封自己（它已在 cur/）。"""
    cfg = llm_settings(cd, stack)
    model = cfg.get("model") or "(not set: the llm kernel's default pack)"
    effort = ", reasoning_effort %s" % cfg["reasoning_effort"] if cfg.get("reasoning_effort") else ""
    try:
        goal = goal_state.read(stack)
    except goal_state.GoalBad as e:
        goal_text = "unreadable (%s)" % e
    else:
        goal_text = "%s: %s" % (goal["status"], _short(goal["text"])) if goal else "none"
    phase = compact_state.get("phase")
    kind, rec = cooldown.state(stack)
    if rec is None:
        cool = "none"
    else:
        cool = "%s until %s after %d failure%s%s" % (
            kind, rec["until"], rec["failures"], "" if rec["failures"] == 1 else "s",
            " (%s)" % rec["error"]["code"] if rec.get("error") else (" (%s)" % rec["code"] if rec.get("code") else ""))
    waiting = max(_queue_waiting(stack) - 1, 0)
    return "/status: agent-fsm, model %s%s; history %d messages; goal %s; compact %s; cooldown %s; %d more letter%s waiting" % (
        model, effort, _count_rows(os.path.join(stack, "history.jsonl")), goal_text,
        phase or "none", cool, waiting, "" if waiting == 1 else "s")


def _numbers(usage):
    """usage 裡最上層的整數欄（各家端點的鍵名不同，照原樣加）。"""
    return {k: v for k, v in usage.items() if isinstance(v, int) and not isinstance(v, bool)} if isinstance(usage, dict) else {}


def _format(nums):
    return ", ".join("%s %d" % (k, nums[k]) for k in sorted(nums)) or "no token counts"


def usage(stack):
    """/usage 的回答字：observed.jsonl（wait 每次問腦記一列）的 usage 加總與最後一次、context 讀數；沒有額度介面。"""
    total, calls, last, last_endpoint = {}, 0, None, None
    try:
        with open(os.path.join(stack, OBSERVED), encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict) or row.get("kind") not in ("think", "compact"):
                    continue
                nums = _numbers(row.get("usage"))
                if not nums:
                    continue
                calls += 1
                for k, v in nums.items():
                    total[k] = total.get(k, 0) + v
                last, last_endpoint = nums, row.get("endpoint")
    except OSError:
        pass
    if calls:
        tokens = "%d brain call%s with usage in %s: total %s; last call%s: %s" % (
            calls, "" if calls == 1 else "s", OBSERVED, _format(total),
            " (%s)" % last_endpoint if isinstance(last_endpoint, str) else "", _format(last))
    else:
        tokens = "no brain call with usage in %s yet" % OBSERVED
    reading = context_use.read(stack)
    context = ("context %.1f%% full (%d of %d tokens)" % (reading["percent"], reading["used"], reading["window"])
               if reading else "context: %s" % context_use.explain(stack))
    return ("/usage: %s; %s; no quota or rate limit to report: the llm kernel gives none "
            "(a pack's budget, if it has one, shows only as BudgetMissing when it is used up)" % (tokens, context))


def exit_note(stopped, me, why):
    """/exit 的回答字。stopped＝stop 的請求有沒有送成。"""
    if stopped:
        return ("/exit: %s stops at the end of this step (stop, not sleep: letters do not start it again, nor does a daemon restart); "
                "letters sent to it wait in its queue; aos-agent ctl start %s brings it back" % (me, me))
    return "/exit: could not stop (%s); still running" % why
