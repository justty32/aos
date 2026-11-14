# WAIT_USER 舊帳 36 筆逐筆查證後怎麼改：37 個子項結案、17 個搬進使用者專區、2 件改列待派工（11-14）

← [2026-11-14](README.md)｜[WAIT_USER](../../../../wf/WAIT_USER.md)｜線 ok-pilot

## 結論

- 36 筆舊帳拆成 54 個子項：**A 結案 37、B 要你決定 16、C 要你親手做 1**（另 1 封 fyi 收用法提醒）。
- B、C 寫成 **14 封專區信**（decide 12、verify 1、fyi 1）：10 封 11-14 已寄、3 封 11-14 10:50 第二批寄、1 封等回公司機對過名單再寄。
- `wait-user/` 從 36 行剩 14 行：01 剩 10、02 剩 2、03 剩 0、04 剩 2。留下的都改成一行「搬進專區哪封信」的指標，只有公司機暫存夾那筆保留原行。
- 2 件不用再等你、只是還沒人做的（hook 四種事件、two-machines T7 第 1～7 步），改列 WAIT_USER 新的一節「待派工」，由頂層排。
- 有 3 筆結案是推出來的，不是實際驗過的（下表標「推斷，非實證」）。

## 來源與授權

- repo-aos 11-14 來信：「把 WAIT_USER 的 36 筆舊帳逐筆重寫，寄進專區」。
- 使用者對 [view-1114](view-1114.md) 方向題 5（「`WAIT_USER` 的 36 筆舊帳要搬嗎？推薦 a 派一隊 opus 逐筆重寫寄進專區」）答「都按照推薦」＝a。
- 頂層 11-14 裁示（repo-aos）：A 照建議結案、從 wait-user 檔裡拿掉；不用等使用者只是沒人做的改列「待派工」；3 筆推出來的結案要寫明「推斷，非實證」；信分兩批寄，公司機那封等回公司機。

## 做法

ok-pilot 派 4 隻 opus 子 agent 並行唯讀查證（01 前 9 筆、01 後 7 筆、02、03＋04），每筆拆成子項、分 A／B／C、附證據（commit 雜湊、檔案＋節），B／C 寫成專區信；ok-pilot 驗格式、抽讀、修稿。逐筆原表在 [`wf/temp/ok-pilot/wu/`](../../../../wf/temp/ok-pilot/wu/SUMMARY.md) 各夾的 `status.md`。之後照表改 `wf/wait-user/01～04`：整筆 A 的拿掉，含 B／C 的整行換成一行指標，再改 WAIT_USER 類別表的數字、加「待派工」一節。

## 結案清單（37 個 A 子項）

「原檔」寫的是 `wf/wait-user/` 哪份、改寫前的第幾筆。理由、證據從各 `status.md` 抄（有縮短）。

