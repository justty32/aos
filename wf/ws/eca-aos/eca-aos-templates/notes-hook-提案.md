提案：eca 壓縮（compact）之後，提醒它讀自己的 notes.md，而不是頂層的 wf/HANDOFF.md（線 eca-aos-templates-1122-notes-hook；只出提案與原型，正在用的範本沒改）。

# compact 後讀自己的筆記：提案（11-22）

← [地盤](README.md)｜起因：[筆記調查-1122](../../../../proto8/thinking/2026-11/22/筆記調查-1122/README.md)「會出問題的地方」｜我的[筆記](notes.md)

## 問題

eca 壓縮後，有兩支 SessionStart（matcher compact）hook 的輸出會進對話：

1. **repo 的 `wf/tools/compact_reload.sh`**（`.claude/settings.json` 掛；範本有 `--setting-sources project,local`，工作區在 repo 的每一隻 eca 都會跑）：貼 `user.md` 全文，加上 **`wf/HANDOFF.md` 的第一條**。
2. **範本的 `compact_hook start`**（`proto8/templates/eca-claude/cli.json` 的 `settings` 掛）：印「read your handoff notes again (the handoff file or session log your workspace's rules name, or `$AOS_STACK/handoff.md`)」，再附 stack 的 `handoff.md` 尾巴與 before_compact 交的補回字。

兩支都把 subagent 指向頂層的交接，而那是 eca-aos 的。系統文字裡雖然有一句「compact 後讀 notes.md」，但壓縮那一刻貼進來的兩段字都在叫它去讀另一個檔，而且離得更近。所以 hook 要做的不只是提醒，還要**改掉這個互相矛盾的指示**。

## 三種做法

| | 做法 | 路徑從哪來 | 好處 | 代價 | 影響正在跑的誰 |
|---|---|---|---|---|---|
| **A（推薦）** | `compact_hook start` 讀 `$AOS_STACK/notes_path`（一行，絕對路徑或相對 `AOS_WS`）。有這個檔時，換成印「your own notes are X, read them now」；是 subagent（`AOS_PARENT_STACK` 不是空的）時再多一句「頂層的交接是上層的、不是你的」。沒有這個檔時，輸出跟現在一字不差 | stack 裡一個檔。上層 `subagent add` 時寫（跟[地盤規矩](../../README.md)第 4 條「上層替下層建」一起做），或 agent 自己用 Write 寫 | 範本不綁 repo 的 `wf/ws/` 慣例，別的工作區照用；要開才開（opt-in）；改動小（原型 +23 行）；不用動 daemon | 每隻要有人寫一次那個檔；stack 不在 repo 時（換機）要跟著 `_stack` 走 | 用 eca-claude 範本的全部（eca-aos、eca-claude、eca-aos-templates、eca-aos-kb、aos-eca-frontend，外加 start-eca 的 ann 抄本），下一次壓縮起生效；沒寫 `notes_path` 的照舊，不受影響 |
| B | 不記路徑，從層級推：`$AOS_WS/wf/ws/<上層…>/<自己的名字>/notes.md`。名字取 `AOS_STACK` 的資料夾名，上層取 `AOS_PARENT_STACK`；更上層要讀上層 stack 的 env，或直接 glob `wf/ws/**/<名>/notes.md` | 推出來的 | 不用每隻設定；新掛的 subagent 自動有 | 把這個 repo 的 `wf/ws/` 慣例寫死進通用範本（範本也給別的工作區用）；要讀別人的 stack，或靠名字在整棵樹裡唯一；路徑規矩一改，範本就跟著要改 | 同 A，但不是 opt-in：檔存在的每一隻都會換句子 |
| C | 範本不改：每隻在自己 stack 的 `hookeds.json` 掛一個 `before_compact` hook（一支小程式，讀 `notes_path` 或寫死路徑），回 `{"restore": "your own notes are X …"}`。現有的 `compact_hook start` 會把它印成「restored after compact」 | 寫在 hook 程式或它讀的檔裡 | 用現成的擴充點，範本與測試都不動 | 「讀工作區規矩說的交接」那句還在，兩句互相矛盾、只是多了一句；每隻都要 `aos-agent hook add`（要動 daemon，或 agent 先 `self_tools add` 加回 self_hook）；那支 hook 程式要放哪也得再決定 | 只有掛了 hook 的那幾隻 |

推薦 A：它是唯一能**取代**那句錯誤指示的做法（C 只是多一句），又不像 B 把 repo 的慣例寫進範本。

## 原型（A）與試跑

- 檔案：`temp/proto-1/compact_hook`，是範本那支抄出來改的（temp/ 不進 git，所以 diff 全文貼在下面）。
- 單元情況（`env -i`，假的 stack）：
  1. 沒有 `notes_path`：輸出跟範本原版 `diff` 結果相同。
  2. subagent、相對路徑：印出筆記路徑和「不是你的」那句，不再印「workspace's rules name」那句；stack 的 `handoff.md` 照附。
  3. 頂層（`AOS_PARENT_STACK` 是空的）：只印筆記那句。
  4. 路徑指到不存在的檔：stderr 一行 warning，照樣提醒。
- 真的壓一次（11-22，haiku，cwd＝repo，所以 repo 的 `compact_reload.sh` 也一起跑、HANDOFF 那段也貼進去了；SessionStart 掛原型，假 stack 的 `notes_path` 指到我這份 notes.md）：`Say ok.` → `/compact` → 問「壓縮後叫你先讀哪個檔、wf/HANDOFF.md 是不是你的」。答：先讀 `…/eca-aos-templates/notes.md`；`wf/HANDOFF.md` 不是它的，是上層 `…/procs/eca-aos` 的。不過它也補了一句「hook 沒直接點名那個檔，這是我推的」。所以題 3 的 b 仍然值得做。
- 沒驗的：在真的 aos 回合裡（aos-eca-turn → claude）壓縮。原型沒接進範本，活樹也沒碰。

要正式做時還得跟著改：範本 README 和 `templates/docs/01` 的「壓縮前後的 hook 點」段、`templates/tests/test_eca_compact_hook.py` 加上面四個情況，再重抄 `start-eca/agents/ann`（`test_ann_is_the_same_file`）。

```diff
--- proto8/templates/eca-claude/compact_hook
+++ temp/proto-1/compact_hook
@@ -21,6 +21,7 @@
 import sys
 
 LIMIT = 8000                                       # handoff.md 最多附這麼多字（太長只留尾巴，最新的通常在後面）
+NOTES = "notes_path"                               # 原型（線 eca-aos-templates-1122-notes-hook）：stack 裡一行，這隻自己的筆記在哪（絕對，或相對工作區 AOS_WS）
 RESTORE = "compact_restore.txt"                    # before_compact 的 hook 交的補回字，放在 $AOS_STACK/claude/ 等 SessionStart 印
 BLOCKED = 10                                       # handler 退 10：攔下 before_compact
 
@@ -131,11 +132,32 @@
         return ""
 
 
+NOTES_TEXT = """[aos] compact: your own notes are %s. Read them now, before anything else%s."""
+NOT_YOURS = ("; you are a subagent (your parent's stack is %s), so a top-level handoff file the workspace's rules name "
+             "is your parent's, not yours: carry on from your notes, this compaction's summary and the letters in your queue")
+
+
+def notes_line(stack):
+    """$AOS_STACK/notes_path 有一行路徑＝回提醒那句（含路徑；subagent 多一句「頂層的交接不是你的」）；沒有這個檔或是空的＝None（照舊）。"""
+    raw = read(os.path.join(stack, NOTES)).strip() if stack else ""
+    if not raw:
+        return None
+    path = raw.splitlines()[0].strip()
+    ws = os.environ.get("AOS_WS", "")
+    if not os.path.isabs(path) and ws:
+        path = os.path.join(ws, path)
+    if not os.path.isfile(path):
+        warn("%s names %s, which is not a file; reminding of it anyway" % (os.path.join(stack, NOTES), path))
+    parent = os.environ.get("AOS_PARENT_STACK", "")
+    return NOTES_TEXT % (path, (NOT_YOURS % parent) if parent else "")
+
+
 def start():
     stack = os.environ.get("AOS_STACK", "")
+    line = notes_line(stack)
     path = os.path.join(stack, "handoff.md") if stack else ""
     text = read(path) if path else ""
-    print(START % ((", or %s" % path) if path else ""))
+    print(line if line else START % ((", or %s" % path) if path else ""))   # 有筆記＝這句取代「讀工作區規矩說的交接」
     if text.strip():
         if len(text) > LIMIT:
             text = "[... %d earlier characters left out ...]\n" % (len(text) - LIMIT) + text[-LIMIT:]
```

## 要使用者選的題目

1. **用哪種做法？** A（stack 記路徑，opt-in）／B（從層級推，綁 `wf/ws/`）／C（範本不改，每隻掛 hook）。**推薦 A**。
2. **只印路徑，還是連筆記全文一起貼？**
   - (a) 只印路徑：每次壓縮只多一行，要靠它自己去讀。
   - (b) 貼全文（上限比照 handoff 8000 字）：一定看得到，但每次壓縮多吃到 8 KB；`compact_reload.sh` 本來就已經貼 30 KB 以上。
   - **推薦 a**：真實試跑時它照路徑讀得到。
3. **repo 的 `compact_reload.sh` 怎麼辦？** 它在 `wf/tools/`，不是我能改的範圍。
   - (a) 不動，靠範本那句「不是你的」蓋過去：試跑可行，但兩段字還是並排出現。
   - (b) `AOS_PARENT_STACK` 不是空的（subagent）就不貼 HANDOFF 那段，改印一句「你的交接看自己的筆記」：最乾淨，要另開一條線改 wf/tools。
   - (c) 由 `compact_reload.sh` 自己去讀 `$AOS_STACK/notes_path` 並貼出來，範本不改：一處就搞定，但只對工作區在這個 repo 的 eca 有效。
   - **推薦 A ＋ b**。（11-22 15:25 起 `compact_reload.sh` 被線 `progress-tidy-1122-apply` claim 著，那邊改的是 progress 條目的 `$ref` 印法、跟這題無關；要做 b 得等它交完，或先跟它講好。）
4. **`notes_path` 誰寫？**
   - (a) 上層在 `subagent add` 時寫：跟建地盤同一步，寫進地盤規矩第 4 條。
   - (b) agent 自己寫：系統文字裡交代一句。
   - **推薦 a**；現有的三隻由 eca-aos 各寫一次。
