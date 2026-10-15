# 2026-10-14 aos-fsm：十題拍板、改寫清單、風險、未決

← [JSON 入口](../2026-10-14-json-entry.md)｜上一份：[07-fsm樹與一拍](07-fsm樹與一拍.md)｜下一份：[09-daemon套fsm](09-daemon套fsm.md)

## 13. 十題拍板（使用者；★＝沒選 AI 推薦）

1. 本體抽成通用 aos-fsm；agent＝fsm＋預設表資料夾，aos_agent.py 不存在。
2. ★ 方法表只用明寫：`states` 一定寫在 agent.json，不靠慣例檔名 `inst-<state>.json`；查不到＝錯（走第 5 題）。
3. ★ 不做繼承：沒有 extends、沒有搜尋路徑；每個 agent 寫整張表，想沿用就一格一格寫範本路徑或 `$ref`；範本資料夾不是父類。
4. ★ 下一狀態：「inst 回傳和結束碼都可以。aos fsm 用 inst 回傳」→ 兩種概念上都正當；aos-fsm 採 stdout 最後一份的 `next`。（10-14 晚改：沒吐＝看表上靜態 next，表也沒有才留原狀態，見 [10](10-lisp組合子.md)。）
5. 出錯：有 `error` 格就跳去（帶原狀態與錯），沒有就留原狀態＋`last_error`；沒 ret（被殺一半）重進同狀態、標 `prev.interrupted`。
6. 現在狀態記在 state 窗（phase＋data）。state 窗**必填**，缺 key 或 `null` 報錯不執行（10-14 夜使用者定，比照 N-19，見 [13](13-動工前拍板.md)；原「沒開＝每拍從 `start` 起」作廢）。
7. think 同步／非同步：規範只說走到 think 就跑那格 inst，阻塞等回覆或丟請求下一拍再看**兩種都合規**；換一格即可；都不自己 setsid／fork。**基礎實作先做阻塞版**（10-14 夜改，見 [12](12-七題回覆.md)；原「預設非同步」的說法作廢）。這解掉 aos-llm／agent 規劃頁的 Q1。
8. loop 不加鉤子。
9. daemon 策略格（child_exit）重做 daemon 時再接，預設維持現行為。
10. inst 不加 pre／post／on_timeout。

另：共同核心＝方法表 lib（`aos_methods.py`：載表、呼叫一格、取 stdout 最後一份），不含繼承。使用者補定：每格的值＝aos-inst TARGET（檔、資料夾、`#/位置`）；fsm 可巢狀。

## 14. 已定事項要改寫的

- 規劃頁 §3／§4 agent.json 加 `start`、`states`（值＝TARGET）、選填 `end`；aos_agent.py 改為通用 aos_fsm.py＋預設表資料夾。
- §7 四態從寫死變成預設表；思考拆成子 fsm（ask → waiting），加選填 `error` 格。
- §4 steps.jsonl 每行改成 fsm 通用的 `{step, from, to, code, ms}`＋方法 ret 的 `data`。
- Q1 已解：規範中立、換一格即可；基礎實作阻塞版（C-25 由非同步那格解，不是預設）。
- Q5 保險絲拆家：10 分鐘掛在 aos-llm 單子的 `timeout_ms`＋waiting 格自己的期限；loop 單子的 `timeout_ms` 變外層（≥ 最長方法）；`max_steps` 歸 fsm（自上次回 `start` 起算）；retries 歸 ask／waiting 方法；8000 字歸 tool 方法。
- Q4 問模型＝通用規則的特例：fsm 偵測沒 ret 就以 `prev.interrupted` 重進，tool 方法再決定問模型。
- Q8 agent-ctl.json、Q11 agent.lock/、Q12 心跳可選：上移為 fsm 的窗與設定 key。
- Q13 不做信箱：決定不變；但乙版 think 的請求資料夾本身就是一個 N-16 信箱（agent 寄、處理者收）；以後 agent 自己收信＝換 idle 那格。
- D-5：方法 inst 寫 `stdin_inherit`＝Conflict（fsm 一定蓋 stdin）。D-1：`--start`、`--max-steps` 鏡射，`states` 不鏡射（Q10）。
- N-11：表屬身體類、不走 ctl 改；但每拍是一次啟動，改表或方法檔下一拍生效（自我改進入口，Q3「改壞靠 git」照用）。
- 候選 argv[0] 規矩「不自己 setsid」順便定案：想非同步就丟請求資料夾，不背景 fork。
- lib：ctl-state.md 加一列 fsm（state 窗必填、七值照舊，FSM 狀態名放 `phase`）；README 相依鏈與 code map 加 `aos_methods.py`、`aos_fsm.py`。
- 10-12 inst-json §5「那個 inst 是狀態機切換程式」仍成立，切換程式變通用；規劃頁 §9 巢狀（畫家用畫筆）不變，而且「一格＝資料夾＝子物件」跟它同一個道理。

## 15. 風險

- 每拍多兩層行程（loop → inst → fsm → inst → 方法），巢狀再加兩層；空拍約 3～5 次 Python 啟動 ≈ 0.1～0.3 s，1 s 間隔可接受，百毫秒級不行。
- 除錯要看兩層 state 窗（外層 phase、think/state.json 的子 phase）；steps 每行記 from／to，`work/N-args.json`、`N-ret.json` 留每格的進出可重播。
- 寫到一半被殺（history 寫了、ret 沒出）下一拍會重進同狀態；方法冪等與否規範不保證（N-20），方法自己顧。
- 相對路徑：範本 inst 以 agent 資料夾（或 inst.json 的 `cwd`）跑，`argv[0]` 與檔名寫絕對路徑或靠 PATH。
- 乙版要先有人在處理請求資料夾（worker loop、服務或人），多一個前置動作；沒人處理＝waiting 一直等到期限。（基礎實作先做甲版，所以第一個 demo 沒這個前置。）

## 16. 新增未決

- ~~巢狀三題~~（**已定**，全照推薦，見 [07 §12.4](07-fsm樹與一拍.md)）。
- 請求資料夾的 key 名、誰負責處理（第一版 demo 用一個 worker loop？）、waiting 期限數字。
- aos-fsm 哪些進規範、哪些只是程式說明，等動工時定（[NORMS 待定](../../NORMS/08-待定.md)）。