| 原檔 | 條目 | 結案理由 | 證據 |
|---|---|---|---|
| 01 第 1 筆 | 待裁頁前三份 | 只是索引：精選頁 17 題、第二輪 43 題都已答，第二輪沒答的 5 題下午在對話裡裁了；大頁沒答的 109 題各自在 01 第 3～16 筆裡列著，不用再掛一筆總的 | `proto8/thinking/2026-11/13/裁定落地-1113.md` 開頭與「沒做的」；`decide_20261113_wu.json` 各 section 對到 01 第 3～16 筆 |
| 01 第 4 筆 | 11-13 其餘各線代定（4c） | 代定可翻、不擋工，依 user.md 沒回答的邊緣狀況通則結案：kernel 框架線己二 4～10、線未 1～9、線酉框架 1～3、eca-as-kernel 線酉 1～10；a2a 1～10；ops A1 2～7、B1 2～3、B3 1～4；線庚 5 條；工具路徑 1～5；index X2～X10；線乙 1～4 | 各檔「代定」節，11-14 user-advice 與之後的 commit 都沒翻案；線己二 9、10 已由 ok-kf 11-14 重做（`2d92205bf`、`374645271`）；線酉 6 有原話「提示注入這塊就是風險自己承擔」；線己二 6 有 K-F50 備註「可以用unset吧」 |
| 01 第 6 筆 | 程式碼整理第 1、9 題（6c） | 第 1 題隨 metainfo-views 結案、第 9 題 11-13 已裁（條目本身寫明） | 原條目；`decide_20261113_wu.json` cl-9＝A |
| 01 第 8 筆 | tidy 矛盾：N-17（8a） | 你 11-13 選「先不選」但留了原則「盡量只讓daemon相關的碰pid…推薦遵守。不遵守也沒差」；兩種讀法都不用改程式，只差把 N-17 的說法改成這句原則，是 agent 能做的文字活 | `裁定落地-1113.md` 第 98～102 行 |
| 01 第 8 筆 | tidy 矛盾：已裁的那幾處（8d） | C-42（11-13 B）、aos-teams 沙箱那句（11-13 A，入口已改「家機 codex 也用沙箱」）、P-05／P-06／P-27（r2 cv-*）、AGENTS 單機（W7，已寫兩台輪流） | `裁定落地-1113.md`；`wf/workflows/dispatch/aos-teams.md`「權限邊界」；AGENTS.md「開發環境」 |
| 01 第 9 筆 | 外部 MCP E1、E3、E4、E5、E7（9b） | 代定可翻、不擋工，依通則結案（E1 helper 遞通行碼、E3 通行碼檔寫法、E4 每輪警告、E5 沒實測〔agent 能自己驗〕、E7 網址與名字限制） | `proto8/thinking/2026-11/12/external-mcp/06-施工結果.md` §代定 |
| 01 第 10 筆 | 外部 MCP fsm 代定 G2、G5～G13 | 已施工、程式仍照代定；內部細節、可改回、沒有對外動作。G13 是你 Q2「統一」的做法，已照做。依通則結案 | `proto8/thinking/2026-11/12/external-mcp/08-fsm施工結果.md` §代定；G10 的 `net` 只是說明標記（`lib/mcp_freeze.py:106`），跟沙箱的 `net` 不相干 |
| 01 第 11 筆 | json 工具代定 D40～D49 | 已施工、在用（`json_len` 已進子 agent 那台）；錯誤句、輸出形狀等內部細節，依通則結案 | `proto8/thinking/2026-11/12/json-tools/04-aos-json下沉與len與jsonx-multi.md` §代定（接 D39） |
| 01 第 12 筆 | index-link 代定 L2～L12、`$ref` 代定 R1～R7 | 三題已裁、`#/` 已做；其餘是路徑怎麼接、壞了怎麼標的細節，後來又被 ref-index-unify 統一一次；R7 是邊緣狀況。依通則結案 | `proto8/thinking/2026-11/12/index-link.md` §代定（可翻）；`proto8/thinking/2026-11/12/ref-hash.md` §代定（可翻） |
| 01 第 13 筆 | eca 子 agent 代定 T1～T9（12a） | 已施工、在用（子 agent 拿 `mcp__aos_sub__*`）；依通則結案 | `proto8/thinking/2026-11/12/eca-task-subagent.md` §代定清單；`proto8/templates/eca-claude/tools_sub.json` |
| 01 第 13 筆 | eca 子 agent U2：Explore、Plan 要不要也給少功能那台（12b） | **推斷，非實證：** 現況＝T3「不給、叫了被擋」；同一族的 U1 你 11-13 答「以後再想辦法處理，不急。」；影響小（這些類型照樣有內建讀檔工具）。依通則結案，真需要時再提 | `eca-task-subagent.md` §未定題；`proto8/thinking/2026-11/13/decide_20261113_wu-top.reply.txt`（sub-U1:C） |
| 01 第 13 筆 | 附帶：P-43 要不要補 `tools_sub` 一句（12c） | 已補 | `proto8/docs/CONVENTION/02-題目stack停錯腦/03-P-43-本文.md:12` |
| 01 第 14 筆 | `$ref` 跟 index 統一剩的五個細節（A7、A6、A5、U5、U3／A3） | 已定案、已施工；都是寫法細節，沒有對外動作、可改回。依通則結案 | `proto8/thinking/2026-11/12/ref-index-unify.md` §細節代定、§要使用者看的 |
| 01 第 15 筆 | `_metainfo` 其餘代定（14b） | 已施工（壞了且 prog 不在 PATH＝CommandMissing、提醒只印 stderr、index_view 不印多的鍵、metainfo_check 多 `notes`）；內部細節，依通則結案 | `proto8/thinking/2026-11/12/metainfo-views.md` §代定 |
| 01 第 15 筆 | `_metainfo` 讀法疑義第 1 點（14c） | 照最小的做（指每一項的值）；讀錯的後果只是最外層多的鍵被當成一項印出來、不報錯。依通則結案 | `metainfo-views.md` §原話讀法上的疑義 第 1 點 |
| 01 第 15 筆 | `_metainfo` 讀法疑義第 3 點：主觀那份蓋過去算不算數（14d） | **推斷，非實證：** 照最小的做（只當參考）；同組第 2 點你 11-13 答「這只是用來參考的概念。」，跟現況一致；11-14 頭腦風暴輪接手這方向、沒出待裁，你 11-14 也定了「需求不清時先發想、不急著規劃」。結案，等它自然浮現 | `metainfo-views.md` §疑義第 2、3 點；`proto8/thinking/2026-11/14/aos-brainstorm/README.md` 第 5 點；`wf/workflows/common/user/03-討論紀錄與規劃.md` |
| 01 第 16 筆 | kernel 是橋題 1：「上一層是硬體」嚴到哪（15a） | **推斷，非實證：** 已被後來的裁定帶過：11-13 晚你照推薦裁了 kernel 限資源計畫（kernel 定政策、daemon 起行程時套限制與身分、bwrap 管看得到什麼）＝推薦的 ②「上層畫框、下層在框裡直通」；11-14 已在施工（線限 B1～B3） | `proto8/thinking/2026-11/13/kernel-limits-plan.md` 開頭與 §使用者裁定；commit `51dc8b931` |
| 01 第 16 筆 | kernel 是橋題 3：要不要重畫框架圖紙（15b） | 已照推薦 A 走：你 11-13「kernel框架現在就可以開工了」、11-14「你列的這些都可以。開始推進吧」，照原圖紙施工、沒重畫 | `proto8/thinking/2026-11/13/kernel-framework-開工.md` §使用者原話；`proto8/thinking/2026-11/14/kernel-framework-1114.md` §使用者原話 |
| 01 第 16 筆 | 附帶：kb-ctl、題 2 | 11-13 已裁、條目自己寫已結 | `proto8/thinking/2026-11/12/kernel-as-bridge/06-細聊-手與門.md`；`decide_20261113_wu.json` kb-ctl＝A |
| 02 第 1 筆 | fsm 真腦跑一晚 | 你 11-14 改主意：不另外跑一晚，改拿 LiteLLM gpt 直接做實際施工，之後各線都這樣做 | `a31c00647`；`wf/workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md` 第 25、37 行 |
| 02 第 2 筆 | kernel 問腦包（Python 重寫）真腦驗 | 已實際用真腦跑過：活樹 `llm-gpt` 跑的就是 Python 版 `lib/aos/kernel_llm`、腦接 LiteLLM 真 gpt；11-13～14 多條線經它問腦（ok-skyrim 四隻 fsm 共 188 次、ok-pilot 的 sol-1～6） | `~/aos-home/kernels/llm-gpt/loop.json`；`proto8/thinking/2026-11/13/gpt-fsm-team.md` 第 67 行；`46c3ba1c5` |
| 02 第 3 筆 | hook 線 eca haiku 真對話 | 不用再等使用者：agent 現在可在暫存樹跑真 haiku 的 eca；11-13 已用 `kernel_gate` 掛 on_clock hook、確認掛得上也會觸發。剩 queue／tool 四種事件沒專門驗，**改列 WAIT_USER「待派工」** | `proto8/thinking/2026-11/13/eca-as-kernel/02-正式版實跑.md` 第 48～51 行；`proto8/thinking/2026-11/14/misc-1114.md` 第 136 行 |
| 02 第 4 筆 | eca 新工作區的信任選單 | 是「遇到才做」的步驟、已寫進手冊；常用工作區都已信任（`~/aos-home/ws`、`~/repo/aos` 都 `hasTrustDialogAccepted: true`） | `proto8/thinking/2026-11/13/aos-home-手冊.html`「今天第一次」第 1 條；`proto8/thinking/2026-11/12/ops-notes-to-aos.md` 第 252 行 |
| 02 第 5 筆 | two-machines T7 第 1～7 步（5a） | 撤出待使用者：agent 能在家機暫存樹自己跑（真 claude 已有先例），還沒人跑，**改列 WAIT_USER「待派工」** | `proto8/thinking/2026-11/10/two-machines/14-真機驗證.md` 第 1～7 步；先例 `misc-1114.md` 第 136 行 |
| 02 第 6 筆 | no-pid P8 scope 的 memory.max | 家機這半 11-14 實測通過：`systemd-run --user --scope -p MemoryMax=4G -p CPUQuota=200%` 退 0，讀到 `memory.max`＝4294967296、`cpu.max`＝`200000 100000`；公司那半已併進 03 | 子 agent 實跑輸出；`proto8/thinking/2026-11/05/no-pid/18-P8實作結果.md` 第 66、72 行 |
| 02 第 7 筆 | 真 Claude Code 讀不讀 aos-mcp 的 instructions | 已過時：11-12 拿掉了 aos-mcp 塞 `instructions` 的整套，現行 aos-mcp 沒有 instructions | `proto8/thinking/2026-11/12/knowledge-removal.md` 第 17 行；出處 `proto8/thinking/2026-11/05/agent-knowledge/06-11-05晚-接線.md` 第 23 行（原條目連到 small-thought，連錯了） |
| 02 第 8 筆 | 親手試 aos-daemon-ctl 停起 | 試驗場 `~/code/playground` 已被 `~/aos-home` 取代；這幾個指令 11-13 起天天在用，11-14 撞到的 stopped 列當機已修；測試蓋到 stopped 列重起後不被起 | `80f0c3b1f`；`proto8/impls/aos-daemon/tests/test_lifecycle.py`、`test_ctl.py` |
| 02 第 9 筆 | 親手試 daemon 狀態窗與 log | 「睡著時不寫窗」有測試蓋住；state 窗代定 1～10 依通則結案；「帶給使用者的」兩條只是條文加註，裡面的舊名已改或拿掉 | `test_lifecycle.py` `test_response_only_changes_leave_stable_windows_untouched`；`proto8/thinking/2026-11/02/state-window/06-實作結論-11-02.md` |
| 02 第 10 筆 | reply_to 後沙箱信箱多一格權限 | 前提不成立：條目寫「沒用過 `setup.sh --mailbox` 就不用管」，這台從沒跑過；以後跑 setup.sh 會一起建 `reply/` 三格 | `id aos-run`＝no such user、`/srv/aos-run` 不存在（11-14 查）；`proto8/cmd/aos-sandbox/root/setup.sh` 第 64 行 |
| 03 第 1 筆 | 家機 `~/aos-home` 搭好停著 | 樹已起來、天天在用；兩處 claude 信任都按過；備份改放 `~/.aos/saves/`（用法收進 fyi 信） | `~/.claude.json` 兩處 `hasTrustDialogAccepted: true`；commit `54789088d` |
| 03 第 2 筆 | 家機試驗場 `~/code/playground` 五隻 | 11-12 晚後就停了、被 `~/aos-home` 取代；「沒驗」那幾項不必在舊樹上驗（`/goal`、`/compact` 卡信那條沒查到驗過的紀錄，但不靠這棵舊樹） | `~/code/playground/.stack` 最後寫入 11-12 22:33；commit `f14c851a9`、`21a090824` |
| 03 第 3 筆 | 試 eca_tidy | 過時：跑在已停的 playground 樹、讀 11-12 舊快照；產出已抽查、十條都收了 | `proto8/thinking/2026-11/12/eca-tidy-review.md`；commit `981dc1859`、`c39fc540a`、`2e1e69de2` |
| 03 第 4 筆 | 公司 WSL 樹整天開著、畫面要重開 | 過時：你 11-13 下班就關機，下次起樹畫面本來就重開；`~/aos-saves` 0825 那夾不再追；換檔重抄是 agent 的事（用法收進 fyi 信） | commit `63b7d9cbd`、`54789088d` |
| 03 第 5 筆 | `~/code/playground-ak5` 要刪 stack 重建 | arknights 凍結到至少 12-14，不碰 ak5；解凍時再看 | `wf/workflows/common/user.md`「凍結中的線」 |
| 03 第 6 筆 | 對判官下指令改寫法 | 只是寫法提醒，已是現行行為、寫在文件與 `--help` | `aos-daemon-ctl --help`；`proto8/thinking/2026-11/06/os-impl/08-aos-daemon-ctl永遠直寄實作結果.md` |
| 04 第 1 筆 | 重連主 session 的 aos MCP（1a） | 不用做了：家機主 session 已是樹裡的 repo-aos；`~/.claude.json` 舊 aos MCP 那行 11-13 晚已拿掉，沒有設定指向 `~/.cache/aos-mcp-aos` | commit `21a090824`；`~/repo/aos` 專案 `mcpServers` 是空的 |
| 04 第 3 筆 | `~/.claude.json`、`~/.codex/config.toml` 舊路徑信任紀錄 | W6 已裁「清掉」，是 agent 下次在公司機開工的雜活（改前備份），已記在 SESSION-LOG | `proto8/thinking/2026-11/13/收工待裁-回覆落地.md` W6 列；SESSION-LOG 第 14 行 |

