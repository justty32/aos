← [thinking](README.md)｜Fable 打撈七代探針的發現，2026-10-11

# 七代探針真正「探到」的東西

**這份是什麼**：使用者 10-11 說兩個月的程式「作為探針，替我探究到了一些問題」。這裡只撈**做了才知道**的發現——實跑出來的數字、撞到才看見的坑、真模型的實際行為。設計決定、功能清單、裁決理由都不收（那些在各代 notes 裡自己有家）。

**怎麼讀**：四組（a 模型行為、b 行程與檔案、c daemon／tick、d 工作流）。第三欄是「在 proto8『一切都是 POSIX 行程、資料夾＝空間、tick＝時間』的模型下還成立嗎」：**成立**＝核心要面對；**任務自己的事**＝核心不管、但寫 agent／排序行程的人會再踩；**不成立**＝proto8 的模型讓它消失。每條都可點回原檔查數字與怎麼量的。

**只看五條的話**：a-2（文字交件）、a-4（整包勝過一步步問）、b-5（在飛請求被殺就永遠卡住）、c-2（每回合產檔＝垃圾）、d-1（立法跑在實作前太遠）。

---

## a. 關於 LLM 行為的實測（15 條）

| # | 發現（一句白話） | 哪一代、哪個檔 | proto8 下 | 對 proto8 的一句建議 |
|---|---|---|---|---|
| a-1 | 笨模型（luna）25～50% 的回應不是合法 JSON：`"."`、`[]`、亂碼、`</final>` 殘渣、空字串；deepseek／haiku 一次都沒壞 | proto7-1 [problems-real R-5](../../proto7-1/notes/problems-real.md) | 成立 | LLM 節點後面**一定**接一個程式節點驗格式＋重問一次；把它當 S 表示式裡的固定節點，不是可選項 |
| a-2 | 交件格式改成純文字段落（`=== 路徑 ===`）之後，luna 被格式擋下的輪次從一半掉到幾乎 0（4×6×2 題只剩 3 輪） | proto7-2 [apprentice-5](../../proto7-2/notes/play/2026-10-09-real-ai/apprentice-5.md)、[menu-ab](../../proto7-2/notes/play/2026-10-10-menu-ab/README.md) | 成立 | 和 LLM 交換「成品」用文字段落；JSON 留給程式對程式 |
| a-3 | 讀自己寫的技能書有效：同類坑第 2～4 題一次就過 0/33 → 21/33，輪數 2.78 → 1.33（p＝0.001）；但前一輪 AP4 題目坑不同就沒證明 | proto7-2 [apprentice-5](../../proto7-2/notes/play/2026-10-09-real-ai/apprentice-5.md)、[apprentice-4](../../proto7-2/notes/play/2026-10-09-real-ai/apprentice-4.md) | 任務自己的事 | 核心只要給 agent 一個「自己可寫、下次會被放進 system prompt」的檔；證明過的是「同一種坑記得住」，不是「學得會新坑」 |
| a-4 | 一步步問（選單）**輸給**一次交整包：同模型同三題，整包 12/15、分層 2/15，分層 token 還多 1.8 倍；輸的原因是每步只看得到一段需求、選錯段就修不到 | proto7-2 [menu-ab](../../proto7-2/notes/play/2026-10-10-menu-ab/README.md) | 成立 | 拆 S 表示式時，拆出來的要是**程式節點**，不是更多更小的 LLM 節點；LLM 節點寧少寧大 |
| a-5 | 每次呼叫是單獨一問：hello 選單第一層沒附來信，10/10 都選「出口」；把那層要的資訊放進去才 10/10 過 | proto7-2 [decisions-10-10 MN1](../../proto7-2/notes/decisions-2026-10-10.md)、[menu-aos](../../proto7-2/notes/play/2026-10-10-menu-aos/README.md) | 成立 | 每個 LLM 節點的輸入要自足；「它上一步看過」不算 |
| a-6 | 本機規則敢說 none 就挑對 17/17、AI 呼叫 0；原本問 AI 挑技能 5/17 還花錢 | proto7-2 [decisions-10-09 r4 SK1](../../proto7-2/notes/decisions-2026-10-09/04-r4.md)、[longtask 問題 5](../../proto7-2/notes/play/2026-10-09-longtask/README.md) | 成立 | 這是 2.16「把模型節點換成程式節點」的成功案例；寫死的規則要**允許不選**，不然又得問 AI |
| a-7 | 便宜模型當寫手反而最貴：每張成功單 astra 132 萬 token、haiku 1950 萬、deepseek 燒光倒閉；簡單題先便宜後升級省 49% 時間，難題反貴 83% | proto5 [lessons 35](../../proto5/playbook/lessons.md)、proto7-2 [ef3](../../proto7-2/notes/play/2026-10-09-real-ai/ef3.md) | 成立 | 排「誰先用大腦」時用「總 token ÷ 成功次數」，不用單價；升級鏈只對簡單題划算 |
| a-8 | 「多問一次模型」的功能常不回本：compact 摘要要撐 11～16 問才回本；長任務 compact 只降 55%、本機摘要沒內容、journal 根本不在提示裡 | proto5 [lessons 8、9](../../proto5/playbook/lessons.md)、proto7-2 [longtask 問題 3](../../proto7-2/notes/play/2026-10-09-longtask/README.md) | 任務自己的事 | 任何「叫 LLM 幫你壓縮／描述」的節點預設關；先算回本門檻，壓的東西要真的在提示裡 |
| a-9 | LLM 只靠讀檔能看懂世界：盲讀五題 12 次有 10 次 ≥ 4/5；錯的全是「把舊事件當現況」和「規則只寫在程式註解裡、檔裡沒有」 | proto7-1 [blindread](../../proto7-1/probes/blindread/README.md) | 成立 | 2.6「檔案系統＝LLM 的自省能力」有實證；代價是**規則要寫進檔**，狀態檔要分得出「現任」與「歷史」 |
| a-10 | LLM 操作 daemon 時格式幾乎沒讀錯，錯的全是時間與生命週期：restart 用舊定義、一次性工作寫進常駐表、舊 `last_error` 當現況、cwd／子根路徑基準 | proto7-1 [infra-needs §H](../../proto7-1/notes/infra-needs.md)（N-65、N-69、Q6） | 成立 | 時間與生命週期的語意要少、字面一致；每筆錯誤帶回合戳記讓它分新舊 |
| a-11 | 代理有固定前置開銷：LiteLLM 塞 1644 token 的 Codex 系統提示（一單 63%），模型因此以為自己在 Codex 要先看檔；sol 回兩個 choice，aos 只讀 `choices[0]` 把答案丟了 | proto7-2 [proxy-overhead](../../proto7-2/notes/play/2026-10-09-real-ai/proxy-overhead.md)、[litellm-truncation](../../proto7-2/notes/play/2026-10-09-real-ai/litellm-truncation.md) | 成立 | LLM 節點的原始回應整份落盤；解析失敗先看 raw 再怪模型 |
| a-12 | 信件驅動的 agent 鏈上一個人回 none，全隊 13 分鐘沒人動；kernel 看到「大家都有進度、用量不動」＝一切正常 | proto7-1 [problems-real R-1](../../proto7-1/notes/problems-real.md) | 任務自己的事 | 「資源行程 idle」不等於沒事；排序行程要有「全員閒置＋目標未完成」的偵測，或讓 agent 定時自醒 |
| a-13 | 成果經 LLM 轉手就不是測過那份：lead 結案時記憶裡沒有 PASS 信，照自己以為的重打一份（36/36 變 29/36）宣告完成；記憶視窗也會被一個對象（ci 38 封）洗掉 | proto7-1 [problems-real R-13、R-15](../../proto7-1/notes/problems-real.md) | 任務自己的事 | agent 要有「不經 LLM 原樣搬運」的工具（save）；驗收過的東西不要再過腦袋 |
| a-14 | 一次 LLM 呼叫跨 5～75 回合，處理過的 tock 81～100% 是 idle；kernel 判「卡住」在真模型下**全是**在等 LLM 的誤判，每次誤判多付一次錢 | proto7-1 [problems-real R-3、R-8](../../proto7-1/notes/problems-real.md) | 成立 | tick 不等 LLM；對「在等外部資源」的行程另計時限，不用回合數判卡住 |
| a-15 | 新手（Haiku／luna 只讀 README）試 10 個模組全不過：第一次跑就被迫碰別的包、README 後半露內部代號、「見 spec」；menu 包改三輪才過 | proto7-2 [newbie](../../proto7-2/notes/play/2026-10-09-newbie/README.md)、[menu 新手](../../proto7-2/notes/play/2026-10-10-menu/README.md) | 成立 | 任何東西第一次跑 ≤ 2 指令、不依賴別的包；進階另放一頁 |

