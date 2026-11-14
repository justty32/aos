# 蒐集 01i（ok-skyrim 隊 sky-astra-d 原文）：skyrim 與 aos 兩邊 wf 骨架的差異——skyrim 有 aos 沒有、兩邊寫法不同、aos 獨有

← [README](README.md)｜[02 借鑑清單](02-借鑑清單.md)｜隊員原文照收，隊長只加這兩行；它只陳述事實、不做借鑑判斷。檔內提到的 `out/01?-*.md` 是隊員工作區裡的原檔名。

# wf 差異：保留期與 lint、待辦計數、跨 repo 驗證、遊戲工作流、文件分層與模板版本。
A：skyrim 現有而 aos/wf 未找到的工具或專用流程，逐項列出落實與使用證據。
B：兩邊都有的進度、使用者頁、教訓、資料工具、規劃與派線，寫法不同。
C：aos 獨立工作流與索引工具的名稱、路徑。
以下只盤點檔案與程式，不判斷採用與否；設定存在不等於本輪執行通過。

## 閱讀範圍與路徑記法

本文 `S/`＝`/home/lorkhan/repo/moddings/skyrim/`，`A/`＝`/home/lorkhan/repo/aos/`，`T/`＝`/home/lorkhan/repo/workflows/`。每個縮寫路徑皆接在此絕對根後；節名或函式名定位同一檔內容。

A、B 保留六格，C 一行一項。兩邊 `AGENTS.md` 尾戳分別為 v0.6+368468a、v0.5；不能只憑戳判斷內容，aos 後來已刪 wf-lint（`A/wf/session_logs/2026-11/2026-11-13.md:85`）。

「沒有」限指定 wf 範圍；grep／glob 包含 hidden、停用 gitignore，略過二進位檔。本任務 brief 的命中不算機制實例。

## A. skyrim 有、aos 沒有

### A1. wf-lint 的 project-local hook 與保留期檢查器

1. **是什麼**：skyrim 保留可選 wf-lint 與保留期外掛；aos 已刪 wf-lint。
2. **出處**：`S/wf/tools/wf-lint.sh` 的 `run_local_hook()` 與結束碼段；`S/wf/tools/wf-lint-local.sh:2`；`S/wf/tools/wf-lint-retention.sh:2`；`S/wf/STRUCTURE.md`「archive 規則」local 段；`A/wf/session_logs/2026-11/2026-11-13.md:85`。
3. **怎麼運作**：掃描根為 `<dir>` 時，找 `<dir>/wf/tools/wf-lint-local.sh`，執行 `bash <hook> <dir> <strict>`；`--self` 不跑。母 repo hook 只轉呼叫 retention。retention 用 git tracked 清單找 `archive/`、`done/`、`superseded/`、`history/`，豁免 `l10n/mods/`、`plugins/`；場次同時超過 30 天且不在最近 5 場才報過期。檢查 hub 的 2048／4096 bytes 與 2026-11-05 起場次 STATE 的 8192 bytes。這是程式實作的範圍，沒有自動刪檔。
4. **為什麼這樣定**：`S/wf/workflows/decisions.md`「記錄」2026-11-05 原話：「封存的其實也可以刪掉了。該來把整個repo做瘦身」。`T/CHANGELOG.md`「未發布」記 local hook 是讓專案不必修改 kernel 檔；來源為 skyrim 想接自家檢查。
5. **靠什麼落實**：retention 印 `ARCHIVE-DIR`／`STALE-SESSION`／`HUB-OVERSIZE`，有 finding 退 1；外層只有 `--strict` 將 local finding 當失敗。一般 BROKEN 本來就退 1。`S/wf/tools/test_wf_lint_local.py` 的 `test_failing_hook_warns_plain_and_fails_strict` 測這個區別。`S/.github/workflows/docs.yml` 明寫「wf-lint 不在 CI」。另有呼叫位置邊界：`S/wf/workflows/testing.md` 示例傳 `--strict wf`，依函式實作會找 `wf/wf/tools/wf-lint-local.sh`，不是母 repo 那支；要觸發母 repo hook，掃描根必須是母 repo。本文只靜態對照，未實跑。
6. **實際有沒有在用**：入口、hook、retention、測試都在；`S/wf/workflows/tidy/reports/2026-11-05/README.md` 有刪封存與各 repo lint 數字，但不足以證明每次都跑 retention。aos 搜 `**/wf-lint*.sh` 無檔；搜 `ARCHIVE-DIR|STALE-SESSION|HUB-OVERSIZE` 無文字命中。aos 日誌有使用者「wf-lint整支刪掉吧。」與 commit `70e6d4fd8`，故不把歷史 lint 回報當現役工具。

