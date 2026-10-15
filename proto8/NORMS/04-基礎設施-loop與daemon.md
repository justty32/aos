← [回入口 NORMS.md](../NORMS.md)｜主題：**基礎設施／loop、daemon**｜概念：[CONCEPTS 基礎設施 § loop 與 daemon](../CONCEPTS/03-基礎設施.md#loop-與-daemon)｜規範：本檔｜實作：[lib loop.md](../lib/loop.md)、[lib daemon.md](../lib/daemon.md)

同主題：[inst](03-基礎設施-inst.md)｜loop 與 daemon｜[窗](05-基礎設施-窗.md)｜[命令列與指示詞](06-基礎設施-命令列與指示詞.md)｜[組合子](07-基礎設施-組合子.md)

# 基礎設施／loop、daemon

loop 與 daemon 的 state／ctl 窗（含必填 N-19）在[窗](05-基礎設施-窗.md)。

## loop（與 daemon 共用）

- **N-31**（原 h6，草稿）loop／daemon 的 stdout：每真的跑了一次 inst 吐一份 `{run, code, ms}`（daemon 沒 inst 就不吐），結束時吐一份總結，`end`＝最後狀態字串（`"done"`／`"stopped"`）。（10-14 深夜）
- **N-44**（10-15 收工後定，草稿）loop.json 選填 `stop_on_end`（布林，預設 false）：包的是 aos-fsm 時，某一次的 stdout 裡出現 fsm **結束那拍的那行**（N-40：帶 `"end": true` 與 `from`、`to`）＝不再起新的一次，loop 正常結束（`end`＝`"done"`）。訊號走 stdout 不走結束碼（N-43 只定 0／非 0）、不走 ctl（不必寫 stop、不必輪詢）。inst 寫了 stdout 檔就讀這次寫進去的那段；沒寫＝loop 自己替它接一個暫存檔。daemon.json 照 N-28 同義。（使用者 10-15 收工後「都按照推薦」，主控推薦：「fsm 走到 end 時，loop 應直接停，不靠輪詢 ctl」）

## daemon

> **daemon 兩義**：①[C-04](../CONCEPTS/01-設計理念.md) 說的 daemon＝aos 與 Linux 之間的借階層（Linux 那邊的事全在這層）；②這裡的 daemon＝管一群 loop 的程式（`aos-daemon`，C-36）。[名詞表](../CONCEPTS/附錄1-名詞.md)兩列都留。

- **N-10** 指令式控制＝往資料夾放 `名字.json`，一個檔一條指令；處理完變成 `名字.json.done`，內容是一問一答 `{"request", "ok", "result"|"error": {"code", "msg"}}`；`.done` 只在終局才出現；`ok` 是唯一要看的，`code` 只供參考；`.done` 由丟指令的人清。（10-12）
- **N-28**（候選 g，10-14 夜末使用者拍板，草稿）**daemon.json 是 loop.json 的嚴格超集**：同名 key 同義（節奏、窗、收尾、`id`）。`inst`＝daemon 自己每拍串行跑一次的身體，跑法跟 loop 一樣（阻塞到它結束），在 daemon 裡**選填**（純監工不需要），在 loop 裡維持必填。daemon 多的是 `children`（並行、長壽的子 loop）、`policies`、`control_dir`、`work_dir`（以及 table 窗等）。**`control_dir` 改選填**：指令資料夾是一種窗，沒給就不掃（N-13）。一份合法的 loop.json 直接丟給 aos-daemon 也要能跑。daemon 與 loop 同名 key 語義相同，預設值可不同（daemon `times` 預設不限、`interval_ms` 200；loop `times` 1、`interval_ms` 0），所以沒寫 times 的 loop.json 丟給 daemon 會一直跑（原 h9，10-14 深夜定）。`policies.child_exit` 是一個 aos-inst TARGET（寫法同 fsm 的格；子項結束時問它怎麼辦），`children` 每項是一個 aos-loop 設定的 TARGET（路徑、`檔#/位置`，或內嵌物件）（原暫定 f，10-15 使用者『全定』）。daemon 不另留 save 檔：`table` 窗（N-14 的一種，只有 daemon 寫）就是 save 檔，`load: true`（旗標 `--load`）起來時讀它接回，所以 load 要有 table 窗（原暫定 d，10-15 使用者『全定』）。推翻 10-12「daemon 沒有 inst、身體內建＝掃資料夾」。（10-14）
