# `.env` 格式比較：拿掉變數、多行、引號

← [notes](README.md)｜[proto8](../README.md)｜起點：[aos-exec-s6-runit 04 § 3 方向題 b](aos-exec-s6-runit/04-不適合-衝突-方向題-套件.md)｜2026-10-22，AI 寫

**AI 寫的參考，不算數**：條文以 [CONCEPTS](../docs/CONCEPTS.md)、[NORMS](../docs/NORMS.md) 為準。使用者 10-22 的題目：「b.看看工作量、看看大家都是怎麼做的。」——方向題 b 是 aos 的 `.env` 要不要補「拿掉變數（unset）」「多行值」「引號」。同天追加：「Hmmm，甚至有可能，有了s6-envdir之後，我們甚至不需要.env了。但還是先調查吧」——這個選項在 04。各家的事實查自官方文件（10-22），每格附連結；沒有實跑。

<!-- wf-nav -->
## 分檔

| 分檔 | 涵蓋 |
|---|---|
| [01-各家做法](dotenv-格式比較/01-各家做法.md) | docker、compose、systemd、python-dotenv、node dotenv、dotenvx、direnv、bash、envdir 一族、POSIX `env`、GitHub Actions 的比較表，與看得出的六件事 |
| [04-拿掉env改用envdir](dotenv-格式比較/04-拿掉env改用envdir.md) | 使用者追加的選項：拿掉 `.env`、改在 argv 鏈上接 s6-envdir——envdir 補不回來的規則 |

## 結論

- **各家**：沒有標準 `.env`。dotenv 那一族有引號、跳脫、多行，但**都沒有「拿掉變數」**；拿掉變數的是 envdir（空檔）、systemd（另一個設定 `UnsetEnvironment=`）、bash／direnv（本來就是 shell）。只有名字的一行，docker＝從外面帶進來、python-dotenv＝不設、systemd＝跳過。多行值各家都綁在引號（與跳脫）上。
- **使用者定的**（10-22，原文與決定在 [ideas 10-22 § 3](../thinking/2026-10-22-ideas.md#3-env-基礎子集與---dotenv-override10-22)，規則在 [N-58、N-59 第 4 件](../docs/NORMS/10-基礎設施-定義與工作區.md)）：「照建議：1 改成預設不蓋、加 --dotenv-override 才蓋；2 引號、註解、去空白都做；3 字串轉向算新的一跳、不吃旗標。可以開始做。」——格式做 python-dotenv 的基礎子集（各家不一致的寫法報錯）；unset、多行、跳脫不做（「然後我會覺得拿掉變數這個功能沒必要。」）。
- **不做的那幾項，需要時的路**（都不用改 aos）：拿掉變數＝入口 argv 前面接 `env -u 名字`（GNU／BSD／busybox 有，不是 POSIX）或 `s6-envdir` 放空檔；多行值＝JSON 物件的 `.env` key 字串裡寫 `\n`，或 `{"$ref": "secrets.json#/key"}` 從別的 JSON 拿，或只傳檔名讓程式自己讀（docker 官方映像的 `*_FILE` 慣例），或 `s6-envdir -f`（整份檔就是值）。
- **拿掉 `.env`、改接 s6-envdir**（使用者追加的選項，[04](dotenv-格式比較/04-拿掉env改用envdir.md)）：使用者接著定了 `.env` 的格式（上一點），`.env` 留著。envdir 補不回 `${}` 接 PATH 與「`.env` 改 `AOS_ENTRY`」；祕密要各自設權限時，照樣可以在 argv 鏈上接 s6-envdir（跟方向題 a 不衝突——envdir 是使用者自己寫在 argv 裡的）。