### A2. WAIT_USER 計數核對器

1. **是什麼**：把 hub 寫的 open 數與子檔標題實數對帳；兩邊都有 WAIT_USER，只有本次 skyrim 範圍讀到這支專用核對器。
2. **出處**：`S/WAIT_USER.md` 計數表；`S/wait-user/README.md`「規則」；`S/tools/waituser_count.py` 檔頭、`evaluate()`、`main()`。
3. **怎麼運作**：從 hub 表找子檔，子檔以容器標題下一層為條目；封存標題及後續不計。自指 hub 的錨點也能計。原句：「hub 本身不是真相來源。」輸出每類 `hub=N actual=M OK|MISMATCH|ERROR`，也可用 `--json`。
4. **為什麼這樣定**：核對器檔頭指明判準出自 `wait-user/README.md`，避免自行發明規則；`--fix` 未做，理由是另一條 wu-stale 線在改子檔，這支唯讀避讓。
5. **靠什麼落實**：`--check` 數字不同退 1；缺檔／解析錯退 2；不加 `--check`，單純數字不同不使指令失敗。`S/wait-user/README.md` 要增減後核對；`S/.github/workflows/docs.yml` 跑 `tools/test_*.py`，並沒有直接執行現有 hub 的計數命令。`S/wf/workflows/common/code-map/CODE_MAP.md`「母 repo 本機工具」列出 `test_waituser_count.py` 的測試範圍。
6. **實際有沒有在用**：`S/WAIT_USER.md` 有四列 8／12／18／8，明列核對命令；實讀 `S/wait-user/home-setup.md` 可見 open 標題及下層連結。未重算四類數字。aos 搜 `waituser_count` 與 glob `*waituser*` 都無命中；`A/wf/WAIT_USER.md`「待使用者項」另寫 11-13 晚起新題寄使用者專區，不再加入舊分類檔。

### A3. 母 repo 跨 submodule 的文件、索引與 git gate

