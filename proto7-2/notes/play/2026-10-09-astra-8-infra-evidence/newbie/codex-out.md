本線列出 9 項：A 類 4、B 類 4、C 類 1；沒有判高嚴重度。  
受測 HEAD 為 `cd544440`。全程唯讀、未呼叫網路或 LLM；執行了六個模組的 help 與不落盤的函式探針。  
下列建檔重現供隊長執行，全部限制在 `/tmp/astra8-newbie-*`；未把它們宣稱為已實跑。  
前輪的 handed、永久卡住、跨信記憶、空洞摘要及 metrics 多回合分類，都已有對應修補；本次發現主要在修補後的接合邊界。

### NEW-newbie-1〔A／up，中〕重跑 up 會清掉使用者設定的 brain 參數

- 契約：`proto7-2/modules/up/ADVANCED.md:105`「每 `progress_every` 回合（up.json，預設 5，0＝不寄）」；`:115` 說明可設 `stall`、`max_steps`；`:119` 以 up.json 的 `deadline` 為不確定期限；`:145`「`up.json` 可設 `max_prompt_chars`」。
- 程式：`proto7-2/modules/up/aos7_up.py:44` 重新建立 `settings = dict(...)`；`:49` 只額外保留 `interval_ms`、`early_tock`；`:54`「`atomic(node / '.aos/up.json', settings)`」。其餘 brain 設定被覆蓋掉。
- 重現：直接跑正式 `prepare()`，只替換外部 CLI 與 daemon 存活查詢；實際設定讀寫照原程式。

```bash
T=$(mktemp -d /tmp/astra8-newbie-config-XXXX)
export T PYTHONDONTWRITEBYTECODE=1
python3 -B - <<'PY'
import json, os, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, 'proto7-2/modules/up')
import aos7_up as u

n = Path(os.environ['T']) / 'bob'
(n / '.aos').mkdir(parents=True)
(n / 'AGENTS.md').write_text('已導入的 node\n')
cfg = dict(v=1, node=str(n), house=str(n.parent), name='bob',
           you='you', mail_root=str(n.parent), model=None,
           litellm_url='http://localhost:4000/v1',
           budget='budget/llm', holder='brain', gateway='llm.fake')
custom = dict(deadline=12, max_steps=7, progress_every=2,
              compact=False, max_prompt_chars=20000)
p = n / '.aos/up.json'
p.write_text(json.dumps(cfg | custom))
with patch.object(u, 'run', return_value=''), \
     patch.object(u, 'alive', return_value=False):
    u.prepare(n, None)
after = json.loads(p.read_text())
print({k: after.get(k, 'MISSING') for k in custom})
PY
rm -rf "$T"
```

- 預期／推斷實際：預期五個自訂值保持；實際全部變成 `MISSING`。重啟後期限、步數上限、進度信頻率及提示上限回到預設。此欄位遺失已由不落盤探針確認。
- 修法：以既有設定為底合併 up 管理的欄位，保留並驗證 brain 的可設定欄位。

### NEW-newbie-2〔A／brain，中〕task 壞掉後重播，journal 超過 20 行就可能重記

- 契約：`proto7-2/modules/up/ADVANCED.md:111`「task.json 壞掉就刪掉從第 1 回合重播（每回合的 call 已有回條，不重問、不重記）」。
- 程式：`proto7-2/modules/up/aos7_up_brain.py:80` 刪除壞 task；`:269`「`old = path.read_text().splitlines()[-20:]`」；`:271` 僅在這 20 行用 `startswith(key)` 去重；`:336` 每次 `step_on()` 呼叫 journal。
- 重現：重現恢復路徑所用的 task 讀取及 journal 寫入，不需要 AI。

