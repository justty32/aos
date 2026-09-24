← [工具大開發時代](README.md)｜[notes 索引](../README.md)

# 三波開發計畫

工具代號見 [catalog.md](catalog.md)。

## 分波的原則（審查 M1 改過）

- **第一波**：workflows 團隊的最短路徑。它**不另外開新的逃生口**：新工具只寫固定位置（`team/outbox/<自己>/`、自己的筆記）、或跟 base 一樣關在工作根目錄、或是在牢外跑**自帶的固定檢查器**；沒有一支新工具會執行專案裡的檔或任意指令。
  **但第一波整體不是安全的**：工人手上的 base `bash` 本來就關不住（讀寫得到主機別處、帶著環境變數），`--root` 指到拋棄式資料夾也不會縮小它的權限。所以第一波的定位是**在信任環境裡的功能原型**：模型只用 LiteLLM `deepseek-chat`、專案是拋棄式的、機器上沒有要保護的東西在工人碰得到的地方。**正式的模型驗收在第二波牆接上之後重跑一次。**
- **第二波**：要牆（[agent-access](../2026-09-24-agent-access/README.md) 的 `access.json`＋bwrap，另一隊正在做）才安全的——跑任意程式、碰家外映射、唯讀看信任資料；再把第一波全部放進牢重驗。
- **第三波**：錦上添花，大多是「讓模型做更多事」，照治理原則放最後。

## 共用的契約（第一波第 0 步，隊 1 半天先做完再開其他隊）

審查 M12：各隊要共用的格式與入口先落地、先合，其他隊再平行做。這一步由**隊 1** 做、**先合進 main**：

