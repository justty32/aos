# aos 問題總表 1113：把 11-13 晚各條線記下的「撞到的 aos 問題／試驗紀錄」合併成一張表（只整理，不判斷設計、不提新方案）

← [2026-11-13](README.md)｜來源：[gpt-fsm-team 06](gpt-fsm-team/06-試驗紀錄.md)（T1～T43）、[user-zone-plan 06](user-zone-plan/06-試驗紀錄.md)（專06）與 [07](user-zone-plan/07-使用者裁定與施工.md)（專07-T）、[wf-into-aos-plan 06](wf-into-aos-plan/06-試驗紀錄.md)（wf）、[agents-feedback-1113-題目](agents-feedback-1113-題目.md)（意；只取還沒做的，T24 已做不收）、[wake-timer](wake-timer.md)（鐘）、[ref-path-rules](ref-path-rules.md)（址）、[sandbox-sender-fix](sandbox-sender-fix.md)（修）。

優先序：高＝會出錯或會害資料；中＝不順；低＝小事。狀態：已修（commit）／在修（哪條線）／沒動。「已修」＝repo 程式與文件已進 commit，活樹執行檔或抄本是否已換看備註。同一件事不同來源併成一條，來源編號都列。agents-feedback 題單自己標的優先序（T01、T02、T05 等標高）與本表按上面定義重排的不同，以本表為準。wake-timer、ref-path-rules 沒有獨立的試驗紀錄段，只取其中明寫的缺口。

