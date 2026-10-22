# aos（proto8）跟 s6、runit 的對照

← [notes](README.md)｜[proto8](../README.md)｜2026-10-22，AI 寫（使用者 10-21 晚：「關於s6/runit的對照，納進之後要做的事情中吧」）

**這份只是對照與「可借鏡的點」，不是規範**：條文以 [CONCEPTS](../CONCEPTS.md)、[NORMS](../NORMS.md) 為準，要借哪一點由使用者決定（鐵律 5）。s6／runit 的事實都附原始文件連結（skarnet.org、smarden.org）；aos 這邊以 [bin README](../bin/README.md) 與條文為準。

一句話的背景：s6（skarnet.org）和 runit（smarden.org）都是 daemontools 一脈的「服務監管」工具——一支監工盯一個長壽程式，死了就重起；設定就是一個資料夾，裡面放 `run` 等小檔。這跟 aos 的「資料夾＝程式」、loop／daemon 是同一個家族的想法，所以對照起來特別有用。

<!-- wf-nav -->
## 分檔

| 分檔 | 涵蓋 |
|---|---|
| [01-chain-loading與環境](s6-runit/01-chain-loading與環境.md) | 1. chain loading（execline／chpst 一路 exec vs aos-exec 一路往下）、2. envdir vs `.env` |
| [02-監管與重啟](s6-runit/02-監管與重啟.md) | 3. 監管樹（s6-svscan／s6-supervise、runsvdir／runsv vs aos-daemon／aos-loop）、4. 重啟策略、5. readiness |
| [03-日誌狀態控制訊號](s6-runit/03-日誌狀態控制訊號.md) | 6. 日誌、7. 狀態檔、8. 控制、9. 訊號 |

每一點都分四段：s6／runit 怎麼做、aos 怎麼做、可借鏡、aos 刻意不同的地方。

## 最值得先看的五點

**一、別把 aos-exec 養肥，交給鏈上的小程式。** 換使用者、資源上限、拿鎖、一個祕密一個檔這些事，argv 陣列入口前面接 `chpst`／`s6-envdir` 就做得到，aos-exec 只做 N-59 那幾件；以後想加旗標前先問「能不能交給鏈上另一支」（[01 § 1](s6-runit/01-chain-loading與環境.md)）。

**二、aos 的結束碼 10 不是孤例。** s6 的 `finish` 退 125、`s6-svc -O` 也是「被管的那個說別再叫我了」（[02 § 4](s6-runit/02-監管與重啟.md)）。

**三、若日後要做自動重起，s6 的防爆衝規則現成可抄。** 兩次起動至少隔 1 秒、穩定跑過一段才死就不等（[02 § 4](s6-runit/02-監管與重啟.md)）。

**四、子項 stderr 的輪替，照 s6-log／svlogd 的 `current`＋帶時間舊檔＋留 n 份。** 全是「先寫再改名」的檔案操作，跟 N-05 同路（[03 § 6](s6-runit/03-日誌狀態控制訊號.md)）。

**五、aos 已經比 s6 多的：`adopt` 接回。** s6／runit 靠「監工不會死」，aos 靠 pid＋啟動時間＋`boot_id` 認回活著的子 loop；若想「換 daemon 版本不停子項」，s6 的 SIGQUIT（只有監工走）是一個訊號的差別——方向題（[02 § 3](s6-runit/02-監管與重啟.md)、[03 § 9](s6-runit/03-日誌狀態控制訊號.md)）。

## 跟 aos 現有原則的衝突或張力

沒有找到「借鏡點跟 CONCEPTS／NORMS 條文直接打架」的地方。有四處要注意：

**子項 stderr 會一直長。** N-28 寫「子 loop 的輸出檔不無限長」「stderr 只在出錯時 append」，bin 版 aos-daemon 是把 stderr 全部 append 到小格的 `stderr`、不輪替。這是現況與條文的落差（N-28 已自註「完整實作待補」，10-22 前叫標準實作），不是這份對照造成的。〔10-22 註：N-28 已照程式改寫成「aos 不保證子項輸出不無限長、使用者自己承擔」，見 [NORMS/04](../NORMS/04-基礎設施-loop與daemon.md)。〕

**自動重起。** 監管工具的核心就是自動重起，aos-daemon 偏偏不做（使用者 10-20「照預設」）。這是選擇、不是衝突；只有在使用者想改時，s6 的規則才派得上用場。

**readiness、事件通知、logger 管道都是 fd／管道機制。** 跟 C-64「用檔案（而不是程式之間的管道）」方向相反，所以只能借形狀（例如 state 窗多一欄），不能照搬做法。

**用 `chpst`／`s6-envdir` 接在 argv 陣列前面**，`argv[0]` 沒 `/` 就要走 PATH。C-61「工具的地址不用 PATH」講的是 agent 的工具，aos 自己的 `aos-exec`、`aos-loop` 本來就走 PATH，所以不衝突；只是系統上得裝這些程式。
