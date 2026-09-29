# proto6 第一段原型：規格缺口與本輪取捨

僅記錄，不修改 `proto6/spec/`。以下含任務書要求明記的範圍縮減；不是宣稱已變更規格。

## G-1．P-101／B-605 create-cgroup 缺少 root 的結束碼
卡在哪：P-101 說建立失敗回 125，但 CLI 開 create 而未填 cgroup_root 是設定錯還是初始化錯，沒有明分。
原型暫時怎麼做：設定或 CLI 任一開 create，缺 cgroup_root 都在初始化前回 2。
建議問使用者什麼：正式版是否固定把缺少 root 歸為用法／設定錯 2？

## G-2．B-605／P-107 cgroup 命名及樹形（已定，第十六批）
**已定（第十六批）**：照原型這套命名，寫進 spec B-605／P-107；首版不做碰撞偵測。見[裁定 07](../../notes/verdicts/07-review-fixes-and-proto-gaps.md) 第 8 條。
卡在哪：node id 是任意長絕對路徑，spec 沒定框名；不能直接當 cgroup 名稱。
原型暫時怎麼做：daemon 放 `<root>/daemon`；node 放 parent 框下的 `n-<sha256(node_id) 前16 hex>`，本格放其 `tick`；once 放 parent 框下的 `once-<同法 hash>`。
建議問使用者什麼：是否採用這套名稱？正式版是否需要完整 hash 或碰撞偵測？

## G-3．B-605 省略 root 時父框可能仍有其他程序（已定，第十六批）
**已定（第十六批）**：省略 cgroup_root 時，daemon 啟動先在自己所在那層開 `daemon` 子層，把自己和那層其他程序都搬進去，那層只當分支。原型已補（`evacuate`）並加測。見[裁定 07](../../notes/verdicts/07-review-fixes-and-proto-gaps.md) 第 9 條。
卡在哪：daemon 以自身原 cgroup 為子樹，再搬進 daemon 葉框，原框可能仍有 scope shell；開 controller 時會碰 no-internal-process。
原型暫時怎麼做：本輪完全不啟用 controller、不寫 subtree_control、不寫資源上限；真 cgroup 測試使用直接 scope 啟動 daemon。
建議問使用者什麼：正式啟用 controller 前，是否要求委派根只能有 daemon，或由部署方另準備空分支？

## G-4．P-109 runner 診斷位置與 git ignore
卡在哪：spec 說 daemon 收集 runner stderr，未定位置；若未 ignore，格首 clean 可能刪掉仍開著的診斷檔。
原型暫時怎麼做：資料夾 node 覆寫 `.aos/runner-stderr.log`，node new 加上此檔的 ignore；once 單檔 runner 診斷丟到 /dev/null，未啟動仍有 .err。
建議問使用者什麼：正式位置、輪替與留存政策要怎麼定？

## G-5．P-105／P-601 自動停格事項的最小格式
卡在哪：本輪不做 ops，卻必須留下停格證據；尚未接正式事項目錄與查詢。
原型暫時怎麼做：`.aos/attention/daemon-<boot_id>-<序號>.json`，內容含 version、node_id、reason、last_tick；先設 paused，寫失敗只警告。
建議問使用者什麼：下一輪是否直接遷到 P-601 open/done 布局及正式 reason/message 欄位？

## G-6．P-104 不同內容重新登記的簡化
卡在哪：正式更新要核對整棵暫停、全空子樹及下授額度，超出本輪更新流程。
原型暫時怎麼做：相同登記成功且不變動 paused/pending；內容不同一律 registration_conflict。已解除 once 的同路徑重登也拒絕，避免誤當新 attempt。
建議問使用者什麼：正式更新及 once 同路徑重登，應如何區分維護修改與新 attempt？

## G-7．P-106 cgroup limits 觀察暫回空物件
卡在哪：本輪不設 controller 上限，尚未提供完整 cpu/memory/pids 讀值介面。
原型暫時怎麼做：有建框則核對 cgroup.procs 可讀，回實際 path 與 limits:{}；框不存在／不可讀回 resource_observation_failed；未建框及解除 once 回 null。
建議問使用者什麼：下一輪是否需要把外部已設定的 controller 值也完整列出？

