← [入口 dotenv-格式比較](../dotenv-格式比較.md)｜涵蓋：選項「拿掉 aos 的 `.env`、改在 argv 鏈上接 s6-envdir（或 envdir／chpst -e）」——envdir 補不回來什麼、多出什麼｜上一份 [01-各家做法](01-各家做法.md)

使用者 10-22 追加：「Hmmm，甚至有可能，有了s6-envdir之後，我們甚至不需要.env了。但還是先調查吧」。結果：使用者接著定了 `.env` 的格式（[ideas 10-22 § 3](../../thinking/2026-10-22-ideas.md#3-env-基礎子集與---dotenv-override10-22)），`.env` 留著；下面是換成 envdir 時會碰到的事實，給以後再想這件事的人。

# 1. envdir 補不回來的

| 靠 `.env`（或 JSON 物件的 `.env` key）的事 | 條文 | 改成 envdir |
|---|---|---|
| `${名字}` 展開，`PATH=${AOS_CD}/bin:${PATH}` 接舊值 | N-59 第 4 件「`.env` 的值」 | **做不到**：envdir 的值照字面、不展開。使用者 10-21 要 `.env` 的第一個理由就是 PATH（「主要是PATH的問題」）。替代只剩：入口是單子時用 `envs` 加 `{"$env": "PATH", "$prefix": "絕對路徑/bin:"}`（前綴要寫死）、或寫一支小殼（少用 sh） |
| 每走進一層就讀那層的 `.env`，`sub/run` 沿路都讀 | N-59 第 4 件「走進一層」 | envdir 只在寫了它的那條鏈上作用；沒有「走到哪讀到哪」 |
| `.env` 設的 `AOS_ENTRY` 對這一層挑入口有作用 | N-59 第 4 件、N-57 | **做不到**：envdir 寫在入口裡，入口已經挑完了。只有放在 aos-exec 外面（`s6-envdir d aos-exec X`）才影響挑入口 |
| `$env` 指示詞讀得到 `.env` 設的值 | N-59 第 4 件「一直有效到真正開跑」 | argv 陣列的指示詞在 exec 之前就解了，**讀不到** envdir 設的值；envdir 之後的子程式才看得到 |
| 可執行檔入口（`+x` 的程式、殼）也能吃到 `.env` | N-59 第 4 件 | 要嘛入口改寫成 argv 陣列接 envdir，要嘛程式自己設 |

只拿掉 `.env` 檔、留 JSON 物件的 `.env` key 的話，`${}` 接 PATH 與改 `AOS_ENTRY` 都還在（`{".env": {"PATH": "${AOS_CD}/bin:${PATH}"}, "_exec": [...]}`），代價是入口要寫成 `_exec.json` 物件。

# 2. 換成 envdir 多出的

- **好處**：一個變數一個檔，各自 `chmod`（C-64 借 Linux 權限，`.env` 一份檔做不到）；空檔＝拿掉；`-f` 整份檔是值（多行）；不用自己定引號、跳脫。
- **外部依賴**：agent 資料夾要靠 s6／runit／daemontools 其中一個（方向題 d）。Debian／Ubuntu 有套件（universe），Fedora 沒查到、要自己編（[aos-exec-s6-runit 04 § 4](../aos-exec-s6-runit/04-不適合-衝突-方向題-套件.md)）。
- **路徑**：`s6-envdir` 在 `/usr/bin`；execline 那 52 支（`envfile`、`importas` 等）在 `/usr/lib/execline/bin/`，**不在 PATH 上**。daemontools 的 `envdir` 名字短、容易撞名。s6-envdir 預設只讀每個檔前 4096 bytes（`-L` 取消）。
- **寫法變長**：每個要設環境的入口都得是 argv 陣列並以 `s6-envdir` 開頭；同一組變數要給好幾格時，每格都要接一次（或放在最外面）。

# 3. 跟方向題 a「aos-exec 只用標準庫」

**不衝突**：a 管的是 aos-exec 自己不叫外部程式替它做事；使用者在**自己的 argv** 裡接 s6-envdir，aos-exec 只是照字面 exec。反方向才違反 a：讓 aos-exec「找到 `secrets/` 就自動接 s6-envdir」。