| # | 優先 | 現象 | 影響 | 來源 | 狀態 |
|---|---|---|---|---|---|
| 1 | 高 | aos-sandbox 的 rw 最後綁、蓋過 ro，表達不了「repo 可寫、.git 唯讀」 | 想讓工人寫 repo 又保護 .git 做不到 | [gpt T32](gpt-fsm-team/06-試驗紀錄.md)、[修 T32](sandbox-sender-fix.md) | 已修（a3d99b933） |
| 2 | 高 | 在沙箱裡寫沒綁的路徑（$HOME 等）會「成功」：寫進暫存根、退 0、主機沒檔 | agent 以為寫成了，事後才發現檔不在 | [gpt T36](gpt-fsm-team/06-試驗紀錄.md)、[修 T36](sandbox-sender-fix.md) | 已修（a3d99b933） |
| 3 | 高 | 腦請求的寄件人取工作區、不是 stack：同工作區的 agent 共用一份額度，信箱與額度兩處身分不一致 | 分不出誰花的；額度對不上人。（信箱信封與 aos-lock 仍用工作區優先，代定不動；C++ 執行檔活樹待停樹換） | [gpt T31](gpt-fsm-team/06-試驗紀錄.md)、[gpt T38](gpt-fsm-team/06-試驗紀錄.md)、[修 B](sandbox-sender-fix.md) | 已修（8706d7398） |
| 4 | 高 | 額度 senders 的 key 寫錯不明顯、等於沒設（key 相對 kernel stack，不是定義夾） | 以為有每寄件人上限，其實沒有 | [gpt T39](gpt-fsm-team/06-試驗紀錄.md)、[修 T39](sandbox-sender-fix.md) | 已修（8706d7398） |
| 5 | 高 | 沙箱設定寫壞＝不套沙箱照跑，只在 stderr 印 warning | 以為關住了其實沒關。（與使用者 11-12 晚「出事自己負責」裁定衝突，待裁） | [gpt T21](gpt-fsm-team/06-試驗紀錄.md)、[修 T21](sandbox-sender-fix.md) | 沒動 |
| 6 | 高 | 檔案工具不擋工作區外、shell 沒有指令黑白名單；eca 的 before_tool 看不到 CLI 自己的 Bash／Write | 寫壞 repo 外的東西、擋 git commit、commit 前跑 codemap_gen 都只能靠自律 | [gpt T4](gpt-fsm-team/06-試驗紀錄.md)、[wf 3](wf-into-aos-plan/06-試驗紀錄.md)、[專06-11](user-zone-plan/06-試驗紀錄.md) | 沒動 |
| 7 | 高 | 同帳號：全套 agent 與使用者是同一個 linux uid，「只有使用者能寫的夾」用檔案權限做不到 | 專區、守門只能算紀律，刻意造假擋不住（AGENTS.md 已寫明） | [專06-10](user-zone-plan/06-試驗紀錄.md)、[專06-11](user-zone-plan/06-試驗紀錄.md) | 沒動 |
| 8 | 高 | 信箱寄件人自報：from 可任意給、信封 sender 由環境變數算；送進 queue 的信沒有寄件人欄 | 指揮分不出 DONE 信真假；agent 分不出人打的還是轉的 | [gpt T14](gpt-fsm-team/06-試驗紀錄.md)、[專06-2](user-zone-plan/06-試驗紀錄.md)、[專06-13](user-zone-plan/06-試驗紀錄.md) | 沒動 |
| 9 | 高 | 轉述的「使用者同意了」沒辦法驗證；使用者的裁定只靠信件轉述；手機答覆天生是轉述 | push、刪檔等要使用者本人的事無從確認 | [意 T08](agents-feedback-1113-題目.md)、[意 T09](agents-feedback-1113-題目.md)、[專06-12](user-zone-plan/06-試驗紀錄.md)、[專06-16](user-zone-plan/06-試驗紀錄.md) | 已修（bfd40f05c） |
| 10 | 高 | 設了 AOS_LINUX_USER_STACK 後，任何 agent 的 shell 打 aos-mailbox read（沒帶 -s）都讀到使用者專區並讀完就刪；read 預設讀完即刪 | 使用者的信會被 agent 讀掉、刪掉，new/ 裡沒看過的連警告都沒有 | [專07-T1](user-zone-plan/07-使用者裁定與施工.md)、[專06-3](user-zone-plan/06-試驗紀錄.md) | 沒動 |
| 11 | 高 | jsonx 的寫入有 follow，會順 $ref 寫到別的檔，守門程式只看 path 擋不住 | 給 jsonx 等於開任意寫 | [gpt T35](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 12 | 高 | agents_ctl 能 rm daemon 表上任何 agent；agent_def tools/llm/system 直接改共用定義且沒有 reset | 指揮可動到活樹其他 agent 或所有工人共用的定義 | [gpt T7](gpt-fsm-team/06-試驗紀錄.md)、[gpt T20](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 13 | 高 | hook handler 是 symlink 時 aos-exec 用真實路徑當 argv[0]，handler 找不到旁邊的設定檔，on_error stop 把 astra 停掉 | 共用守門不能靠 symlink 放進各定義；單元測試是好的、掛上才壞 | [gpt T37](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 14 | 高 | 在 agent 的 shell 裡起樹會起錯位置 | 活樹可能被起在錯處，停樹重起時再出事 | [意 T07](agents-feedback-1113-題目.md) | 沒動 |
| 15 | 高 | 知識庫（與 lib）活樹抄本落後正本，且看不出抄自哪個 commit；改了要重抄／停樹換才生效 | repo-aos 讀到的是舊節點；新程式、新旗標活樹沒有 | [意 T05](agents-feedback-1113-題目.md)、[wf 17](wf-into-aos-plan/06-試驗紀錄.md)、[鐘 施工紀錄](wake-timer.md)、[修 沒做的](sandbox-sender-fix.md) | 沒動 |
| 16 | 高 | $ref 與 index 路徑的舊規則各寫各的、# 左右的意思不統一（使用者 11-13 晚要求統一） | 兩邊條文與程式不一致；index 半已接共用解析器，$ref 的 C++ 半停在件數 gate | [址](ref-path-rules.md) | 在修（線址：$ref 路徑） |
| 17 | 中 | agent-fsm 沒有「做完就退」：腦停下回 idle 空等，佔 daemon 一格 | 工人不會自己消失，要母或人 rm | [gpt T1](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 18 | 中 | 沒有步數或總 token 上限；--max-tool-calls 要手改 fsm.json，agent_def 改不了 | 繞圈的工人只能靠外面 stop | [gpt T2](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 19 | 中 | 子 agent 做完沒有主動通知母；subagent ask 會卡住母的 act 格（上限 30 分） | 指揮帶多個工人只能輪流 listen 或等信，每次 listen 算一次工具呼叫 | [gpt T3](gpt-fsm-team/06-試驗紀錄.md)、[gpt T24](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 20 | 中 | listen 取「最後一則不帶工具的回答」：工人中途說一句就被當回報；也不能指定等哪一封 | 工人講一半停下就被誤判完成 | [gpt T28](gpt-fsm-team/06-試驗紀錄.md)、[意 T13](agents-feedback-1113-題目.md) | 沒動 |
| 21 | 中 | 母可透過 subagent op hook／tools／llm／system 改子的覆蓋層；有 self／events 包就能拆守門、加回工具；self_llm 可換成貴的包 | 指揮或工人的權限上限＝實際能給的上限，最小權限只能靠不給包 | [gpt T5](gpt-fsm-team/06-試驗紀錄.md)、[gpt T6](gpt-fsm-team/06-試驗紀錄.md)、[gpt T12](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 22 | 中 | 活樹／出廠 llm kernel 的模型名跟家機 proxy 對不上、沒有 astra 與 effort 包；家機活樹沒有 llm kernel；知識庫沒寫怎麼加 endpoint 包 | 照文件填會 EndpointUnknown；agent-fsm 卡在 wait 格 | [gpt T9](gpt-fsm-team/06-試驗紀錄.md)、[gpt T10](gpt-fsm-team/06-試驗紀錄.md)、[gpt T33](gpt-fsm-team/06-試驗紀錄.md)、[gpt T8](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 23 | 中 | llm_http 只打 chat/completions、沒有 responses API、沒有讀取逾時與 429／5xx 重試；推理內容跨工具呼叫能否接上沒驗 | proxy 卡住只能等；gpt 系可能每步重想、變慢變貴 | [gpt T11](gpt-fsm-team/06-試驗紀錄.md)、[gpt T30](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 24 | 中 | 頂層（不在樹裡的 Claude Code）沒有 mail_notify，只能自己輪詢；mail_notify 新起來時不提醒已在等的信 | 頂層要盯 DONE 信得自排輪詢；先寄後起的 agent 不會被叫醒 | [gpt T15](gpt-fsm-team/06-試驗紀錄.md)、[gpt T16](gpt-fsm-team/06-試驗紀錄.md)、[專06-18](user-zone-plan/06-試驗紀錄.md) | 沒動 |
| 25 | 中 | ctl rm 母不會連子一起收；同名同 stack 再 add 會接舊 history | 孤兒子 agent；工人名字不能重用，與額度 key 互相牽制 | [gpt T25](gpt-fsm-team/06-試驗紀錄.md)、[gpt T26](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 26 | 中 | --history task 以最後一則 user 訊息切任務，mail_notify／goal 提醒也是 user 訊息 | 有信箱的指揮不能用 task 模式，只能帶完整 history（貴） | [gpt T27](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 27 | 中 | 單一 main、沒有工作區隔離；守門 hook 限不到「這張單的檔」 | 多工人並行越界只能事後驗收發現 | [gpt T29](gpt-fsm-team/06-試驗紀錄.md)、[wf 9](wf-into-aos-plan/06-試驗紀錄.md) | 沒動 |
| 28 | 中 | shell 黑名單只看 git commit 的常見寫法（加全域選項就繞過）；gpt 工人用 shell >> 寫檔，守門只看指令不看寫到哪 | 守門只是第一道，真正擋住的是沙箱 | [gpt T41](gpt-fsm-team/06-試驗紀錄.md)、[gpt T43](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 29 | 中 | aos-daemon-ctl add／rm 的回信信箱預設開在呼叫者的 stack 底下，不用也留著；aos-daemon 會重排 cur/ 殘骸 | 在別人 stack 留下新夾；專區借 cur/ 的做法哪天被 daemon 接管會撞 | [gpt T42](gpt-fsm-team/06-試驗紀錄.md)、[專06-7](user-zone-plan/06-試驗紀錄.md) | 沒動 |
| 30 | 中 | 人沒有新信通知（mail_notify 只掛 agent）；repo 沒有任何桌面／手機通知實作 | 使用者不知道有新信 | [專06-4](user-zone-plan/06-試驗紀錄.md)、[專06-15](user-zone-plan/06-試驗紀錄.md) | 沒動 |
| 31 | 中 | ~/aos-home/ws/public、ws/tools、ws/temp 家機原本都不存在；沒有撐過關機又不在 repo 的持久暫存處 | agent 沒地方放共用／暫存的東西（public、tools 已於 bfd40f05c 建；temp 未確認） | [專06-17](user-zone-plan/06-試驗紀錄.md)、[wf 13](wf-into-aos-plan/06-試驗紀錄.md)、[意 T06](agents-feedback-1113-題目.md) | 沒動 |
| 32 | 中 | aos hook 沒有 compact 事件、沒有每輪前注入事件（畫面 hook 只記帳） | HANDOFF 讀回只能靠 CLI 的 SessionStart hook | [wf 1](wf-into-aos-plan/06-試驗紀錄.md)、[wf 2](wf-into-aos-plan/06-試驗紀錄.md)、[wf 16](wf-into-aos-plan/06-試驗紀錄.md) | 沒動 |
| 33 | 中 | 知識庫 rules.json 沒有程式讀進 prompt；system.txt 與定義在 ~/aos-home 不進 git，兩台機器各長各的 | 規矩靠 agent 自己去讀；家機與公司機漂移 | [wf 4](wf-into-aos-plan/06-試驗紀錄.md)、[wf 5](wf-into-aos-plan/06-試驗紀錄.md) | 沒動 |
| 34 | 中 | aos 信箱不跨機器、與 wf/inbox 不互通；沒有廣播、topic、團隊信箱、進度板；信讀後無留痕 | 跨機器的信與公告要走 repo | [wf 6](wf-into-aos-plan/06-試驗紀錄.md)、[wf 11](wf-into-aos-plan/06-試驗紀錄.md)、[wf 12](wf-into-aos-plan/06-試驗紀錄.md) | 沒動 |
| 35 | 中 | goal／todo 不給 eca、不進 git；goal 只是一句話無工單欄位；外面看不到工人的 todo；goal 被標 abandoned 後 resume 回 GoalEnded | 跨 session 沒做完的事沒對應；BLOCKED 後續做得重寫整句 goal | [wf 8](wf-into-aos-plan/06-試驗紀錄.md)、[gpt T17](gpt-fsm-team/06-試驗紀錄.md)、[gpt T18](gpt-fsm-team/06-試驗紀錄.md)、[gpt T40](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 36 | 中 | 通用版 knowledge/wf 缺 HANDOFF、CLAIMS、inbox 等對應；$ref 只能整段換、沒有覆蓋式寫法；_index 一格的 index 只能指另一份 index | wf 轉入 aos 時只能用額外鍵 base 當約定 | [wf 14](wf-into-aos-plan/06-試驗紀錄.md)、[wf 15](wf-into-aos-plan/06-試驗紀錄.md)、[wf 18](wf-into-aos-plan/06-試驗紀錄.md) | 沒動 |
| 37 | 中 | json 的 #/鍵 引用沒有任何工具查（check_anchors 只查 md）；index_gen 手寫 index 得先登記 hand_indexes | md 轉 json 後斷掉的引用只能靠 git grep；--apply 可能蓋掉手寫的 | [wf 19](wf-into-aos-plan/06-試驗紀錄.md)、[wf 20](wf-into-aos-plan/06-試驗紀錄.md) | 沒動 |
| 38 | 中 | 別條線同時在暫存（staged）檔案 | commit 若不點名檔會把別線的暫存一起帶走 | [wf 24](wf-into-aos-plan/06-試驗紀錄.md) | 沒動 |
| 39 | 中 | gpt 隊兩份定義拿掉 events 包後，沒有任何叫醒自己的工具（clock_register、self_hook 都在 events 包） | astra、sol 不能設計時器（寄給線隊決定） | [鐘 一、代定 6](wake-timer.md) | 沒動 |
| 40 | 中 | 子 agent 不能寄信，主 agent 變傳話筒 | 主 agent 被當傳話筒（已裁，待施工） | [意 T01](agents-feedback-1113-題目.md) | 沒動 |
| 41 | 中 | new_mail 通知只說幾封、誰寄，每次都打斷 | 打斷成本高（已裁，待施工） | [意 T02](agents-feedback-1113-題目.md) | 沒動 |
| 42 | 中 | 寄出的信沒有回執；回應沒帶寄出時間 | 寄出後不知有沒有到 | [意 T03](agents-feedback-1113-題目.md) | 沒動 |
| 43 | 中 | a2a 名稱每次重開都變 | agent 間用舊名稱找不到人（已裁：改用 aos 名稱走信件） | [意 T04](agents-feedback-1113-題目.md) | 沒動 |
| 44 | 中 | 獨立 proc 的停法不清楚；重複事件要自己去重 | 不知怎麼收掉；事件重複處理 | [意 T10](agents-feedback-1113-題目.md)、[意 T11](agents-feedback-1113-題目.md) | 沒動 |
| 45 | 中 | set-def 換完沒印換前換後；mcp.json 要跑一輪才更新 | 不確定換成了沒 | [意 T15](agents-feedback-1113-題目.md) | 沒動 |
| 46 | 中 | 想要 rename 指令（已裁：用 ctl rm＋ctl add -s 兩步，說明待補）；沒有一鍵健康檢查；停樹起樹沒包成指令 | 改名、起停樹、起完核對都手工 | [意 T19](agents-feedback-1113-題目.md)、[意 T20](agents-feedback-1113-題目.md)、[意 T21](agents-feedback-1113-題目.md) | 沒動 |
| 47 | 中 | 新工作區沒有鋪初始檔案的機制 | 每次新工作區手工起骨架 | [意 T23](agents-feedback-1113-題目.md) | 沒動 |
| 48 | 低 | effort 只能一個後綴一個 endpoint 包；額度只有次數與 token、沒有金額 | 包表變長；astra 價格無法直接換算成錢 | [gpt T8](gpt-fsm-team/06-試驗紀錄.md)、[gpt T13](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 49 | 低 | on_clock hook 只在每格開頭檢查，卡在長的 wait／act 時不跑 | 做不了卡住看門狗 | [gpt T19](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 50 | 低 | 文件兩個入口講單支關（aos-agent tools rm 與 self_tools rm）；07 分檔待補三條仍空 | 讀者不知誰管誰 | [gpt T22](gpt-fsm-team/06-試驗紀錄.md)、[gpt T23](gpt-fsm-team/06-試驗紀錄.md) | 沒動 |
| 51 | 低 | 人用的 mailbox_send 與 aos-mailbox send 不收多的 key；--box 寄到不存在的夾不替人建；aos-post take 只認最舊一封；reply_to 在 symlink 下沒驗過；aos-post 不擋 cur/ 同名 | 寄信或認領時的小地雷；兩封同名信搬 done/ 會撞 | [專06-1](user-zone-plan/06-試驗紀錄.md)、[專06-5](user-zone-plan/06-試驗紀錄.md)、[專06-6](user-zone-plan/06-試驗紀錄.md)、[專06-8](user-zone-plan/06-試驗紀錄.md)、[專07-T7](user-zone-plan/07-使用者裁定與施工.md) | 沒動 |
| 52 | 低 | ~/.aos/log.md、~/.aos/say/ 不知誰建誰用；world.json 沒寫 ~/.aos 與 ~/aos-home 佈局；公司 WSL 的 systemd --user、linger 沒查 | 文件缺漏 | [專06-9](user-zone-plan/06-試驗紀錄.md)、[專06-14](user-zone-plan/06-試驗紀錄.md) | 沒動 |
| 53 | 低 | 刪掉 ~/.aos/stack/mailbox 後，沒設變數的 shell 打 aos-mailbox where／send 會重建；知識庫路徑相對工作區（mailbox_send 寄專區要給絕對路徑，~ 不展開） | 舊信箱被悄悄長回；寄專區失敗 | [專07-T2](user-zone-plan/07-使用者裁定與施工.md)、[專07-T4](user-zone-plan/07-使用者裁定與施工.md) | 沒動 |
| 54 | 低 | 使用者的 zsh source env.sh 帶 AOS_STACK／AOS_WS，回信寄件人變成那棵樹的 ws；zsh 裡 q2:c* 被當萬用字元；claude 身的 Read 讀名片被權限擋 | aos-user 回信時自己換環境（已在 aos-user 端處理）；其餘要加引號、改用 aos-user door | [專07-T3](user-zone-plan/07-使用者裁定與施工.md)、[專07-T5](user-zone-plan/07-使用者裁定與施工.md)、[專07-T6](user-zone-plan/07-使用者裁定與施工.md) | 沒動 |
| 55 | 低 | aos 沒有領地／租約機制；index_view 只讀不生成（沒有 index_gen／index_check 對應） | CLAIMS、index 只能留 repo 自己的 | [wf 10](wf-into-aos-plan/06-試驗紀錄.md) | 沒動 |
| 56 | 低 | 過時文件與不實回報：.claude/commands/wf-lint.md 事實已過時；git 最後 commit 時間不能判斷工作流最後被用；子 agent 回報的路徑要抽查 | 文件與盤點容易誤導 | [wf 21](wf-into-aos-plan/06-試驗紀錄.md)、[wf 22](wf-into-aos-plan/06-試驗紀錄.md)、[wf 23](wf-into-aos-plan/06-試驗紀錄.md) | 沒動 |
| 57 | 低 | codex 的 .git 預設唯讀、沒提示；啟動時身分會被舊文件誤導；compact 後 MCP 工具要先查 schema（不是 aos 的事） | 小地雷 | [意 T16](agents-feedback-1113-題目.md)、[意 T17](agents-feedback-1113-題目.md)、[意 T18](agents-feedback-1113-題目.md) | 沒動 |
| 58 | 低 | ctl state NAME 要寫成 --target NAME（ArgumentsBad）；舊畫面的 ClockMissing 沒提示關掉重開；ctl ls -l 多一欄畫面 | 指令小不順 | [意 T12](agents-feedback-1113-題目.md)、[意 T14](agents-feedback-1113-題目.md)、[意 T22](agents-feedback-1113-題目.md) | 沒動 |

## 統計

| 項目 | 條數 |
|---|---|
| 總條數 | 58 |
| 優先：高 | 16 |
| 優先：中 | 31 |
| 優先：低 | 11 |
| 狀態：已修 | 5 |
| 狀態：在修 | 1 |
| 狀態：沒動 | 52 |
