# mail 進階

← [README（日常用法）](README.md)

日常只要 README 的 send／read／done／audit。這份給要用其他狀態、團隊、身份格、程式 API，或要維護本包的人。

## 目錄

- [本包資訊](#本包資訊)
- [全部狀態](#全部狀態)
- [完整指令](#完整指令)
- [團隊與身份格（含 orders、程式 API）](#團隊與身份格)
- [檔案與復原](#檔案與復原)
- [契約卡](#契約卡)
- [已知限制](#已知限制)
- [驗證](#驗證)

## 本包資訊

| 項目 | 內容 |
|---|---|
| 分類 | 多 node 的檔案郵局 |
| 接法 | C 工具 `aos7-mail`、函式 `aos7_mail.handle` |
| 預設 | 關，不裝就不存在 |
| 依賴 | Python 3 標準庫、events 包公開 publish/read/CLI、核心 aos7_fs |
| 程式 | `aos7-mail` 薄殼呼叫 `aos7_mail_cli.py`（參數與白話輸出）；`aos7_mail.py` 負責投遞、路由、輪詢、audit、辦結與復原；`aos7_mail_setup.py` 負責 ROSTER 原子追加與 team 完整發布 |
| 範例 | [examples/two_nodes.sh](examples/two_nodes.sh)，自己檢查後印 OK |
| 測試 | [tests/test_mail.py](tests/test_mail.py)＋[tests/test_mail_review.py](tests/test_mail_review.py)，29 項測試 |

## 全部狀態

- **REQUEST**：請對方辦事。只有它需要對方 done 時回終局狀態，audit 也只追它。
- **PROGRESS**：進度回報，不結案。
- **DONE／BLOCKED／NEEDS-USER／FAILED**：終局回報（完成／卡住／要使用者決定／失敗）；回 REQUEST 時用 `--re <請求id>` 或由 done 自動帶上。
- **必達提醒**：REQUEST 另外發一則 events 的 must 提醒，但信件才是權威，提醒失敗仍算寄信成功。
- **團隊／上游**：團隊信箱給成員共讀，`--up` 自動找到團隊領導或 ROSTER 指定的上游。

日常省略 STATUS 時：send 預設 REQUEST；done 只給一句話時預設 DONE。

## 完整指令

```text
aos7-mail [--root R] send <我> <對象|--up|team:<隊>> [<STATUS>] '<一句話>' [正文檔] [--re <REQUEST-id>]
aos7-mail [--root R] read <我> [--quiet] [--json]
aos7-mail [--root R] done <我> <序號|信檔名|信id> [[<終局STATUS>] '<一句話>' [正文檔]]
aos7-mail [--root R] audit [<我>] [--json]
aos7-mail [--root R] roster <我> --who W --up U --territory T --can C --cannot X [--team 隊]
aos7-mail [--root R] team <隊> <領導> [成員...]
```

`aos7-mail --help` 與 `aos7-mail <指令> --help` 不需要 root。

`--root` 也可放指令後面，優先於環境變數 `AOS_MAIL_ROOT`；沒有 root 就拒絕。名字只准英數字、`.`、`_`、`-`，另拒絕 `.`、`..` 與根目錄保留名 `teams`。

收件者 `R/<對象>/` 不存在時仍照寄並自動建信箱，stderr 印 `注意：<對象> 是新信箱（第一次收信）`；請確認名字沒有打錯。

send 成功印一行 JSON `{"sent": "絕對信檔路徑", "id": "唯一id"}`。未給正文四段都寫「無」；一般正文放在「做了什麼」，另外三段寫「無」；已有協定的四段標題則保留正文。第一個 `# ` 是非空的一行結論。

read 的個人未辦信依檔名排序，從 1 起列 `<序號>  <檔名>  <一句話>`；這個序號也能給 done。
其他行是 `團隊  <檔名>  <一句話>`、`指示  <段落第一行>`、`等回信  <檔名>  <一句話>`、`復原  <檔名>  <一句話>`。
「等回信」只列我寄出的未結 REQUEST，收到的請求已在序號行，不重列；團隊與 orders 只列新增內容。
非 quiet 個人信每次全列，沒東西印 `（沒有新信）`。`--json` 回物件陣列，信件有 frontmatter，個人信另有 `number`。

read／done／handle 的 `<我>` 只准個人名；`team:` 僅可當 send 收件者。
done 可以給序號、檔名或 id；成功印 `已辦結 <檔名>，已回 DONE 給 alice`，非 REQUEST 印 `已歸檔 <檔名>`。
read 在 stdout flush 後原子保存 `.numbers.json`（序號→信 id），只含這次列出的個人未辦信，非 JSON 也一樣。done 序號只照最近這份快照找信，不因新信插入或 journal 復原而改指別封；快照不存在或序號不在快照時退出 2「序號 N 不在最近一次 read 的清單裡，請先 read …」；這樣才不會辦到剛到、還沒看過的信。信已在 done 則成功印 `已辦結過 <檔名>`。quiet 沒列個人信會保存空快照。

REQUEST 的 done 必須給結論（STATUS 省略時為 DONE）；自動回給 reply-to（本郵局的 `R/<名字>/inbox` 路徑，取 inbox 的父目錄名作收件者；未填則 from），`re` 指向請求 id。團隊成員回覆非領導的對象時也給領導一封副本（領導自己辦結也會收到這份副本）。重跑同一封 done 不再回信。

退出碼：0 成功；1 僅 audit 發現未結 REQUEST；2 用法／檔案錯誤，stderr 一行說明。read 有未結請求仍退出 0。

## 團隊與身份格

設定自己的身份格（只追加，同名拒絕；團隊欄位只是聲明，實際成員資格以 members 為準）：

```sh
"$P/modules/mail/aos7-mail" roster alice --who '範例寄件者' --up chief \
  --territory 'alice 的資料夾' --can '寄信' --cannot '驗證別人身份'
"$P/modules/mail/aos7-mail" send alice --up PROGRESS '開始檢查'
```

ROSTER 位在 `$R/alice/wf/workflows/inbox/ROSTER.md`，以 `aos7-wfnode init` 裝出的模板那份為正本；既有檔只在「## 現役成員」段尾加格，沒有該段則加在檔尾；不存在才建有標題與「現役成員」的最小檔。每格照專案 ROSTER 格式寫九個欄位；鎖內先寫同目錄暫存、完整關閉後 os.replace，程序中斷不會截斷原檔。可加 `--team dev` 聲明團隊；領導與無團隊者的 `--up` 讀自己那格的上游。

建立團隊（同一人不能在別隊；既有 members 完全相同則冪等成功，不同則退出 2）：

```sh
"$P/modules/mail/aos7-mail" team dev lead bob carol
"$P/modules/mail/aos7-mail" send bob --up PROGRESS '向領導報進度'
"$P/modules/mail/aos7-mail" send carol team:dev PROGRESS '這段讓全隊知道'
"$P/modules/mail/aos7-mail" read bob --quiet
```

`$R/teams/dev/members` 首行是 lead；只有成員可投 team:dev，且只收 PROGRESS／終局廣播；REQUEST 先退出 2「團隊信箱只收廣播（PROGRESS／終局）；要人辦事請直接寄給成員」。team 在 `R/.staging/mail-team-*` 準備完整 members 與 inbox 後 rename 發布；中斷時 team_of 看不到未發布名冊，下次 team 持 membership 鎖清掉殘留 staging 後可重跑。每人的 `.seen-team` 記已讀信 id 集合，避免同分鐘後來發布的信被時間游標漏掉。團隊信是廣播，不會由某個成員 read 移走。

orders 位在 `$R/<我>/inbox/orders/<我>.md`，只能追加；每段用 `## <ISO時間> — from: <名字> — <結論>` 開頭。read 以 `.orders-offset` 保存讀到的 byte offset；檔案截短會拒絕。上游指示的權重依專案協定，由讀信者判斷。

`audit [<我>]` 單獨檢查未結 REQUEST；不給名字就掃整個郵局。掃所有 inbox 與 done，比對 REQUEST 的 id 與終局信的 re；PROGRESS 不會結案。個人 audit 列出自己寄出或收到的未結請求。

`read <我> --quiet` 適合每步執行：只報未報過的個人信、團隊新信、orders 新段與復原，不列等回信或空信箱提示；沒有新東西時 stdout 完全空（`--json` 也一樣）。
個人 id 記在 `.seen`，非 quiet 全列也更新它；讀過不等於辦完。所有 seen／orders 游標在全部讀取成功、stdout flush 之後才提交；途中被殺容許重列，不會永久漏報。
沒有背景推播或 watch。

函式 API（自行將包根加入 `sys.path`）：

```python
from aos7_mail import handle

def handler(letter):
    # letter 是含 id/from/to/status/title/body/file 等欄位的 dict。
    return 'DONE', '已檢查輸入並完成處理', '檢查結果'

handle(root, 'bob', handler)
```

handle 處理個人 inbox 所有未辦信，同格操作拿辦結鎖。handler 的外部副作用發生在日誌之前，被殺可能重做，屬於至少一次；日誌原子落地之後不再呼叫 handler。已 journal 的信直接復原，非 REQUEST 的 handler 結果不產生回信。

## 檔案與復原

只解析非點開頭的 `.md` 一般檔案；忽略 `.gitkeep`、隱藏 `.md`、其他副檔名與目錄，頂層／done／團隊信箱共用此規則。

信格式照 inbox PROTOCOL：frontmatter 是 `from to status at reply-to id re`，正文固定「做了什麼／產出／沒做到／需要決定」四段。信 id 使用寄件者＋秒級時間＋隨機值。

node 信箱的未辦信、`done/`、`.tmp/`、`.handled/`、`.seen` 等都在 `R/<名字>/inbox/`；events 仍在 `R/<名字>/events/`。團隊仍用 `R/teams/<團隊>/members`（首行領導）與 `R/teams/<團隊>/inbox/`。

未辦信路徑：`R/<名字>/inbox/<YYYYmmddTHHMM>-<寄件者>-<STATUS>.md`。先在 `.tmp/` 寫完整關閉，再 `os.link(tmp, final)` 原子發布；撞名以 `<YYYYmmddTHHMM>_<n>-<寄件者>-<STATUS>.md` 重試，同時避開 inbox／done 檔名，完成後刪暫存。`.delivery.lock` 共用於固定 id 查重、投遞、歸檔與 audit 的每格快照；link 失敗不覆蓋既有信。同寄件者一分鐘內多封時，直接拒收會丟信，所以拒覆蓋後加序號重試。frontmatter 只認獨立一行的 `---`，名字中的三連字號不會截斷欄位。

辦結順序固定：

1. 先完整驗證回信，再原子寫 `.handled/<id>.json`，保存所有回信對象與內容；非法結論不會留下復原日誌。
2. 寄固定 id `re-<請求id>-<STATUS>` 的回信與領導副本；在對方 inbox＋done 查同 id，有就不重寄。
3. 在 delivery 鎖下 link 原信進 done，再 unlink 頂層；既有同 id 表示已發布，不同 id 則重試 `<YYYYmmddTHHMM>_<n>-<寄件者>-<STATUS>.md` 避撞，絕不覆蓋歷史。
4. 從 must 最前面開始，僅確認連續 `kind=mail.request` 且 id 對到已辦 REQUEST 的事件；未辦或非 mail 事件擋住後續 ack。

read 遇到已有日誌的頂層信會補做 2–4，並印 `復原`；搬移後被殺也會在下一次 read／done 補 ack。每次 ack 先透過公開 CLI `read --channel must --ack 0` 取得 events 真正的 `acked_upto`，同步 `.acked` 再往下檢查；events 已確認但本地落後、舊段被淘汰時也能繼續。保留 `.handled` 與所有鎖檔，不要人工清掉它們。

REQUEST 的 must 以 `publish(..., kind="mail.request", event_id=信id, payload={id,from,to,file}, must=True, node=收件者)` 發布。full／unknown 或發布例外只印 stderr，send 仍退出 0；請求仍可由 inbox／audit 發現。ack 經 `aos7-events read --channel must --ack N` 子程序；本包不 import events store。確認失敗保留位置，下次重試。

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
- 依契約卡「must 通道獨佔」，mail／author 必須分 node；共用 must 時，非 mail 事件會阻住後續 mail ack，其他消費者也可能提前確認 mail 提醒。
- 收件者名／寄件者名不驗真偽，audit 的 re 是合作式證據，不是不可偽造的憑證。
- 團隊信是共讀廣播，只收 PROGRESS／終局，send 團隊 REQUEST 退出 2；done／handle 只處理個人 inbox。需要指定人辦的 REQUEST 請直接寄給該人。
- 掃描信與去重是線性搜尋，seen／seen-team、handled 與歷史不自動縮減；不含重試提醒、跨郵局 reply-to 或團隊增刪成員。
- 非 quiet 未辦信與等回信會重列；quiet 是新信提醒，已報過但未辦的信請用非 quiet read 查看。
- read 的函式 API 是批次 context manager：`with poll(root, me, quiet=True) as rows:`，呼叫者須在區塊內輸出並 flush，正常離開才保存游標；區塊內出錯不保存。
- 輸出與游標沒有跨程序交易，flush 後保存前被殺可能重報；orders 同長度覆寫無法辨識，請遵守 append-only。
- audit 是每格持鎖快照，不是全郵局同時快照；並行寄／辦時可短暫列出剛結案的請求，下次重讀即可。

## 驗證

在 repo 根跑：

```sh
systemd-run --user --scope -p TasksMax=300 python3 -B proto7-2/tests/run_all.py modules/mail/tests
sh proto7-2/modules/mail/examples/two_nodes.sh
```

29 項測試全綠，範例印 OK，第一次跑整段已在真實檔案系統執行，最後 audit 退出 0。
測試 import base 啟用 SIGKILL 鉤子；既有 10 項保留，新增審查 1–7 各一項與人類介面一項。
新增分鐘信名／歸檔避撞與模板 ROSTER 段內追加兩項；另確認讀信及終局回信後、原信歸檔前皆不 ack。
涵蓋 160 封固定同分鐘並行投遞、辦結中斷與 handler 一次、連續 must ack，以及輸出 flush 前／後中斷、flush／audit 失敗、真的 retention gap、並行送／辦／audit。

前輪七項退化驗證各只跑對應 `test_review<N>_`，全部退出 1，還原後清除 `__pycache__` 再跑全套全綠：

| 審查 | 拿掉的修法 | 對應測試／紅燈訊息 |
|---|---|---|
| 1 | 移除 done 檔名避撞，歸檔退回 rename | `test_review1_archive_never_overwrites`：`投遞必須避開 done 檔名`（兩封檔名相等） |
| 2 | seen／orders 提交搬到輸出前 | `test_review2_seen_only_after_flush`：`True is not false : flush 前不得保存 .seen` |
| 3 | 起始 ack 改信本地 `.acked` | `test_review3_ack_reconciles_after_retention`：`2 != 4 : 本地落後與舊段淘汰不得卡住後續 ack` |
| 4 | 歸檔與 audit 移除共用 delivery 鎖 | `test_review4_archive_and_scan_share_delivery_lock`：`BlockingIOError not raised : 歸檔必須持 delivery 鎖` |
| 5 | 移除日誌前完整回信驗證 | `test_review5_invalid_title_cannot_poison_journal`：`True is not false : 非法回信不得建立日誌` |
| 6 | frontmatter 退回 `split('---', 2)` | `test_review6_three_hyphen_names_parse`：`KeyError: 'id'` |
| 7 | 移除 done／handle／read 個人名驗證 | `test_review7_only_people_can_read_done_handle`：`0 != 2`（團隊 done 誤成功） |

另單獨退化歸檔防覆蓋（保留投遞避撞），審查 1 同測試紅：`歸檔不可覆蓋舊信`；只移除 audit 的 delivery 鎖，審查 4 同測試紅：`BlockingIOError not raised : audit 必須在 delivery 鎖下列檔讀信`。

原始防撞／日誌也重新退化實跑：直接 rename 投遞令 `test_parallel_delivery` 紅：`8 != 160 : 160 封同秒投遞不可被覆蓋`；省略日誌令 `test_handle_crash_side_effect_once` 紅：`'2' != '1'`。前輪審查完整輸出在 `/tmp/x1/red1.txt`～`red7.txt`，額外證據在同處 `red-1-archive-only.txt`、`red-4-audit-only.txt`、`red-delivery-link.txt`、`red-journal.txt`。

第二輪新增 6 項：序號綁快照（同分鐘插入／已辦冪等／quiet 快照）、序號 journal 中斷重跑、flush 前不改快照、ROSTER replace 前 SIGKILL、team publish 前 SIGKILL／重試／冪等、團隊 REQUEST 先拒絕。每條拿掉修法實跑退出 1，還原後再驗證全綠：

| 條目 | 拿掉的修法 | 紅燈證據 |
|---|---|---|
| 1 插入 | 保留快照檢查，但改依即時未辦信排序選信 | `test_round2_numbers_bind_snapshot`：`False is not true : 序號不得辦掉後插入的信` |
| 1 journal | 同上，排除已 journal 信再選序號 | `test_round2_numbers_resume_journal`：`False is not true : 重跑序號必須復原原 journal 的信` |
| 2 | replace 前先 truncate／寫入原檔 | `test_round2_roster_atomic_replace`：`replace 前被殺原 ROSTER 必須不變` |
| 3 | 改在公開 teams 目錄直接準備 | `test_round2_team_atomic_publish`：`('dev', 'lead') is not None : 中斷時 team_of 不得看到半份名冊` |
| 4 | 移除團隊 REQUEST 拒絕 | `test_round2_team_request_rejected_first`：`0 != 2` |

第二輪完整紅燈輸出：`/tmp/x1/round2/{numbers-insert,numbers-journal,roster,team,request}.txt`。

本輪新增真 wfnode 雙 node 整合與雜檔過濾兩項：init alice／bob 後在模板「現役成員」段追加身份格，其餘內容逐字保留；REQUEST → read／done → 終局回信，`.gitkeep` 不列信。找不到 `AOS7_WF_HOME`（預設 `~/repo/workflows`）的 `tools/wf-init.sh` 時整合測試 skipTest。本機實跑未 skip，alice／bob 的 `aos7-wfnode check` 退出碼都是寄信前 0、收辦回信後 0。清除 mail 的 `__pycache__` 後再跑指定指令，兩輪都是 28 項全過；`aos7_mail.py` 357 行。

10-09 回改（新手試用不過）：加 `--help`（不需 root）、send 省略 STATUS 預設 REQUEST、done 只給一句話預設 DONE、錯誤訊息改白話並附例子；README 只留日常四指令，其餘移來本檔。新增 `test_newbie_help_and_defaults`，共 29 項。
