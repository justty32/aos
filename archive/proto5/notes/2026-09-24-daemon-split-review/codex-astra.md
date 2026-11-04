← [daemon 分開的理由審查](README.md)

# codex 獨立意見（gpt-6-astra，兩次）

任務書＝[task.md](task.md) 全文，外加一段：「你是獨立審查者，沒看過其他人的意見。可讀 repo 任何檔、可跑唯讀指令驗證。輸出 ≤6 KB，先講結論，五題逐題答，最後列你最有把握與最沒把握的各一點。」
指令：`codex exec -m gpt-6-astra -s read-only -C <worktree> -o <out> - < <task>`；第二次加 `-c model_reasoning_effort=high`。兩份都沒看過兩個子隊的 memo。**兩份是同一顆模型，綜合時打折算。**

隊長補查：第二份說 exp4「吞掉錯誤、沒統計成功率」——已逐一單跑，四種做法都退 0（[exp/README.md](exp/README.md)）；「不是千顆常駐壓測」這點成立。

---

## 第一份（astra，預設推理）

**結論：切使用者是有效的隔離手段，但推不出「daemon 必須長駐 root，因此必須拆成兩支程式」。建議保留目前 daemon／kernel 的行程分工，daemon 維持一般使用者；工具權限先走 bwrap。** 若將來需要跨 UID，再加入受限的特權啟動與停止機制。

本次只讀程式、規範與既有實驗，未改檔、未跑 sudo，未碰模型服務。

**1．切使用者一定需要 root daemon 嗎？**

不一定。換成任意主機 UID，需要相應權限，通常由 root、特權小幫手或系統服務提供；權限不必放在整支 daemon。

| 方法 | root／授權需求 | 擋得住與擋不住 | cpu 範式與千顆成本 |
|---|---|---|---|
| root daemon＋setuid／setpriv | daemon 持有切身分權限；孩子降權 | 不同 UID 配合檔案權限可互擋；不自動限制網路、資源、公開檔 | 親子管理直接；需安排跨 UID 投單與讀回音。直接降權成本低，未有本機實測 |
| `sudo -u` 白名單 | daemon 不必 root；管理員先設 sudoers | 可限制目標身分、命令；若命令可讀任意可改腳本，白名單仍可能等同任意執行 | 多 wrapper／PAM；pipe、PID、停止階梯需接合。千次成本未測 |
| 系統層 systemd-run | 系統 manager 有權限；呼叫者須獲授權 | `User=` 隔 UID，另設 sandbox／資源限制；單換 UID 不限網路 | service 由 systemd 管，不再是 daemon 直接孩子；每顆 unit 有管理成本，未測 |
| 各使用者的 user service | 已建立帳號與啟動管道；服務自身不用 root | 各 manager 跑自己的 UID；一般 `--user` 不能任意換人 | 每人一個 manager 可管多顆；跨使用者控制與信箱權限較複雜，未測 |
| bwrap user namespace | 啟用非特權 user namespace 時不用 root | 靠掛載白名單隔檔案；單一 UID 映射只是改內部號碼。socket、繼承 fd、開放網路仍是通道 | 保留主機檔案所有權，最順手；wrapper 生死須驗。既測每次 0.72～1.19 ms |
| subuid 多 UID namespace | daemon 不用主機 root；需預配 subuid／subgid 與特權映射助手 | 不同主機 UID 真能互擋；namespace 管理者仍須受信任，不防它 | 家可各有主人，但外面的人讀取、清理與祖先路徑變麻煩；既測 1.43 ms |
| setgid＋群組權限 | 既有群組內操作可免 root；任意換群組需授權 | 適合分享，不足以隔離同 UID 的敵對程式；目錄 setgid 只管群組繼承 | 成本小；共用可寫目錄也不能保證「只投單、不刪別人的單」 |

