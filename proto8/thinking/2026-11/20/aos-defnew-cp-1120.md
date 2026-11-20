線 aos-defnew-cp-1120 的紀錄：把 `agent_def new` 改成純粹 cp（路徑一律不改寫、不警告），做了什麼、證據、對不上處、替使用者做的選擇。

← [當天](README.md)｜依據：[aos-pylib-plan-1120/12 第 10 題](aos-pylib-plan-1120/12-使用者已答.md)「待裁第 10 題」

## 依據

使用者 11-20（逐字）：「就是說，好比C語言的include，並且是#include "..."，我是希望夾內的路徑都不改。也就是說它的功能會很單純，就是純粹的cp過去，各種相對路徑就這樣。我其實也會覺得agent_def new過去之後，還要特別去改寫tools.json內的路徑，有點麻煩。」指到夾外的相對路徑抄到不同深度會指錯，他選「也不管，跟 #include 一樣」。開工：「開工吧」。

## `new` 原本做的每一件事（先列再動手）

| 做的事 | 算不算「改寫路徑」 | 處置 |
|---|---|---|
| 解 `template`／`from`（含指示詞、從工作區算）、檢查 `path` 不在、建上層夾 | 不算（是找來源與目的地，不碰內容） | 照留 |
| `shutil.copytree(symlinks=True)`：捷徑照搬、略過 `__pycache__` | 不算（就是 cp） | 照留 |
| `tools_file`：讀 `interfaces.json` 找 `aos-agent.tools` 宣告，壞了報 `DefBad` | 只為了改寫才讀 | 拿掉（`interfaces.json` 不再被 new 讀，壞的照抄、留給 check） |
| `rebase_tools`：tools 檔裡相對的 `path`、`env_file`、`$override` 換算成從新位置走回原目標，有換就整份重寫（indent 2、排版變；是捷徑的 tools 檔會換成普通檔） | **是** | 拿掉 |
| `write_lineage`：`_metainfo.json` 寫 `lineage`（蓋掉舊的、其他鍵照留；整份用 indent 2 重寫；是捷徑的換成普通檔） | 不算（11-12 使用者要的血統，不是路徑） | 照留（拿不準是否也該拿掉，見「替使用者做的選擇」） |
| 先寫同層暫存夾再改名、失敗清暫存夾 | 不算 | 照留 |

別的路徑改寫：沒有。hooks.json、fsm.json、loop.json 的相對路徑本來就沒改寫。

## 改了什麼

- `py/tools/agent/agent_def/_entry`：拿掉 `tools_file`、`rebase_tools` 與呼叫；檔頭與 `--help` 改說純粹 cp。
- `_metainfo.json` summary、`_tooldef.json` description（英文）補「copied as it is, like cp -r」與夾外相對路徑的後果一句。
- 測試 `tests/test_agent_def.py`：見下。
- 知識庫 `knowledge/aos/agents.json`（agent_def 的 Rules 第一條）、`docs/NORMS/附錄4-持久檔.json`（interfaces.json 的 reader／evidence 拿掉 agent_def；tools.json 的 writer 改成「人手寫（agent_def new 整份照抄、不改，路徑也不改寫）」、evidence 拿掉 rebase_tools）、`py/docs/03-索引-agent等.md`（agent_def 那列）。

## 新測試（`tests/test_agent_def.py`，30 → 32 支連 def_edit 那檔）

- `test_copy_is_byte_for_byte_and_rewrites_no_path`：來源夾有排版怪的 tools.json（夾內 `fn/add.py`、夾外 `../tool`、`env_file`、`$override`、絕對、指示詞）、hooks.json、fsm.json 的 `../../shared/x.py`、權限 750 的檔、空夾、指夾內／夾外（斷的）／絕對的三種捷徑、`__pycache__`、帶舊 lineage 的 `_metainfo.json`；抄到同層、深三層、工作區外三處，逐項比：檔的 bytes 與權限位、夾的權限位、捷徑的目標字串全相同。
- `test_every_stock_template_is_copied_byte_for_byte`：repo 每份有 `interfaces.json` 的範本（agent-fsm、agent-python、eca-claude、eca-pi、reviewer）用 `template` 抄到深兩層，同上逐 byte 比。
- `test_symlinked_tools_file_stays_a_link`：tools.json 是捷徑就照搬捷徑（從新位置指到哪就是哪）。
- 改：`test_outside_template_through_symlink_uses_literal_path`、`test_path_outside_workspace_ok` 改成斷言照抄；`test_env_file_and_override_rebased` 刪（併進第一支，斷言相反）；`test_failure_removes_temp_folder` 改成 `test_broken_interfaces_is_just_copied`（new 不再讀 interfaces.json；失敗清暫存夾仍由 `test_lineage_bad_metainfo` 管）。
- **設計上本來就不同的（逐 byte 比較的例外）**：① `_metainfo.json`：多（或換掉）`lineage` 一個鍵，整份以 indent 2 重寫，來源是捷徑時換成普通檔；② `__pycache__` 不抄。
- 新測試對舊程式跑（舊 `_entry` 抄成暫存樹的 `agent_def_oldcheck`）：5 支失敗（三處目的地的逐 byte 那支、工作區外那支、壞 interfaces 那支），證明測得到改寫。

