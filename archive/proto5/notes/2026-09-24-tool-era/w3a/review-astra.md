全程未修改檔案。以下依原始碼與不落檔的 mock 檢查判定；未執行會建立暫存檔的完整測試，也未實跑 bwrap。

## 必修（會造成逃逸、資料壞、測試會漏的 bug）

- **[P1] [proto5/lib/aos_team_toolsmith.py:264]、[proto5/lib/aos_agent_tools_dev.py:1386]：牢的第二次探測失敗，會在主機直接跑草稿。**  
  現象 → toolsmith 先確認能關牢，但子程序 `tools test` 又探測一次；第二次失敗就退回不關牢執行，事後檢查報告的 `jail` 已太晚。  
  重現 → 第一次 `jail_ready()` 回成功，第二次回失敗；mock 已確認走到「工具直接在這台機器上跑」分支。  
  建議 → 增加強制關牢模式，toolsmith 必須使用；任何探測或啟動失敗都直接拒跑。

- **[P1] [proto5/lib/aos_team_spawn.py:214]、[proto5/lib/aos_team_spawn.py:168]：崩潰後重試可能跳過新設定的人批要求。**  
  現象 → `effects: null` 的舊申請直接進 `_auto_finish`；`realize` 雖重算 policy，卻沒處理 `approve: true`。  
  重現 → 不用人批的申請寫好紀錄、尚未改名冊就中止；把申請者改成要人批，再重送原申請。mock 結果仍是寫名冊、回 `DONE`，沒有開題。  
  建議 → 自動恢復時重新檢查是否需要人批，必要時轉待批准；與人的 `approve` 路徑明確區分。

- **[P1] [proto5/lib/aos_team_spawn.py:165]、[proto5/lib/aos_team_spawn.py:179]：名冊更新沒有共用鎖，並行操作會互相覆蓋。**  
  現象 → 原子換檔只能避免半份 JSON，不能避免遺失別人的更新；郵差有自己的鎖，但人的 `spawn approve` 沒拿同一把鎖。  
  重現 → 郵差自動生 A，同時人工批准 B；兩邊都讀到舊名冊，各自加一列再寫，最後寫入者會抹掉另一列及其 `mail_to` 更新。  
  建議 → 自動生成、人工批准與 `rm` 共用名冊交易鎖，涵蓋重新讀取、檢查、修改與寫入。

- **[P2] [proto5/lib/aos_team_spawn.py:323]：失敗後補做成功，不會補寄成功通知。**  
  現象 → `_auto_finish` 已存 `FAILED` effects、郵差已歸檔；人修好後跑 `spawn approve s-NNNN`，只印「回信郵差寄」，沒有排信，也沒有更新舊 effects。  
  重現 → 讓 init 失敗一次，郵差處理完退信後修復並補做。mock 確認此分支的通知及紀錄寫入呼叫均為零。  
  建議 → 補做成功時建立可去重的成功通知，並記下恢復結果。

- **[P2] [proto5/lib/aos_team_spawn.py:86]、[proto5/lib/aos_team_spawn.py:122]：用「名字還在不在名冊」推狀態，會留下幽靈名額。**  
  現象 → 自動生成成功後移除成員，舊 `q: null` 紀錄變回 `approved`，再次佔人數與名字；反過來，名冊剛寫好但 init 失敗，也會被顯示成「已生」。  
  重現 → 上限 2、原有 1 人，生出第 2 人後移除，再申請不同名字；mock 得到 `TooMany`，實際名冊只有 1 人。  
  建議 → 紀錄持久化的完成／失敗／移除狀態，不能單靠名冊推斷；人數只計真正未完成的申請。

- **[P2] [proto5/lib/aos_team_spawn.py:250]、[proto5/lib/aos_team_post.py:129]：自動生成後，郵差同一輪仍用舊名冊，合法信會被永久退件。**  
  現象 → `realize` 回傳新名冊，但 `_auto_finish` 丟掉；`Post.roster` 要下一輪才刷新。  
  重現 → 同一輪信箱中，先處理生成 W，再處理領隊寄給 W 的信／handoff；前一份已成功，後一份卻因舊 `mail_to` 被拒。舊名冊驗信的 mock 結果是 `BadRecipient`。  
  建議 → spawn 改名冊後立即刷新郵差的名冊，再處理下一封信。

## 建議（不修也不會壞）

- **[proto5/lib/test/test_team_spawn.py:372]**：「崩到一半」測試其實先完整生成，再把 `effects` 清空，沒有覆蓋真正的中途失敗。建議補上寫紀錄後、寫名冊後、init 失敗、補做回信，以及生成後移除的案例。
- **[proto5/spec/team/spawn.md:32]、[proto5/lib/aos_team_format.py:757]**：規格寫團隊 `templates: []` 是「誰都不准生」，但成員的非空 `templates` 可以覆蓋它。依這次逐成員設定的裁決，建議改成「未另設成員白名單者不准生」。
- **[proto5/lib/aos_team_toolsmith.py:268]**：總逾時只直接殺掉測試主程序，而工具另開 session；是否留下子程序、讓郵差超過宣稱的約 90 秒，**沒把握**，尚缺實際程序樹測試。建議補「總逾時發生時仍有工具在跑」的測試。

## 沒問題的（一句話列你確認過的重點）

- **[proto5/lib/aos_team_spawn.py:45、104]**：一般新申請會擋額外 `mounts/tools/model`、非白名單模板、越界 `mail_to`、超額人數及超出的 `may`；`SAFE_MAY` 是規格明列的例外。
- **[proto5/lib/aos_team_spawn.py:147]**：固定名冊設定下，A→B→C 的模板白名單與人批限制會逐代保留；已用記憶體檢查確認兩代繼承。
- **[proto5/lib/aos_team_format.py:567、744]**：成員 `spawn: false` 會關掉新申請權限；寄件人也會核對 outbox、檔名與 `from`，不能直接偽裝成領隊。
- **[proto5/lib/aos_team_toolsmith.py:197、417]**：草稿取自申請內容，批准前核對快照 sha256；改 staging 不會換掉待裝程式，批准安裝仍由人執行。
- **[proto5/lib/aos_team_toolsmith.py:422]、[proto5/lib/aos_agent_tools.py:150]**：既有包的覆蓋限制有接上；**[proto5/lib/aos_agent_tools_dev.py:1165]** 也確實套用草稿每次執行的逾時。