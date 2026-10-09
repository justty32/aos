# skills 包（幫 AI 挑工具說明書）

← [modules](../README.md)

**一句話（ELI5）**：一個資料夾裡有個 `skills/` 抽屜，每本說明書是一個子資料夾；`index` 把每本的書名和一句簡介抄成目錄，`pick` 照你的題目挑一本、告訴你它放哪。

## 要懂的三個詞

| 詞 | 一句白話 |
|---|---|
| skill（說明書） | 一個資料夾，裡面的 `SKILL.md` 開頭寫 `name`（＝資料夾名）和 `description`（什麼時候用），後面是做法。 |
| 目錄（索引行） | `- 名字: 簡介`，一本一行。挑的時候只看這一行。 |
| pick（挑一本） | 給一句題目，回最合適那本 `SKILL.md` 的完整路徑；都不合回 `none`。 |

文中的 **node** 就是「裝著 `skills/` 的那個資料夾」，不用另外學。

## 第一次跑（照抄，約 1 分鐘，不花錢、不連網、不寫進 repo）

先 `cd` 進 repo（任何一層都行，第一行會自己找 repo 根；人在 repo 外就把第一行改成 `S=<repo 路徑>/proto7-2/modules/skills`），整段貼上：

```sh
S="$(git rev-parse --show-toplevel)/proto7-2/modules/skills"
N="$(mktemp -d /tmp/skills-demo.XXXXXX)"; mkdir "$N/skills"
ln -s "$S"/library/* "$N/skills/"                       # 放三本現成的說明書進抽屜
python3 "$S/aos7-skills" index "$N"                       # ① 抄目錄
python3 "$S/aos7-skills" pick "$N" "看看信箱，把別的 agent 寄來的信辦掉"   # ② 挑一本
```

看到這些就跑通了：

```text
- aos-inbox: Read and handle the agent mailbox …
- aos-test: Run the proto7-2 test suite …
- wf-lint: Check the wf/ documentation tree …
aos7-skills: 本機挑選（關鍵字比對，沒問 AI、不記帳）；要讓 AI 挑，見 README「進階：讓 AI 挑」
/tmp/skills-demo.XXXXXX/skills/aos-inbox/SKILL.md
```

第三、四行之間那句是提示不是錯：沒設定 AI 時，`pick` 用關鍵字比對來挑。資料都在 `$N`，不要了 `rm -rf "$N"`。

**第一次跑到這裡就夠了。** 下面都是進階，用到再看。

## 指令（只有三個，`--help` 有一樣的說明）

- `aos7-skills index <node>`：抄目錄，stdout 一本一行，順便存 `skills/index.json`。格式不合的那本不收，stderr 說原因。
- `aos7-skills pick <node> "<題目>"`：挑一本，印 `SKILL.md` 路徑；挑不到印 `none`。
- `aos7-skills mount <node> <skill> <任務名>`：把一本借給 aos 的某個任務用（見下面「進階：掛給任務」）。

| 退出碼 | index | pick | mount |
|---|---|---|---|
| 0 | 全收 | 挑到，印路徑 | 已掛 |
| 1 | 有不收的（其餘照寫） | 回 none（或 AI 回了目錄外的名字） | — |
| 2 | 沒有 skills/ | 設定不對（AI 模式：帳的設定讀不到） | 找不到空間根／skill／任務，或 skill 在空間外 |
| 3 | — | AI 模式出事：帳任務沒在跑，或 llmcall 沒送到 | tasks.json 讀不到，沒動它 |

## 進階：讓 AI 挑

`pick` 看 node 裡有沒有 `budget/llm/` 資料夾決定怎麼挑：**沒有**就本機關鍵字挑（上面第一次跑）；**有**（或你給了 `--budget`）就把「題目＋目錄」經 [llmcall](../../packs/llmcall/README.md) 問 AI。問 AI 會用掉 token，所以要先「開帳」：`budget/llm/grant.json` 寫這個 node 最多能用多少 token（下例 100000 個），再在背景起一個「帳任務」（ledger）負責扣帳。帳本身怎麼運作見 [budget](../../packs/budget/README.md)。

接著上面的 `$S`、`$N`，用假 AI（`llm.fake`，也是照關鍵字猜，不花錢）走一次記帳流程：