## G-8．P-109 原來源 bytes 改變的錯誤代號
卡在哪：來源仍可讀但任意 bytes 改變，不一定是 user 改變；UserMismatch 名稱可能過窄。
原型暫時怎麼做：與密封 memfd 快照不同回 UserMismatch／125；讀取失敗回 ReadFailed。沒有放行子程式、不寫 exit。
建議問使用者什麼：是否新增 SourceChanged／InstChanged，與真正的 UID 不一致分開？

## G-9．P-201 inst 第1版 取值指示詞本輪未做
卡在哪：本輪明示不做 $ref/$env/$at 等展開，但必須拒絕，不能誤當一般值執行。
原型暫時怎麼做：執行欄位遇到非 $opt 的 $ 開頭物件回 DirectiveUnsupported／125；$opt 六種選項照做；user 中任何物件維持 UserInvalid。
建議問使用者什麼：下一輪是否沿用 proto5 的完整展開順序、循環鏈與錯誤集合？

## G-10．P-210 node resume 暫只送 IPC
卡在哪：本輪明示省略持鎖驗證 inst/tasks/領域設定及提交手改。
原型暫時怎麼做：CLI resume 要確認（--yes 可跳過）後只送 node.resume；daemon 只開閘，pending 或到期才跑。
建議問使用者什麼：下一輪先補通用 inst/tasks 驗證，還是與 kernel/agent validator 一起落地？

## G-11．P-104 once 不存在帳號與指定驗收互相矛盾（已定，第十六批）
**已定（第十六批）**：照 P-104，登記 once 時帳號就要存在，否則回 `user_invalid` 拒絕。原型已拿掉 once 的放寬，測試改成登記就被拒；wake 時仍重新解析。見[裁定 07](../../notes/verdicts/07-review-fixes-and-proto-gaps.md) 第 10 條。
卡在哪：P-104 要求登記時 inst user 已存在，但任務書測試6要求不存在帳號仍可 register，wake 才產 .err。
原型暫時怎麼做：只對 once 的不存在帳號名稱延後解析，暫存父 owner 作查詢 owner；wake 必定重新解析／核額度，失敗回 launch_failed/125、user_invalid .err、解除。普通 node 仍拒絕。
建議問使用者什麼：正式版要登記時拒絕，還是把「授權可登記」和「執行帳號可解析」分成兩階段？

## G-12．B-603 測試用假 cgroup 不是核心隔離
卡在哪：普通檔案沒有核心的程序繼承、PID 身分與原子清空保證；os.kill(pid,0) 對 zombie 也成功。
原型暫時怎麼做：FakeCgroup 保存 PID，輪詢時補記可見後代；zombie 視為已停止執行，由父程序 wait。runner 用 subreaper 清理脫離 session 的後代；真後端以核心 populated/cgroup.kill 判斷。假模式仍有 PID 重用及取樣空窗，僅限測試。
建議問使用者什麼：假後端是否只要求可重現測試，不承諾與真 cgroup 完全等價？

## G-13．P-104 額度中尚不存在的帳號預授
卡在哪：P-104 允許從設定下傳尚不存在的確切名稱，建立帳號後再綁 UID；本輪無 helper／account_create。
原型暫時怎麼做：identity_grant 名稱必須現在可解析，且以 UID 排除 root、別名重複與越權；不保存未綁 UID 的額度。
建議問使用者什麼：延後到 helper 帳號建立流程時，如何持久保存「確切名稱→首次 UID」綁定？

## G-14．H-004／P-106 CLI 跨 boot 分頁
卡在哪：CLI 已印出的頁面無法撤回；分頁期間 daemon 重啟，直接自動重列會讓串流消費者看到混合世代。
原型暫時怎麼做：IPC 每頁帶 boot_id；CLI 偵測切換就回1、提示重列，不自動重送已輸出的頁面。
建議問使用者什麼：正式 CLI 要緩存完整清單後輸出，還是允許回1讓呼叫者重新查詢？
