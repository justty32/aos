# 審查任務：tool-era 第一波第 3 隊（files／wf 工具包、aos-json、aos-directives）

你是唯讀審查者。用繁體中文回答。只讀、不改任何檔、不跑會寫檔到 repo 的指令（可以在 /tmp 自己的暫存資料夾試跑）。

## 要審的東西（git worktree，分支上 main 之後的 commit）

- `proto5/tools/files/`：`json_edit`、`md_section`、`_files.py`、`_jsonedit.py`、`_mdsec.py`、`_trust.py`、`files.json`、`config.json`、`README.md`（`_common.py` 是 base 那份的逐字複製，不用審）
- `proto5/tools/wf/`：`wf_doc`、`wf_init`、`wf_lint`、`wf_residue`、`wf_table`、`_wf.py`、`wf.json`、`update-snapshot.sh`、`README.md`；`snapshot/` 是 `~/repo/workflows` 固定 commit 的快照（只看 `SNAPSHOT.json`，裡面的檔不用審）
- `proto5/lib/aos_json_cli.py`、`proto5/lib/aos_directives_edit.py`、`proto5/cli/aos-json`、`proto5/cli/aos-directives`
- `proto5/spec/aos-agent/tools-files.md`
- 測試：`proto5/lib/test/test_tools_files.py`、`test_directives_edit.py`、`test_tools_wf.py`

## 對照的規格

- `proto5/notes/2026-09-24-tool-era/catalog.md` 的 T-json、T-md、T-wf、T-directive 四段（逐字對）；`plan.md` 的「隊 3 檔案＋workflows（7 條）」驗收；共同規則 1～5。
- `proto5/tools/README.md`（工具包格式、錯誤格式）、`proto5/spec/aos-agent/tools.md`、`access.md`（權限牆：關牢時工具在 bwrap 裡，cwd＝`/work/<cwd>`、程式的資料夾唯讀掛在 `/opt/tool`、`AOS_TOOL_ROOT` 有值）。

## 請特別看

1. **信任資料**（catalog T-json、審查 M1）：`_trust.py` 沒關牢時能不能被繞過（符號連結、`..`、`$ref` 鏈、`tools` 列資料夾、自訂 `system`／`history`／`access` 路徑、硬連結、檢查與寫之間換路徑）？關牢時「交給牆」這個判斷對不對？
2. **原子性與崩潰**：寫檔、`expect_sha`、`wf_init` 的 staging／committing／roll-forward：在任何一步被 SIGKILL，重跑同一行能不能收回來？有沒有會把專案弄壞、或留下讓之後判斷錯誤的殘渣？
3. **關牢相容**：wf 工具在 bwrap 裡（快照唯讀、target 可能是掛載點、`/work` 以外寫不到）跑不跑得起來；有沒有偷用到牢外路徑。
4. **不執行專案裡的檔**（plan：驗收員只跑工具包自帶的固定檢查器）：`wf_lint`、`wf_table` 會不會跑到專案裡那份 `wf-lint.sh`／`tabledb.py`，或被專案裡的東西（`fmt-vars.local.json`、`.py`）帶著執行任意程式碼？
5. **錯誤訊息**：一行、模型看得懂、有沒有說能不能自己修；成功純文字退 0、失敗最後一行 JSON 退 1，沒有 Traceback。
6. **規格對不上**的地方（catalog 要的、plan 驗收要的）與測試沒蓋到的重要路徑。
7. `aos-directives` 的人格分節編輯：版本、還原、鎖、`content` 用了指示詞時的行為。

## 回答格式

分「必修」與「建議」兩節，每條：編號（M1、S1…）、檔名:行號、問題一句、為什麼、建議怎麼改。沒問題的面向一句帶過。最後一行寫「必修 N 條、建議 M 條」。