```sh
P="$(git rev-parse --show-toplevel)/proto7-2"; B="$P/packs/budget/bin/aos7-budget"
mkdir -p "$N/.aos" "$N/budget/llm"
printf '{"round":5,"open":false}\n' > "$N/.aos/round.json"   # 帳要一個已結束的回合
sed -e 's/"author"/"skills"/' -e 's/: 1000,/: 100000,/' "$P/packs/llmcall/examples/fake/grant.json" > "$N/budget/llm/grant.json"
( cd "$N" && python3 "$B" init budget/llm &&
  { python3 "$B" ledger budget/llm & L=$!
    python3 "$S/aos7-skills" pick "$N" "看看信箱，把別的 agent 寄來的信辦掉"
    kill $L; } )
```

印 `{"ok": true, "why": null}`（開帳成功）和同一個 `aos-inbox/SKILL.md` 路徑就對了。換真 AI：另開一個新 node（開過的帳不能改），grant 的 `gateway` 寫 `llm.litellm`，模型用 `--model`（預設 `chatgpt-gpt-6-sol-high`）；或直接跑題庫 `bank.py --gateway llm.litellm`（見下）。同題同目錄同模型再問一次不會重問，只重印上次的結果。

## 進階：必用表

在 `skills/` 放 `must.json`（`{"任務類型": "skill 名"}`），`index` 會多寫一張 `skills/MUST.md`（任務類型 → 必用 skill），派工作時抄給接手的人，免得「有工具沒人用」。例：`printf '{"任務類型：改完程式":"aos-test"}' > "$N/skills/must.json"`，再跑一次 `index`。

## 進階：掛給任務

`mount` 在 node 的 `.aos/tasks.json` 那個任務加 `mounts["skill-<名>"]`，任務執行時就看得到 `mnt/skill-<名>`、能跑它附的 `scripts/`。只在 aos 空間裡有用：node 的上層要有 `.aosd/`（aos 常駐程式管的那層資料夾，叫空間根），skill 資料夾也得在那層裡面；symlink 到外面的掛不進去，直接讀 SKILL.md 即可。

## 契約卡

| 項目 | 內容 |
|---|---|
| 接法 | C 工具（人、kernel、AI 跑）；不改核心 |
| 職責 | 驗 SKILL.md 格式、產索引行與必用表、挑一本（本機關鍵字或經 llmcall 問 AI）、改 tasks.json 掛載 |
| 前置 | pick 本機模式：無；pick AI 模式：node 有開好的 budget 帳與帳任務（見 [llmcall](../../packs/llmcall/README.md)）；mount：node 在 aos 空間裡 |
| 保證 | 索引只有 name＋description；拒收的不進索引；本機模式不碰帳與 llmcall；AI 模式同題同索引同模型＝同一個 call，重跑只重印回條；mount 拿 tasks.json 的鎖、讀不到不覆蓋 |
| 不管 | skill 內容對不對、腳本安不安全；不複製外部 skill 進 repo（用 symlink）；不自動更新 index.json |
| 記錄 | 每次 pick 追加 `skills/.pick/log.jsonl`（via＝local／llmcall、call、題目、答案、used、退出碼、秒數）：效率四指標（每題 token、並行、時間、重試）由它算 |

格式來源：`~/repo/workflows/skills/README.md`（本 repo 外），跟 Claude Code／workflows 的 skill 同格式。

## 程式與測試

- `aos7-skills`（入口）、`aos7_skills.py`（index／pick／mount）、`library/`（aos 自製三本：aos-test、aos-inbox、wf-lint）。
- `bank.py`＋`examples/bank.json`：選用題庫 10 題（11 本候選：library 3＋workflows 8），印分數與四指標。真 AI：`python3 proto7-2/modules/skills/bank.py --gateway llm.litellm`（每題 1 次 call）。
- 2026-10-09 實跑（[bank-real-2026-10-09.json](examples/bank-real-2026-10-09.json)）：`chatgpt-gpt-6-sol-high` 經 llmcall 選對 **10／10**；每題 token 約 2576、並行 1、每題 3.2 秒、重試 0；同 node 重跑 0 次新呼叫、每題 0.08 秒（重印回條）。關鍵字（假 AI／本機模式同一套）8／10。
- 測試：`python3 proto7-2/tests/run_all.py modules/skills/tests`。
