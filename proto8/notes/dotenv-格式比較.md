# `.env` 格式比較：拿掉變數、多行、引號

← [notes](README.md)｜[proto8](../README.md)｜起點：[aos-exec-s6-runit 04 § 3 方向題 b](aos-exec-s6-runit/04-不適合-衝突-方向題-套件.md)｜2026-10-22，AI（opus）寫

**這份是 AI 寫的參考，不算數**：條文以 [CONCEPTS](../CONCEPTS.md)、[NORMS](../NORMS.md) 為準，要不要補、補哪一項由使用者決定（鐵律 5）。使用者 10-22 的題目：「b.看看工作量、看看大家都是怎麼做的。」——方向題 b 是 aos 的 `.env` 要不要補「拿掉變數（unset）」「多行值」「引號」。同天追加：「Hmmm，甚至有可能，有了s6-envdir之後，我們甚至不需要.env了。但還是先調查吧」——這個選項在 04。

各家的事實查自官方文件（10-22），每格附連結；沒有實跑。aos 的現況照 N-59 第 4 件、N-60、`proto8/bin/aos-exec` 與 `proto8/tests/test_exec_env.py`。C++ 版（impls）這台沒有，工作量照 code map 推估。

<!-- wf-nav -->
## 分檔

| 分檔 | 涵蓋 |
|---|---|
| [01-各家做法](dotenv-格式比較/01-各家做法.md) | docker、compose、systemd、python-dotenv、node dotenv、dotenvx、direnv、bash、envdir 一族、POSIX `env`、GitHub Actions 的比較表，與看得出的六件事 |
| [02-aos現況與工作量](dotenv-格式比較/02-aos現況與工作量.md) | aos `.env` 收什麼、判壞什麼、安靜照字面的坑；三項各自的形狀、bin／C++ 改幾行、幾個測試、動哪些條文、風險 |
| [03-替代方案與建議](dotenv-格式比較/03-替代方案與建議.md) | 不改 `.env` 的做法（入口前接 `env -u`、envdir 空檔、JSON `.env` key）、最小可行建議、全都不做的後果 |
| [04-拿掉env改用envdir](dotenv-格式比較/04-拿掉env改用envdir.md) | 使用者追加的選項：拿掉 `.env`、改在 argv 鏈上接 s6-envdir（全拿掉／只留 JSON `.env` key／現況）；逐條對照會少掉的規則、多出的依賴與好處、刪除工作量、跟 (a) 的關係 |

## 一句話的底

- **各家**：沒有標準 `.env`。dotenv 那一族有引號、跳脫、多行，但**都沒有「拿掉變數」**；拿掉變數的是 envdir（空檔）、systemd（另一個設定 `UnsetEnvironment=`）、bash／direnv（本來就是 shell）。只有名字的一行，docker＝從外面帶進來、python-dotenv＝不設、systemd＝跳過。
- **工作量**：拿掉變數**小**（約 3～4 行、2～3 個測試）；多行**中**（heredoc 形狀約 12～15 行，或靠引號）；引號**大**（要真的相容就得換一支解析器，跳脫字元沒有底）。
- **建議**（使用者定）：只做一項就做拿掉變數，先只做「JSON `.env` key 的值 `null`＝拿掉」——不動 `.env` 檔文法、補的是現在完全做不到的事。多行今天已能用 JSON `.env` key 寫；引號照字面，跟 C-56「寫什麼就做什麼」一致，不建議加。
- **現況最大的坑**跟補不補無關：從別家抄來的 `X="a b"`、`X=a # 註解` 不會報錯，會靜靜拿到含引號、含註解的值（[02 § 1](dotenv-格式比較/02-aos現況與工作量.md)）。
- **拿掉 `.env`、改接 s6-envdir**（使用者追加）：最 KISS、順便解了 unset 與多行、每個祕密一個檔好分權限；但**丟掉 `${}` 接 PATH 與「`.env` 改 `AOS_ENTRY`」兩件 10-21 明確要過的事**，envdir 補不回來。折衷是只拿掉 `.env` 檔、留 JSON `.env` key（這兩件都還在）。刪比加大：拆 10-21 四輪長出來的規則、兩版再逐案比（[04](dotenv-格式比較/04-拿掉env改用envdir.md)）。跟 (a) 不衝突——envdir 是使用者自己寫在 argv 裡的。
