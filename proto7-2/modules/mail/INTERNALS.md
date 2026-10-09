# mail 內部設計

← [ADVANCED](ADVANCED.md)｜[測試](tests/README.md)

## 檔案與復原

只解析非點開頭的 `.md` 一般檔案；忽略 `.gitkeep`、隱藏 `.md`、其他副檔名與目錄，頂層／done／團隊信箱共用此規則。

信格式照 inbox PROTOCOL：frontmatter 是 `from to status at reply-to id re`，正文固定「做了什麼／產出／沒做到／需要決定」四段。信 id 使用寄件者＋秒級時間＋隨機值。

node 信箱的未辦信、`done/`、`.tmp/`、`.handled/`、`.seen` 等都在 `R/<名字>/inbox/`；events 仍在 `R/<名字>/events/`。團隊仍用 `R/teams/<團隊>/members`（首行領導）與 `R/teams/<團隊>/inbox/`。

未辦信路徑：`R/<名字>/inbox/<YYYYmmddTHHMM>-<寄件者>-<STATUS>.md`。先在 `.tmp/` 寫完整關閉，再 `os.link(tmp, final)` 原子發布；撞名以 `<YYYYmmddTHHMM>_<n>-<寄件者>-<STATUS>.md` 重試，同時避開 inbox／done 檔名，完成後刪暫存。`.delivery.lock` 只用於投遞（含固定 id 查重）、歸檔與 audit 的每格快照；一般 read 不拿別人的 delivery 鎖，已 journal 的信仍會補回信及歸檔；link 失敗不覆蓋既有信。同寄件者一分鐘內多封時，直接拒收會丟信，所以拒覆蓋後加序號重試。frontmatter 只認獨立一行的 `---`，名字中的三連字號不會截斷欄位。

辦結順序固定：

1. 先完整驗證回信，再原子寫 `.handled/<id>.json`，保存所有回信對象與內容；非法結論不會留下復原日誌。
2. 寄固定 id `re-<請求id>-<STATUS>` 的回信與領導副本；在對方 inbox＋done 查同 id，有就不重寄。
3. 在 delivery 鎖下 link 原信進 done，再 unlink 頂層；既有同 id 表示已發布，不同 id 則重試 `<YYYYmmddTHHMM>_<n>-<寄件者>-<STATUS>.md` 避撞，絕不覆蓋歷史。
4. 從 must 最前面開始，僅確認連續 `kind=mail.request` 且 id 對到已辦 REQUEST 的事件；未辦或非 mail 事件擋住後續 ack。

read 遇到已有日誌的頂層信會補做 2–4，並印 `復原`；搬移後被殺也會在下一次 read／done 補 ack。ack 從本地 `.acked`（無檔為 0）+1 用 in-process events read 掃描；retention 缺口表示已確認淘汰，跳到缺口後繼續，其他缺口或 errors 停止。有進展才起一次公開 CLI `aos7-events ack --events DIR N`，成功後寫回傳值到 `.acked`；無進展零個子程序。本地只寫 events 確認值，ack 後被殺可重掃已辦信，舊段淘汰也能繼續。保留 `.handled` 與所有鎖檔，不要人工清掉它們。

只在對方已有 events/ 資料夾時，REQUEST 的 must 以 `publish(..., kind="mail.request", event_id=信id, payload={id,from,to,file}, must=True, node=收件者)` 發布。full／unknown 或發布例外只印 stderr，send 仍退出 0；請求仍可由 inbox／audit 發現。ack 經 `aos7-events ack --events DIR N` 子程序；本包不 import events store。確認失敗保留位置，下次重試。

## 契約卡