```bash
T=$(mktemp -d /tmp/astra8-newbie-replay-XXXX)
export T PYTHONDONTWRITEBYTECODE=1
python3 -B - <<'PY'
import collections, json, os, sys
from pathlib import Path
sys.path.insert(0, 'proto7-2/modules/up')
import aos7_up_brain as b

n = Path(os.environ['T'])
(n / 'brain').mkdir()
for step in range(1, 26):
    b.journal(n, 'letter1', step, f'做完第 {step} 步')
(n / 'brain/task.json').write_text('{')
print('恢復後 task:', b.task_of(n))
# 第三步已不在最後 20 行，模擬重播到第三步。
b.journal(n, 'letter1', 3, '做完第 3 步')
rows = [json.loads(s) for s in (n / 'notes/journal.jsonl').read_text().splitlines()]
counts = collections.Counter((r['re'], r['step']) for r in rows)
print('第三步筆數:', counts[('letter1', 3)])
print('總筆數:', len(rows))
PY
rm -rf "$T"
```

- 預期／推斷實際：預期第三步仍 1 筆、總共 25 筆；實際第三步 2 筆、共 26 筆。compact 把舊行移入 archive 後，相同的去重缺口也會出現。
- 修法：用持久的 `(信 id, step)` 完成標記去重，不以 journal 最後 20 行作唯一證據；比對應解析欄位，避免數字前綴碰撞。

### NEW-newbie-3〔A／ask，中〕回信正文有指定 Markdown 標題時，標題前的答案會被漏印

- 契約：`proto7-2/modules/up/README.md:13`「印 bob 的回信全文」；`proto7-2/modules/mail/ADVANCED.md:46`「一般正文原樣使用」。
- 程式：`proto7-2/modules/up/aos7_up_ask.py:14` 依四種標題切割；`:19` 只遍歷 `parts[1::2]`、`parts[2::2]`，沒有輸出 `parts[0]`。`:52` 還會先把回信歸檔，再顯示。
- 重現：

```bash
T=$(mktemp -d /tmp/astra8-newbie-body-XXXX)
export PYTHONDONTWRITEBYTECODE=1
python3 -B - <<'PY'
import sys
sys.path.insert(0, 'proto7-2/modules/up')
from aos7_up_ask import show_body
show_body('關鍵答案：42\n\n## 做了什麼\n算完了\n', '計算結果')
PY
rm -rf "$T"
```

- 預期／推斷實際：預期至少保留「關鍵答案：42」與「算完了」；實際只印「算完了」。不落盤探針已確認，原信仍存在，但 ask 顯示不完整且已將它歸檔。
- 修法：保留非空的前言 `parts[0]`；最好只移除確定由舊模板產生的空段，不刪一般正文。

### NEW-newbie-4〔A／mail，中〕ack 游標 JSON 型別錯誤會直接 traceback，連 read 都無法完成

- 契約：`proto7-2/modules/mail/ADVANCED.md:68`「stderr 一行 `aos7-mail: <發生什麼>。<怎麼辦>`」；`proto7-2/notes/blueprint-errors.md:18` 不確定時應保留證據，`:39` 要以退 3、一行「不確定」說明。
- 程式：`proto7-2/modules/mail/aos7_mail_ack.py:26` 直接載入 `.acked`；`:27`「`upto, cursor, unsure = local, local + 1, False`」沒有驗證整數型別。`aos7_mail_cli.py:116`、`:133` 的例外處理皆未接住 `TypeError`。
- 重現：

```bash
T=$(mktemp -d /tmp/astra8-newbie-ack-XXXX)
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$T/bob/inbox" "$T/bob/events"
printf '[]\n' > "$T/bob/inbox/.acked"
python3 -B proto7-2/modules/mail/aos7-mail --root "$T" read bob
echo "rc=$?"
cat "$T/bob/inbox/.acked"
rm -rf "$T"
```

- 預期／推斷實際：預期一行白話錯誤、保留 `.acked`，適合退 3；實際退 1，出現 `TypeError: can only concatenate list (not "int") to list` traceback。該算術例外已由不落盤探針確認。
- 修法：載入 ack 游標時驗證為非負整數，異常轉成保留證據的明確錯誤；其他持久游標也採相同驗證方式。

### NEW-newbie-5〔B／compact、mail，低〕部分退 2 路徑仍先建立資料夾與鎖檔

