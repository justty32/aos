← [回入口 NORMS.md](../NORMS.md)｜主題：**基礎設施／loop、daemon**｜概念：[CONCEPTS 基礎設施 § loop 與 daemon](../CONCEPTS/03-基礎設施.md#loop-與-daemon)｜規範：本檔｜實作：[lib loop.md](../lib/loop.md)、[lib daemon.md](../lib/daemon.md)

同主題：[inst](03-基礎設施-inst.md)｜loop 與 daemon｜[窗](05-基礎設施-窗.md)｜[命令列與指示詞](06-基礎設施-命令列與指示詞.md)｜[組合子](07-基礎設施-組合子.md)｜[定義與工作區](10-基礎設施-定義與工作區.md)

# 基礎設施／loop、daemon

loop 與 daemon 的 state／ctl 窗（含必填 N-19）在[窗](05-基礎設施-窗.md)。

## loop（與 daemon 共用）

- **N-31**（原 h6，草稿）loop／daemon 的 stdout：每真的跑了一次 inst 吐一份 `{run, code, ms}`（daemon 沒 inst 就不吐），結束時吐一份總結，`end`＝最後狀態字串（`"done"`／`"stopped"`）。（10-14 深夜）
- **N-44**（10-15 收工後定，草稿）loop.json 選填 `stop_on_end`（布林，預設 false）：包的是 aos-fsm 時，某一次的 stdout 裡出現 fsm **結束那拍的那行**（N-40：帶 `"end": true` 與 `from`、`to`）＝不再起新的一次，loop 正常結束（`end`＝`"done"`）。訊號走 stdout 不走結束碼（N-43 只定 0／非 0）、不走 ctl（不必寫 stop、不必輪詢）。inst 寫了 stdout 檔就讀這次寫進去的那段；沒寫＝loop 自己替它接一個暫存檔。daemon.json 照 N-28 同義。（使用者 10-15 收工後「都按照推薦」，主控推薦：「fsm 走到 end 時，loop 應直接停，不靠輪詢 ctl」）（10-16：agent 不再造 ret.json、定義改成 `.aos/` 資料夾（C-50 改字）。**10-16 KISS 重審拍板 4**：agent 的定義不含 loop、由外面的 loop 驅動（N-53）——外面那個 loop 正是靠本條在 agent 走到 end 時停，所以本條留（頂層判斷）；「認法改成只看頂層 `end: true`、不認 `from`／`to`」（重審 3.13）沒定。）

## daemon

> **daemon 兩義**：①[C-04](../CONCEPTS/01-設計理念.md) 說的 daemon＝aos 與 Linux 之間的借階層（Linux 那邊的事全在這層）；②這裡的 daemon＝管一群 loop 的程式（`aos-daemon`，C-36）。[名詞表](../CONCEPTS/附錄1-名詞.md)兩列都留。

- **N-10**（10-12 定；**10-16 使用者刪**）原「指令式控制資料夾」（往資料夾放 `名字.json`＝一條指令、回 `名字.json.done` 一問一答）整套刪。daemon 表上有誰改由 ctl 宣告（N-54）；暫停、停掉某個子 loop＝直接寫它的 ctl（N-06）；看它＝讀它的 state 窗。（使用者 10-16：「不留」，[KISS 重審拍板 1](../thinking/2026-10-16-kiss-recheck.md#使用者拍板10-16)）實作待改：`aos_daemon_folder.py`、`ctl_dir` 還在。
- **N-28**（候選 g，10-14 夜末使用者拍板，草稿）**daemon.json 是 loop.json 的嚴格超集**：同名 key 同義（節奏、窗、收尾、`id`）。`inst`＝daemon 自己每拍串行跑一次的身體，跑法跟 loop 一樣（阻塞到它結束），在 daemon 裡**選填**（純監工不需要），在 loop 裡維持必填。daemon 多的是 `children`（並行、長壽的子 loop）、`policies`、`work_dir`、`adopt`。（原有 `ctl_dir`＝N-10 指令資料夾，10-16 隨 N-10 刪；table 窗 10-16 併進 state 窗，見下。）一份合法的 loop.json 直接丟給 aos-daemon 也要能跑。daemon 與 loop 同名 key 語義相同，預設值可不同（daemon `times` 預設不限、`interval_ms` 200；loop `times` 1、`interval_ms` 0），所以沒寫 times 的 loop.json 丟給 daemon 會一直跑（原 h9，10-14 深夜定）。`policies.child_exit` 是一個 aos-inst TARGET（寫法同 fsm 的格；子項結束時問它怎麼辦），`children` 每項是一個 aos-loop 設定的 TARGET（路徑、`檔#/位置`，或內嵌物件）（原暫定 f，10-15 使用者『全定』）。**daemon 收子項只看它自己需要的**（C-52；10-15 深夜使用者「不留」）：是物件、沒 `inst` 有 `argv` 就包成跑一次、ctl／state 沒寫就自己放；裡面的 loop key 與 inst 一概不驗、原樣灌給子 loop，寫錯了子 loop 自己退 1、錯在它的 stderr，daemon 只看到它結束（原 h15「add 先驗 inst」拿掉）。daemon 不另留 save 檔：**子項表寫在 daemon 自己的 state 窗**（`children` 一列一項：id、pid、啟動時間、`phase`…；10-16 改，原本另開一扇 `table` 窗，KISS 重審 3.3 照 Fable 推薦併進 state 窗），state 窗就是 save 檔。**`adopt`**（布林，**預設 `true`**；旗標 `--adopt`）：daemon 重起時讀自己上次的 state 窗、把還活著的子 loop 接回（pid＋啟動時間對得上才認，N-17），不重起它們；寫 `false`＝不接回。state 窗本來就必填（N-19），所以不必另外要求什麼；第一次起來沒有舊的 state 就沒東西可接。心跳照 N-17／N-32 留。（使用者 10-16：「給選項，默認留」，[KISS 重審拍板 2](../thinking/2026-10-16-kiss-recheck.md#使用者拍板10-16)；key 名 `adopt` 是頂層照 C-54 挑的——說的是「認領活著的子 loop」，表窗併掉後已沒有一份「save 檔」可 load；取代原 `load`（預設 false，原暫定 d，10-15 使用者『全定』）。實作待改：程式還是 `load`、預設不接回、另寫 table 窗。）推翻 10-12「daemon 沒有 inst、身體內建＝掃資料夾」。（10-14）10-16：子項若是一份定義，照 [N-47](10-基礎設施-定義與工作區.md) 用 `aos exec 子項的工作區 定義` 跑（實作待改）。
- **N-54**（10-16 定，草稿）**daemon 表上有誰，寫在 daemon 的 ctl 窗**：daemon 的 ctl 多認一個 `children`＝「我要表上有誰」，每項寫法同 N-28 的 `children`；照 N-06 是整份期望——ctl 有 `children` 就照它（多出來的起、少掉的收掉移除），沒寫＝回 daemon.json 的 `children`。要暫停、停掉、改某個子 loop 的節奏＝直接寫它的 ctl（誰都可以寫，N-06），要看它＝讀它的 state 窗；daemon 回報實際的表在自己的 state 窗（N-28）。這是 N-11「ctl 只能蓋節奏類 key」的例外（頂層判斷：刪了 N-10 之後，增減子項只剩這條路）。（使用者 10-16 對 N-10：「不留」，照 [KISS 彙整 3.1](../thinking/2026-10-15-kiss/README.md) 原推薦；[KISS 重審拍板 1](../thinking/2026-10-16-kiss-recheck.md#使用者拍板10-16)）兩個人同時改 ctl 會互相蓋掉（後寫的算），見[待定](08-待定.md)。實作待改。