- **職責**：完整投遞檔案信、身份與團隊路由、輪詢追加資料、查未結請求、日誌保護的辦結復原。
- **前置條件**：本地支援 hard link／rename／flock 的檔案系統，所有寫者走本包、信體發布後不改；reply-to 指向同 root 的參與者 inbox；orders append-only；events must 單消費者。
- **何時算確認提醒**：讀信不算 ack；終局回信落盤、原 REQUEST 搬進 `done/` 之後才推進 must ack。
- **must 通道獨佔**：一個 node 的 events must 通道由 mail 獨佔；學徒（author）的 must 用別的 node，以既有 send 轉交留回條。
- **保證**：並行寄件不互蓋、不見半封信；STATUS 拒絕非法值；終局回覆對到請求；日誌落地後不重做 handler；固定回信 id 防重寄；不越過非 mail must 確認。
- **明確不管**：handler 外部效果交易、產品決策、授權、身份鑑別、網路送信、斷電耐久、歷史清理。

## 已知限制

- 不 fsync，抗程序 SIGKILL，不承諾斷電；send 若在信落地與 events publish 之間被殺，可能缺提醒，信仍是權威。
- send 被殺可能留下 `.tmp/` 完整或未完整暫存，收件輪詢不看暫存；正常投遞後會清空。
- 依契約卡「must 通道獨佔」，mail／author 建議分 node。共用 must 時誰都不替對方確認（author intake 遇沒確認的 mail.request 會停，10-09 RV-fix-C）；mail 遇到非 mail 事件時讀 events 目前確認到哪（`load_state` 的 acked_upto）：別人已確認的讓過、接著確認排在後面的自己的提醒；別人還沒確認的就停下，不替它確認（10-09 MLfix）。
- 收件者名／寄件者名不驗真偽，audit 的 re 是合作式證據，不是不可偽造的憑證。
- 團隊信是共讀廣播，只收 PROGRESS／終局，send 團隊 REQUEST 退出 2；done／handle 只處理個人 inbox。需要指定人辦的 REQUEST 請直接寄給該人。
- 掃描信與去重是線性搜尋，seen／seen-team、handled 與歷史不自動縮減；不含重試提醒、跨郵局 reply-to 或團隊增刪成員。
- ack 從本地 `.acked` 起算：若有人刪掉重建某 node 的 `events/`（seq 從 1 重來），要一併刪 `inbox/.acked`，否則新提醒不會被確認。
- 非 quiet 未辦信會重列；等回信改由 audit <我> 查；quiet 是新信提醒，已報過但未辦的信請用非 quiet read 查看。
- read 的函式 API 是批次 context manager：`with poll(root, me, quiet=True) as rows:`，呼叫者須在區塊內輸出並 flush，正常離開才保存游標；區塊內出錯不保存。
- 輸出與游標沒有跨程序交易，flush 後保存前被殺可能重報；orders 同長度覆寫無法辨識，請遵守 append-only。
- audit 是每格持鎖快照，不是全郵局同時快照；並行寄／辦時可短暫列出剛結案的請求，下次重讀即可。

## 身份與序號狀態的原子發布

ROSTER 位在 `$R/alice/wf/workflows/inbox/ROSTER.md`，以 `aos7-wfnode init` 裝出的模板那份為正本；既有檔只在「## 現役成員」段尾加格，沒有該段則加在檔尾；不存在才建有標題與「現役成員」的最小檔。每格照專案 ROSTER 格式寫九個欄位；鎖內先寫同目錄暫存、完整關閉後 os.replace，程序中斷不會截斷原檔。可加 `--team dev` 聲明團隊；領導與無團隊者的 `--up` 讀自己那格的上游。

team 在 `R/.staging/mail-team-*` 準備完整 members 與 inbox 後 rename 發布；中斷時 team_of 看不到未發布名冊，下次 team 持 membership 鎖清掉殘留 staging 後可重跑。

read 在 stdout flush 後原子保存 `.numbers.json`（序號→信 id），只含這次列出的個人未辦信，非 JSON 也一樣。done 序號只照最近這份快照找信，不因新信插入或 journal 復原而改指別封；快照不存在或序號不在快照時退出 2「序號 N 不在最近一次 read 的清單裡，請先 read …」；這樣才不會辦到剛到、還沒看過的信。信已在 done 則成功印 `已辦結過 <檔名>`。quiet 沒列個人信會保存空快照。