1. **是什麼**：skyrim 母 repo 有跨 repo 連結、索引覆蓋、pin 與 staged 大小／垃圾 gate；僅確認 aos/wf 沒這組工具，不指 aos 沒 CI。
2. **出處**：`S/tools/check_markdown_links.py` 檔頭、`_markdown_under()`、`main()`；`S/tools/check_code_map_coverage.py` 檔頭、`collect()`；`S/tools/submodule_pins/guard.py` 的 `check_updates()`；`S/tools/hooks/pre-commit`、`S/tools/hooks/pre-push`；`S/.github/workflows/docs.yml`。
3. **怎麼運作**：連結器掃 tracked 加未 ignore 的 untracked Markdown，進入非 `projects/` 的已初始化工作區 submodule；CI 可跳未初始化 gitlink 目標與 symlink，輸出跳過數。索引器逐個所屬 repo 列 tracked `.py/.sh`，用檔名是否出現在指定索引頁判覆蓋；缺口清單 baseline 暫時放行，baseline 指到已不存在腳本則報 STALE。pin gate 只看這次 push 改動的 gitlink，remote 不可達時嘗試 fetch；若仍不可達，通常拒絕母 repo push。
4. **為什麼這樣定**：連結器檔頭記 2026-10-23 新寫四份索引卻未被掃、仍得綠燈；`_markdown_under()` 記拆 submodule 後有 87 條壞鏈未受檢。索引器檔頭說：「A tool nobody indexes is a tool the next agent rewrites from scratch.」pin guard 註解記不識別 `on-demand` 會在 Git 遞迴推送之前擋住本可解決問題的那次 push。
5. **靠什麼落實**：連結壞或索引新增缺口／stale baseline 退 1。pin gate 對未初始化 submodule、本機缺 commit 只是警告放行；`push.recurseSubmodules=on-demand|only` 也放行給 Git 處理，不是全面 fail-closed。pre-commit 呼叫 `S/agentctl/tools/repo_hooks/precommit_gate.py`，按 `policies.json#/policies/mother` 擋超過 1048576 bytes 的 staged blob 與 shared 垃圾 patterns，違規退 1、設定錯退 2；private gate 缺席則提示放行。CI 跑兩組 unittest、連結器；只有 `agentctl/tools/README.md` 存在才跑 code-map coverage。
6. **實際有沒有在用**：`S/.git/config` 的 `[core] hooksPath = tools/hooks`，`[push] recurseSubmodules = on-demand`；hook 與 private gate 本體都讀得到，證明本地有接線，但本輪未 commit／push／fetch。`.github/workflows/` 只有 `docs.yml`，可證 CI 定義存在，未查遠端執行結果。`S/tools/code_map_coverage_baseline.txt` 有實際非註解路徑，與 CODE_MAP「目前是空的」不符；本文以資料檔為準。aos/wf grep `check_submodule_pins|check_code_map_coverage` 無命中，glob `*submodule*`、`*coverage*` 亦無檔；不能據此推論 aos 的其他目錄沒有同類能力。

### A4. Skyrim 專用的取得、部署與實機驗收鏈

1. **是什麼**：`S/wf/WORKFLOWS.md`「Skyrim 專屬工作流」串接取得、部署與驗收；以下只記入口契約，未驗下游程式。
2. **出處**：`S/wf/workflows/mod-discovery/README.md`「分工」；`nexus-intake/README.md`「版本閘門」；`localization/README.md`「建層」；`profile-change/README.md`「施工窗」；`runtime-qa/README.md`「基線與證據窗」；以上短路徑均接 `S/wf/workflows/`。其餘入口是同層 `movesets/README.md`、`crash-triage.md`、`follower-combat-compat.md`、`follower-combat-config.md`、`mod-update.md`、`safe-apply.md`、`modpack-planning/README.md`。
3. **怎麼運作**：discovery 只查使用者給的 URL、不下載；nexus-intake 依查證→版本閘門→下載→入庫→安裝→稽核，中文層靠二進位拓撲而非 API 版號認同版。profile-change 指定 `main → feat/* → release/* → main`，磁碟只有一個 profile。runtime-qa 要固定條數、fresh log window、逐項證據與 teardown。movesets 先模擬再實套，比對其他格零變動、cross-mod 零。crash-triage 分凍結／崩潰再按 DLL／資料／素材歸因；mod-update 逐項勾 SEQ、中文層、facegen、LOD、下游 master、動畫。safe-apply 原句：「操作當下重讀現行狀態，不採信計畫檔裡的舊快照。」
4. **為什麼這樣定**：`nexus-intake/README.md` 開頭說六段「每一段都有一個會靜默失敗的地方」；`localization/README.md` 寫覆蓋層放本體下面會完全失效卻無徵兆；`runtime-qa/README.md` 記鎖路徑不存在會讓釋放檢查恆真。`safe-apply.md`「寫前與備份」說整檔 hash 會被 MO2／別線回寫而誤擋，因此 soft baseline 搭配 hard anchor。
5. **靠什麼落實**：入口點名 `housecarl_nexus_*`、`instance/tools/layer_apply.py`、`mo2_cycle_verify.sh`、`skse_smoke.sh`、movesets 的 `winner_diff.py`／`ktsim.py`。profile-change 說 layer_apply 先驗鎖、CRLF、備份，新增 missing master 就還原；safe-apply 要非 tmpfs 備份與寫後驗證。下游程式未讀，僅記工作流要求。
6. **實際有沒有在用**：`S/wf/user/2026-11-05-agent-bridge-screenshot.md` 有 0.10.0、20 次連拍與未驗邊界；`S/wf/workflows/follower-combat-config.md`「r3」有 2026-11-02 全員預設的授權與版本契約。兩者是現存文件證據，未查全部原始 runtime log。aos/wf grep `mod-discovery|nexus-intake|localization/README|profile-change|runtime-qa|movesets/README|crash-triage|follower-combat-compat|mod-update|safe-apply` 無命中；`A/wf/WORKFLOWS.md` 亦無此遊戲鏈。