1. **`team.json`**、團隊資料夾佈局（[catalog A 段開頭](catalog.md#團隊資料夾a-段共用的地基)）、**信**、**任務單**、**申請**的 JSON 格式，寫成 `spec/team/` 的規範（每檔 ≤ 8 KB）。
2. `cli/aos-team` 的空殼：子命令分派表，每個子命令先是「還沒做」；其他隊只填自己那格的實作模組。
3. `lib/aos_agent_say.py` 裡的投檔函式抽成可共用（郵差要用同一個；不改行為）。

草稿（隊 1 可以改，改了要在報告寫明）：

```json
{"_metainfo": {"_type": "aos_team", "_version": 1},
 "project": "../p", "tz": "Asia/Taipei",
 "members": {
   "lead":     {"template": "lead",     "model": "smart", "mail_to": ["worker-1", "reviewer", "human"]},
   "worker-1": {"template": "worker",   "model": "cheap", "mail_to": ["lead", "human"]},
   "reviewer": {"template": "reviewer", "model": "mid",   "mail_to": ["lead", "human"]}},
 "limits": {"stale_minutes": 10, "max_members": 6}}
```

信（`team/outbox/<寄件人>/<id>.json`，`id`＝`<epoch ns>-<pid>-<寄件人>`）：

```json
{"id": "…", "from": "worker-1", "to": "lead", "status": "DONE", "reply_to": "t-0001", "rev": 1, "text": "…", "at": "2026-09-25T10:00:00+08:00"}
```

`status` 只准 REQUEST／DONE／BLOCKED／NEEDS-USER／FAILED／PROGRESS。申請（開單、問人、壓縮、生成員…）也是 outbox 裡的一個檔，多一格 `"kind": "handoff"|"ask"|"compact"|…`。人的名字固定 `human`。成員的 `input` 一律是資料夾 `input/`（審查 M3）。

## 誰改共用的檔（審查 M12）

| 檔 | 唯一的改動者 | 別隊要改怎麼辦 |
|---|---|---|
| `lib/aos_agent_cli.py`（`aos-agent` 子命令分派） | 隊 4 | 隊 1 的 `init --template`：隊 1 寫好 `aos_agent_init.init_from_template()`，隊 4 接一行旗標 |
| tick 的 idle 一步（自動壓縮、事件紀錄） | 隊 4 | — |
| `cli/aos-team` 分派表 | 隊 1（第 0 步定好） | 別隊只新增自己的模組 |
| `proto5/README.md` 指令表、`lib/README.md`、`tools/README.md`、`notes/README.md` | **收尾隊** | 各隊把要加的列寫進自己的報告，收尾隊一次加 |

合併：每隊做完**先 rebase 到最新 main**（保留自己的 commit，不是 `reset --hard`），在 rebase 後的分支上跑全部測試，再由調度者在主 repo ff-merge。順序：隊 1 第 0 步 → 隊 3 → 隊 1 其餘 → 隊 2 → 隊 4 → 收尾。

---

## 第一波：workflows 團隊跑起來（4 隊並行＋收尾 1 隊）

| 隊 | 工具 | 模型（照調度慣例） | 領地（新檔為主） |
|---|---|---|---|
| 1 骨架 | 第 0 步契約；T-team、T-template、T-route、T-handoff（`handoff`、`board`、`aos-team task`）、T-ask（`ask_human`、`aos-team wait/answer`） | Opus | `spec/team/`、`cli/aos-team`、`lib/aos_team*.py`（郵差除外）、`proto5/templates/`、`aos_agent_init.py`（加函式） |
| 2 郵差 | T-say（`team_say`）、T-post（郵差＋書記＋看停滯）、T-verify（固定檢查器）、T-beat | Opus | `proto5/tools/team/`、`lib/aos_team_post.py`、`aos_team_verify.py`、`aos_team_beat.py` |
| 3 檔案＋workflows 包 | T-wf（快照、`wf_doc`、staging 的 `wf_init`、`wf_lint`、`wf_residue`、`wf_table`）、T-md、T-json、T-directive | gpt-sol（量大、照規格） | `proto5/tools/wf/`、`proto5/tools/files/`、`cli/aos-json`、`cli/aos-directives` |
| 4 記憶與紀錄 | T-events（含 `aos-llm call` 記 usage）、T-context（人用）、T-compact（機械版＋自動＋申請）、T-notes、`aos-agent history --archive` | Opus（碰 tick 鎖與恢復規則，最難） | `lib/aos_agent_{events,context,compact}.py`、`aos_agent_cli.py`、tick 的 idle 一步、`aos_llm_call.py`（只加寫 usage）、`spec/agent/`、`spec/aos-agent/` 新檔 |
| 5 收尾（前四隊合完才開） | T-score、三個模板的人格定稿、`routes.json`、各份 README 與索引、教程 07、真跑驗收、試玩 | Opus；試玩派 gpt-sol 當新手 | `lib/aos_team_score.py`、`proto5/templates/*/prompts/`、`tutorials/07-team.md`、共用 README |

前提：talk 合進 main（隊 4 要搬它的 `/context` 算法，讓 talk 改叫同一個函式）。

### 任務書骨架（每隊一份，把 ⟨…⟩ 填掉就能開）

```text
你是 aos proto5「工具大開發時代」第一波 ⟨隊名⟩ 隊。用繁體中文、白話。
你在 git worktree 裡；第一步 git reset --hard main（這時你還沒有任何 commit）。

## 目標
⟨一句話⟩。工具規格照 proto5/notes/2026-09-24-tool-era/catalog.md 的 ⟨T-xxx…⟩；
共用格式照 spec/team/（隊 1 第 0 步已合進 main）。格式要改：寫進報告，不要自己改 spec/team/。

## 先讀
proto5/README.md、proto5/tools/README.md＋tools/base/（工具寫法）、spec/agent/info.md §3.3、state.md §4.1（收件）、
spec/aos-agent/cli-talk.md（say 投檔）、idle.md、spec/team/、notes/2026-09-24-tool-era/{workflows-as-team,catalog,axes,plan}.md、⟨本隊額外的⟩。
~/repo/workflows 唯讀；要用它的東西就照 catalog T-wf 做固定版本快照。

## 領地
可以新增／修改：⟨檔案清單⟩。共用檔照 plan.md〈誰改共用的檔〉：不是你的就寫進報告，不要改。

## 規則（照 catalog〈共同規則〉）
規則放工具不放人格；不給模型「等」的工具；工具描述越短越好（報告附每個工具的描述字數）；
一份資料一個寫的人；成功純文字退 0，失敗最後一行 JSON 退 1；寫檔暫存檔＋rename；崩在半路重跑同一行收得回來（要有 KILL 在窗口裡的測試）。
不叫模型（除非 catalog 寫了）；不碰 LM Studio／ollama。真模型只用 LiteLLM localhost:4000 的 deepseek-chat。

## 交付
1. 程式＋單元測試（cd proto5/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test 全綠，報新增幾條）。
2. 規範：⟨新檔或改哪一節⟩。README／索引要加的列寫在報告裡（收尾隊加）。
3. 報告 proto5/notes/2026-09-2x-tool-era-⟨隊名⟩.md：做了什麼、真跑輸出、每個工具六軸自評（axes.md §5；量得到的附數字）、
   跟共用格式不合的地方、要使用者拍的。
4. astra 唯讀審查：寫 review-task.md，codex exec -m gpt-6-astra -C <worktree> -s read-only -o <報告夾>/review-astra.md - < 任務書；必修全修。
5. 交件前 git rebase main（不要 reset），rebase 後再跑一次全部測試。

## 驗收（寫死 ⟨N⟩ 條）
⟨見下面各隊⟩

## 規則
不推、只在 worktree commit；commit 訊息繁中，結尾兩行照調度者給的。
最後一則訊息：worktree 路徑、分支、commit、測試數字、六軸一句話、合併時要注意的檔。
```

### 各隊驗收（寫死）

- **隊 1 骨架**（7 條）：① 第 0 步：`spec/team/` 與 `aos-team` 空殼先合；② `aos-team init --config` 照草稿生三個成員，`aos-agent check` 各自全過、`input` 都是資料夾；③ `start`／`stop`／`ls` 對三人都對；④ `ask` 命中 `tool` 規則時不寫任何成員的 `input/`、直接印工具輸出；命中兩條或含否定詞時落穿給 lead；⑤ `route test` 對每條規則的命中／不命中例句全過才准存；⑥ `handoff` 申請經（假）郵差建出 `t-0001`、狀態 `queued`；舊 rev 的 DONE 不改狀態；⑦ `wait ls`／`answer q-…` 回到發問者、待辦少一條。
- **隊 2 郵差**（8 條）：① `team_say` 名冊外收件人、非白名單 STATUS 都回 `BadArguments`；信在別人的 `outbox/` 目錄＝身分不符退信；② 郵差跑一次：信進收件人 `input/mail-<id>.json`、`post/sent/<id>.json` 有紀錄、原檔進 `outbox/done/`；③ **崩潰窗口**（審查 M2）：在「投進 input 之後、寫 sent 紀錄之前」KILL，**並讓收件人在重跑前把信收走**（進 `done/` 或停在 `intake`），重跑不重投；另兩個窗口（sent 之後／搬 outbox 之後）同樣不重投、不漏動作；④ DONE → 提交一次性驗收工作（不在郵差裡同步跑）→ 不過＝工人收到「REQUEST 修正（第 2/3 次）＋逐條結果」、attempt 用完＝FAILED 給領隊與人；⑤ 有 `judge` 條目＝開審查子任務，逐條全 PASS 才 done；⑥ 看停滯：假成員卡在 think（健康不是 ok）與收單後沒進展兩種都只報一次 PROGRESS；在等別人的不報；⑦ 心跳：到期派出、在途不重派、DONE 才更新；漏三次只補一次並報告；模型提出的列未經 `answer` 不跑；⑧ 真 daemon＋kernel 整合：郵差當反覆工作跑、一封信從 outbox 到對方記憶。
- **隊 3 檔案＋workflows**（7 條）：① `wf_init` 在拋棄式資料夾導入 heartbeat 包；**在 wf-init 跑到一半時 KILL，重跑成功**（staging）；② `wf_residue` 正確數出三種殘留、讀不到的檔另列；③ `wf_doc` 讀得到快照裡的 `IMPORT.md`、讀不到快照外；④ `json_edit` 五種 op、壞 pointer、改完非法不寫、`expect_sha` 不符回 `Conflict`；⑤ `json_edit` 對 agent 的信任資料拒絕——包括 `info.json` 用 `$ref`／自訂路徑指到的人格、記憶、工具檔（不是只看檔名）；⑥ `md_section` 標題不唯一回 `NotUnique`、`append_item` 格式不對拒絕；⑦ 每個工具描述字數列表，全包 < 3000 字元。
- **隊 4 記憶與紀錄**（8 條）：① `aos-agent context` 的數字與 talk `/context` 一致（同一函式）；② `events.jsonl` 每批記起訖與成敗、`usage.jsonl` 在 LiteLLM 真跑時有 token 數；③ `compact --dry-run` 不改檔；④ `compact` 後記憶照 agent §3.2 驗得過、`tool_calls` 與結果成對、archive 在、縮完低於 `--max-tokens`；⑤ 還沒 done 的任務那幾輪原樣保留；⑥ 崩潰窗口：寫 archive 後、換 history 前 KILL，重跑結果一樣、history 從不缺；⑦ 鎖被佔退 101、`batch` 不是 null 拒絕；自動壓縮在 tick 同一把鎖裡做、不死鎖；⑧ 真模型（deepseek）壓縮後再問一句，回話正常（不 400）。

### 第一波的整體驗收：真跑 workflows 小例子（功能試跑）

**例子 1 導入**（[workflows-as-team §2.4](workflows-as-team.md#24-走一遍驗收例子把-workflows-的-heartbeat-包導入一個空專案)）：把 heartbeat 包導入空專案 `~/tmp/wf-try/p`。（審查 M7）
- **固定的專案事實** `facts.json`：專案一句話「試跑用的空專案」、驗證指令「無」、時區 `Asia/Taipei`、分支慣例「直接在 main」、使用者偏好「繁中、直接做」、佈局標準、flavor heartbeat、不裝 skills；**範例區塊**（routines 的範例分區）一律刪掉、不自己編。事實表裡沒有的就回 NEEDS-USER，不准猜（`IMPORT.md` 原文禁止瞎填）。
- **Done when**：`IMPORT.md` 的四條（用 `wf_residue` 與 `wf_lint_strict` 檢查器，不用 `grep -c` 退出碼）＋**內容檢查**：`AGENTS.md`、`WORKFLOWS.md`、`workflows/tick.md`、`routines.md`、`schedule.md` 都在；`WORKFLOWS.md` 的派發表有 tick／routines／schedule 三列；`facts.json` 的時區、專案一句話出現在對應檔裡。
- 這個例子**只驗「導入文件」這條路**（門房→工人→驗收），**不驗**心跳引擎、也不驗審查。

**例子 2 落穿＋審查**：`aos-team ask "把 p 的 WORKFLOWS.md 開頭那段說明改寫得更白話，意思不能變"`。門房沒規則 → 領隊開單（含一條 `judge`：「原意沒變」與機械的 `wf_lint_strict`）→ 工人改 → 驗收 → 審查逐條判。驗領隊、審查兩個 agent 與任務狀態機。

**例子 3 心跳**（可選，隊 2 的 T-beat 做了才跑）：人 `aos-team routine add` 一條 `every 2m` 的「數 p 裡的 md 檔數量寫進 notes」，看它到期派出、完成、下次再派。

**重來要重置全部**（審查 S7）：每次跑之前刪掉整個團隊資料夾與 `p` 重建（記憶、信、任務、排程都歸零）；模型、`llm.json`、kernel 的 cpu 數固定不變，寫在報告裡。

**功能過關線**（使用者可改；這是「能不能用」，不是六軸分數，審查 M14）：
- 例子 1 跑 3 次，至少 2 次 Done when 全過；每次領隊被叫 0 次；模型呼叫 ≤ 25 次。
- 例子 2 跑 2 次，至少 1 次走完 done，任務狀態每一步在 `aos-team task show` 看得到。
- `aos-team mail` 印出來，人一行一行看得懂每步誰做（派一位新手 gpt-sol 只拿 README＋教程 07 照做並回答「每一步是誰做的」，照 play/ 五條標準打分，報告放 `notes/play/`；**模型扮的新手只是代理**，最後還是要使用者自己看一遍）。

**六軸評分**另外做：用 `aos-team score` 填表，照 [axes.md](axes.md) 的門檻給分；**穩定軸要 10 次才評**，功能試跑 3 次時 S 寫「2/3 次過」、不給分。B 軸這波一定低（工人的 bash 沒關），報告寫明，第二波重評。

---

## 第二波：接上牆（牆那隊合進 main 之後開；3 隊並行）

| 隊 | 工具 | 模型 | 內容 |
|---|---|---|---|
| A 造工具 | T-toolnew、T-tooltest、T-wrap-py | gpt-sol | `aos-agent tools new／test／wrap-py`（新檔 `aos_agent_tools_dev.py`，跟牆那隊的 `tools ls/add/rm/alias` 分開；`aos_agent_cli.py` 的分派那一行交給當時的擁有者）；wrap-py 產的工具包預設關牢 |
| B 牆接線 | 第一波全部進牢；T-verify 開 `cmd_ok`（牢裡跑專案自己的指令）；T-context 模型版、T-recall、T-notes 映射 | Opus | 照 agent-access 契約「有表就全關」：團隊模板的 `access.json` 預設工人只映射專案（rw）、`team/outbox/<自己>/`（rw）、`team/notes/<自己>/`（rw）、wf 快照（ro）；先跟牆那隊確認 outbox 在家外、不撞「信任資料重疊」規則（審查 M11）；郵差讀申請時再驗一次身分、角色、路徑、操作 |
| C 申請類 | T-access-req、T-persona、T-lock、T-pool | Sonnet（規格清楚、量小） | 都走 T-ask 的待辦；`_pool` 照 priority 提案 |

**驗收**：① 第一波三個例子在「工人關牢」下各重跑，功能結果不變；這次跑滿 10 次例子 1，正式給六軸分數；B 軸要 ≥ 4；② `tools wrap-py` 包固定 fixture（有註解、各型別各一、該拒收的各一），拒收表正確；裝給工人後，交接書要它用這支工具完成一件事，模型沒寫任何 bash；③ 逃逸測試照 agent-access 的 experiment.md：工人 `cat` 別的成員的家、寫 `access.json`、寫別人的 outbox、在信裡冒名，全部被擋或被郵差退信；④ 六軸重打，跟第一波逐軸比。

## 第三波：錦上添花（挑著開，2～3 隊）

| 工具 | 為什麼放最後 |
|---|---|
| T-spawn | 模型生成員＝常駐成本（每人一份反覆工作）＋邊界擴大的風險；先看固定編制夠不夠 |
| T-toolsmith | 模型寫程式給自己用，一定要牆＋人批；先看第二波「人給檔、機械包」夠不夠 |
| T-wrap-cli | 要解析 help 文字，可能要模型 |
| T-compact `--summarize`、T-wrap-py `--describe-with-llm` | 都是「加一次模型」的選項，照治理原則先證明機械版不夠 |
| T-crystal | 要前兩波累積的 `route.log` 才有東西統計 |

**驗收**：每個附「機械版 vs 加模型版」的六軸對照；加模型的要證明 L 軸的損失換到了什麼（例如門房命中率從 x% 升到 y%、負例沒有誤觸）。

## 總表

| 波 | 並行隊數 | 前提 | 粗估 |
|---|---|---|---|
| 一 | 隊 1 第 0 步（半天）→ 4 隊並行 → 收尾 1 隊 | talk 合進 main | 各隊 1～2 天；收尾 1 天 |
| 二 | 3 | 牆那隊合進 main | 各隊 1～2 天 |
| 三 | 2～3 | 前兩波的紀錄 | 看挑幾個 |
