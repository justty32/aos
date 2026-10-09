← [author 包](../README.md)｜[工具卡](../toolcards/aos-tool.json)

把學徒交的新增工具或模組驗過三關，再只發到 apprentice 分支。

- 工具卡：一題型的規格，寫清楚能寫哪個資料夾、必有哪些檔與上限。
- 需求單：BRIEF 格式的 JSON，寫任務、範圍、必用工具與固定 N 條驗收。
- 候選：學徒交的一個 JSON，包含新增檔案、索引一列與 REPORT。
- 三關：依序做靜態檢查、跑測試與答案檢查、審查，失敗就停。
- apprentice 分支：過三關才寫的 git 分支，merge 永遠是人。

## 第一次跑（新手照抄，約 5 分鐘）

在 repo 根目錄照抄；離線示範選 rules，shared clone 放在臨時目錄。練習題的答案已合進 main，所以要以合進來之前的版本當基準。

```sh
A4_C=proto7-2/packs/author/checkers/aos_three_gates.py
A4_E=proto7-2/packs/author/examples/aos-tool-usage
A4_REF=$(if git cat-file -e HEAD:proto7-2/packs/usage 2>/dev/null; then git rev-parse "$(git log --diff-filter=A --format=%H -- proto7-2/packs/usage/README.md | tail -n 1)^"; else git rev-parse HEAD; fi)
python3 "$A4_C" brief "$A4_E/request.json"
echo "brief exit=$?"
python3 "$A4_C" check "$A4_E/request.json" "$A4_E/bad-link.json" --reviewer rules --ref "$A4_REF"
echo "bad-link exit=$?"
python3 "$A4_C" check "$A4_E/request.json" "$A4_E/valid.json" --reviewer rules --ref "$A4_REF"
echo "valid exit=$?"
A4_TMP=$(mktemp -d)
git clone -q --shared --no-checkout . "$A4_TMP/repo"
A4_RESULT=$(python3 "$A4_C" publish "$A4_E/request.json" "$A4_E/valid.json" --reviewer rules --repo "$A4_TMP/repo" --ref "$A4_REF")
echo "publish exit=$?"
printf '%s\n' "$A4_RESULT"
A4_BRANCH=$(printf '%s\n' "$A4_RESULT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["branch"])')
git -C "$A4_TMP/repo" log --stat -1 "$A4_BRANCH"
echo "log exit=$?"
```

本次已照抄實跑（10-09，採答案合入前的基準，含 scope 與白名單沙箱）：brief 退出 0；bad-link 退出 2，failed_gate=1 且 rule=lint；valid 退出 0，三關全過；publish 退出 0，dup=false；log 退出 0。job 是 `usage1_9ebf9840`，分支是 `apprentice/usage1_9ebf9840`；log 列出 INDEX.md 加一列與四個新增檔案。候選 bytes 不變，job 就不變。

## 指令

| 指令 | 用法 |
|---|---|
| brief | `brief <request.json>`，印 BRIEF markdown |
| check | `check <request.json> <candidate.json>`，印三關 JSON |
| publish | `publish <request.json> <candidate.json>`，重跑三關再新建分支 |

check 與 publish 可加 `--reviewer rules|astra|file:PATH`、`--no-scope`、`--repo R`、`--ref REF`。預設審查器是 astra、ref 是 HEAD、repo 是檢查器所在的 git 根目錄；原型前綴從檢查器位置推算。預設測試在 user scope 跑，TasksMax=300、RuntimeMaxSec=900；已在 scope 的測試用 `--no-scope`。

| 退出碼 | 意義 |
|---|---|
| 0 | 全過或相同樹的重複發布（dup=true） |
| 2 | 輸入壞或某關不過 |
| 3 | 同名分支已有不同樹或目標是 symbolic ref |
| 4 | archive、必需工具（wf-lint、bwrap、codex）或執行狀態不明；測試或審查逾時 |

## 三關

| 關 | 檢查 |
|---|---|
| ① | 嚴格 JSON、欄位、範圍、佈局、測試、大小、README、lint 與索引連結；一起回報 |
| ② | run_all.py 跑自帶測試，再由需求單指定的 check_answer.py 獨立驗答案與唯讀；兩者都在 bwrap 沙箱裡跑（白名單掛載、空環境與 HOME、斷網，只有物化 tmp 可寫；需求單與 fixture 使用 tmp 裡的複本），外面再包 systemd scope |
| ③ | rules 掃所有非 .md／.json 候選檔，逐行比卡上規則；file:PATH 讀預錄審查，與 astra 一樣要求完整嚴格 JSON verdict；astra 真呼叫 codex exec |

題目在 `../examples/aos-tool-usage/` 與 `../examples/aos-module-diag/`；工具卡另有 [aos-module](../toolcards/aos-module.json)。每次驗證先從指定 ref 解出臨時原型，再加入候選；結束清掉臨時目錄。lint 使用檢查器所在 repo 工作樹的 wf-lint.sh，因此無 checkout 的發布 clone 也能驗證。

## 界線

學徒只發到 apprentice/，不寫 lib/ 與別的包；merge 是人。publish 從固定 ref 與候選原文，用臨時 index 新建樹與 commit，不動 HEAD、原 index、工作樹或任何其他分支；同名分支只比樹，不覆蓋。第一關只收 root 直下 tests/test_*.py；第二關要求 runner 實際跑過至少一項測試，所以拿掉第一關時 bad-notest 仍被第二關 rule=test 擋住。

astra 審查要真呼叫，離線用 rules；此處實跑結果是 rules，不代表 astra 已接受。這套檢查按工具卡與答案驗證，適用於已授權的學徒原型。