## B. 兩邊都有但寫法不同

### B1. 文件保留、活狀態與使用者頁

1. **是什麼**：共有進度、待辦與使用者頁；落點與保留方式不同。
2. **出處**：`S/wf/STRUCTURE.md`／`A/wf/STRUCTURE.md`「archive 規則」；`S/SESSION-LOG.md`「現役工作」；`A/wf/INDEX.md`「頂層文件」；`S/wf/user/README.md` 開頭；`A/wf/workflows/decide-page.md`「題目資料檔」；`A/wf/WAIT_USER.md`「待使用者項」。
3. **怎麼運作**：skyrim 原句「本地覆寫（2026-11-05 起，取代上段）：過時即刪。」成品與被 hash／manifest 釘住的檔除外；aos 要搬到所屬工作流的 archive/，原句「不刪」。skyrim 根 SESSION 只管母 repo，另導到 agentctl；aos 進度與 HANDOFF 在 wf。skyrim 集中 `wf/user/YYYY-MM-DD-主題.md`，摘要連原報告，頁用畢 30 天刪、仍被 open 引用則留。aos decide-page 的資料跟出題線走、不設集中批次夾，頁預設產到桌面；digest 另管白話讀物。
4. **為什麼這樣定**：skyrim 的瘦身裁示見 A1；`S/wf/user/README.md` 明確分開使用者濃縮結果與 agent 內部 REPORT。`A/wf/workflows/decide-page.md`「跟看板怎麼分」寫「看板『待你裁』是唯一的收件匣」，不另起第三套；使用者沒點開的題仍待定。
5. **靠什麼落實**：skyrim 保留期檢查範圍見 A1，不能把文件列的使用者頁 30 天規則也說成 retention 已自動檢查；`S/.gitignore` 確有 `wf/user/**/*.html`。aos decide-page 文件要求 `check/build/parse/apply/land`，程式本輪未展開，僅確認文件流程；新題寄專區依 `A/wf/WAIT_USER.md`，本輪未操作活樹。
6. **實際有沒有在用**：skyrim `wf/user/README.md` 有 10-10 至 11-05 多頁索引，11-05 截圖頁已實讀；aos `wf/workflows/digest/README.md` 有兩批入口，`wf/WAIT_USER.md` 留四類舊帳。aos 搜 `wf/user/` 只命中本次 brief，不代表沒有給人看的頁，因此本項放 B，不放 A。

### B2. 教訓與回覆規矩的分層

1. **是什麼**：skyrim 集中 lessons 與 reply-style；aos 歸回各工作流，不是沒有教訓。
2. **出處**：`S/wf/lessons/README.md`「來源／新增規則」；`S/wf/lessons/wf-kernel.md`；`S/wf/workflows/common/reply-style.md`「核心規則」；`A/wf/workflows/common/gotchas.md`「哪類坑記哪裡」；`A/wf/workflows/common/user.md`；`A/wf/workflows/dispatch/aos-teams.md`「交接」。
3. **怎麼運作**：skyrim 每個 `##` 是固定 slug，保留日期、事實、Why、How to apply、使用者原話；「lessons 是知識庫不是流程文件」，超 16 KB 才按子主題拆，不用 `-N`。reply-style 管聊天、不管 commit／程式註解等內容。aos 共通坑入口導向各分檔，專屬坑放各自工作流；user 也拆成 01／02／03。
4. **為什麼這樣定**：`S/wf/lessons/README.md` 說 slug 被記憶與其他文件引用，故不改；2026-10-26 要保留現行結論、去掉流水帳。aos 的歸層理由見 `A/AGENTS.md`「分層思想」：「durable 知識歸到它所屬的那一層／那個工作流」。
5. **靠什麼落實**：本次讀到的都是文件約定；未看到強制檢查 slug、16 KB 或回覆風格的工具。aos `AGENTS.md` 明禁寫 Claude 自動記憶；skyrim lessons README 卻說記憶原檔仍在、指標尚未改、兩邊並存且記憶較新，兩者不能混讀成同一現況。
6. **實際有沒有在用**：已實讀 skyrim `wf-kernel.md` 的升級與本地覆寫教訓；aos gotchas 入口有三份分檔與派工 lessons 指標。aos 搜 `lessons 是知識庫|reply-style.md` 無現役命中。skyrim 記憶目錄未讀，較新僅是 README 自述。

