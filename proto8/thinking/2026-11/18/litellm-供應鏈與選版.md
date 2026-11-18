# litellm 供應鏈事故查證與選版：查到的事故、選 1.109.1 的理由、雜湊怎麼驗

← [litellm-proxy-接gpt帳號](litellm-proxy-接gpt帳號.md)｜[2026-11-18](README.md)

線 litellm-1118，11-18 上網查（來源附在下面）。

## 一、供應鏈事故（上網查的，附來源）

litellm 今年被下毒兩次，還有一串 proxy 的嚴重漏洞。

| 時間 | 出事版本 | 怎麼中的 | 做了什麼壞事 |
|---|---|---|---|
| 2026-03-24 | PyPI `1.82.7`、`1.82.8` | CI 裡沒釘版的 Trivy 被人換掉，偷到維護者的 PyPI 上傳權限，直接傳到 PyPI（GitHub 沒有對應的 tag） | 1.82.7 藏在 `proxy_server.py`；1.82.8 多一個 `litellm_init.pth`——**每次開 Python 都會跑，不用 import**。偷 SSH 金鑰、雲端憑證、`.env`、k8s、環境變數，加密後送到 `models.litellm.cloud`；在 `~/.config/sysmon/` 留後門 |
| 2026-10-21 | `1.107.0`（PyPI＋Docker `latest` 等標籤） | 5 月有人把內部服務的管理金鑰推上公開 repo、一直沒撤；10-10 攻擊者藉它拿到組織 owner 權限，10-21 用**官方自己的發布流水線**簽名發布 | `cook.pth`＋`sitecustomize.py`，一樣每次開 Python 就跑；偷憑證、載入遠端執行工具，資料送 `webhook.site`。**簽名與 Trusted Publishing 來源證明都是真的**，所以「有簽名」不等於乾淨 |

官方說法：3 月那次說 1.82.6 以前乾淨、1.83.0 起走新流水線；10 月那次說 1.107.0 以前都安全、建議釘 `1.106.2` 或事故前的明確版本。官方自己也承認 10 月的事故有些判斷後來改口，以「攻擊鏈」那篇為準；攻擊者 10-10～10-21 有 owner 權限，那段期間的其他版本官方沒有明說排除。

proxy 本身的嚴重漏洞（都已修，選版時要避開）：CVE-2026-42208 不用登入的 SQL injection（1.83.7 修，在 CISA 已被利用清單）、CVE-2026-49468 Host 標頭繞過驗證（1.84.0 修）、GHSA-7hp6 內部使用者升管理員再經 MCP 執行指令（1.100.4 等修）、GHSA-w4c7 企業版讀檔洩 master key（開源版沒開授權不受影響）、GHSA-2rwg Azure 參數偷憑證（11-12 公布，1.108.6／1.109.1 修；我們沒用 Azure）。另外官方 11 月開了「Private Registry」：最嚴重的修補先私下給企業客戶，公開版可能晚到。

來源：
- 官方 3 月：<https://docs.litellm.ai/blog/security-update-march-2026>
- 官方 10 月：<https://docs.litellm.ai/blog/security-incident-oct-21-2026>、<https://docs.litellm.ai/blog/security-incident-oct-21-2026-attack-chain>、<https://docs.litellm.ai/blog/security-changes-after-oct-21-2026>
- 官方安全文章總表：<https://docs.litellm.ai/blog/tags/security>；私有修補：<https://docs.litellm.ai/blog/litellm-private-registry-access>
- GitHub 公告：<https://github.com/BerriAI/litellm/security/advisories>（GHSA-7hp6-4w63-5g45、GHSA-w4c7-34wj-hqm8、GHSA-2rwg-2wh4-7c4f 各頁）
- 第三方分析：<https://futuresearch.ai/blog/litellm-pypi-supply-chain-attack/>、<https://snyk.io/articles/poisoned-security-scanner-backdooring-litellm>、<https://www.tenable.com/cve/CVE-2026-42208>、<https://www.sentinelone.com/vulnerability-database/cve-2026-49468/>

## 二、選哪一版、怎麼驗

選 **1.109.1**（PyPI 11-12 上架，到今天 6 天）：

- 在兩次下毒之後、上面列的公開漏洞都修了（含 11-12 才公布的 GHSA-2rwg）；GitHub 上有對應的 `v1.109.1` tag。
- 不選今天剛出的 1.110.0：下毒版本過去都是幾小時到一天內被發現，剛出的版本沒人替你踩過。
- `chatgpt/` 這個 provider 1.106 起就有；1.109.0 起另有「codex 自己帶登入穿過 proxy」的模式（見第三節）。

驗法（沒有一步是「相信它」）：

1. `uv pip compile --generate-hashes --exclude-newer 2026-11-13` 解出 `requirements.lock`：litellm 連相依共 117 個，每個釘版加 sha256；相依也只收 11-13 以前上架的，躲開這幾天的新版本。
2. `pip download --require-hashes --only-binary :all:`：只抓 wheel、不抓原始碼包（原始碼包安裝時會跑它的建置腳本）。
3. 自己寫一支小腳本，逐一把 117 個 wheel 算 sha256，**另外**向 PyPI 的 JSON API 對一次、確認沒被撤下（yanked）：117 個全對。litellm 那個是 `1c8b4dd6…bdaaf`。
4. 同一支腳本打開每個 wheel：找 `.pth`、`sitecustomize.py`、`usercustomize.py`、`cook.*`，再在 litellm 系的三個套件裡搜已知外送網域（`models.litellm.cloud`、`checkmarx.zone`、`webhook.site`）和後門字樣：**全部沒有**。
5. `pip install --no-index --find-links wheels --require-hashes`：離線、照雜湊裝。
6. 裝完 venv 裡只有一個 `.pth`：`_virtualenv.pth`（18 bytes，內容是 `import _virtualenv`，uv 建 venv 自己放的）。

限制要講清楚：PyPI 上的 litellm 1.109.1 **沒有** PEP 740 來源證明（查 PyPI integrity API 回 404），所以雜湊只證明「我裝的跟 PyPI 上的一樣」，不證明 PyPI 上那份沒被動過；10 月那次連官方簽名都是真的。第 4 步的特徵搜尋只擋已知手法。