## b. 關於行程與檔案的坑（11 條）

| # | 發現（一句白話） | 哪一代、哪個檔 | proto8 下 | 對 proto8 的一句建議 |
|---|---|---|---|---|
| b-1 | `rename` 原子、內容不是：整個 inst 層一開始沒 fsync，崩潰後留零長度檔；而且 tmpfs 的 fsync 是 no-op，測試建在 /tmp 什麼都證不了 | 八月 [salvage 02 §三](../../wf/salvage/02-踩過的坑.md) | 成立 | 寫檔 → fsync → rename → fsync(dir)；耐久性別在 /tmp 證明；「靠隔壁副作用救到」的正確性最危險 |
| b-2 | 修好一個 bug 讓另一個 bug 現形：併發重複執行率 9.8% → 37% → 0～1%；修補當下 ctest 全綠 165 案全過 | 八月 [salvage 02 §一](../../wf/salvage/02-踩過的坑.md) | 成立 | 碰檔案系統並行的東西做完**立刻**壓力腳本打（K 支 × 200 回合量重複率／遺失率）；單元測試看不到這種事 |
| b-3 | 無聲故障最貴：rc=0、stderr 空、資料被丟；兩層對「檔案存在嗎」用不同 syscall（lstat vs open）夾出第三態；收件匣一根 FIFO 讓 `open()` 無限阻塞、六個行程疊著 | 八月 [salvage 02 §二](../../wf/salvage/02-踩過的坑.md)；proto7-1 [infra-needs N-56](../../proto7-1/notes/infra-needs.md) | 成立 | 讀外部可寫目錄前驗 `S_ISREG`、用 `O_NONBLOCK`；`opendir` 給名字不給保證 |
| b-4 | `rename` 靜默覆蓋、不互斥，`.runi` 不是鎖；check-then-act 兩支同時進來各讀一份再各自 rename | 八月 [salvage 02 §四](../../wf/salvage/02-踩過的坑.md) | 成立 | 資料夾裡的「認領」一律 `O_EXCL`／`link`／`RENAME_NOREPLACE`；發布排他與取件互斥是兩件事 |
| b-5 | brain 連同在飛的 llmcall 一起 SIGKILL，就永遠卡住：intent 已記、raw 沒到、照規則不重送、brain 沒有次數上限；心跳照跳、status 一切正常，後面 11 封信全被擋。只殺 brain 則孤兒 llmcall 寫完回條、新 brain 接得上 | proto7-2 [longtask 問題 1](../../proto7-2/notes/play/2026-10-09-longtask/README.md) | 成立 | 每筆「在途外部請求」要有次數／時間上限與人看得見的出口；「不知道」可以是狀態，不能是永遠 |
| b-6 | SIGKILL 子 daemon 留孤兒：任務被 reparent 給 init，daemon 只能每 20 ms 輪詢 /proc；pid 會重用、殭屍要讀 stat 才分得出；任務改自己寫的 pid.json 能把 kill 導去打別人；killpg 亂送在公司 WSL 整台掛兩次 | proto7-1 [problems-core P-03、P-04、P-07](../../proto7-1/notes/problems-core.md)、[infra-needs N-63、Q1](../../proto7-1/notes/infra-needs.md)；[dispatch lessons 11](../../wf/workflows/dispatch/lessons.md) | 成立 | 「一切都是行程」就得先定任務的程序邊界（subreaper 或 cgroup）；殺之前驗身分（environ／starttime），永不打 pgid 0、1、自己 |
| b-7 | 原子寫的暫存檔 `x.json.tmp.1383587` 被別人當正式檔讀到；SIGKILL 留下的 tmp 要有人掃，且只能在寫者 pid 確定不在時刪 | proto7-1 [infra-needs N-52](../../proto7-1/notes/infra-needs.md)；proto7-2 [problems A2-07](../../proto7-2/notes/problems.md) | 成立 | 暫存名 `.<名>.tmp.<pid>`；掃資料夾一律忽略 `.` 開頭 |
| b-8 | WSL 跟原生 Linux 不一樣的四件事：/tmp 不是 tmpfs、整台常關（三週 25 次開機、閒置 15 秒關 distro）、monotonic 比牆鐘慢 4% 且睡醒大跳、/mnt/c 無 UID 隔離；Landlock 只有 ABI 3；公司 WSL 8 核同時只能一條線跑程式 | proto6 [WSL 機器查證](../../proto6/notes/2026-09-29-wsl-machine-check.md)；[dispatch lessons 9](../../wf/workflows/dispatch/lessons.md) | 成立 | 「daemon 永遠活著」不能當前提；時間先後用序號不用牆鐘；重啟＝全部 unknown 是常態 |
| b-9 | 起行程的成本實測：fork/exec 0.1 ms、`systemd-run --user` +5 ms、加資源限制 +25 ms、每任務一層 cgroup +0.14 ms、git commit 2 ms；一個動作一支 Python 程序約 13 ms，這台機器約 100～150 回合／秒 | proto6 [systemd-run 延遲](../../proto6/notes/probes/systemd-run-latency.md)、[per-task cgroup](../../proto6/notes/probes/per-task-cgroup-cost.md)；proto7-1 [infra-needs N-41](../../proto7-1/notes/infra-needs.md) | 成立 | 資源也是行程、排序也是行程，數量會多：cgroup 便宜可用，systemd 每次加限制別用；interval 下限別低於直譯器啟動 |
| b-10 | 寫入順序＝恢復順序：先寫總結再寫 ended、restart 先加項再 kill、tick 先記 round.json 再清槽；反過來就是「殺了沒重起」「結束永遠不報」「總結跳號」 | proto7-1 [infra-needs N-20](../../proto7-1/notes/infra-needs.md)；proto7-2 [problems P2-03、P2-07](../../proto7-2/notes/problems.md) | 成立 | 每個兩步寫入先問「中間被殺會怎樣」；驗法是在那個點真的 SIGKILL（7-2 有 `AOS7_TEST_CRASH` 鉤子） |
| b-11 | 讀壞表當空表寫回，會把別人的項目全砍掉（實驗重現過）；壞檔當「不存在」繞過了所有保護 | proto7-2 [problems 錯誤四分支 G1](../../proto7-2/notes/problems.md) | 成立 | 讀檔四分支：沒有／OK／壞掉／不知道；後兩種一律不寫、不當空 |