### B3. 通用資料工具、CODE_MAP 與檢查入口

1. **是什麼**：兩邊都有 `wf-table/1`、tabledb 與拆檔修連結；skyrim 工具拆成更多模組且留整組測試，aos 加了生成式 JSON 索引與 code map。
2. **出處**：兩邊 `wf/tools/tabledb.py:2`；`S/wf/tools/` 下列檔頭；`S/wf/workflows/common/code-map/CODE_MAP.md`「母 repo 本機工具」；`A/wf/tools/index_gen.py:2`；`A/AGENTS.md` 鐵律 3；`A/wf/workflows/common/user.md`「commit 前跑什麼」。
3. **怎麼運作**：tabledb 同樣提供 CRUD、links/check/open/resolve、`$fmt`。skyrim `Table` 在 `tabledb_table.py`；aos 的 `tabledb.py` 檔內保留資料模型。skyrim CODE_MAP 人工指向各 repo 索引並用 coverage 對帳；aos `index_gen.py` 從檔頭一句話產 `_index.json`，同次產 `wf/knowledge/code-map/proto8/<夾>.json`，只列 git tracked 範圍。
4. **為什麼這樣定**：`T/docs/CHANGELOG-v0.5.1.md`「逐檔」記工具接近 8 KB 才拆，公開用法不變。`A/wf/tools/index_gen.py` 檔頭記 11-13 統一生成與 11-12 超過 15 個直屬項目的索引門檻。`S/wf/lessons/wf-kernel.md`「kernel-tools-not-mcp-not-skill」原話：「mcp 就不用了，那就太重」。
5. **靠什麼落實**：skyrim tabledb check 有壞鏈退 1；wf-lint 可選，不是每次 commit 必跑。aos 原句「只跑生成器」指 commit 前，index_check／check_anchors 是可選；index_gen 檢查不一致退 1，缺描述報 `DescMissing`。兩邊的驗證入口也不同：`S/wf/workflows/testing.md`「母 repo 驗證」列 unittest、連結、diff/status/submodule；`A/wf/workflows/testing.md` 開頭統一必跑只有 build，另挑定向測試，不設統一 ctest。
6. **實際有沒有在用**：skyrim CI 有 wf 工具 unittest 步驟；aos `wf/tools/` 實列 index_gen 與設定，`wf/knowledge/` 實列 code-map.json／code-map。只是接線與檔案證據，本輪沒有執行生成器或測試。

工具速查來源均為 `S/wf/tools/<檔名>` 已讀的檔頭／定義：

