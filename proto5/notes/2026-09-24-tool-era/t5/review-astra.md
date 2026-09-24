本次找到 **5 項必修**。只審 `75eadc0..HEAD -- proto5`，未改檔、未跑模型或啟動 daemon／kernel。跑了 10 個不需寫檔的單元測試，全過；另以記憶體 mock 重現門房繞過與 score 例外。完整測試需要建立暫存檔，受本次唯讀環境限制，未跑。

**必修**

- **M1｜`proto5/lib/aos_team_route.py`，`ask()`：群組替換能繞過禁用命令。**  
  `validate_routes()` 檢查的是替換前的 `run[0]`，但 `ask()` 連第一格也替換。例如 `run: ["{cmd}"]`、句型 `執行 (?P<cmd>\w+)`，配上「執行 stop」的命中例句，驗證會過，替換結果就是 `["stop"]`。已用 mock 確認，沒有真的停團隊。  
  **改法：**禁止第一格使用群組，並在執行前再次核對命令白名單；至少重新套用 `ask/init/rm/start/stop` 的禁令。

- **M2｜`proto5/lib/aos_team_score.py`，`load_member_logs()`、`done_when_count()`、`Reader.json_dir()`：仍有 Traceback 路徑。**  
  有效時間戳的事件若是 `{"ev":"think_end","id":[]}`，去重會拋 `TypeError`；任務的 `verify: [{"results":1}]` 也會拋 `TypeError`。兩者已重現。列資料夾時的 `PermissionError` 也未被 `json_dir()` 接住。CLI 只接 `TeamError`，因此違反「壞資料跳過、讀不到計數、不會 Traceback」的承諾。  
  **改法：**先驗證實際會使用的欄位型別，再去重／加總；壞行或壞任務計入 skipped。列目錄的 `OSError` 也要接住。

- **M3｜`proto5/lib/aos_agent_init.py`，`_notes_dir()`、`_ensure_notes()`、`_guard_team()`：內建 notes 沒有驗實際落點。**  
  若初始化前已有 `team/notes/worker-1 → ../tasks`，`makedirs(exist_ok=True)` 接受它，`notes` 又按名字直接跳過團隊保護檢查，最後會把任務目錄掛成可寫。指向另一成員的 notes 也會讓兩人共用筆記。一般 access 檢查保護的是該 agent 的信任資料，不能補上團隊任務表這層限制。這需要預先存在的連結，並非乾淨初始化後模型自行逃出。  
  **改法：**新建／補掛內建 notes 前，驗證路徑各層及實際落點，拒絕連到控制目錄或其他成員筆記；人已手動設定的掛載，仍照既定規範保留。

- **M4｜`proto5/spec/team/examples/routes.json`，`import` 規則：把試跑事實當成通用驗收。**  
  新增檢查硬性要求 `AGENTS.md` 含「試跑用的空專案」、`user.md` 含 `Asia/Taipei`。教程直接教人安裝這份規則，但它接受任意 facts 檔。真專案或其他時區即使完全照 facts 正確導入，也會驗收失敗，甚至誘導工人填假資料來過關。  
  **改法：**通用規則只保留通用結構檢查；這兩條移到試跑專用規則，或從明確的事實資料產生驗收值。

- **M5｜`proto5/lib/aos_team_score.py`，`collect()` 信件統計：時間窗規範與實作不符。**  
  第 415～416 行讓 `reply_to` 指向該單的信直接繞過時間窗。因此任務結束很久後再寄的追問、補充信也會被算入，並非只補算結束當下的完成通知。`score.md` 卻寫信件「只算時間窗裡的」。  
  **改法：**一般信仍套時間窗；若要納入終局通知，明確限制通知種類／來源，並在規範寫出例外。

**建議**

- **S1｜計分要標明是部分指標。** L／R／F 的數字門檻對得上 axes.md，但沒有實作「模型當排程器」「要人推才動」等降分條件；失敗或取消很快也能拿 F 高分。R 全部呼叫都沒回 usage 時，仍可能以零 token 得 5 分。建議標成「次數分／已知 token 分／耗時分」，用量全未知時留空。
- **S2｜score 大量資料。** 每次都把全隊所有事件、usage、任務和信讀進記憶體，`--task` 也一樣；成本隨累積資料量增加。可先讀任務決定時間窗，再串流統計。輪換目前遇到缺號就停止，`.1` 不在但 `.2` 還在會漏讀，宜逐一檢查 1～20。
- **S3｜同名重建的筆記生命週期。** `rm` 搬走家，但 notes 留在原處，同名重建會接回舊筆記。目前沒有足夠規範依據判定必須阻擋；至少在 `rm/init` 明說「保留／沿用舊筆記」，避免使用者以為是全新身分。
- **S4｜`machine_lines()` 的 `ok` 容易被當成正在運作。** 帳本讀法確實共用 `aos_agent_status.ledger()`，但沒檢查 kernel 是否停止或恢復中。建議顯示「已登記，狀態 queued／…」，或加 kernel 健康判斷。
- **S5｜compact 參數不完全一致。** 整數範圍一致且都拒絕 bool；工具把 null 當省略，郵差直接收 null 會拒絕。工具拒絕空白 reason，郵差接受。沒有越權問題，但「驗證一致」的描述宜收斂或統一。

**確認沒問題的**

- 名冊與模板不能用 `mounts.notes` 偷換位置；`notes: true` 配非團隊模板會被拒絕。舊家只補缺少的 notes，不覆蓋既有人手掛載。正常目錄配置下，不同成員各有自己的路徑。
- `compact_me` 不收 `member`，身分來自工具設定；郵差再檢查非 human 只能壓縮自己。
- `wf_doc` 清掉 `_FENCE` 後，`resolve(snap, …)` 與打開後的 `check_open()` 都以 **snap** 為界；一般外連 symlink、越界 `..`、外部絕對路徑與指向快照外的 `/proc/self/…` 都受檢查。
- `run` 不經 shell、不切割群組中的空白，仍只經 `aos-team` 命令表解析；`--target` 不會重新經頂層解析。一般規則仍須防止群組整格變成選項。`count-md` 的數字＋`m/h/d` 群組及 fullmatch 足以排除題述注入值。
- score 正常資料的 `ev＋id` 去重、null id 不去重、連續輪換檔、失敗 think 計數、領隊起點推定與未滿 10 次不給 S 分，符合 `score.md`。
- `ls --json` 保持既有成員陣列合理；`render_review()` 帶父單 facts、`Layout.events()` 改到實際事件檔也正確。教程主要指令與輸出相符，需修的是上述通用導入規則。