# mail 進階

← [README（日常用法）](README.md)

日常只要 README 的 send／read／done；查帳用的 audit 也在這份。這份給要用其他狀態、團隊、身份格、程式 API，或要維護本包的人。

## 本包資訊

| 項目 | 內容 |
|---|---|
| 分類 | 多 node 的檔案郵局 |
| 接法 | C 工具 `aos7-mail`、函式 `aos7_mail.handle` |
| 預設 | 關，不裝就不存在 |
| 依賴 | Python 3 標準庫、events 包公開 publish/read/CLI、核心 aos7_fs |
| 程式 | `aos7-mail`→`_cli`（參數、白話輸出）；`aos7_mail.py` 解析、投遞、路由、audit；`_box` 辦結與輪詢；`_ack` 提醒確認；`_help` 說明文字；`_setup` ROSTER 與 team |
| 範例 | [examples/two_nodes.sh](examples/two_nodes.sh)，自己檢查後印 OK |
| 測試 | [tests/README.md](tests/README.md)，35 項測試 |

## 全部狀態

- **REQUEST**：請對方辦事。只有它需要對方 done 時回終局狀態，audit 也只追它。
- **PROGRESS**：進度回報，不結案。
- **DONE／BLOCKED／NEEDS-USER／FAILED**：終局回報（完成／卡住／要使用者決定／失敗）；回 REQUEST 時用 `--re <請求id>` 或由 done 自動帶上。
- **必達提醒**：REQUEST 只在對方已有 `events/` 資料夾時發一則 must 提醒，但信件才是權威，提醒失敗仍算寄信成功。
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

收件者 `R/<對象>/` 不存在時仍照寄並自動建信箱，stderr 印 `aos7-mail: 注意：<對象> 是新信箱（第一次收信）。確認名字沒打錯；沒錯就不用管`。

send 成功印一行 JSON `{"sent": "絕對信檔路徑", "id": "唯一id"}`。機器欄位只在信頭；第一個 `# ` 是非空的一行結論，結論下方附白話狀態（請求信不附），讀信時狀態行不算進 body，JSON 另有 `plain` 欄位。一般正文原樣使用；已有四段協定標題時只印有內容的段落，空段不印、不補「無」。

read 的個人未辦信依檔名排序，從 1 起列 `<序號>  <檔名>  <一句話>`；這個序號也能給 done。
其他行是 `團隊  <檔名>  <一句話>`、`指示  <段落第一行>`、`復原  <檔名>  <一句話>`。
read 不跑 audit；未結 REQUEST 用 `audit <我>` 查（文字前綴「等回信」）。團隊與 orders 只列新增內容。
非 quiet 個人信每次全列，沒東西印 `（沒有新信）`。`--json` 回物件陣列，信件有 frontmatter，個人信另有 `number`。

read／done／handle 的 `<我>` 只准個人名；`team:` 僅可當 send 收件者。
done 可以給序號、檔名或 id；成功印 `已辦結 <檔名>，已回 DONE 給 alice`，非 REQUEST 印 `已歸檔 <檔名>`。
read 在 stdout flush 後保存 `.numbers.json`（本次個人信的序號→id）。done 只照最近快照找信，新信插入不改號；快照缺序號就提示「請先 read」，不會辦到沒看過的信。已在 done 印 `已辦結過 <檔名>`；quiet 沒列個人信會保存空快照。

REQUEST 的 done 必須給結論（STATUS 省略時為 DONE）；自動回給 reply-to（本郵局的 `R/<名字>/inbox` 路徑，取 inbox 的父目錄名作收件者；未填則 from），`re` 指向請求 id。團隊成員回覆非領導的對象時也給領導一封副本（領導自己辦結也會收到這份副本）。重跑同一封 done 不再回信。

## 退出碼

統一表見 [blueprint-errors §2–§4](../../notes/blueprint-errors.md)。

- **0**：做到；提醒失敗不改 send 成功。
- **1**：做不到：audit 找到未結 REQUEST；或撞名／被拒（團隊同名不同名單、成員已在別隊、同名 ROSTER 格、非成員投團隊信箱、`--up` 找不到上游）。
- **2**：參數、名字、序號或信件欄位不對，照 stderr 的用法與例子改。
- **3**：I/O、鎖或 stdout flush 出錯，無法確定做了多少，已寫下的信與狀態留著，照原樣重跑接續。

不用 4。stderr 一行 `aos7-mail: <發生什麼>。<怎麼辦>`，3 以「不確定：」開頭；無參數印說明退 2，help 退 0；JSON 欄位不變。

## 團隊與身份格

設定自己的身份格（只追加，同名拒絕；團隊欄位只是聲明，實際成員資格以 members 為準）：

```sh
"$P/modules/mail/aos7-mail" roster alice --who '範例寄件者' --up chief \
  --territory 'alice 的資料夾' --can '寄信' --cannot '驗證別人身份'
"$P/modules/mail/aos7-mail" send alice --up PROGRESS '開始檢查'
```

ROSTER 位在 `$R/<我>/wf/workflows/inbox/ROSTER.md`，只在「## 現役成員」段尾追加自己的九欄身份格，無該段則加檔尾；同名拒絕。`--team dev` 只是聲明，資格以 members 為準。領導與無團隊者的 `--up` 讀自己的上游。

建立團隊（同一人不能在別隊；既有 members 完全相同則冪等成功，不同則退出 1）：

```sh
"$P/modules/mail/aos7-mail" team dev lead bob carol
"$P/modules/mail/aos7-mail" send bob --up PROGRESS '向領導報進度'
"$P/modules/mail/aos7-mail" send carol team:dev PROGRESS '這段讓全隊知道'
"$P/modules/mail/aos7-mail" read bob --quiet
```

`$R/teams/dev/members` 首行是 lead；只有成員可投 team:dev，且只收 PROGRESS／終局廣播；REQUEST 先退出 2「團隊信箱只收廣播（PROGRESS／終局）。要人辦事請直接寄給成員」。每人的 `.seen-team` 記已讀信 id 集合，避免同分鐘後來發布的信被時間游標漏掉。團隊信是廣播，不會由某個成員 read 移走。

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

## 驗證

在 repo 根跑 `systemd-run --user --scope -p TasksMax=300 python3 -B proto7-2/tests/run_all.py modules/mail/tests`。測試與範例跑法見 [tests/README.md](tests/README.md)，復原與限制見 [INTERNALS.md](INTERNALS.md)。