## 專區信清單（14 封）

信名是專區收下時給的名字；沒寄的寫檔名（在 `wf/temp/ok-pilot/wu/` 底下）。

| # | 檔 | kind | 標題 | 寄送狀態 | 信名 |
|---|---|---|---|---|---|
| 1 | 01a/letters/02-push.json | decide（irreversible） | 家機 main 目前有 55 個 commit 沒推上 origin，要推嗎？ | 11-14 已寄 | 01794620885119601328.1568311.947077 |
| 2 | 01a/letters/03-W16改口摺疊.json | decide | 知識庫的「整理」說明要不要也補上「改口摺疊」那一節？ | 11-14 已寄 | 01794620885150278773.1568317.947080 |
| 3 | 01a/letters/04-1113代定兩處.json | decide | 11-13 各線代定：挑出兩處會碰到你自己操作的，其餘照代定結案 | 11-14 已寄 | 01794620885180998295.1568325.947083 |
| 4 | 01a/letters/05-命名與同質比較.json | decide | 規範有三處跟現況對不上：夾名連字號、mailbox 夾名、同質比幾樣 | 11-14 已寄 | 01794620885212140969.1568339.947086 |
| 5 | 01a/letters/06-程式碼整理.json | decide | 程式碼整理剩的幾題：哪些會改行為要你點頭，其餘一次照推薦 | 11-14 已寄 | 01794620885243272191.1568357.947089 |
| 6 | 01a/letters/07-條文整理第三輪.json | decide | 條文整理第三輪：照程式改的五處要你點頭，加上三題整理的人不能自己選邊的 | 11-14 已寄 | 01794620885274081862.1568371.947092 |
| 7 | 01a/letters/09-外部MCP通行碼.json | decide | 外部 MCP：沒指定通行碼檔時，claude 那身的 Bash 看得到通行碼，要不要擋？ | 11-14 已寄 | 01794620885304510812.1568376.947095 |
| 8 | 01b/letters/09-外部MCP同步.json | decide | 外部 MCP 工具抄進 aos 之後，server 那邊改了怎麼辦（兩題，都已照現況施工） | 11-14 已寄 | 01794620885335160485.1568388.947098 |
| 9 | 01b/letters/14-沙箱設定寫壞.json | decide | 沙箱設定寫壞時，要照跑（不套沙箱）還是拒跑？（你 11-12 選照跑，gpt 隊試驗後有人想翻） | 11-14 已寄 | 01794620885365660267.1568393.947101 |
| 10 | 02/letters/11-sandbox-root.json | decide | 沙箱「換成別的帳號跑」要不要用 root 設一次？ | 11-14 已寄 | 01794620885396347900.1568412.947104 |
| 11 | 02/letters/05b-two-machines-roundtrip.json | verify | 下次在公司時：/mnt/c 起一棵樹、公司↔家機經 GitHub 來回一次 | 11-14 10:50 第二批（待寄） | — |
| 12 | 03/letters/01-試驗場收帳.json | fyi | 試驗場舊帳六條都收掉了，只剩兩句用法給你留著 | 11-14 10:50 第二批（待寄） | — |
| 13 | 04/letters/01-舊aos-mcp殘留.json | decide（irreversible） | 家機舊 aos MCP 留下的兩個 cache 夾，要刪嗎 | 11-14 10:50 第二批（待寄） | — |
| 14 | 04/letters/02-公司機暫存夾刪除名單.json | decide（irreversible） | 公司 WSL ~/code 底下 11-13 的暫存夾，這份刪除名單可以嗎 | 等回公司機對過名單再寄 | — |

