# 2026-10-14 JSON 入口：argv 空出來（下午）與重做七題拍板

← [JSON 入口](../2026-10-14-json-entry.md)｜上一份：[03-決定未決](03-決定未決.md)｜下一份：[05-aos-llm-agent題](05-aos-llm-agent題.md)

## 4. argv 空出來（下午）

使用者原話：「因為現在aos-inst的呼叫方式改變，所以argv那塊就空出來了，一些東西可以從inst json格式中搬出來，先前一些沒做的選項也可以做了。」

前提：inst.json 格式已定不變（N-12），所以「搬出來」＝argv 多一條等價途徑（鏡射＋覆蓋），不是刪 inst.json 欄位。

### 4.1 argv 衍生的新題（全部使用者拍板）

- **D-1 argv 角色＝鏡射＋覆蓋**：設定 JSON 每個頂層 key 有同名旗標（`--cwd`、`--timeout-ms`、`--stdout-append`…），機械對應、不另發明欄位；旗標蓋過 JSON；JSON 一字不改；aos-inst／loop／daemon 同一條規則。旗標只准鏡射既有 key；daemon／loop 起子程式仍一律走 stdin JSON。
  - 範圍補充（使用者隨後拍板）：aos-loop／aos-daemon 的命令列同樣有同名旗標（如 `--times`、`--interval-ms`、`--ctl`、`--state`、`--work-dir`、`--load`、`--save`），同一條規則。**只鏡射最外層 key**；loop.json 裡包的那份 inst 設定（巢狀欄位，如內層 cwd）不鏡射，要改就改檔或用 `$ref`。這是已定，不是未決。（**後放寬**：Q10 使用者說同名旗標是為方便、非硬規則，物件型除非很小很少不鏡射，見 [05](05-aos-llm-agent題.md)。）
- **D-2 `--` 做，可與 JSON 併用**：`aos-inst [旗標] [TARGET] -- cmd args…`，`--` 後整段蓋過 JSON 的 argv。
- **D-3 優先序**：旗標 > JSON；TARGET 檔與 stdin 二選一（給 TARGET 就不讀 stdin，讀 stdin 寫 `-`）。
- **D-4 run()**：`run(x)` 收路徑或 dict；dict＝命令列合成好的那份設定。loop 改直接起子程序灌 stdin，run() 主要給 tasks 和人。
- **D-5 `*_inherit`**：留著、分情況。走 TARGET 照舊；參數從 stdin 來時 `stdin_inherit` ＝ Conflict 錯誤，`stdout_inherit`／`stderr_inherit` 允許，但 stderr 警告串流可能被弄髒。
- **D-6 子程式參數**：用現有 `stdin: "params.json"`，不加新 key；LLM 工具轉接把 arguments 落成 call.json。

### 4.2 推翻 10-12 的三條

以下三條是 10-12 的決定，這批**推翻**。這是 10-14 新前提（argv 不再被 TARGET 獨占）下的改變，不是忘了：

- 「命令列不開旗標」→ 改為 D-1 鏡射旗標。
- 「run() 只收路徑，跟命令列一致」→ 改為 D-4 收路徑或 dict。
- 「inst 不再加東西（`--` 不碰）」→ 改為 D-2 做 `--`。

不重開：`--base`（使用者 10-12 主動拿掉）、AOS_INST_SELF、多 TARGET。

## 5. 重做規劃頁七題（使用者拍板，下午）

第 3、7 題先前已定，不動。

- **第 1 題 inst 的 stdout**：一份結果 JSON `{code, signal, timed_out, pid, ms, exit_file}`。
- **第 2 題 loop 的 stdout**：每回合一份 `{run, code, ms}`＋總結 `{end, runs, skipped, last_code}`（daemon 同形）。
- **第 4 題 id**：設定 JSON 加選填 key `id`；daemon 起 loop 時填原 loop.json 的 realpath#/位置，手打沒給＝null；因鏡射自動有 `--id`。
- **第 5 題 stdin 多份 JSON**：只看第一份，其餘在 stderr 警告。（使用者沒選 AI 推薦的「報錯不跑」；10-14 夜補：這是實作的選擇，規範 N-12 不動，實作想嚴格直接報錯不跑也可以，見 [12](12-七題回覆.md)。）
- **第 6 題 daemon 底下 loop 的門**：落 `work_dir/N/ret.json`、`err.json`。`times` 為 null 時會一直長，記為未決。
- **第 8 題 共用檔**：抽一個（如 `aos_cli.py`），連 argv 一起：TARGET／`-`／旗標合成設定＋三扇門 JSON 串流；當符合 N-12 程式的範本。
- **第 9 題縫一**：改 N-11 一個定義：「設定檔」＝程式啟動時合成、只讀一次的那份設定，不管來自檔、stdin 還是 argv 旗標；其餘不動。
- **第 9 題縫二**：N-09 維持選填；N-13 的提醒稍晚由 Q9 整條拿掉（見 [05](05-aos-llm-agent題.md)）。
- **第 9 題縫三**：旗子通用、節奏不通用：開了 ctl 窗的程式都認 `paused`／`stop`；`times` 等節奏 key 只有反覆跑的程式認。

NORMS 已照縫一～三改（N-06、N-07、N-09、N-11、N-13）；argv 旗標細則（D-1～D-6）還沒寫成 N 條文，見 [NORMS 待定](../../NORMS/08-待定.md)。

## 6. 本節新增未決

- daemon 底下 loop 的 `ret.json`／`err.json` 在 `times: null` 時無限增長（第 6 題的代價）。（**已結**，10-14 深夜方案 B：stdout 丟掉、不再有 ret.json，見 [15](15-ret與半份JSON.md)。）
