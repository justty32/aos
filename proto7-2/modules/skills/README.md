# skills 包（給 node 上的 AI 挑工具說明書）

← [modules](../README.md)｜呼叫閘道：[llmcall](../../packs/llmcall/README.md)｜格式來源：`~/repo/workflows/skills/README.md`（本 repo 外）

**一句話（ELI5）**：node 有一個 `skills/` 抽屜，每個說明書是一個資料夾；`index` 把每本的書名和一句簡介抄成目錄，`pick` 把「題目＋目錄」交給 AI 挑一本，回那本的路徑；`mount` 把那本（連附的腳本）借給某個任務用。

## 五個概念（只要記這些）

| 概念 | 一句白話 |
|---|---|
| skill | 一個資料夾，裡面 `SKILL.md` 開頭寫 `name`（＝資料夾名）和 `description`（什麼時候用），後面是做法；可附 `scripts/`。跟 Claude Code／workflows 的 skill 同格式。 |
| 索引行 | `- 名字: 簡介`，一本一行；AI 只看這一行決定要不要翻開，所以**索引只有 name＋description**。 |
| pick | 題目＋索引行交給 AI（經 llmcall、有帳），AI 回一個名字，工具回那本 `SKILL.md` 的完整路徑。同題同目錄再問一次不會重問。 |
| 掛載 | 把整本 skill 資料夾掛到某個任務的 `mnt/skill-<名>`，任務就能跑它的 `scripts/`。 |
| 必用表 | 可選的 `skills/must.json`（`{"任務類型": "skill 名"}`），`index` 照它產 `MUST.md` 表，派單時抄進交接書，免得「有工具沒人用」。 |

## 第一次跑（照抄，約 1 分鐘）

從 repo 根目錄（看得到 `proto7-2/` 的那層）整段貼上。pick 一律經 [llmcall](../../packs/llmcall/README.md) 記帳，所以要先開一本帳（`budget/llm`，grant 從 llmcall 範例抄、把使用者改成 skills、額度調大）並在背景起帳任務（ledger）。用假 AI（`llm.fake`：照關鍵字猜），不花錢、不連網；資料留在暫存資料夾。

```sh
P="$(pwd)/proto7-2"; S="$P/modules/skills/aos7-skills"
N="$(mktemp -d /tmp/aos7-skills-demo.XXXXXX)"
mkdir -p "$N/skills" "$N/.aos" "$N/budget/llm"
ln -s "$P"/modules/skills/library/* "$N/skills/"            # 三本 aos 自製 skill
printf '{"任務類型：改完程式":"aos-test"}' > "$N/skills/must.json"
python3 "$S" index "$N"                                      # ① 印索引行，寫 index.json、MUST.md
printf '{"round":5,"open":false}\n' > "$N/.aos/round.json"   # 帳要一個已關的回合
sed -e 's/"author"/"skills"/' -e 's/: 1000,/: 100000,/' "$P/packs/llmcall/examples/fake/grant.json" > "$N/budget/llm/grant.json"
( cd "$N" && python3 "$P/packs/budget/bin/aos7-budget" init budget/llm &&
  { python3 "$P/packs/budget/bin/aos7-budget" ledger budget/llm & L=$!
    python3 "$S" pick "$N" "看看信箱，把別的 agent 寄來的信辦掉"   # ② 回 aos-inbox 的 SKILL.md 路徑
    kill $L; } )
cat "$N/skills/MUST.md"; echo "資料在 $N"                # ③ 必用表
```

看到三行 `- aos-…: …`、一行 `…/aos-inbox/SKILL.md`、一張「任務類型 → 必用 skill」小表，就跑通了（中間的 `{"ok": true, "why": null}` 是開帳成功）。

## 指令（對外只有三個）

在任何目錄都可以跑，`<node>` 是 node 資料夾：

- `aos7-skills index <node>`：讀 `<node>/skills/*/SKILL.md`，stdout 印索引行，寫 `skills/index.json`（有 must.json 再寫 `MUST.md`）。格式不合的（沒有 `---` 開頭、缺 name 或 description、name 跟資料夾名不同）**拒收**，stderr 說原因。
- `aos7-skills pick <node> "<題目>" [--budget budget/llm] [--model chatgpt-gpt-6-sol-high]`：要 node 有帳（`budget/llm`）而且帳任務在跑；帳的 grant 是 `llm.fake` 就用假 AI，`llm.litellm` 就問真 AI。stdout 印 `SKILL.md` 完整路徑。
- `aos7-skills mount <node> <skill> <任務名>`：在 `.aos/tasks.json` 那個任務加 `mounts["skill-<名>"]`。skill 資料夾必須在空間根（有 `.aosd/` 的那層）裡面；symlink 到外面（例如 ~/repo/workflows）的掛不進去，直接讀 SKILL.md 即可。

| 退出碼 | index | pick | mount |
|---|---|---|---|
| 0 | 全收 | 選到，印路徑 | 已掛 |
| 1 | 有拒收（其餘照寫） | AI 回 none 或索引外的名字 | — |
| 2 | 沒有 skills/ | 設定不對：grant 讀不到或 gateway 不認得 | 找不到空間根／skill／任務，或 skill 在空間外 |
| 3 | — | 執行時出事：帳任務沒在跑，或 llmcall 沒交付（它的訊息照轉） | tasks.json 讀不到，沒動它 |

## 契約卡

| 項目 | 內容 |
|---|---|
| 接法 | C 工具（人、kernel、AI 跑）；不改核心 |
| 職責 | 驗 SKILL.md 格式、產索引行與必用表、經 llmcall 挑一本、改 tasks.json 掛載 |
| 前置 | pick：node 有開好的 budget 帳與帳任務（見 [llmcall](../../packs/llmcall/README.md)）；mount：node 在 aos 空間裡 |
| 保證 | 索引只有 name＋description；拒收的不進索引；同題同索引同模型＝同一個 call，重跑只重印回條；mount 拿 tasks.json 的鎖、讀不到不覆蓋 |
| 不管 | skill 內容對不對、腳本安不安全；不複製外部 skill 進 repo（用 symlink）；不自動更新 index.json |
| 記錄 | 每次 pick 追加 `skills/.pick/log.jsonl`（call、題目、答案、used、退出碼、秒數）：效率四指標（每題 token、並行、時間、重試）由它算 |

## 程式與測試

- `aos7-skills`（入口）、`aos7_skills.py`（index／pick／mount）、`library/`（aos 自製三本：aos-test、aos-inbox、wf-lint）。
- `bank.py`＋`examples/bank.json`：選用題庫 10 題（11 本候選：library 3＋workflows 8），印分數與四指標。真 AI：`python3 proto7-2/modules/skills/bank.py --gateway llm.litellm`（每題 1 次 call）。
- 2026-10-09 實跑（[bank-real-2026-10-09.json](examples/bank-real-2026-10-09.json)）：`chatgpt-gpt-6-sol-high` 經 llmcall 選對 **10／10**；每題 token 約 2576、並行 1、每題 3.2 秒、重試 0；同 node 重跑 0 次新呼叫、每題 0.08 秒（重印回條）。假 AI（關鍵字猜）8／10。
- 測試：`python3 proto7-2/tests/run_all.py modules/skills/tests`。