- 契約：`proto7-2/notes/blueprint-errors.md:17`「參數、檔案形狀、用法錯；**什麼都沒動**」；`proto7-2/modules/compact/ADVANCED.md:46` 重申「參數、設定或範圍不合；什麼都沒動」。
- 程式：`proto7-2/modules/compact/aos7_compact.py:669`、`:670` 先建 `compact/lock`，之後 `:599` 才拒絕不存在的 forget 檔；`proto7-2/modules/mail/aos7_mail_box.py:65` 先鎖 `.handle`，`:69` 才拒絕不存在的序號。`proto7-2/lib/aos7_fs.py:195`–`:199` 會建立鎖的父目錄與鎖檔。
- 重現：

```bash
T=$(mktemp -d /tmp/astra8-newbie-bad-XXXX)
export PYTHONDONTWRITEBYTECODE=1
mkdir "$T/node"
python3 -B proto7-2/modules/compact/aos7-compact \
  forget "$T/node" --file notes/missing.jsonl --from 1 --to 1
echo "compact rc=$?"
python3 -B proto7-2/modules/mail/aos7-mail \
  --root "$T/post" done bob 1 '做完了'
echo "mail rc=$?"
find "$T" -type f -printf '%P\n' | sort
rm -rf "$T"
```

- 預期／推斷實際：兩者退 2，且沒有新增檔；實際留下 `node/compact/lock`、`post/bob/inbox/.handle.lock`，後者連原本不存在的郵局與信箱一起建出來。
- 修法：先做唯讀的存在性與參數預檢，再進鎖內複驗；不要為明確無效的操作建立工作目錄。

### NEW-newbie-6〔B／brain、compact，低〕brain 改用「步」後，compact 沒同步解析，摘要仍使用「回合」

- 契約：`proto7-2/modules/up/ADVANCED.md:103`「信的進度一律叫『步』，『回合』只指心跳叫醒一次」；`proto7-2/modules/compact/spec.md:12` 承諾摘要按信分組並列步驟範圍，但文字仍寫「第 a～b 回合」。
- 程式：`proto7-2/modules/up/aos7_up_brain.py:337` 寫「`第 {step} 步`」；`proto7-2/modules/compact/aos7_compact.py:165` 的 `STEP` 僅匹配「回合」；`:249` 摘要仍輸出「第 … 回合」。
- 重現：

```bash
T=$(mktemp -d /tmp/astra8-newbie-unit-XXXX)
export PYTHONDONTWRITEBYTECODE=1
python3 -B - <<'PY'
import sys
sys.path.insert(0, 'proto7-2/modules/compact')
import aos7_compact as c
ident = 'you-20261009T010000-012345abcdef'
for unit in ('回合', '步'):
    row = {'text': f'- 12:00 第 7 {unit} {ident}：做完大綱\n'}
    print(unit, c.item(row, '.md'))
PY
rm -rf "$T"
```

- 預期／推斷實際：兩種歷史格式都應辨識 `step=7`，新的摘要用「步」。實際「回合」得到 `step=7`，「步」得到 `step=None`，且工作內容殘留「第 7 步 ：」。此結果已由唯讀探針確認。
- 修法：解析同時接受舊「回合」及新「步」，新產生的工作進度摘要統一用「步」，同步 compact 文件。

### NEW-newbie-7〔B／up、mail，中〕up 允許取名 teams，但 ask 與 mail 都拒收這個 node

- 契約：`proto7-2/modules/up/ADVANCED.md:84`「名字只准英數、`.`、`_`、`-`，不能以 `.` 開頭，you 留給人」；`proto7-2/modules/mail/ADVANCED.md:42` 另有「根目錄保留名 `teams`」。
- 程式：`proto7-2/modules/up/aos7_up_cli.py:88` 沒拒絕 `teams`；`proto7-2/modules/up/aos7_up_ask.py:39` 明確拒絕 `teams`，卻回報「找不到 node」；`proto7-2/modules/mail/aos7_mail.py:30` 也拒絕此名字。
- 重現：隔離名稱驗證，避免啟動背景程序。