依據：[setpriv](https://man7.org/linux/man-pages/man1/setpriv.1.html)、[sudoers](https://www.sudo.ws/docs/man/1.9.14/sudoers.man.pdf)、[systemd 原始文件](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml)、[user namespaces](https://man7.org/linux/man-pages/man7/user_namespaces.7.html)、[bwrap](https://github.com/containers/bubblewrap)。

兩個容易漏掉的地方：

- **能啟動不等於能停止。** 普通 daemon 對不同 UID 孩子未必有 TERM／KILL 權限；父子關係本身不授權，須由特權 supervisor／systemd 完成停止。[kill(2)](https://man7.org/linux/man-pages/man2/kill.2.html)
- 「一個家一個主人」目前是協定，**不是每家一個 UID**。改 UID 後，投單、ack、讀回音都要重新配置；共享目錄寫權不足以強制現有規則。

既有數字是 `/bin/true` 的序列微基準。千次約為 bwrap 0.72～1.19 秒、map-auto 1.43 秒，**不是千顆常駐 cpu 的容量證明**；記憶體、fd、輪詢及每次工具是否重開牢仍要量。

**2．分開的理由還剩多少？**

- **故障隔離：最強。** 排程出錯時，管理 cpu 生死的行程仍活著。但現碼 `reap()` 是孩子「非零退出」才重拉；tick 失敗、斷鏈或卡死不能一概宣稱會自救。
- **daemon 小而穩定：中強。** 排程還會加入停車、喚醒等變化，避免一起擾動監督者有實益；只是要持續守住邊界。
- **一個 daemon 管多個 kernel 家：中。** 共用生命週期管理合理，但 daemon 也成為共同故障點。
- **K2 另一個家：弱。** 能證明需要多個排程領域，不能單獨證明需要另一支 executable，更不構成權限牆。
- **未來切 UID：條件式理由。** 若真採用，支持把特權部分縮小；不足以支持現在整支 daemon 跑 root。

**合起來足以支持現在保留分開行程；不足以證明必須是兩個執行檔。** 同一個 `aos` 的兩個子命令也能保留故障與權限邊界。

**3．對 I 隊結論的影響**

**結論不變，論據要修正。** 維持「現在不合併；帳本依既定方向改 sqlite；操作入口可統一」。

拿掉「切使用者所以 daemon 必須 root」這条推論，保留故障隔離與減少連動修改的理由。sqlite 解的是帳本成本與一致性，與 UID、執行檔數量分開判斷。

**4．權限這條線怎麼走？**

預設 **同一主機 UID＋bwrap 牢**：信任 daemon／kernel／啟動器；把不可信工具放牢內，掛載白名單、清環境、隔離 PID、預設無網路，控制資料與多餘 fd 不交給工具。不能只設 `--uid`。

CLI agent 若可自行跑 shell，應把**整個 CLI agent 執行樹**納入隔離；只包 aos 工具入口不夠。藏 K2 路徑也不夠。

只有需要「連牢外的不同工作負載也互不信任」時，再疊不同 UID；依**信任領域**分配，不必每顆 cpu 一個帳號。不同 UID 管檔案身分，bwrap 管可見資源，兩者互補。subuid 可行，但現階段操作代價較大。

**5．要使用者拍的（附預設）**

- 是否撤掉「必須 root」作為拆分理由？**預設撤掉，保留分開行程。**
- 是否要求兩個執行檔？**預設不要求，統一入口即可。**
- 隔離對象是工具／CLI agent，還是連 kernel 都互不信任？**預設前者，管理層受信任。**
- 是否現在加入跨 UID？**預設不加；出現兩個互不信任的牢外工作負載再啟動設計。**

**最有把握：** 權限邊界取決於行程憑證、資源暴露與授權，與執行檔有幾支沒有必然關係。

**最沒把握：** 千顆 cpu 的實際啟動與常駐成本；現有微基準不足以替 sudo、systemd 或完整工作負載下容量結論。

---

## 第二份（astra，high）

**結論：不同 UID 是有效的權限工具，但「因此 daemon 必須常駐 root，所以要分成兩支程式」推不出來。建議保留 daemon／kernel 分工與行程隔離，daemon 預設普通使用者；目前先走 bwrap。** 本次全程唯讀。

**1．切使用者需要 root 嗎？**

換成其他主機 UID，需要適當特權或已授權的服務；**特權不必放在 aos daemon 裡**。

| 做法 | root／隔離能力 | cpu 範式與啟動成本 |
|---|---|---|
| root daemon＋setuid／setpriv | daemon 持特權；降權後配合檔案權限可隔開各家。須清附加群組、能力及可恢復身分，並限制再次提權。 | 最貼近現有父子關係；直接降權成本小，這條未實測。 |
| sudo -u 白名單 | daemon 不必 root；sudo 與管理員設定提供特權。隔離來自目標 UID；NOPASSWD 只是免密碼。 | 多一層啟動／監督；入口、參數、程式及設定均須受保護。不能只准 aos-exec，卻讓人任填 inst。成本未測。 |
| 系統層 systemd-run | 系統管理器有特權；呼叫者須獲授權。User= 可隔離，DynamicUser= 要處理 UID 回收與持久檔。 | 家仍可保留，但 service 由 systemd 當父親，須改 pipe／收屍接法；千個 unit 成本未測。 |
| 各使用者的 systemd user 服務 | 各自已用該身分啟動，日常不用 root；单一普通 user manager 不能任意換人。 | 每個身分需管理器與投遞授權；一服務一家可行，中央 daemon 不再直接當爸爸。成本未測。 |
| bwrap user namespace | 系統允許非特權 namespace 時不用 root；單 UID 映射不隔開同 UID 的檔案，靠掛載白名單等限制。 | 可包工具、保留原 cpu；包整顆須接好控制 pipe／PID。實驗約 0.72～1.19 ms。 |
| subuid 多 UID namespace | daemon 不需主機 root，但依賴預配 subuid/subgid、帶權限的映射助手。不同外部 UID 確實隔離；namespace 爸爸仍須信任。 | 要分配 UID、處理祖先目錄、交件權限及外部維護；約 1.43 ms。 |
| setgid＋群組權限 | 既有群組可用；任意換 GID／清群組需要特權。適合分享權限；同 UID 換群組不能隔開各自擁有的檔案，也不隔開同 UID 行程。 | 易接，但沒有把「只能投遞」變成硬規則；額外成本小、未測。 |

依據：[setpriv](https://man7.org/linux/man-pages/man1/setpriv.1.html)、[sudoers](https://raw.githubusercontent.com/sudo-project/sudo/main/docs/sudoers.man.in)、[systemd.exec](https://man7.org/linux/man-pages/man5/systemd.exec.5.html)、[systemd-run](https://man7.org/linux/man-pages/man1/systemd-run.1.html)、[UID 映射](https://man7.org/linux/man-pages/man7/user_namespaces.7.html)。

共同缺口：UID 不會自動限制網路、資源或公開檔案；群組可寫的 requests 也不等於只能新增、不能改單。普通 daemon 經助手換 UID 後，**強制停機也要委託有權限者**，當父親不自帶跨 UID 發訊號權。

既有實驗是 200 次串行 `/bin/true` 平均：直接 0.19 ms、單 namespace 0.34 ms；千次 bwrap／多 UID 約合 0.7～1.4 秒總耗時，**不是千顆常駐 cpu 壓測**。腳本吞掉錯誤且不統計成功率，不能據此保證無瓶頸。共用 namespace 可攤提映射成本，但尚未量過。

**2．分開的理由還剩多少？**

- **強：故障隔離。** tick 失敗與 kernel cpu 死亡是兩層；daemon 重拉的是符合 restart 條件的 cpu，不能修壞帳本或程式死循環。排程出錯時，其他 cpu 仍有人監督，確有價值。
- **中強：生死管理保持簡單。** idle-wait 繼續增加 kernel 邏輯，更有理由不把它塞進生死管理迴圈。
- **中：一個 daemon 管多個 K。** 可共用監督；但 daemon 本身仍是共同故障點。
- **弱：K2 分家。** 有管理價值，沒有自動增加安全性；同 UID 在牢外仍可能讀帳本、投遞工作。

這些足以支持**目前保留角色與行程邊界**，不足以要求兩個可執行檔；同一執行檔的兩個子命令也行。

不能直接 sudo 現有 daemon：它接受 target、解析 inst 並啟動，未建立跨身分授權；就算孩子降權，父親解析／開串流的權限仍要審。[現行啟動程式](../../lib/aos_exec.py)

**3．對 I 隊結論的影響**

**維持「現在不動；需要改善帳本時優先③」。** 撤掉「切 UID 必須 root daemon」這項論據，不代表合一就有收益。sqlite 解帳本問題；隔離與合一是別的軸。兩步開機可用一個入口包裝，無須先合併行程。

**4．權限線怎麼走？**

預設信任 daemon／kernel／cpu 執行框架，**不信任模型能控制的程式**：工具走 bwrap；CLI agent 須包住整支及子孫，不能只靠 L 隊工具包裝。掛載白名單、清環境、隔離 PID／proc、收緊 fd 與 socket；K、D、K2 不開放直接寫，必要操作走受信任入口。bwrap 保護程度取決於參數，並非用了就完整隔離。[上游安全說明](https://github.com/containers/bubblewrap/blob/main/SECURITY.md)

需要隔開不同信任群體、包括牢外程式時，再加不同 UID＋bwrap。按信任群體分 UID，別預設每顆 cpu 一個；agent 會換 cpu，身分不能意外跟著池座位走。兩種方案仍共用 Linux 核心。

**5．要使用者拍的（附預設）**

- 現在合一嗎？**不合，保留行程隔離；操作入口可統一。**
- daemon 要常駐 root 嗎？**不要；日後真需跨 UID，再選受限助手或系統服務。**
- 隔離範圍？**所有不可信工具及 CLI agent；無法建立指定牢就拒跑。**
- 現在每 agent／cpu 配 UID 嗎？**不配；有不同信任群體才加，並保留 bwrap。**

最有把握：**切 UID 的需求不能證明 daemon 必須 root，更不能證明必須兩個執行檔。**

最沒把握：**千顆 cpu 的完整啟動與維護成本**；目前短程式測量不足以替各方案排名。