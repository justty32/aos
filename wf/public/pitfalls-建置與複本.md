# wf/public/pitfalls-建置與複本 — 暫存樹建置、乾淨複本跑測試、試真東西別碰原件

← [wf/public](README.md)｜[pitfalls 總頁](pitfalls.md)｜整套驗收的跑法見 [patch-and-commit「驗收跑全套」](patch-and-commit.md)

每條：適用、做法、驗過、出處、投稿。**驗過**＝投稿隊實際照做成功。

## 暫存樹編 impls 的 C++：make 目標要用 `<名字>_main`

- **適用**：在暫存樹（`~/code/<線>-1114/build`，CMake 指向暫存的 `src/proto8/impls`）改了 aos-exec、aos-loop、aos-llm-kernel 這類 C++，要編好再跑 `impls/*/tests`。
- **坑**：`make aos-exec` 只編出靜態庫 `lib/lib<名字>.a`，`impls/<名字>/bin/<名字>` 不會重編。測試把 `impls/<名字>/bin` 放在 PATH 最前面，跑到的是舊 bin，看起來像改壞了。
- **做法**：
  ```
  cd ~/code/<線>-1114/build
  make help | grep <名字>      # 會看到 <名字> 和 <名字>_main 兩個目標
  make -j8 aos-exec_main aos-loop_main aos-llm-kernel_main
  ls -la ../src/proto8/impls/<名字>/bin   # 時間要是剛剛
  ```
- **快速判斷**：測試紅了、錯誤訊息卻還是改之前的字，先看 bin 的修改時間。
- **驗過**：ok-misc 11-14，T17。只編 `aos-exec` 時 6 紅，改編 `aos-exec_main` 後全綠。
- **出處**：`proto8/thinking/2026-11/14/misc-1114.md`
- **投稿**：ok-misc（`wf/temp/ok-misc/public-submit/暫存樹編C++要編_main目標.md`）

## 乾淨複本要帶齊依賴：wf/tools 測試連 proto8 一起抄，impls 測試連 lib 一起抄

- **適用**：在 repo 外的乾淨複本跑 `wf/tools/tests` 或 `impls/*/tests`。
- **坑**：
  - 只抄 `wf/tools`：`test_a_held_kernel_request_stays_at_the_gate` error，`ModuleNotFoundError: No module named 'test_kernel_gate'`（test_quiet 從 `proto8/lib/agent/kernel_gate/tests` 借 test_kernel_gate）。
  - 只抄 `impls` 和 `knowledge`：aos-llm 的 test_full 找不到 `proto8/lib/base/llm_fake` 而 error。
  - 都不是程式壞了。
- **做法**：wf/tools 的測試用 `git archive HEAD wf/tools proto8/lib proto8/py proto8/cmd | tar -x -C <複本>`；impls 的測試整個 `proto8` 一起抄。再照 [06 第 2 條](../workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md) 經清環境腳本跑。
- **快速判斷**：只紅一兩支、又是 ModuleNotFoundError 或找不到檔，先懷疑複本抄得不夠全。
- **驗過**：ok-pilot 11-14，驗 f446f3d86 時：只抄 wf/tools，test_quiet 1 支 error；連 proto8/lib、py、cmd 一起抄，7/7 綠（審稿對過 `wf/tools/tests/test_quiet.py` 第 13、106 行）。ok-misc 11-14 遇到 llm_fake 那種。
- **出處**：`wf/tools/tests/test_quiet.py`；commit f446f3d86 的驗收；`wf/temp/ok-misc/wrapup-1114/經驗.md` 第 5 則
- **投稿**：ok-pilot（`wf-tools測試要連proto8一起抄.md`）；ok-misc 收尾稿併入

## 乾淨複本的標準跑法：git archive＋疊檔、執行檔自己編、PATH 不撿到活樹的

