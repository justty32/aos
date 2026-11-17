AI 對 aos 的 daemon、信件、kernel 與額度、安全這幾塊還沒做的意見，一條一兩句。

# 意見：daemon、信件、kernel、安全

← [advices](README.md)｜下一份 [02-範本工具知識庫](02-範本工具知識庫.md)

出處的檔都在 `wf/advices/archive/`，「」裡是原條標題的開頭。沒標「沒查證」的，11-17 對 HEAD 615180ad9 查過還沒做。

## 安全

- daemon 起 proc 把整份環境往下傳，API key 進每個 proc：改環境白名單，模型的 key 由定義或 env_file 明給；另做只印變數名的 aos-env；暫存 stack 用 umask 077。（安全.md「原型把整份環境寫進檔」）
- exec.json、loop.json 每次重寫用 0666 開檔，envs 裡的 key 變 644 明文：加 0600 的祕密模式，或 envs 只存 env_file 路徑。11-17 另一條線在給 files.cpp 加 mode，做完要再核。（安全.md「exec.json、loop.json 每次重寫都是 0666」）
- aos-daemon 的 adopt 讀不到 `/proc/<pid>/environ` 就當成自己的，換 uid 會收養錯：改比 `/proc/<pid>/status` 的 Uid。（daemon與行程.md「daemon 靠 /proc/<pid>/environ 認自己的行程」）
- 一信一夾：跨 uid 後寄件人能鎖信、收件人能改信。使用者在 Q10 選了一信一檔，還沒施工；同時把 Python 端讀信收成共用的 read_letter，aos-post 加「take 指定的一封」。（信件與溝通.md「信件一封一個夾」「各元件各自寫死 letter.json」「aos-post 沒有認領指定的一封」）
- aos-share reset 沒防呆：擋 `/`、HOME、活樹根，參數前加 `--`，setfacl 失敗也跑完其餘步驟再彙總退出碼。（安全.md「aos-share reset 沒有防呆」）
- aos-share check 對有 ACL 的檔誤報 secret-open：有 ACL 時照 getfacl 判。（安全.md「aos-share check 的 secret-open」）

## daemon 與行程

- eca 已寫出 result，`claude -p` 卻因背景工作不退出，aos 當這輪還在跑、被 kill 後整隻停：看到 result 給一段寬限就收掉 CLI，照 result 算成功。沒查證 aos-eca-turn 本身與 11-16 的冷卻改動。（daemon與行程.md「eca 一輪寫出 result 之後 CLI 行程不退出」）
- 帶 `--envs` 的 add 把 exec 包一層，表上 exec 變 null，set-def 拒收（subagent 掛的子全是這種），as_written、`--path-json` 也掉；不帶 envs 的查不到 parent：照 ok-devt 第 2 期把 parent、notify_box、envs 放上列、由 daemon 設。（daemon與行程.md「子 agent 不知道是誰生了它」「帶 --envs 的 add 換了掛法」）
- 部長看不出自己帶的線是忙、閒還是停：給範圍限定的唯讀查詢（phase、上次活動、未讀信數），或明文禁止。沒查證（aos-view v2 全景頁可能已夠）。（daemon與行程.md「部長看不到自己帶的線」）
- daemon 替 proc fork 的那層命令列跟主 daemon 一樣，pgrep 核對會假警報：改 argv0。（daemon與行程.md「daemon 替 proc fork 的那一層」）
- `--limits` 沒有管整隻 agent 總 CPU 的鍵（cpu_s 按程序算）：加 cgroup 的 cpu.max。（daemon與行程.md「--limits 的 cpu_s 按程序計」）

## kernel 與額度

- Claude 的用量（eca、fable、Argon）不經 llm kernel，aos 裡看不到：把 Claude 電表做成正式指令、接上電力卡（使用者已裁 aos 外的也列、只顯示不分配）。（kernel與額度.md「Claude 用量沒有任何 aos 入口能看」）
- state、ctl ls 分不出在排腦、額度被拒還是卡住：state 印等腦秒數與排第幾，ls 的 REASON 帶 BudgetMissing 的 endpoint 與 resets_at，aos-llm 加「現在排幾個」。（kernel與額度.md「state 和 ctl ls 看不出」）
- kernel_gate 的站掛在主人的 on_clock，主人跑長回合時下屬 3 秒就 KernelFailed。三案：存表檔路徑、站獨立成小行程、只調秒數與快取；gate 設計在等使用者開口。（kernel與額度.md「gate 站掛在主人的 on_clock」）
- 帳本看不出提示快取命中率：aos-llm 加看帳的子指令，至少知識庫 brain.json 寫一句「命中率低先查 session id」。（kernel與額度.md「llm kernel 的帳本看不出快取命中率」）
- subagent、agents_ctl 收到 BudgetMissing 不印 resets_at，「晚點再試」等於拒絕：錯誤行印 try again after HH:MM。（kernel與額度.md「掛 proc 的寄信人收到 BudgetMissing」）
- kernel_hold 通知分不出工人移除自己還是被別人移除：分列 caller、target，相同時標 self。（kernel與額度.md「kernel_hold 通知分不出」）
- test_batch8_live 在乾淨複本沒有執行檔，固定紅：沒有就 skip 並印原因。（kernel與額度.md「kernel_llm 管寄出請求的測試」）

## 信件與溝通

- 長回合裡收不到新信（live_mail 已有、預設關）：回合結束補報到了幾封；waitdone、listen 等到新信就提早返回；寄件人查得到對方上次讀信的時刻。（信件與溝通.md「agent 在長回合裡收不到新信通知」）
- 信會在路上交錯：mailbox_send 加選填的 as_of，記寫信時已讀到對方哪一封，mailbox_read、aos-view 標出來。（信件與溝通.md「信會在路上交錯」）
- reply_to 是相對路徑，信搬了信箱回信就寄丟：存絕對路徑。（信件與溝通.md「aos-post 的 reply_to 是相對路徑」）
- mailbox_send 一次只寄一人：to 收陣列或加 cc。（信件與溝通.md「mailbox_send 不能一次寄多人」）
- sent_at 印 UTC，clock 提示印本機時間：mailbox_read、mailbox_peek 加本機時間欄。（信件與溝通.md「信的 sent_at 印 UTC」）
- fyi 信的 status 只能 DONE／FAILED／BLOCKED，沒寫進 schema/letter.json：寫進 schema，aos-user send 加 `--dry-run`。沒查證。（信件與溝通.md「fyi 信的 status 規則」）
- 授權回信沒有機器可讀的範圍：irreversible 的題帶 targets 路徑清單，回信原樣帶回，動手前核對。沒查證。（信件與溝通.md「使用者授權的回信沒有機器可讀的授權範圍」）
