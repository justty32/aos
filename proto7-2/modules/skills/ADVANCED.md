← [README](README.md)

# skills 進階

## 指令

- `aos7-skills index <node>`：抄書名和簡介，stdout 一本一行，存 `skills/index.json`。拒收合成 stderr 一行，其他照寫。
- `aos7-skills pick <node> "<題目>"`：挑一本，印 SKILL.md 路徑；挑不到印 `none`。
- `aos7-skills mount <node> <skill> <任務名>`：把一本掛給 aos 空間裡的任務。

## 退出碼

| 碼 | 意思 | index | pick | mount |
|---|---|---|---|---|
| 0 | 做到了 | 全收 | 挑到；llmcall 退 4 仍交付並提醒對帳 | 已掛 |
| 1 | 做不到 | 有拒收，其他照寫 | none、AI 回目錄外名字、帳任務沒在跑、llmcall 做不到 | — |
| 2 | 你給的不對 | 沒有 skills/ 或參數不合 | grant 不是 JSON／缺 holder、不支援的 gateway、`--reserve`／`--deadline` 不是正數、llmcall 參數不合 | 找不到空間根／skill／任務，或 skill 在空間外 |
| 3 | 不確定 | 讀寫故障 | grant 讀不到（讀寫故障）、鎖忙、llmcall 未確定、回條解析失敗 | tasks.json 讀不到或格式不合、讀寫故障 |

全 aos 共用語意見 [blueprint-errors](../../notes/blueprint-errors.md)。錯誤在 stderr 一行：`aos7-skills: 發生什麼。怎麼辦`；3 以「不確定：」開頭，照原樣再跑一次會接續。成功時 stderr 空；llmcall 退 4（已交付、帳沒清）時那句提醒照傳：挑到退 0，挑不到退 1 並把提醒接在同一行。

## 進階：本機怎麼挑（觸發詞）

SKILL.md frontmatter 可多寫兩行（都可選，單行、用「、」或逗號分隔）：

```text
triggers: 跑測試、全套測試、測試
not_for: 寫測試、測試報告
```

- 有 `triggers` 的書只看觸發詞：題目裡出現幾個不同的觸發詞就幾分（中文照字串比；含英數的要整詞，`test` 不算中 `testing`）；`not_for` 任一出現，這本就不算。
- 最高分唯一才挑；**0 分或平手都回 none**，寧可不挑也不挑錯。
- 都沒觸發詞命中時，才看沒寫 `triggers` 的舊書：數題目和簡介（名字的詞多算一次）有幾個詞相同，**≥2 詞**且唯一最高才挑。
- index 的 `index.json` 每本多 `triggers`、`not_for` 兩欄；stdout 目錄行不變。

## 進階：讓 AI 挑

node 沒有 `budget/llm/` 就只用上面的本機挑，不問 AI、不記帳。有該資料夾或給了 `--budget` 時，**仍先本機挑**；只有本機平手，或題目明說「用技能」（`用技能`、`用 skill`、`use skill`）才經 [llmcall](../../packs/llmcall/README.md) 問 AI，同題同目錄同模型是同一個 call，重跑不重問。問 AI 需先開帳並起帳任務，詳見 [budget](../../packs/budget/README.md)。skills 不自己開帳或起帳任務；帳沒在跑時，錯誤訊息最後會附可直接複製的起帳指令，另開終端讓它一直跑著。

接著 README 的 `$S`、`$N`，照抄假 AI 範例（不花錢）：

```sh
P="$(git rev-parse --show-toplevel)/proto7-2"; B="$P/packs/budget/bin/aos7-budget"
mkdir -p "$N/.aos" "$N/budget/llm"
printf '{"round":5,"open":false}\n' > "$N/.aos/round.json"
sed -e 's/"author"/"skills"/' -e 's/: 1000,/: 100000,/' "$P/packs/llmcall/examples/fake/grant.json" > "$N/budget/llm/grant.json"
( cd "$N" && python3 "$B" init budget/llm &&
  { python3 "$B" ledger budget/llm & L=$!
    python3 "$S/aos7-skills" pick "$N" "用技能：看看信箱，把別的 agent 寄來的信辦掉"
    kill $L; wait $L; } )
```

