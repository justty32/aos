# session_logs — 日誌

[SESSION-LOG](../SESSION-LOG.md)｜[INDEX](../INDEX.md)

日誌：當月每天一個檔 `<月>/<日期>.md`，已結束的月份收成月摘要 `<月>.md`（原檔封存在 `archive/`）；下表每天一句「這天定下了什麼」，點進去看當天動了什麼、結論連到哪。寫法見 [user/02](../workflows/common/user/02-交接與收工.md#日誌怎麼寫2026-10-26-定)。

<!-- wf-nav -->
| 日期 | 這天定下了什麼 | 全文 |
|------|------|------|
| 2026-11-11 | 定：工具 `agents_children` 改名 `subagent`、舊名不留；公司機真腦一律走 eca、agent-fsm 真腦回家測；agent 能改自己的 system 文字（aos-agent system＋self_system：fsm 取代、eca 附加、只給 reset）；人的信箱預設 ~/.aos/stack；hook 加起來／停下與照時鐘觸發的 `on_clock`（格裡寫條件、到了才跑、不進 history），時鐘登記＋專用信箱那套不做；公司試驗場照今天的 main 刷新、加 codex 那隻 | [2026-11-11](2026-11/2026-11-11.md) |
| 2026-11-10 | 定：arcagi 停線、等 aos 大修完再續；今天公司以討論為主、不 push、下班前統一 push；兩台輪流＝git 過去一行起根接著跑、路徑三種寫法、`aos-image` 不做、/mnt/c 可放、kernel 不在不停；晚上（家機）七條線收攏進 main：agent 能看改自己（self_*）、互寄信（mailbox）、被時鐘寄信叫醒、生子並調它（agents_children）、讀寫純 JSON 記憶庫；小模型裝不下工具說明＝調 LM Studio 的 context | [2026-11-10](2026-11/2026-11-10.md#2026-11-10) |
| 2026-11-09 | 定：時鐘一律改名 clock、單位 cycle（`_clock`、`AOS_CLOCK`、`aos-clock`、`*_cycles`）；熱寫檔有變才寫、state 的回音欄拆到 `state_flux.json`；daemon 中斷只做訊號門鈴 `aos-daemon-ctl poke`（預設 `--ctl`、SIGUSR1／2 一律擋，socket／搶占不做）；daemon 不認鐘、鐘＝根的一列普通 proc（子 daemon 預設聽外層）；格式版本機制等使用者主持的大修之後才轉正，現在只埋種子（狀態檔讀不了改名留證＋warning、`.bad-*` 進 gitignore 不自動清）；大修材料放桌面不進 repo、不凍結核心、跟著 main；公司 WSL 試驗場改三層、程式改用 `~/repo/aos-tools` | [2026-11-09](2026-11/2026-11-09.md#2026-11-09) |
| 2026-11-07 | 定：aos-daemon-ctl 一律直寄 daemon、aos-agent 經判官，判官睡著由設計系統的人管理、手動叫醒；sol 審查 32 題依使用者裁定（判官範本開排隊、保有序可選且預設關、短旗標各支自定、給 LLM 看的也英文）；gpt 系不做設計決策與架構規劃，施工／文件／網頁／雜活優先派 gpt；知識庫節點英文、內文照語料原文，給人看走附屬白話庫或問答 agent，evidence 不搬、格式過檢查即 commit、一致率只記；os-impl 09 先選 A，後以 daemon 裁定 B 翻「失敗下表」：任意 proc stop 寫公開 ctl、已知非 0 留 stopped、收工 sleeping；edge-1107 四題已裁（超大秒數直接報錯、狀態檔壞了只補文件、判官先標完成、aos-tick 暫存檔加 pid） | [2026-11-07](2026-11/2026-11-07.md#2026-11-07) |
| 2026-11-06 | 定：aos-daemon 的 stack 鎖不再被 fork 出來的子行程帶走（`pthread_atfork` 關鎖，`kill -9` 後立刻再起＝起得來）；撞鎖時只看 phase、不對 /proc 印 pid；adopt 比 `boot_id`（no-pid P1，代定 4 條可翻案）；大重構 S5 公司重做進 main：proto8 按角色分成 impls／cmd／py／lib／kernel／templates（夾名＝指令名、執行檔在 `<名>/bin/<名>`），家機 S5 分支作廢、S7 分支要疊到 S5＋P1 之上；大重構 S5 公司重做進 main：proto8 按角色分成 impls／cmd／py／lib／kernel／templates（夾名＝指令名、執行檔在 `<名>/bin/<名>`），家機 S5 分支作廢、S7 分支要疊到 S5＋P1 之上；daemon／loop 的窗多「最近一次有反應」`responded_at`（有反應才寫、睡著不動）、daemon 記上一層 `daemon`、信箱認 ping（no-pid P2，代定 5 條可翻案）；fable 把昨晚想法對現況的落點與排程寫成 apply-ideas（都不插進 S 步、tick 改 deadline 跟 S9 同人緊接、aos-serve 排大重構後；D1＋Q1～Q5 待使用者） | [2026-11](2026-11/2026-11-06.md#2026-11-06) |
| 2026-11-05 | 定：aos-mcp 工具失敗時把 stderr 最後一段附給外部 agent（C-52 例外）；llm kernel 不再寫 `served.jsonl`；無痛遷移——sleep／wake 開放成指令、image 裡的路徑相對「管我的 daemon」、stack 不存定義副本、啟動四步「複製→（沒有才）起 daemon→環境變數盡量少→aos-exec」（規劃，8 題待裁）；kernel＝管 proc 是否可執行、daemon＝最基礎 kernel、問腦改掛 daemon、`AOS_LLM_KERNEL`＝llm daemon 的 stack（規劃，2 題待裁）；給 agent 的 aos 知識分層成知識庫、第一個通用元件「層級式記憶工具」`memory`（查詢三招、`AOS_MEMORY` 指知識庫、多 agent 共用；Haiku／luna 9／9） | [2026-11](2026-11/2026-11-05.md#2026-11-05) |
| 2026-11-04 | 定：沒有新決定（tidy P4-D／E 補完對讀、晚上 P2／P3／P4 續收斂；round 刪掉後的 13 條條文攤給使用者裁；aos-post 改版做完：全套驗過、條文照「都按照建議」加註，`…Exists` 成代號第五種結尾；四元素審查十題裁定並全部實作，`_metainfo.json`、daemon 小格名可設、add 看入口 JSON、N-63 `AOS_` 四種性質表；send_message／memory、resident-bob 封存、整份 AI 產出的 thinking 刪，NORMS 加舊名對照表附錄3；晚上「思考是 aos 函數」照推薦實作：問腦＝寄請求信給 llm kernel 收回信、`AOS_BRAIN_*` 退場、`aos-llm` 成基礎工具，四題可翻案；夜裡使用者選項定：換腦只留 `llm.json` 代號、`AOS_KERNEL` 只當 hub，P-23 刪「不跑本機模型」，P-42 正式改寫，N-14 窗不帶 `kind` 定案；邊緣狀況三條線〔llm kernel、daemon／aos-agent、基礎積木〕修十幾處，使用者口徑「風險自擔」、只有 add 被拒照推薦立刻報 `AddRejected`；llm kernel 舊信處理完就刪） | [2026-11](2026-11/2026-11-04.md#2026-11-04) |
| 2026-11-03 | 定：`aos-eca-hub` 改名 `aos-eca-ctl`（不留舊名、舊紀錄照舊名，代定 6 條） | [2026-11](2026-11/2026-11-03.md#2026-11-03) |
| 2026-11-02 | 定：使用者 CPU 類比（CF／CD／CO＝指令位置、STACK／WS＝兩個主暫存器、ENTRY 與 cwd 無關）只記原文；試驗場 bob-cathy 代定 8 條 | [2026-11](2026-11/2026-11-02.md#2026-11-02) |
| 2026-11-01 | 定：parts 降為 agent 慣例層的約定（aos-exec 格式的 `parts.json`）、以刪掉 aos-parts 為目標；註冊檔與固定名字共存；round 不重切、使用者要深思；parts.json 不併；收五格的門檻只當參考、比技術棧優缺點；A 題當天做完：`aos-parts` 刪了、沒留殼（器官共用 `lib/agent/parts.py`），`parts.json` 換 aos-exec 格式，`AOS_ROUND_ON_EMPTY` 改 `aos-round --on-empty`（另：10 月每日檔收成月摘要）；下午試驗場現場開始（agents/bob 兩個檔跑通），使用者定原則：環境變數像 Janet 的 `dyn`、只在必要時用；晚上裁環境變數五題（hub 型不改、腦到時候再說、格旋鈕 42 個改 argv／檔、傳話筒待裁、`AOS_ENTRY` 不拿掉）、刪 aos-round 整支、整體瘦身明天再說 | [2026-11](2026-11/2026-11-01.md#2026-11-01)、[10 月月摘要](2026-10.md) |
| 2026-10-31 | 定：parts 與 fsm 平級進標準庫層（fable 收斂建議改成 aos-exec 約定＋薄殼，待裁）；固定名字限縮到單一入口檔；aos 環境變數補 AOS_ 前綴（「都按照預設」）；round 先單檔、不重切 | [2026-10](2026-10-parts/17-10-31.md#2026-10-31)、[結論](../../proto8/thinking/2026-10/31/parts-round/README.md) |
| 2026-10-30 | 定：agent 這層是訊息 queue、aos-loop 是 agent 的內部組件；外部 coding agent 是黑盒子、生命週期在外面包；aos-hub 改 aos-eca-hub；round 化作 loop／fsm 薄殼 | [2026-10](2026-10-parts/16-10-30.md#2026-10-30)、[結論](../../proto8/thinking/2026-10/29/agent-bob/README.md#決定10-30) |
| 2026-10-29 | 定：窗與投遞並列、身分＝路徑、紀錄不進交流標準；介質後續規劃都照建議；agent 的輸入是 queue（`history.jsonl`），塞話偷看共用 aos-say／listen | [2026-10](2026-10-parts/15-10-29.md#2026-10-29)、[結論](../../proto8/thinking/2026-10/28/medium/README.md) |
| 2026-10-28 | 定：hub 以 kernel 記的為準、分 pause／stop；aos-tools 註冊檔（每個 agent 資料夾一份）；agent 的各種單位都要是 aos 函數；round 七條「照新做法」；格走註冊檔→固定名字→預設 | [2026-10](2026-10-parts/14-10-28.md#2026-10-28)、[結論](../../proto8/thinking/2026-10/28/hub-kernel/README.md)、[aos-tools](../../proto8/thinking/2026-10/28/aos-tools/README.md)、[hub 實作](../../proto8/thinking/2026-10/28/hub-adapter/README.md)、[agent 操作](../../proto8/thinking/2026-10/28/agent-ops/README.md)、[一輪 round](../../proto8/thinking/2026-10/28/agent-round/README.md) |
| 2026-10-27 | 定（代定、可翻案）：很多 claude 由 aos-hub 統一列出、cd 一個指令接入、閒置收起再 `--resume` 叫回；外部 claude 經 MCP（aos-mcp）叫 aos 的資料夾程式 | [2026-10](2026-10-parts/13-10-25至10-27.md#2026-10-27)、[結論](../../proto8/thinking/2026-10/27/claude-switch/README.md) |
| 2026-10-26 | 定：proto8 條文收進 `docs/`、雜項收進 `extras/`；tidy 加原則 5「內容精簡」；wf-lint 改可選；日誌每條一行、結論只連過去、月底收月摘要 | [2026-10](2026-10-parts/13-10-25至10-27.md#2026-10-26)、[結論](../workflows/common/user/02-交接與收工.md#日誌怎麼寫2026-10-26-定) |
| 2026-10-25 | 定：C-54 計數一律 `counter_<被數的>`、上限 `max_*`、時間點 `<發生了什麼>_at`；context 用到約 30% 就換手 | [2026-10](2026-10-parts/13-10-25至10-27.md#2026-10-25)、[結論](../../proto8/docs/CONCEPTS/01-設計理念/C-54-命名方法.md) |
| 2026-10-24 | 定：當天各項嘗試都照建議做、可翻案，落條文等使用者看過；loop／fsm／daemon 的 `exec` 可直接放內嵌單子；存取控制純靠 Linux | [2026-10](2026-10-parts/12-10-24.md#2026-10-24)、[真腦實測交接](2026-10/2026-10-24-真腦實測/README.md)、[結論](../../proto8/thinking/2026-10/24/exec-relative/README.md#10-24-稍晚exec-直接放單子路-3-採用) |
| 2026-10-23 | 定：命名照 C-54 統合（入口 `_entry`、`.stack/`、要跑什麼一律 `exec`、純文字帶 `.txt`）；刪 Python 版、全用 C++；`$ref` 可寫陣列 | [2026-10](2026-10-parts/11-10-23.md#2026-10-23)、[結論](../../proto8/docs/CONCEPTS/01-設計理念/C-54-命名方法.md) |
| 2026-10-22 | 定：分層＝核心 aos-exec＋loop／daemon、標準庫 fsm、最上層 agent／kernel（C-74）；`.env` 預設不蓋已有環境變數；aos-tick 功用未定、擱置 | [2026-10](2026-10-parts/10-10-22.md#2026-10-22)、[結論](../../proto8/docs/CONCEPTS/01-設計理念.md#分層10-22-使用者定) |
| 2026-10-21 | 定：aos-exec 旗標放在 XXX 前面、支援 `.env`；沒 `argv` 的 JSON 物件當資料夾一路往下（加 `AOS_CO`）；loop／daemon／fsm 只收一個設定檔 | [2026-10](2026-10-parts/07-10-21之一.md#2026-10-21)、[結論](../../proto8/thinking/2026-10/21/ideas/README.md) |
| 2026-10-20 | 定：子 agent 普通工作派 opus、簡單派 sonnet、高難度規劃才派 fable；指示詞 `path` 改 `$path`、加 `$prefix`，寫法寬容但錯仍是錯 | [2026-10](2026-10-parts/06-10-20.md#2026-10-20)、[結論](../../proto8/thinking/2026-10/20/ideas.md#8-指示詞改版pathprefix寬容10-20-晚) |
| 2026-10-19 | 定：資料夾＝程式，入口由 `AOS_ENTRY` 指，aos 只訂環境變數和一支 aos-exec；proto8-2 併進 proto8、N-52 作廢；aos 的程式都不動 PATH | [2026-10](2026-10-parts/05-10-19.md#2026-10-19)、[結論](../../proto8/docs/CONCEPTS/01-設計理念.md#資料夾程式與環境變數10-19-使用者定) |
| 2026-10-16 | 定：C-56 補「寫什麼就做什麼」、`*_inherit` 帶回來；用檔案是為了借 Linux 權限（C-64）；agent 是一台狀態機、由外面 loop 驅動；frame 改叫 stack | [2026-10](2026-10-parts/04-10-16.md#2026-10-16)、[結論](../../proto8/docs/CONCEPTS/01-設計理念.md#檔案權限10-16-使用者定) |
| 2026-10-15 | 定：KISS 是最高原則（C-56），巢狀徹底切乾淨、上層不看也不知道下層；設計時默認沒有指示詞可用（N-45）；少用 sh | [2026-10](2026-10-parts/03-10-15.md#2026-10-15)、[結論](../../proto8/docs/CONCEPTS/01-設計理念.md#最高原則10-15-深夜使用者定原文) |
| 2026-10-14 | 定（使用者「隨你」）：ret／err 用方案 B，結果從 state 窗讀、stderr 只在出錯時長；被殺時只寫一半的 JSON 不算結果 | [2026-10](2026-10-parts/02-10-12至10-14.md#2026-10-14)、[結論](../../proto8/thinking/2026-10/14/json-entry/15-ret與半份JSON.md#42-使用者拍板經協調-agent-轉達使用者兩題都說隨你) |
| 2026-10-13 | 定：命令列與 `$ref` 支援 `檔#/位置`；不做 `AOS_INST_SELF`；`_metainfo` 格式自由；tick-tock 就是時鐘（C-44）、規範比實作重要（C-45） | [2026-10](2026-10-parts/02-10-12至10-14.md#2026-10-13)、[結論](../../proto8/thinking/2026-10/13/json-path/01-原文決定結論.md#1-決定2026-10-13) |
| 2026-10-12 | 定：proto7-2 太繁複、改開 proto8；thinking 只留原文、決定、結論；清帳（AI 問的舊題、proto7-2 頭腦風暴題與 WAIT_USER 舊帳都不追） | [2026-10](2026-10-parts/02-10-12至10-14.md#2026-10-12)、[結論](../workflows/common/user/03-討論紀錄與規劃.md#討論紀錄只留原文決定結論2026-10-12-夜改) |
| 2026-10-09 | 定（使用者 19:00）：模型分級轉正、心跳可設定、清理先留、LiteLLM 提示不改；對使用者一律 ELI5、少用隊名代號 | [2026-10](2026-10-parts/01-10-02至10-09.md#2026-10-09) |
| 2026-10-05 | 只有實作（proto7-2）；修假綠測試的改動兩次弄掛 WSL，丟棄不再做 | [2026-10](2026-10-parts/01-10-02至10-09.md#2026-10-05) |
| 2026-10-04 | 定：使用者要求開下一批前先停、等他看 W1～W12；`proto7/user-advice.md` 不碰；commit 一律 `git commit <paths>` | [2026-10](2026-10-parts/01-10-02至10-09.md#2026-10-04) |
| 2026-10-03 | 定：kernel／agent 只是探針、精力放 daemon／tick，普通的頂層代定、稍大才問；分層最重要原則是操作與協議用 JSON／文字、LLM 可讀 | [2026-10](2026-10-parts/01-10-02至10-09.md#2026-10-03) |
| 2026-10-02 | 定：proto6 擱置（tick 與 daemon 不做 node 模組、`peers` 先不做）；超標檔先刪過時內容再考慮拆 | [2026-10](2026-10-parts/01-10-02至10-09.md#2026-10-02) |
| 2026-09-25 | 生工人改預設開、不用人批；每公司一個 daemon 和 kernel；llm cpu 總上限 25；市場品質分乘成功率與審查係數 | [2026-09](2026-09.md#2026-09-25) |
| 2026-09-24 | kernel 改池表、daemon 宣告式補足；開機合一家不合一；權限牆與自動壓縮等多題照裁決；模型版工具預設關 | [2026-09](2026-09.md#2026-09-24) |
| 2026-09-23 | 使用者定 cpu 範式：一家一主人、JSON-RPC、所有 request 都是 aos-exec，寫成 cpu／kernel／daemon 三份規範 | [2026-09](2026-09.md#2026-09-23) |
| 2026-09-22 | 23 題逐題拍板；proto5.1 程式整套搬進 proto5；協議 xxx、實作 aos-xxx 命名對齊 | [2026-09](2026-09.md#2026-09-22) |
| 2026-09-21 | proto5 規範先行（inst-posix、directives、agent），proto4-3 凍結當參考 | [2026-09](2026-09.md#2026-09-21) |
| 2026-09-13 | Claude 訂閱不冒充、走 headless；等待語意＝宣告要等的檔；順序是 LLM cpu→syscall→agent 狀態機 | [2026-09](2026-09.md#2026-09-13) |
| 2026-09-09 | proto4-3：key＝inst.json 路徑；daemon＝cpu 管理者、kernel＝第一個程序；proto4-2 作廢 | [2026-09](2026-09.md#2026-09-09) |
| 2026-09-06 | proto2 重建、工具發想全照建議；qa 不能自寫自驗；09-08 翻案 inst 回資料 inst.json、cpu＝反覆執行它的 process | [2026-09](2026-09.md#2026-09-06) |
| 2026-09-05 | 構想重整成新 ideas、照它寫 spec，現有程式碼不當憑據；隔天起改走 proto2 | [2026-09](2026-09.md#2026-09-05) |
| 2026-08-30 | 五個 C++ 核心小專案與 core/tool、core/tick 落地，協定定在 PROTOCOL；home daemon 只有 spec 不實作；等使用者的事只看 WAIT_USER | [最小原型](2026-08.md#2026-08-30-最小原型)、[晚](2026-08.md#2026-08-30-晚)、[深夜](2026-08.md#2026-08-30-深夜)、[WAIT_USER](2026-08.md#wait_user-集中說明2026-08-30) |
| 2026-08-29 | roadmap-run 凍結、全部重來；重寫的人從 salvage 讀起 | [2026-08](2026-08.md#2026-08-29) |
| 2026-08-28 | 拷問停、邊實作邊想，驗出的坑收進 gotchas；開 roadmap（隔天作廢） | [拷問](2026-08.md#2026-08-28-拷問)、[roadmap](2026-08.md#2026-08-28-roadmap) |
| 2026-08-25 | 研討會收成 OPEN-QUESTIONS／BACKGROUND；使用者不想看就用實測取代拍板 | [研討會](2026-08.md#2026-08-25-研討會收場)、[T5](2026-08.md#2026-08-25-t5) |
| 2026-08（未標日期） | 排隊是外部處理器的家務；llms／tooljson 擱置排在 agent loop 後；C ABI 之後再加 | [2026-08](2026-08.md#未標日期原列在-08-25-之後) |
