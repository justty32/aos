# proto5/lib — 測試

← [proto5/lib README](../README.md)｜上一份：[公司與市場](company.md)

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5/lib python3 -m unittest discover -s proto5/lib/test  # 2874 條；repo 根目錄
```

共 101 個測試檔、2874 條（09-25 市場真跑後研發修正，main 90d5c7c 之上實跑，全綠）；涵蓋底層執行、daemon／kernel 按池行為、
agent 讀驗與走格、工具與權限牆、HTTP、崩潰恢復及整合。真子行程測試使用 tempdir、輪詢上限與清理回呼；
崩潰接手的隔離 driver 代替不收孤兒的容器 init 收屍。一檔一行：

| 檔 | 驗證內容 |
|---|---|
| [test_directives.py](../test/test_directives.py) | 指示詞、引用、選項與錯誤 |
| [test_directives_edit.py](../test/test_directives_edit.py) | `cli/aos-directives`（人格分節編輯＋resolve／check）與 `cli/aos-json`（人用 JSON Pointer 改檔）：子行程跑、退出碼、錯誤格式、檔案真的改對 |
| [test_inst.py](../test/test_inst.py) | inst 讀驗、指示詞位置、欄位與選項 |
| [test_exec.py](../test/test_exec.py) | 三種目標、串流、env、退出碼、逾時及舊 API（`run_target`／`run_inst`／`main`） |
| [test_exec_full.py](../test/test_exec_full.py) | `run_target_full`：三類 timed_out、強停、TERM 後退 0、相容性 |
| [test_exec_spawn.py](../test/test_exec_spawn.py) | `aos_exec_spawn.spawn_target`：控制 pipe、pgid／session、顯式串流拒絕、exit 與啟動失敗 |
| [test_exec_cpu.py](../test/test_exec_cpu.py) | 真 cpu：握手、EOF、訊號、stop、Interrupted、timeout、工作串流、`notify` 通知與開機補丟 |
| [test_home.py](../test/test_home.py) | 三類信封、原子放單、ack、五列對帳與 info |
| [test_client.py](../test/test_client.py) | 取名、先查原單、逾時、端到端與 ack |
| [test_daemon.py](../test/test_daemon.py) | 真 daemon 按池、宣告式：scale、補／收／重拉、退避、節流、fd 預算、kill、halt、重開 |
| [test_daemon_cli.py](../test/test_daemon_cli.py) | `aos-daemon` 命令列：boot／halt（家的三種來源、flock 探測、逾時）與 ls／scale／kill |
| [test_daemon_crash.py](../test/test_daemon_crash.py) | daemon 崩潰窗口（按池版）：閘門卡住真 daemon、真 SIGKILL、下一任接手 |
| [test_daemon_fix.py](../test/test_daemon_fix.py) | astra 審查 daemon 側定點：`pool_summary_state` 三態、摘要寫／刪失敗重試、每圈只碰有事的池 |
| [test_kernel.py](../test/test_kernel.py) | kernel 判定、syscall、收回音與派工（帳本第 2 版）；不開外部行程 |
| [test_kernel_pools.py](../test/test_kernel_pools.py) | info 第 2 版讀驗、成員公式、`init --config`、家與模板（不需要 daemon） |
| [test_kernel_tick2.py](../test/test_kernel_tick2.py) | 一格十步：池的長大／縮小、scale 回音、通知三路、排隊懶刪、提交點、搬池、停機縮池（假 daemon） |
| [test_kernel_halt2.py](../test/test_kernel_halt2.py) | 搬池、池從 info 消失、停機縮池與 halt 等待（假 daemon） |
| [test_one_boot.py](../test/test_one_boot.py) | （09-24 one-boot）真 daemon＋真 tick：帳本交易中 kill -9 整筆回滾、`aos-kernel proc`、tick 逾時被砍、daemon 被 kill -9 後接手、連敗退避不停、新單馬上觸發、同時一格、`aos up`／`down` 不留行程、舊 `state.json` 匯入 |
| [test_kernel_boot2.py](../test/test_kernel_boot2.py) | kernel boot 交接與崩潰窗口（某一步丟 Crash，下一格／下一次 boot 照常跑） |
| [test_kernel_cpu.py](../test/test_kernel_cpu.py) | `aos-kernel cpu add／rm／ls`：只改 info、鎖、指示詞保留、按池摘要與一顆一行的字眼 |
| [test_kernel_check.py](../test/test_kernel_check.py) | `aos-kernel check` 各項 ok／warn／bad（假家、flock、手寫 summary.json） |
| [test_kernel_cli.py](../test/test_kernel_cli.py) | kernel 命令列：`--target` 來源、`init`、help、`ack`、`ls` 的摘要與表、halt、舊 `--agent` 指到新指令 |
| [test_kernel_health.py](../test/test_kernel_health.py) | health 優先序、錯誤邊界、`ls` 第一行與 `--json` |
| [test_kernel_crash.py](../test/test_kernel_crash.py) | 閘門卡住真 tick、真 SIGKILL、下一格（或 boot）接手：不重派、不重算、無鬼回音 |
| [test_park_wake.py](../test/test_park_wake.py) | （09-24 停車）102 停車、出貨叫醒、`wake` syscall／CLI、新一代接手舊批、discard、ls 的 parked、崩潰窗口（Crash）；agent 的退出碼、送單帶 wake、start 相容、say／drop_new 投 wake |
| [test_park_crash.py](../test/test_park_crash.py) | （09-24 停車）真 SIGKILL：放好回音檔後／放檔前被砍，下一格照樣叫醒、回音只放成功一次 |
| [test_kernel_fix_r5.py](../test/test_kernel_fix_r5.py) | （fix-r5）check `--probe` 與總結行、ls 的恢復中與 agent 標記、真 daemon 的 boot 印行 |
| [test_kernel_fix_astra.py](../test/test_kernel_fix_astra.py) | astra 審查 kernel 側必修定點：boot 等待中舊 tick 又提交、draining 中拒 boot、摘要讀不到要等、壞通知 |
| [test_kernel_integration.py](../test/test_kernel_integration.py) | 真 daemon＋cpu：反覆／once、halt、重 boot、pool、Interrupted |
| [test_kernel_recovery.py](../test/test_kernel_recovery.py) | 出貨重放、先記未放、鏈與 boot 交接、ack 唯一性 |
| [test_p52_e2e.py](../test/test_p52_e2e.py) | 真 daemon＋真 aos-cpu＋真 tick 鏈的端到端（加減 cpu、忙的做完才收、崩潰退避、halt→boot） |
| [test_rearch_e2e.py](../test/test_rearch_e2e.py) | k／0／llm、envs PATH 的假 llm-http、once 輸出、done_exit、完整停機 |
| [test_advice_r1.py](../test/test_advice_r1.py) | （advice-r1）`aos-agent check` 找 K 與各情形、`aos-kernel ls --json` 欄位與文字表 |
| [test_llm_call.py](../test/test_llm_call.py) | 模型表、組 body、HTTP 與 message 正規化；`aos-llm call`、裸 `aos-llm` 退 2 |
| [test_agent_home.py](../test/test_agent_home.py) | 共用內容六格、人格／記憶／工具與訊息讀驗 |
| [test_agent_info.py](../test/test_agent_info.py) | 完整設定、排程欄位、state 與恢復紀錄讀驗 |
| [test_agent_tick.py](../test/test_agent_tick.py) | waits、三格、批次收送、錯誤與 start／stop |
| [test_agent_crash.py](../test/test_agent_crash.py) | 持久化邊界崩潰與重啟恢復 |
| [test_agent_fix_cli.py](../test/test_agent_fix_cli.py) | start／stop 印行、stop 不讀 info、KernelMismatch、listen --last |
| [test_agent_fix_r4.py](../test/test_agent_fix_r4.py) | （fix-r4）`--target` 與錯誤來源、listen 三態、pause／continue／status、tick 鎖、舊 tick.json |
| [test_agent_fix_r5.py](../test/test_agent_fix_r5.py) | （fix-r5）status 重試中／恢復中、continue 兩階段與 --all、say／--wait 各情形、init --force |
| [test_agent_fix_storage.py](../test/test_agent_fix_storage.py) | done/ 封存、舊式紀錄相容、錯誤訊息的 log 路徑、126／127、ToolInvalid 位置 |
| [test_agent_daily.py](../test/test_agent_daily.py) | init／say／status／continue、stop 用 tick.json、listen 退回讀記憶、help、用法錯 |
| [test_agent_daily_edges.py](../test/test_agent_daily_edges.py) | say --wait 的等待條件、暫態壞檔、逾時與連敗提前結束 |
| [test_agent_status_r3.py](../test/test_agent_status_r3.py) | status 的 health、這次原因／已恢復、連敗次數、-v、--json 新鍵 |
| [test_agent_memory.py](../test/test_agent_memory.py) | 第 4 隊（記憶與紀錄）：`context`、`events`、`usage`、`compact`（含 KILL 崩潰窗口、tick 鎖、自動壓縮、申請）、`history --archive` |
| [test_agent_notes.py](../test/test_agent_notes.py) | `tools/notes/` 的 `note` 工具（add／find／get／rm，wf-table/1 存檔）與 `aos_agent_notes.py`（`notes ls／show`，含 access.json 牢裡路徑換算） |
| [test_agent_listen_tweak.py](../test/test_agent_listen_tweak.py) | listen `--last N`、輪次標頭與收話時間、`--show-calls`／`--show-calls-full`、即時呼叫行 |
| [test_agent_talk.py](../test/test_agent_talk.py) | `aos-agent talk`：一句問答、不重印、slash 指令、逾時補印、Ctrl-C／EOF |
| [test_agent_integration.py](../test/test_agent_integration.py) | 真 daemon／kernel／exec cpu 的 agent 整合（池表） |
| [test_agent_tools.py](../test/test_agent_tools.py) | `tools add` 各情形，真 daemon／kernel／agent＋假模型照劇本用工具 |
| [test_agent_tools_manage.py](../test/test_agent_tools_manage.py) | `tools` 元素 `$opt`（as／only）、`tools ls／rm／alias／unalias`、管理鎖串行化 |
| [test_agent_access.py](../test/test_agent_access.py) | 權限牆 access.json 讀驗、重疊、送件快照、`access` 子命令、check／status |
| [test_access_more.py](../test/test_access_more.py) | 權限牆補測：一批共用快照、壞表整批跑不起來、下一批才用新表、壞 JSON 拒寫 |
| [test_access_round2.py](../test/test_access_round2.py) | 09-24 使用者裁決 1：檔案工具根＝整個 `/work`、唯讀掛點寫不進去、錯誤看得懂；真跑 bwrap（沒有就 skip）與不用 bwrap 兩路 |
| [test_jail.py](../test/test_jail.py) | `aos-jail` 單元與真 bwrap（沒有就 skip）：路徑、環境、網路、唯讀 mount、經真 aos-exec 跑 |
| [test_tools_base.py](../test/test_tools_base.py) | base 工具包：共用參數／config／OutsideRoot、read／write／edit／grep／find／ls |
| [test_tools_base_bash.py](../test/test_tools_base_bash.py) | base 的 bash：輸出合併、cwd、退出碼、逾時、截斷、背景行程收掉 |
| [test_tools_base_fix.py](../test/test_tools_base_fix.py) | base 工具包 astra 後修正：暫存檔與符號連結、大檔、CRLF、grep 各種退路、tools add 併發 |
| [test_tools_files.py](../test/test_tools_files.py) | `proto5/tools/files/`：json_edit、md_section 兩支工具；files／wf 的 `_common.py` 跟 base 逐字一樣；描述字數；`tools add files` 裝得起來 |
| [test_tools_wf.py](../test/test_tools_wf.py) | `proto5/tools/wf/`：workflows 工具包（wf_doc／wf_init／wf_lint／wf_residue／wf_table）；wf_init 兩個崩潰窗口真 SIGKILL 重跑收得回來 |
| [test_team_format.py](../test/test_team_format.py) | 工具大開發時代 T1 第 0 步：團隊共用格式（spec/team/）、任務狀態機、問人、申請登記表、`aos-team` 分派 |
| [test_team_init.py](../test/test_team_init.py) | 第 1 隊：aos-team init／start／stop／ls／rm、模板生家、task 工具包 |
| [test_team_notes_compact.py](../test/test_team_notes_compact.py) | T5 收尾：模板 `notes: true` 的筆記掛載（新家、舊家補掛、保留名）、`compact_me` 工具、郵差收 compact 申請、`Layout.events()` |
| [test_team_review_fix.py](../test/test_team_review_fix.py) | 第 1 隊 astra 必修回歸：審查重播、逾期通知、問題綁單、init 崩潰窗口、rm 中斷、換模板 |
| [test_team_route.py](../test/test_team_route.py) | 第 1 隊門房：整句句型、落穿、例句全過才准存 |
| [test_team_task_cli.py](../test/test_team_task_cli.py) | 第 1 隊人用指令：task ls／show／cancel／reassign、wait ls、answer |
| [test_team_say.py](../test/test_team_say.py) | 第 2 隊 `tools/team/team_say`（spec/team/mail.md）：寫一封信進自己的 outbox；`config.json` 讀取與參數驗證 |
| [test_team_post.py](../test/test_team_post.py) | 第 2 隊郵差兼書記（`aos_team_post`；post.md）：投遞、退件、任務單後續動作、驗收工作、審查、崩潰窗口、看停滯、書記 |
| [test_team_post_crash.py](../test/test_team_post_crash.py) | 第 2 隊郵差崩潰窗口：真 SIGKILL 在窗口裡（收件人重跑前把信收走），重跑不重投、不漏動作 |
| [test_team_post_live.py](../test/test_team_post_live.py) | 第 2 隊驗收⑧：真 daemon＋kernel，郵差當反覆工作跑，一封信到對方記憶；領隊 handoff → 工人（假模型）牢裡叫 `team_say` 回 DONE → 郵差把驗收當一次性工作提交 → done |
| [test_team_verify.py](../test/test_team_verify.py) | 第 2 隊驗收員（`aos_team_verify.py`）：固定檢查器（file_exists／table_filled／check）、judge 排除、CLI |
| [test_team_beat.py](../test/test_team_beat.py) | 第 2 隊心跳（`aos_team_beat`；beat.md）：到期派出、在途不重派、DONE 才更新、漏跑只補一次並報告、模型提的要人批 |
| [test_team_rulings.py](../test/test_team_rulings.py) | 第 2 隊追加：使用者五題裁決（郵差間隔可設定、心跳用自己的身分派工、一次性例行叫 `once`、檢查器壞≠沒過、例行完成不寄 DONE 擾人） |
| [test_team_score.py](../test/test_team_score.py) | T5 收尾 `aos-team score`（score.md）：手造一支小團隊的紀錄，驗六軸計數、門檻、範圍、去重、輪換、`--runs`、`--json`、壞行 |
| [test_team_hr.py](../test/test_team_hr.py) | HR 部 09-25 `aos-team hr`（hr.md）：薪資表／政策讀寫與壞檔、`employment` 驗證、試用不動原團隊與紀錄欄位齊（kernel 那段換成假的）、調薪四種判定、`hr set` 改名冊與家、正式員工人頭與 cpu 計數、擋點 |
| [test_team_t5.py](../test/test_team_t5.py) | T5 收尾的小改動：審查單帶事實、`aos-team ls` 列郵差與心跳、模板人格的變數與關鍵句 |
| [test_team_w2a.py](../test/test_team_w2a.py) | 第二波 A 隊團隊這邊：`route try` 不留痕跡、`mail` 列題目與落穿信、`start` 那兩行標郵差／心跳、`importer` 模板的工具與工具表大小 |
| [test_tools_wf_fill.py](../test/test_tools_wf_fill.py) | 第二波 A 隊 `wf_fill`：真的 wf_init 導入後填到 wf_lint PASS、dry_run 不寫、再跑不動、名字對應規則（同義詞、包含、不只一條不填、範本列）、今天日期照時區、範例只刪認得出的 |
| [test_agent_tools_dev.py](../test/test_agent_tools_dev.py) | 第二波 A 隊 `tools new／test／wrap-py`：fixture（[fixtures/wrap_fixture.py](../test/fixtures/wrap_fixture.py)）拒收表逐條、產的包 test 全過、裝進家後 check 過且關牢、run 的型別驗證、PythonError 不帶 Traceback、壞包報 FAIL |
| [test_team_wall.py](../test/test_team_wall.py) | 第二波 B 隊（spec/team/wall.md）：`cmd_ok` 白名單格式與比對、牢裡執行（退出碼、逾時砍孫行程、輸出只留尾、程式假冒 bwrap 錯誤仍算不過）、wf_lint 關牢、門房 `tool` 關牢與 `NoBwrap`、郵差再驗（路徑、控制字元、假信頭、角色） |
| [test_team_escape.py](../test/test_team_escape.py) | 第二波 B 隊驗收③逃逸測試：`aos-team init` 生真團隊，工具走 `tool_inst` 真送件路徑進 bwrap；讀別人的家、寫 access.json／工具包、寫別人的 outbox、硬連結、冒名、假信頭、越權申請、符號連結、主機 /tmp、環境與網路、wf_doc 讀快照、wf_init staging 在牢裡 |
| [test_notes_recall_context.py](../test/test_notes_recall_context.py) | 第二波 B 隊：notes 包的 `recall`、`context` 兩支工具（token 粗估跟 aos_agent_context 同一套）、`mem` 唯讀掛點（新家、舊家補掛、保留名）、真牢裡寫不進 `/work/mem` |
| [test_team_lock.py](../test/test_team_lock.py) | 第二波 C 隊 `aos_team_lock`（lock.md）：acquire／release／ls、Busy 拒絕、同持有者續租、過期可被搶／可被別人放、冪等、`may_send`、`cmd_lock` |
| [test_team_spawn.py](../test/test_team_spawn.py) | 第三波 W3-1 `aos_team_spawn`（spawn.md）：郵差端 `on_spawn` 每條檢查（模板、人數、`mail_to`、`may` 超權）、冪等；人端 `spawn approve` 生家、改名冊、回覆；工具 `spawn_member` 經真郵差（`may` 擋工人） |
| [test_team_toolsmith.py](../test/test_team_toolsmith.py) | 第三波 W3-1 `aos_team_toolsmith`（toolsmith.md）：郵差端驗草稿、生包、牢裡 `tools test`、開題／退信；人端 `tool approve`（核 sha256、`tools add`）；逃逸測試（讀別人的家、改 staging 換裝的程式、撞既有工具名等），沒有 bwrap 就跳過要真跑的那幾類 |
| [test_company.py](../test/test_company.py) | 公司 `aos_company`：樣板名冊與門房全過驗、開五家不撞名（`--llm-cpu 4` 五家剛好 20）、上限一行與超額、臨時工不算人頭、總機（命中開單、寫手自己的 DONE 不轉、郵差的 DONE 轉回下單人、落穿給窗口、沒寫 reply_to 的配對、退信四種、郵差信裡的〔給〕不理、tool 規則當場回、董事直接下單、崩在記帳與動作之間不重派）；astra 09-25：配不到的 reply_to 不猜、desk 單只有窗口能結、崩了不留孤兒單、董事單接著派、工具中斷不重跑、宿主關了退信、〔給〕只認第一行、up 對齊 K 的池、down 沒停好退 1、自家 daemon 的環境、new 與 status 同一個 cpu 算法；真跑 09-25：草稿不在時補人物的單子寫「無草稿、從原文起」（`if_missing`）、`company.py hr` 自動帶 AOS_KERNEL_HOME |
| [test_market.py](../test/test_market.py) | 市場層 `aos_market`（假帳本）：品質分、總機單算秒數與跳數、排名公式與權重、名次分成與覆寫、只算這輪花的、品質門檻、總池（錢＝總量−已花−手上沒花、名額）、倒閉只收剩的那一種、裁撤全收、撥款被總池縮、撥名額與開戶擋名額、合併計畫與實做；astra 09-25：撥款崩在途中重跑不重撥、轉帳去重與守恆、封存／合併中斷接著做、市場鎖、停機失敗不封存與停好才收回、開戶擋重疊與重用、分數綁輪次、按結案時間算、花光不撥、slots 不收負數、改名撞名、美元不超發、分數驗證；試玩：覆寫負數擋、沒花 token＝最省、每個子命令有說明；真跑 09-25（fixture 是那一輪的原始紀錄）：沒成功結案＝全項 0、快＝董事等的秒數、省只比成功的＋無對照、本輪無分數拒絕、同分均分、證據代號展開、重算 c1 96.25／c2 0 |
| [test_team_cost.py](../test/test_team_cost.py) | 財務部 `aos_team_cost`（cost.md）：記一筆（沒設不記、agent 家推團隊／成員／單號、環境標籤、寫失敗不擋、`ask` 經真 HTTP 假端點）、五種分組、缺價只記 token、改價重算、預算形狀、各家族 since、郵差超預算不派＋寄信一次＋調高後放行、全公司預算照投普通信、`ls` 第一行、回填不重記 |
| [test_llm_ask.py](../test/test_llm_ask.py) | 第三波 W3-2 `aos_llm_ask`：假端點、temperature 0、`parse_json` 各種包法、沒設定／端點掛；`context` 的「上一次問模型」略過 compact 濃縮那一問 |
| [test_agent_tools_wrapcli.py](../test/test_agent_tools_wrapcli.py) | 第三波 W3-2 `tools wrap-cli` 與 wrap-py 描述：fixture（[fixtures/wrapcli/](../test/fixtures/wrapcli/)）argparse 靜態讀與拒收、GNU／怪 help 解析、標準答案比分、`run` 組 argv 不經 shell、提案檔只寫不產包、`--spec`／`--describe` 核 sha（假 ask，不打真模型） |
| [test_compact_summarize.py](../test/test_compact_summarize.py) | 第三波 W3-2 `compact --summarize`：假 ask 回好的／太長／丟關鍵詞／含 `[aos`／丟例外 → 退回機械版照樣縮、dry-run 不叫不寫、tick 自動與申請絕不叫模型、usage 有記、崩在 archive 後重跑 |
| [test_team_crystal.py](../test/test_team_crystal.py) | 第三波 W3-2 `aos-team crystal`：route.log 的 `letter`、句型骨架、機械候選全過 route test、舊 log 靠原文對信、群組只收相對路徑、`--suggest-with-llm` 的機械檢查（假 ask） |
| [test_agent_persona.py](../test/test_agent_persona.py) | 第二波 C 隊 `aos_agent_persona`（persona.md）：show／set／append、自訂 `system` 路徑、壞檔、用法錯、`aos-agent persona` CLI 接線 |

共用工具（不是測試檔）：[\_util.py](../test/_util.py)（底層／agent）、[\_daemon_util.py](../test/_daemon_util.py)
（控制協議孩子、輪詢、孤兒隔離 driver、`read_json`／`wait_for`）、[\_kernel_util.py](../test/_kernel_util.py)
（真 daemon／kernel 測試家，`aos-kernel init --config` 建、`pools=` 傳池表）、[\_kernel_fake.py](../test/_kernel_fake.py)
（假 daemon：只處理 `D/requests/` 的 scale 與 ack、手寫 summary.json，不拉任何 cpu）。

## 09-25 lib 拆檔後的 patch 眉角

母模組把子模組的名字再匯出（`from aos_xxx_yyy import thing`）只是複製一份名字，**不會**轉接子模組自己的
global。以前 `unittest.mock.patch('aos_xxx.thing', ...)` patch 得到的東西，拆檔後如果 `thing` 其實定義在
子模組 `aos_xxx_yyy` 裡，要改成 `patch('aos_xxx_yyy.thing', ...)` 才會生效；patch 母模組那個名字只換了母模組
自己那份引用，子模組內部呼叫 `thing` 還是用它自己那份。目前 repo 沒有測試這樣踩雷（astra 09-25 review 用 grep
確認過一輪），但日後要 patch 再匯出的名字時先想一下它實際定義在哪支模組。