```bash
T=$(mktemp -d /tmp/astra8-newbie-name-XXXX)
export T PYTHONDONTWRITEBYTECODE=1
mkdir "$T/teams"
python3 -B - <<'PY'
import os, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, 'proto7-2/modules/up')
import aos7_up_cli as cli
import aos7_up_ask as ask

node = str(Path(os.environ['T']) / 'teams')
with patch.object(cli, 'up', return_value=0) as start:
    print('up rc:', cli.main([node]), '進入啟動:', start.called)
print('ask rc:', ask.main(['ask', node, '你好', '--wait', '0']))
PY
rm -rf "$T"
```

- 預期／推斷實際：up 在啟動前就拒絕保留名，且說明換名；實際 up 驗證通過、進入啟動，ask 隨後退 2，對存在的目錄說「找不到 node」。
- 修法：共用 up／ask／mail 的個人名稱限制，在任何安裝副作用前拒絕 `teams`，並修正錯誤理由。

### NEW-newbie-8〔B／compact、routines、skills，低〕普通 --help 仍可能在程式目錄產生 Python 快取

- 契約：各包必要副作用限定於工作資料，例如 `proto7-2/notes/intents/compact.md:7`「寫 `<node>/compact/`」、`proto7-2/notes/intents/skills.md:7` 列 index／pick／mount 的寫入；help 沒有指定 node，卻仍可能寫到安裝目錄。對照 `proto7-2/modules/up/ADVANCED.md:90`「不在程式目錄留 `__pycache__`」的既有處理慣例。
- 程式：`proto7-2/modules/compact/aos7-compact:3`、`proto7-2/modules/routines/aos7-routines:3`、`proto7-2/modules/skills/aos7-skills:9` 都在解析 help 前匯入模組，未先禁止 bytecode；up、mail、wfnode 的薄入口已有 `sys.dont_write_bytecode = True`。
- 重現：以快取前綴把所有寫入導向 T，避免污染 repo。

```bash
T=$(mktemp -d /tmp/astra8-newbie-help-XXXX)
for m in compact routines skills; do
  env -u PYTHONDONTWRITEBYTECODE PYTHONPYCACHEPREFIX="$T/cache" \
    python3 "proto7-2/modules/$m/aos7-$m" --help >/dev/null
done
find "$T/cache" -type f -path '*/proto7-2/*' -name '*.pyc' | sort
rm -rf "$T"
```

- 預期／推斷實際：help 不產生包內快取；實際會列出 `aos7_compact`、`aos7_routines`、`aos7_skills` 等 `.pyc`。沒有快取前綴且程式目錄可寫時，會寫進來源旁的 `__pycache__`。本次 help 探針使用禁止 bytecode 的環境，因此沒有實際觸發寫入。
- 修法：三個薄入口在任何本地模組 import 前設定 `sys.dont_write_bytecode = True`，與其他入口一致。

### NEW-newbie-9〔C／QUICKSTART、up，中〕三個操作指令已簡化，但首次成功仍依賴隱藏模板與每視窗設定

- 契約：`proto7-2/notes/blueprint-firstrun.md:7`「新人只要認得……五個詞、會打三個指令」；`proto7-2/QUICKSTART.md:16` 標「3 個指令」，`:18` 卻要求每個視窗先 cd、設定 alias。
- 程式：`proto7-2/modules/up/aos7_up.py:39`–`:41` 依賴外部 `~/repo/workflows`，不存在就要求執行 Git SSH clone 或設定 `AOS7_WF_HOME`；此必要條件只在 `proto7-2/modules/up/ADVANCED.md:5`–`:6` 說明。
- 重現：

```bash
T=$(mktemp -d /tmp/astra8-newbie-first-XXXX)
export PYTHONDONTWRITEBYTECODE=1
AOS7_WF_HOME="$T/no-template" \
  python3 -B proto7-2/modules/up/aos7-up "$T/bob"
echo "rc=$?"
rg -n 'alias|node|心跳|工作簿|技能|練習用' proto7-2/QUICKSTART.md
rm -rf "$T"
```