- `check_anchors.py`：本機 Markdown fragment 檢查；`find_big_lists.py`：表／清單 bytes 與連結數，識別 `wf-nav` 豁免。
- `fix_moved_links.py`：moves.tsv 驅動 md／資料檔改鏈，預設 dry-run；`fix_moved_links_fmt.py`：搬移前後的 `$fmt` 重寫；`fix_moved_links_scan.py`：掃描集合、搬移鏈與 remap。
- `tabledb.py`：CRUD CLI；`tabledb_table.py`：JSON／CSV 資料模型；`tabledb_links.py`：連結欄抽取解析；`tabledb_fmt.py`：展開門面；`tabledb_fmt_expand.py`：目錄／環境值代換；`tabledb_fmt_vars.py`：變數表與 local 合併；`fmt-vars.json`：名字／算法資料，不是可執行工具。
- `wf-lint.sh`：入口與退出判定；`wf-lint-checks.sh`：被 source 的掃描／計數；`wf-lint-local.sh`：本地接線；`wf-lint-retention.sh`：保留期。詳見 A1。
- `test_check_anchors.py`：中文、重複、顯式 anchor；`test_find_big_lists.py`：空行、導航豁免、連結數；`test_fix_moved_links.py`：`$fmt` 搬移與 dry-run。
- `test_tabledb.py`：CRUD／連結／CLI；`test_tabledb_fmt.py`：展開、環境值、壞指示詞；`test_tabledb_fmt_vars.py`：別名、載入優先序與 local 覆寫。
- `test_wf_lint.py`：QUERYCMD、percent encoding、大小與 venv 排除；`test_wf_lint_local.py`：hook 的一般／strict；`test_wf_lint_scope.py`：掃描範圍、ignore 與超過 255 的 BROKEN 計數。未跑測試。

### B4. 規劃與派線入口

1. **是什麼**：共有 planning 與委派，但規劃落點、GPT 權責不同。
2. **出處**：兩邊 `wf/workflows/planning.md`；`S/wf/workflows/agent-dispatch/README.md`「三層派線結構」；`A/wf/workflows/dispatch/aos-teams.md`「誰做什麼」。
3. **怎麼運作**：skyrim 想法表→roadmap 表→plans；aos 路由到 thinking／CONCEPTS／NORMS。skyrim 寫「GPT 的優先級較低，並非禁止使用」；aos 寫「gpt 系不參與設計決策與架構規劃」。
4. **為什麼這樣定**：aos 引使用者分工原話；skyrim planning 說免得卡在 idea／roadmap 分類。
5. **靠什麼落實**：文件與任務書約定；本輪未核 agentctl 派線工具。
6. **實際有沒有在用**：兩邊入口在；skyrim plans 索引有 PoE 計畫，但 `S/SESSION-LOG.md`「暫凍」已寫 11-05 凍結，不能把索引列在現役當成仍獲授權施工。

## C. aos 有、skyrim 沒有

限獨立入口／工具形式；skyrim/wf grep `index_gen|compact_reload|workflows/workshop|workflows/hackathon|workflows/experiments|workflows/digest` 無命中，兩支工具另用 glob 複查也無檔。名稱由以下已讀檔頭確認：

- 研討會：`A/wf/workflows/workshop/README.md`。
- 黑客松：`A/wf/workflows/hackathon/README.md`。
- 單一假設實驗：`A/wf/workflows/experiments/README.md`。
- 分批白話讀物：`A/wf/workflows/digest/README.md`。
- 生成索引：`A/wf/tools/index_gen.py`。
- compact 重讀：`A/wf/tools/compact_reload.sh`。

## 模板版本與變更記錄位置

`T/` 存在；`T/template/AGENTS.md` 尾戳 `wf-kernel v0.6 (2026-09-02)`。`T/CHANGELOG.md` 有「未發布」「v0.6」「v0.5.1」「v0.5」。只記變更條目位置：

- `T/docs/CHANGELOG-v0.5.1.md`：「v0.5.1 (2026-09-02)」「逐檔」。
- `T/docs/CHANGELOG-v0.6.md`：「skills 進契約」「vendor effective-html」「external skills（submodule）」「wf-init --skills 與適配層」「wf-lint」「reply-style.md」「精簡工作流」「既有專案要不要跟」。

## 沒讀到／不確定的

未跑命令／測試、未改來源 repo；未核 CI 執行、遠端 hash 與遊戲狀態。

第一層工作流入口已讀（長檔節錄）；未通讀 findings、plans 深層、所有 lessons／wait-user 子頁。遊戲腳本多只核入口引用（A4）；aos 只作指定範圍對照。

`T/template/kernel/AGENTS.md` 得 FileMissing；更正為 `T/template/AGENTS.md` 後讀到。hook 掃描根、baseline 與 PoE 狀態差別已明列。