開帳印 `{"ok": true, "why": null}`，pick 印 `aos-inbox/SKILL.md` 路徑。真 AI 用新 node（開過的帳不能改），grant 的 gateway 寫 `llm.litellm`，模型用 `--model`，預設 `chatgpt-gpt-6-sol-high`。同題同目錄同模型重跑不重問，只重印回條。

## 進階：必用表

在 `skills/must.json` 寫 `{"任務類型": "skill 名"}`，或讓值是名字陣列。跑 index 會多寫 `skills/MUST.md`，派工作時抄給接手的人。例如 `{"改完程式": "aos-test"}`。

## 進階：掛給任務

mount 改 node 的 `.aos/tasks.json`，替任務加 `mounts["skill-<名>"]`。執行時在 `mnt/skill-<名>` 讀說明、跑 scripts。node 本身或上層要有 `.aosd/`，skill 也得在這個空間裡；連到外面的 symlink 掛不進去，直接讀 SKILL.md 即可。

## 契約卡

| 項目 | 內容 |
|---|---|
| 接法 | C 工具（人、kernel、AI 跑）；不改核心 |
| 職責 | 驗 SKILL.md 格式、產索引與必用表、挑一本、改 tasks.json 掛載 |
| 前置 | 本機挑：無；AI 挑：已開的 budget 帳與帳任務；mount：node 在 aos 空間裡 |
| 保證 | 只用 name、description、triggers、not_for 挑；本機平手或 0 分回 none；拒收不入索引；本機不碰帳或 llmcall；AI 同題同索引同模型是同 call；mount 持 tasks.json 鎖、讀不到不覆蓋 |
| 不管 | skill 內容、腳本安全；不複製外部 skill；不自動更新 index.json |
| 記錄 | `.pick/log.jsonl` 只留最近 50 行（在 skills/ 下，寫時持 `log.jsonl.lock`、並行不丟行）；欄位是 at、via、call、q、answer、picked、used、rc、elapsed，加 score（本機最高分）與 why（一句原因）；舊讀者忽略多的欄即可；bank 用來算四指標 |
| 請求 | `skills/.pick/<call>.<pid>.json` 用完即刪（同題並行各用各的），不論 llmcall 結果；重跑重建同內容，llmcall 自己保留請求、預留與證據 |

格式來源是 repo 外的 `~/repo/workflows/skills/README.md`。

## 程式與測試

`aos7-skills` 是薄入口；`aos7_skills.py` 負責 index／pick／mount；`library/` 是 aos-test、aos-inbox、wf-lint 三本。測試在 `tests/test_skills.py`：索引、掛載、挑選去重、錯誤一行、唯讀帳檢查、記錄封頂與請求清理、觸發詞規則、何時問 AI、L 17 筆本機題庫。

```sh
systemd-run --user --scope -q -p TasksMax=300 python3 proto7-2/tests/run_all.py modules/skills/tests
```

## bank.py 題庫

固定題庫 27 題：`examples/bank.json` 原 10 題，加 [examples/bank/](examples/bank/README.md) 的 L 長任務 17 筆（正確答案一行一題，none 當對）。候選 11 本（library 3＋workflows 8），需 `~/repo/workflows/skills`，可用 `--workflows` 指定。印分數、四指標（每題 token、並行、每題秒數、重試；L 有 5 題重複，重試會多算 5）與 ai_calls、wrong_book（挑錯本）。退出碼 0＝L ≥16、原 10 題 ≥8、挑錯本 0。

2026-10-09 觸發詞版：`--local` 與開帳（假 AI、真 AI）都是 L 17／17、原 10 題 8／10、挑錯本 0、問 AI 0 次（原 10 題錯的兩題回 none）。改版前本機 L 只對 5／17、挑錯 12。[真 AI 全問](examples/bank-real-2026-10-09.json) 原 10 題為 10／10。

```sh
python3 proto7-2/modules/skills/bank.py --local
python3 proto7-2/modules/skills/bank.py --gateway llm.fake
python3 proto7-2/modules/skills/bank.py --gateway llm.litellm --node /tmp/my-skills-bank --out /tmp/skills-bank.json
```

沒給 `--node` 時，暫存 node 結束即清（含例外），報告的 node 為 null，末行不印 node。要重跑不重問就給 `--node`；該 node 會保留。