- 預期／推斷實際：
  - 目前詞表實際有 **6 詞**：node、心跳、工作簿、信、技能、練習用的 AI。
  - 到第一封回信只用 **2 個 aos 操作**：起、ask；加 status 才是 3 個。
  - 照文件兩視窗逐項算，第一封回信前要做 **6 次 shell 操作**：兩次 cd、兩次 alias、起、ask；不是六個 aos 子命令。
  - 必須知道 repo 根與 `/tmp/aos/bob` 是不同目錄、alias 不跨視窗、第一個視窗要保持開啟。
  - 缺模板時第一步退 1，訊息直接引入 Git SSH、另一個 repo 和環境變數，無法只靠目前新手頁跑通。
- 修法：首次頁明列模板前置條件；先用現成入口相對路徑取代每視窗 alias，把工作簿／技能的詳細概念延到第一封回信之後。

### 看過但沒問題

- **handed 原問題已修**：`aos7_up.py:165`–`:166` 先設交棒，再印三行；對應 commit `76e83b41`。本輪未重跑訊號時序測試。
- **傳輸中被殺永久阻塞 FIFO 的原問題已修**：`aos7_up_brain.py:466`–`:481` 有不確定期限，滿期回 BLOCKED；不自動重送，預留保留給維護者處理是現行明載界線。
- **status 已能呈現不確定狀態**：`aos7_up_status.py:216`–`:225` 加第七行；`:198`–`:205` 將 BLOCKED 與正常回信分開計數。
- **跨信記憶已接入**：`aos7_up_memory.py:51` 保存全文與目錄；brain request 附目錄、指定前件及 STATE；50 行輪替與提示裁切都有實作。
- **compact「JSON 前 40 字無內容」原問題已修**：`aos7_compact.py:180`–`:205` 改讀內容欄位；預設納入 STATE，換檔與 wfnode 共用 `.state.lock`。
- **metrics 多步算重試的原問題已修**：`aos7_metrics.py:125`–`:128` 以信分件、每個 call 作 slot；對應 commit `9b8924a9`。
- **skills 原先亂挑及首步重複挑選已有修補**：本機挑選有 triggers／not_for／平手 none；brain 的 `skill_of()` 快取首步結果。
- **mail 必達提醒仍以信件為權威**：只有收件者已有 events 才發布；提醒失敗不要求重寄；未確認的非 mail 事件會阻止 ack 越過。
- **ask 並非唯讀**：會寄 REQUEST、輪詢時更新人的讀取快照、取得終局信後歸檔；這些是其明定用途。ask 等滿期限退 0 也是藍圖明確豁免。
- **stop 範圍有明載**：停整個房子的心跳與任務、不刪資料；共享房子的整屋清理提示亦已在 ADVANCED 明載，未當新發現。
- **routines 基本接線一致**：add 不再裝任務；空清單 rm 不建檔；ls 不帶 `--run` 不執行工作；wfnode 建立的兩張表與 routines 欄位相符。
- **新手主要狀態詞已對齊**：ask 把終局狀態翻成白話，mail 信頭保留機器狀態；kernel 通知已分清工作「步」與監督「回合」。
- **六個模組的頂層 help 均能正常輸出**；本次以禁止 bytecode 的方式呼叫，未執行寫檔測試。

### 可疑未證

- `aos7_wfnode.py:18`–`:24` 只排除根 inbox，仍掃描 `brain/`、`notes/done/` 的 Markdown；`:199`–`:207` 遇到 `{{` 等文字就報模板殘留。一般回信若討論模板語法，保存後可能讓 status 誤報工作簿壞掉；尚未用完整工作流模板核對。
- `up.json` 的 `compact:false` 只關閉 brain 主動呼叫 compact，但 up 另裝獨立 `compact watch` 任務。是否承諾關閉全部自動整理，文件語意尚不夠明確，未編號。

### 沒看完

- 未執行完整 daemon／SIGKILL／並行鎖恢復測試，也未實跑上述建檔重現；唯讀限制下僅核對程式與不落盤探針。
- skills 的 bank 評測器、wfnode 的全部模板填補／導入裁決細節，以及各包所有測試案例未逐一審完。
- metrics 僅核對 brain 分件與重試接線；kernel 僅看通知與 up 接口，未重審其內部。
- 未做新版真人／模型新手試用，也未驗證真 AI 的實際答覆品質及長任務費用。