## 全套測試（git archive 同一個 commit e1209424，各自 install，78 夾、8 個並行）

- 改前 `base`：2949 支；71 夾全過；沒過的 7 夾：frontend（5 error，讀不到 wf/，已知）、apps/feedback（18 error，已知）、apps/gdb（4 fail）、kernel（1）、review_round（1 error）、templates agent-fsm（2）、reviewer（1）。
- 改後 `new2`：2951 支（agent_def 夾 30 → 32，其餘每夾支數相同）；71 夾全過。跟改前不一樣的夾：agent_def（多 2 支，全過）；kernel、review_round 改後過了；gdb 4→1、agent-fsm 2→1；**改後多掉兩夾**：cpp/aos-daemon `test_poke` 1 支、apps/mcp `test_list_changed` 1 支——這兩檔在 base 與 new2 各單獨（不並行）重跑兩次，四次全過，是並行忙時才掉的計時測試，跟本線無關。
- 第一輪改後（`new`）作廢，原因見「坑」。

## 實跑（暫存樹、假腦）

`e2e.sh`：暫存樹裡起根 daemon＋llm kernel（假腦 `fake`），經 `aos-exec` 叫裝好的 `lib/tools/agent/agent_def`：

| | 改前（base） | 改後（new2） |
|---|---|---|
| 1. `new` template agent-fsm → `agents/ann`；`diff -r` 對範本（除 `_metainfo.json`） | 相同；check 空；ann 答 `FAKE ANSWER to: hello (tool said: <時間>)` | 同左 |
| 2. 自己做 `agents/src`（tools.json 只有 `{"mytool": {"path": "mytool"}}`，工具印自己住哪一夾），`new` from → `agents/deep/ann2` | tools.json 被改成 `"../../src/mytool"`；ann2 答 `tool said: mytool of src`（用的是原夾那份） | tools.json 一字不改；ann2 答 `tool said: mytool of ann2`（用自己那份） |

兩輪都 `aos-daemon-ctl -d <自己的 .stack> shutdown` 收掉，aos-exec 行程確認不在。

## 誰靠這個改寫行為（查全 repo）

- repo 裡所有登記檔（`git ls-files` 的 `tools*.json`，與每份 `interfaces.json` 宣告的 tools 檔）：**沒有一份寫相對路徑**，全是指示詞或沒有工具。所以現有範本、kits、start-api／start-eca 的 ann、frontend/aide-def 抄出來都跟以前一樣（上面第二支測試逐 byte 證明範本那半）。
- 叫 `agent_def new` 的流程：llm kernel 與 start-api 的 `kernel.json` 假腦劇本（從 agent-fsm 抄 `defs/helper`）、kits 的步驟、教學（只用 check）——來源都是 agent-fsm，不受影響。
- 會「壞」的只有：使用者自己的定義，tools 檔寫了指到夾外的相對路徑，又抄到不同深度——這是使用者選的「也不管，跟 #include 一樣」，不修。repo 裡沒有這種。
- 不相干、沒動的另外兩種改寫：`fork` 工具的 `fork_copy.rebase`（抄自己進 stack，不是 agent_def）、`defs.load` 疊底時改寫底的相對路徑（`agent_spec_load`，agent-python README 那段；線 aos-pylib-k3-1120 的領地）。
- 沒有範本或教學要修；沒有 NEEDS-USER。

## 坑

- 從 Windows 端（`\\wsl$`）用編輯器改 `_entry` 後，檔的 `+x` 掉了（git 看到 `100755 => 100644`）；第一輪改後測試（`new.tests`）因此作廢，`chmod +x` 補回後重做 `new2`。全套測試裡**沒有一支**抓到工具 `_entry` 沒有 `+x`（測試都用 `sys.executable` 直接跑），只有實跑抓到。

## 替使用者做的選擇

1. **lineage 照寫**：「純粹 cp」與 11-12 定的血統（出生時寫一次 `lineage`）只能取一；血統不是路徑改寫，照留。附帶：`_metainfo.json` 是捷徑時換成普通檔、整份 indent 2 重寫——這是既有行為，沒動。若要連 lineage 也不寫才算純 cp，是另一題。
2. **略過 `__pycache__` 照留**：不是路徑改寫，是不抄快取。
3. **壞的 `interfaces.json` 不再在 new 時報 `DefBad`**：new 已經不讀它；照抄、留給 check 報。
4. **`_tooldef.json` 多一句說明**夾外相對路徑會從新位置算（使用者說不警告，指的是執行時不印警告；工具說明裡寫一句後果，算文件）。