## c. 關於 daemon／tick 的坑（9 條）

| # | 發現（一句白話） | 哪一代、哪個檔 | proto8 下 | 對 proto8 的一句建議 |
|---|---|---|---|---|
| c-1 | 掃資料夾找 node 的代價：子 daemon 起來前父把它的資料夾當自己的 node（兩個 daemon 同時 tick 一個資料夾）；不同 root 重疊沒鎖，node id 跟著 daemon 根變。使用者：「不該掃，一開始就登記」 | [user-advice](../../proto7/user-advice.md)；proto7-1 [problems-core P-10、P-11](../../proto7-1/notes/problems-core.md) | 成立 | 誰有時間線＝一份登記表；「有 `.aos/` 就算」不夠 |
| c-2 | 每回合產資料夾＝垃圾：7 node 360 回合每回合 9 檔、4.4 KB 內容佔 40 KB；真模型 15 分鐘 77 MB、1.4 萬小檔；4000 個舊任務資料夾時 daemon CPU 52%。使用者：「我的老天」「垃圾要定期清」 | [user-advice](../../proto7/user-advice.md)；proto7-1 [problems-core P-12](../../proto7-1/notes/problems-core.md)、[problems-real R-10](../../proto7-1/notes/problems-real.md)、[infra-needs Q3](../../proto7-1/notes/infra-needs.md) | 成立 | 回合紀錄一行 jsonl；每回合不開新資料夾；歷史要嘛搬走要嘛不產 |
| c-3 | 「任務跑完就提前 tock」對常駐任務沒意義：第 1 回合之後每回合 tick→tock 只隔 40 ms，之後整段 idle；kernel／agent 的事全落在回合之間。使用者要固定節拍可選 | [user-advice](../../proto7/user-advice.md)；proto7-1 [problems-core P-16](../../proto7-1/notes/problems-core.md)、[problems D-2](../../proto7-1/notes/problems.md)；proto7-2 [problems P2-01](../../proto7-2/notes/problems.md) | 成立 | tick 是時間格，不是「等誰做完」；跨回合行程是常態不是例外；要提前只給明確的 wake |
| c-4 | 「做一次就好」三個模型全失敗（keep 做完又起每檔 10～14 次、each 63～69 次、spawn 退回 each 約 200 次）；任務表分兩個檔（tasks.json＋spawn）使用者嫌 | proto7-1 [infra-needs N-65](../../proto7-1/notes/infra-needs.md)；[user-advice](../../proto7/user-advice.md) | 成立 | 任務表一個檔；模式要有 LLM 想得到的 once |
| c-5 | kill 一個常駐任務＝restart（下個 tick 照表起回來）；被 kill 的子 daemon 結束碼是 0，分不出「被殺」和「做完」 | proto7-1 [problems D-3、I-1](../../proto7-1/notes/problems.md) | 成立 | 分開「這個實例結束」與「這個任務別再有了」；結束紀錄帶「誰下的手」 |
| c-6 | pause 停不了在飛的 LLM 呼叫；預算「限速」擋不住迴圈（30 對 pause／resume 照樣燒 609k）；單一 paused 位元誰的 resume 都放掉別人的 pause（被放掉 14～17 回合） | proto7-1 [problems-real R-4](../../proto7-1/notes/problems-real.md)、[problems D-4](../../proto7-1/notes/problems.md)、[infra-needs N-81](../../proto7-1/notes/infra-needs.md) | 任務自己的事 | 排序行程要有總額上限不只限速；pause 要帶 owner 各解各的；時間停止（2.11）不等於在飛的請求停止 |
| c-7 | 任務靠環境變數找自己，`cat` 不到；node 搬家後舊任務的 `AOS7_NODE` 還指舊路徑，永遠收不到 tock；只刪 timeline.json 等於「不經 pause 的暫停」 | proto7-1 [problems-core P-02](../../proto7-1/notes/problems-core.md)、[infra-needs Q4](../../proto7-1/notes/infra-needs.md) | 成立 | 身分寫在資料夾裡（birth.json）；搬家＝舊死新生，不支援熱搬 |
| c-8 | 事件式喚醒省 90%：100 條線 95 閒置時，pause 閒線＋有信才 resume，tick／tock 程序每秒 200 → 20、CPU 4.4 → 0.5 秒／秒，信延遲中位 600 → 70 ms；resume 不打斷睡眠會多等一個 interval | proto7-1 [infra-needs N-83、N-84](../../proto7-1/notes/infra-needs.md) | 成立 | tick 要能被事件叫醒，不只定時；resume 要順便 kick |
| c-9 | daemon 被 SIGKILL 後 status.json 一字不變（舊 pid、`stopping: false`）；卡死時 status 照印「心跳活著」。檔案介面沒有獨立的存活證明 | proto7-1 [problems-core P-04 新證據](../../proto7-1/notes/problems-core.md)；proto7-2 [longtask 問題 2](../../proto7-2/notes/play/2026-10-09-longtask/README.md) | 成立 | status 帶 pid＋starttime＋最後更新時間，讀的人自己驗活；「內容沒變」要看得出來 |