- **適用**：要交 commit 前驗自己的改動；main 已往前走、暫存樹落後時尤其要這樣跑。
- **做法**：
  1. `git archive HEAD proto8 | tar -x -C <新夾>`，再只把要交的檔 cp 上去。工作樹裡別人沒交的改動不會混進結果。
  2. 跑法：`env -i PATH=/usr/bin:/bin HOME=$HOME PYTHONDONTWRITEBYTECODE=1 TMPDIR=<新夾>/tmp python3 -m unittest discover -s <tests>`，或經自己的 clean.sh。clean.sh 會換 cwd，`-s`、`-t` 一律給絕對路徑。
  3. 乾淨複本不帶 `impls/*/bin`（[06 第 6 條](../workflows/dispatch/aos-teams/06-公司WSL活樹與任務書硬規則.md)）。要 bin 就用複本自己的原始碼編：另開建置夾 `cmake -S <複本>/proto8/impls -B <新夾>`，再 `make <名字>_main`；**不要從別處抄 bin 進去**（ok-limits 抄了、不符第 6 條、重來）。交件信寫明 bin 從哪來。沒編的話改前改後都會紅同一批，只看差異。
  4. PATH 不要撿到 `~/.local/bin` 的舊執行檔：寫一支 run.sh 把 PATH 換成「暫存樹各 `impls/*/bin`、`cmd/*/bin`＋`/usr/bin:/bin`」。會把 `~/.local/bin` 排最前的測試（wf 測試、test_daily）再給一個假 HOME，它的 `.local/bin` 連到暫存樹的 bin。
  5. `templates/tests` 從上層 discover 不會進 `agent-fsm` 子夾，要另外跑。
  6. 改前、改後各一份複本，用同一支腳本逐夾跑、各出一份 SUMMARY，`diff` 兩份就知道多紅哪幾支（ok-fsm 的 `~/code/fsm-1114/runall.sh <proto8 複本> <輸出夾>`；ok-pilot 的 `~/code/ok-pilot-rm-1114/suite/run.sh`，一個 commit 動幾十個檔時只接受「測試數變多且 OK」這種差異）。
  7. commit 訊息裡的測試數字，在「真的要交的那個 commit」的 archive 上再跑一次才寫（ok-kmsg 交完才補跑，第二筆放行卡在這個結果上）。
- **驗過**：ok-onboard 11-14（guard 152 個測試）；ok-astra；ok-limits（`ws/who-clean-892f5e962/build.sh`、`ws/phase1/build-rehearse.sh`）；ok-sec（Q10 b1 先用到舊 aos-post、在測試信箱寫出舊格式的信，改走 run.sh 後全綠，`/tmp/ok-sec-q10-tools/run.sh`）；ok-fsm（改前改後只多紅一支）；ok-kf。
- **出處**：`wf/temp/{ok-onboard,ok-astra,ok-limits,ok-sec,ok-fsm,ok-kf,ok-misc,ok-kmsg}/wrapup-1114/經驗.md`

## 資料列多了新鍵：既有斷言連新鍵的值一起比，不要剝掉再比

- **適用**：資料列多了一個鍵（例：history 列的 `aos`），既有測試斷言整列相等。
- **做法**：每條斷言改成連新鍵的正確值一起比（信名、answer_to 清單），不寫「先 pop 掉再比」。既有測試順便鎖住新行為。
- **驗過**：ok-pilot 11-14，fsm、eca、aos-agent、subagent 各處的斷言。
- **出處**：`wf/temp/ok-pilot/reply-match/交件.md`「改了哪些既有斷言」；`wf/temp/ok-pilot/wrapup-1114/經驗.md`（head-tools 代寫）

## 暫存 git 的 commit 會吃進 `.orig`、`__pycache__`

- **適用**：在暫存樹用 `git add -A` 留存檔點，之後從那裡匯出補丁或點名檔案交件。
- **坑**：`patch` 留下的 `README.md.orig`、測試產生的 `.pyc` 會被夾帶。
- **做法**：跑測試帶 `PYTHONDONTWRITEBYTECODE=1`；交件只點名真正的檔；匯出補丁時照 [patch-and-commit「匯出補丁」](patch-and-commit.md) 排除 `__pycache__`。
- **驗過**：ok-astra 11-14（ok-fsm 審稿時也提醒）。
- **出處**：`wf/temp/ok-astra/wrapup-1114/經驗.md`

## 試真東西別碰原件

- **適用**：要在使用者的試驗場（或任何活的 stack）上驗某個改動，例如換身體。
- **做法**：`cp -a` 整份到暫存夾；把複本裡用不到的 stack 改名成 `.orig`，只起要驗的那隻；驗完 `aos-daemon-ctl -d <複本>/.stack shutdown`。原件一行不動。
- **驗過**：ok-kf 11-14，驗換身體時照做。
- **出處**：`proto8/thinking/2026-11/14/kernel-framework-1114.md`
- **投稿**：ok-kf（`wf/temp/ok-kf/public-submit/pitfalls-shell-and-reviewers.md`）
