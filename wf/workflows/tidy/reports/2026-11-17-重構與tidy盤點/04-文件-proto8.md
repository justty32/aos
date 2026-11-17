← [入口](../2026-11-17-重構與tidy盤點.md)｜涵蓋：proto8 文件的 tidy 清單｜上一份 [03-文件-wf](03-文件-wf.md)｜下一份 [05-repo層與裁題](05-repo層與裁題.md)

## 文件 tidy：proto8

數字：proto8 非封存 >8 KB 的 md：thinking 11 月 410 份、10 月 2 份、docs 28 份、各夾 README 14 份、各 docs 子夾十多份；`proto8/docs` 沒有 >300 行的檔（共 2480 行）。thinking：10 月 297 檔 1.18 MB，11 月 1081 檔 13.99 MB。

| # | 檔或夾 | 現況（證據） | 問題 | 建議做法 | 工作量 | 風險 | 已知／新 |
|---|---|---|---|---|---|---|---|
| D1 | `thinking/2026-11/13`、`/14` | 13：120 檔 3.09 MB；14：255 檔 4.70 MB；188 份 md >8 KB；AI 產出稿（fable稿／蒐集／備料）88 檔 1.77 MB，最大 `14/board-1114/02-fable稿.md` 60 KB | 還沒提取進 docs、還沒精簡 | 先跑 thinking→docs 提取 11-13～11-17，再照 11-04 的做法分批精簡（裁題 Q1） | 大 | 中（有題還在進行） | 新 |
| D2 | `14/release-1114/06-草稿/v1`、`v2` | 共 1.48 MB；`landing.zh-1280.png`（329892）、`landing-b.zh-1280b.png`（237423）兩對 md5 相同（頂層核過一對） | 網頁已上線到 repo 根 `docs/`（`9211e9c58`），草稿重複 | 見裁題 Q2 | 小 | 低 | 新 |
| D3 | `13/*.html`＋`decide_*.json` | `aos-wu-1113-待你裁.html` 413687、`-r2-` 257004、`decide_20261113_wu.json` 243372；只有 wu 這份沒有 `.reply.txt`；日索引第 16 行寫「128 題，已答 19」 | 已裁完的頁仍佔大空間；wu 是否被 r2 取代沒把握 | 精簡 11-13 時一併判 | 小 | 中 | 新 |
| D4 | thinking 索引落後 | `thinking/README.md:14` 2026-11 寫「142 份、11-01～11-12」（頂層核過）；`2026-11/README.md:21` 11-13 寫「份數 1」但日 README 列 39 份；11-15、11-16 沒夾、11-17 未進 git | 索引沒跟上 | 照日 README 重算；11-17 那份進 git 時月表補一列 | 小 | 低 | 新 |
| D5 | thinking 壞連結 70 條（41 檔） | 至少 17 檔指已刪的 `impls/aos-llm-kernel/…`；`release-1114/00-主紀錄/v1-規劃段.md` 12 條；`kernel-limits-1114/B1`、`B2` 路徑多了 `thinking/`；`13/eca-main-six-fixes.md:53`、`07/daemon-prune/README.md:36` 指不存在的 `common/code-map.md`；其餘是 `連結`／`link` 佔位字 | 指向已不在的檔 | 精簡時一起改純文字 | 小 | 低 | 新 |
| D6 | 「11-14 前是 C++ 的 aos-llm-kernel」沿革句 | docs、docs 子夾、README 共 24 處，例 `CONCEPTS/01-設計理念/01-C-01～C-48.md:11`、`NORMS/05-基礎設施-窗/02-N-09～N-11.md:11`、`impls/docs/01-現況與地圖與依賴.md:5,25`、`lib/aos/kernel_llm/README.md:5`（寫「待換樹時刪」，頂層核過，但 `726f73952` 已刪）；`knowledge/aos/cli/parts/llm_kernel.json` 也有一句 | 違反「沿革只留結論」 | 改現在式 | 中 | 低 | 新 |
| D7 | C-54 R13、R8（`CONCEPTS/…/C-54-命名方法/02-R8～R13.md:14、:8`） | R13 例子還寫「llm 領域有 `aos-llm-kernel` 與 `aos-llm` 兩支」；R8 例子 `budget` 的 `max_calls`、`max_tokens` 現在只見於 `lib/aos/kernel_llm/tests` | 例子指向已移除的程式；R8 沒把握 | R13 換現有例子（上次對讀建議的「改寫成通例」可一起）；R8 對 Python 版核一次 | 小 | 中（條文措辭，要對讀） | 部分已知 |
| D8 | `aos-proto8.pth` 沿革句 | `proto8/README.md:25`、`cmd/README.md:31`、`cmd/aos-agent/docs/04-搬家/04-兩台輪流.md:27` 都寫「11-15 起不再寫」；`install.sh --uninstall` 還會去拿掉舊的 | 沿革句；`--uninstall` 拿舊檔算舊版相容 | 文件改現在式；install.sh 那段要不要留見裁題 Q8 | 小 | 低 | 新 |
| D9 | 各夾 README 超標 | `cmd/aos-agent/README.md` 52298（第 52～85 行是 22 KB 清單，頂層核過大小）、`lib/aos/kernel/README.md` 30987、`lib/agent/guard/README.md` 29002 | >8 KB、條列 >1 KB | 先收斂再拆；guard 等審完 | 中 | 中 | 新（上次只掃日期密的檔） |
| D10 | docs 子夾超標 | `templates/docs/02-agent-fsm.md` 40715、`lib/docs/03-索引-agent等.md` 39788、`cmd/docs/03-aos-daemon-ctl.md` 32772、`kernel/docs/02-kernel-modes.md` 29906 | 使用手冊類，觸發 A | 同上 | 中 | 中 | 新 |
| D11 | `NORMS/附錄1-條號表.md` 等附錄 1～3 | 附錄 1 18709 B、150 個日期 | 沿革句；上次列「要不要整份清請使用者定」 | 裁題 Q9 | 中 | 中 | 已知 |
| D12 | `NORMS/04…/02-N-28.md` | 48328 B，單一區塊 66 項 | 單條超標 | 上次已接受，暫留 | — | — | 已知 |
| D13 | 條文殘留舊例子 | `CONCEPTS/01-設計理念/06-C-68～C-72.md:7` 例子仍寫 `agent-bob/`；`NORMS/08-待定/01:7` 仍引「python版本可以刪掉了」；`CONCEPTS/abbr.json:209` 例子 `proto8/demo` | 指向已不在的東西 | 照「不存在的東西就刪掉」換例子 | 小 | 中（條文） | 部分已知 |
| D14 | `knowledge/README` 第 9、17 行 | 「index 合起來」對「index 是視角」 | 上次列牴觸，沒把握是否牴觸 | 照舊留給使用者 | — | — | 已知 |
| D15 | 上次（11-12）報告留的 | 核過已改 11 項：N-25、P-06、P-27、P-05、`proto8/demo`（docs 只剩附錄3 與 abbr.json）、C-74 `AgentExists`、`py/README.md:17`、cmd/docs 的「N-28 的 10-29 補」、C-42、C-81、C-52 :27；還在：N-17（使用者裁 U，維持）、08-待定/01:7、knowledge/README、附錄 1 | 報告與 SESSION-LOG 第 17 行沒跟上 | W2 一起更新 | 小 | 低 | 已知 |