## d. 關於工作流本身的教訓（4 條）

| # | 發現（一句白話） | 哪一代、哪個檔 | proto8 下 | 對 proto8 的一句建議 |
|---|---|---|---|---|
| d-1 | 立法跑在實作前太遠：41 KB 規格有六條被第一次對抗驗證改掉；一改一行行為要動 7～10 處；四份真相漂了四處（35% vs 37%）沒人發現。十輪拷問站住的只有帶實測數字的條目 | 八月 [salvage 06 §二、§五](../../wf/salvage/06-協作流程的收穫.md) | 成立 | 先跑通最短的一條路再釘規格；每個結論只有一個家；先決定「一次改動付多少代價」 |
| d-2 | 做太快：兩天 380 commit、9 包、15 模組、1444 測試，功能齊、全局讀不懂；員工桌上十二段不同格式。成熟元件被派隊重寫一次（使用者：「直接複製過來就好了啊」） | proto8 [restart §0、§1](2026-10-11-restart.md)；[dispatch lessons 8](../../wf/workflows/dispatch/lessons.md) | 成立 | 程式只准做使用情境日記裡出現過的事；現成的原樣抄、不重寫、不列待問 |
| d-3 | A／B 判準要先寫死、雜訊要算：menu-ab 三條判準與「量不到就寫量不到」先寫，同組 5 次分散當雜訊底線，結論才站得住；AP4 沒證明、AP5 證明，差在題目與判準不在機制。審查者看不到驗收器會誤退件 | proto7-2 [menu-ab](../../proto7-2/notes/play/2026-10-10-menu-ab/README.md)、[apprentice-3x G0](../../proto7-2/notes/play/2026-10-09-real-ai/apprentice-3x.md)、[apprentice-5](../../proto7-2/notes/play/2026-10-09-real-ai/apprentice-5.md) | 成立 | 每次實驗先寫成功判準、雜訊怎麼算、什麼叫「量不到」；審查者與驗收器看同一份判準 |
| d-4 | 多隊同機要排隊：8 核同時一條線跑程式；load 衝 200 時時間敏感測試假失敗；`pgrep -fc` 數錯 9 份實際 1 份害一隊白等 30 分；worktree 起點落後 40 commit 讓 33 條發現作廢（22 萬 token） | [dispatch lessons 6、9、13](../../wf/workflows/dispatch/lessons.md) | 成立 | 真跑序列化；測試不靠時序；開工先確認 HEAD＝main |

---

## 探針沒探到的（別當成已知）

- **斷電耐久**：fsync 那一族全部「讀 diff 確認」，dm-flakey／硬切電從頭到尾沒測（salvage 02 §三）。
- **WSL 第二個 UID**：/mnt/c 與 interop 繞過權限只推論、沒用第二個帳號實測（WSL 查證 §四）。
- **技能書能不能遷移到不同的坑**：AP5 只證明「同一種坑記得住」。
- **真 provider 的 4xx／5xx／逾時**：只在假 HTTP 伺服器測過（real-ai「還沒驗到的」）。
- **cgroup 開了 memory／pids 控制器後 mkdir／rmdir 變多貴**：per-task cgroup 探針沒量。