## 待派工（已列進 WAIT_USER「待派工」一節）

1. **hook 在真 eca 上的 queue／tool 四種事件**（02 第 3 筆）：`queue_before`／`queue_after`／`tool_before`／`tool_after` 還沒在真 eca 上專門驗；agent 可在暫存樹跑真 haiku → [hook 02 § eca 真對話照抄](../10/self-family/hook/02-施工結果.md#eca-真對話照抄會花-claude-額度)
2. **two-machines T7 第 1～7 步**（02 第 5 筆的 5a）：真 claude／codex 找不到對話時的反應、eca 換台、memory 那題；agent 可在家機暫存樹自己跑，步驟 11-10 寫的要先對到現況 → [14-真機驗證](../10/two-machines/14-真機驗證.md)

## 疑點（照抄 SUMMARY「要頂層看的疑點」）

1. **14 封 > 專區每寄件人每小時 10 封**：要分兩批寄（建議先寄 1～10，一小時後寄 11～14）。
2. **push 那封**：push 通常頂層自己跟使用者談；要不要從這批拿掉由頂層定。
3. **公司機暫存夾那封（14）**：名單是 11-13 16:05 的狀態，家機看不到實物；信裡寫了動手前先 ls 對一次、名單外不刪。可以現在寄，或等回公司機對過再寄。
4. **歸 A 但嚴格說是「不用再等使用者、還沒人做」的**：02 的 3（hook 在真 eca 上 queue／tool 事件）、5a（two-machines T7 第 1～7 步 agent 可自己跑）。要做的話是另派的工作，不是使用者的帳。
5. **推出來的結案**（使用者沒直接答那題）：01b 的 eca 子 agent U2、`_metainfo` 讀法疑義第 3 點、kernel 是橋題 1。要保險可各加進一封 decide，到期照現況。
6. **02 的子 agent 跑了一次暫時的 systemd scope** 實測 no-pid P8 的 memory.max（通過、退 0，不碰 repo 與活樹）。任務書是唯讀查證，這步越界了一點，照實報。
7. 新發現沒人追的：沙箱設定寫壞要照跑還是拒跑（11-13 T21），寫在 `sandbox-sender-fix.md` 和 a3d99b933「待使用者裁」，但沒進 WAIT_USER → 已收成第 9 封。
8. `source_path` 錨點沒跑 check_anchors。

頂層對 1～5 的裁示見上面「來源與授權」：分兩批寄、push 那封留著、14 等公司機、4 改列待派工、5 標「推斷，非實證」。

### 改寫時另外記下的

- 01 第 2、3、5、7 筆與 02 第 11 筆整筆都是 B，沒有可結案的子項，指標行寫「整筆搬過去」而不是「其餘子項已結案」。
- 01 第 7、8 筆（tidy 第三輪的兩筆）指向同一封信（第 6 封）。
- 02 第 10 筆（reply_to 信箱權限）本身結案，要跑的話已包在第 10 封信的選項裡。
- 03 六筆全結案，檔裡改留一句說明＋fyi 信的指向，沒有 `- **` 行。
