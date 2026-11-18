# proto8 討論紀錄：2026-11-18

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [公司WSL-重建試跑紀錄](公司WSL-重建試跑紀錄.md) | 公司 WSL 照使用者把舊 aos 整個清掉、照[重建步驟單](../17/重建步驟單.md)從零裝（安裝六步、關、再起、更新五步、eca 版回「好」都過；真模型沒試，端點沒開），試完再清回「沒有 aos」；寫成教學本給之後一步一步教；步驟單對不上的幾處（再起時視窗 B 的 `cd llms`、關樹 `&&` 串）只列建議、步驟單沒動 |
| [litellm-proxy-接gpt帳號](litellm-proxy-接gpt帳號.md) | 查了 litellm 兩次下毒（3 月 1.82.7／1.82.8、10 月 1.107.0）與 proxy 漏洞，選 1.109.1、117 個套件釘版加雜湊離線裝進公司 WSL `~/litellm-proxy/`（只聽 127.0.0.1:4000，起停與拒絕無 key 都試過）；ChatGPT 帳號要使用者親手 `./login.sh` 走一次裝置碼（codex 的登入檔讀不到、也不該共用），登入前真模型沒回過；aos 端不用改檔 |
| [litellm-供應鏈與選版](litellm-供應鏈與選版.md) | 上一份拆出來的一半：兩次下毒與 proxy 漏洞的摘要與來源網址、為什麼選 1.109.1、雜湊與特徵怎麼驗（PyPI 上沒有 PEP 740 來源證明，雜湊只證明跟 PyPI 一樣） |
| [沙箱隔離-實機檢查](沙箱隔離-實機檢查.md) | 不用模型的那一半：公司 WSL 暫存複本真開 bwrap 沙箱，看得到／寫得到／環境變數／行程與三個邊緣狀況都照說明；落差是起手範本的 daemon stack 在工作區裡（綁 ws 就碰得到 daemon，嚴重）、`net:true` 連得到宿主 127.0.0.1 但查不到 DNS、沙箱裡看 daemon 死活會看錯；這台沒有 s6，上限、換帳號與 box_check 紅的兩支驗不到；真模型那半明天補 |
| [下午改動-獨立驗證](下午改動-獨立驗證.md) | 線 verify2-1118 在 HEAD `71df48e88` 乾淨 clone 照[重建步驟單](../17/重建步驟單.md)從頭跑都過（卡點：再起時新視窗 B 少 `source env.sh`）；80 夾測試紅的跟基準一樣、無新增失敗；真 eca 驗 `ctl stop` 延後關畫面、`close`／`ctl rm` 當場關、`set-def` 跑著／停著／睡著三種都照說明；小發現兩個（停著的 set-def 後 `ls` 工作區欄變 `-`、到期單殘留到下次 start），沒修 |
| [eca-pi](eca-pi/README.md) | 研究把 pi coding agent（已從 `badlogic/pi-mono` 搬到 `earendil-works/pi`，npm `@earendil-works/pi-coding-agent`，最新 1.5.2）接成 eca 第三種身：能接，推薦先照 codex 加 `"kind": "pi"` 走 `pi --mode json` 一問一答，再升 RPC（中途收信）、最後畫面＋pi 外掛；坑是 pi 不問權限沒沙盒、答完要等 `agent_settled`、Claude 訂閱不能用；範圍、權限、模型走哪、裝哪版待使用者裁；沒裝沒跑 |
| [eca-claude-小試驗教學](eca-claude-小試驗教學/README.md) | 使用者提的 11 個疑問（停 daemon 複製 stack 重開、預設 stack、自訂定義、aos-post、aos-lock、不用 aos-tree-start、aos-mailbox、不用 aos-kit、沙箱限資源、aos-asuser、aos-share）在公司 WSL 用 haiku 實跑，一題一份照打教學，好往後加；各題的「發現的問題」只列不修；asuser、share 缺 `uidmap`／`acl`，裝好之後的那半是預期、沒實測 |
| [aos-llm-去留調查](aos-llm-去留調查/README.md) | 使用者問 aos-llm 還要不要、要不要改 Python：還在用（wait 格每次問腦寄一次、每拍收一次，judge-llm 與 llm_forward 用 `ask`），不能直接拿掉；它只是 1058 行 C++ 小郵差、不打 HTTP，實測一次問腦 1.3 秒裡它只佔約 25 ms，速度不是理由；推薦丁案（Python 函式庫＋同名薄指令，粗估 10～14 小時），甲（不動）也可以，乙（拿掉）不推薦；等於重裁 11-17 的 X-4 A，待使用者裁；沒改程式 |
| [sbx-fix-1118](sbx-fix-1118.md) | 沙箱碰得到 daemon（檢查紀錄 A）家機重現：照範本 `-w .`，關進沙箱的工具仍看得到 daemon 表、改得到 kernel 與自己的定義、還能 ctl add 一隻在沙箱外跑的 agent；根因是 agent 工作區＝整棵樹（控制台在裡面）；四個修法（專用工作夾／搬 stack／沙箱自動遮／警告），推薦專用工作夾＋警告，待使用者裁 |
| [two-machines 真機驗證（家機）](../10/two-machines/14-真機驗證.md) | 線 t7-home-1118 在家機用真 claude（haiku）跑 T7 第 1～4、6、7 步：resume 不存在的 id 退 1、換帳號夾接不回、eca 換台（兩棵暫存樹）答得出 kiwi、A15 專案夾名猜對都過；claude 2.1.327 換資料夾也接得回（aos 比它嚴、沒改）；eca 的 claude 用 Claude Code 自己的自動記憶、存在樹外，要不要關待使用者裁；codex 那步跳過 |
| [aos-kit-併進ctl](aos-kit-併進ctl.md) | 使用者「aos-kit也不用了，刪掉，功能整合進現有的。」：aos-kit 刪掉，改用 `aos-agent ctl add --kit`／`ctl set-def --kit`，kit 的 system 與 tools 寫成那隻在 stack 裡自己那份、定義夾不動、拿掉用 reset；11-18 晚三題裁定（寫進 stack、eca 也能套、換包直接蓋）都已做；套 kit 後 `tools ls` 的誤導提醒沒修、沒問 |
| [eca-pi-bc-1118](交接-各線/eca-pi-bc-1118.md) | pi 身乙案（rpc、回答途中收信）＋丙案（tmux 畫面＋aos 的 pi 外掛）做完：家機真 pi 1.5.2 整樹實跑（問、續問、中途寄信、aos 工具、畫面回報與收信、slash、ctl stop／set-def）都對；文件 templates/docs/03、knowledge eca.json 改成現況、寫了已知限制 |
| [setdef-night-1118](setdef-night-1118.md) | 使用者 11-18 晚三個裁定照做：set-def 走 kernel 的掛回信帶等待期限（kernel 現成的 queue_wait_ms），格滿時期限到就被拒、不會晚到蓋掉手動掛回的，錯誤行的手動指令補 `-d`（順手修 `-d` 時控制信仍寄 AOS_KERNEL 的舊毛病）；listen 問腦失敗改回讀 stderr 錯誤行（前綴與原話回來），到期單只有 set-def 清；套 kit 後 `tools ls` 不再問是不是抄來的。全套 2397 支過 |
