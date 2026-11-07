11-07 sol 審查 C 區：no-pid P5b、tick-time、json-argv J7、special-cases 四批寫進條文的部分，對使用者原話逐句核，找代定寫成已定、原話寫歪、改讀翻掉原句、沒做卻寫成現況、條文與程式不符，以及四批之間打架的。

# 03 條文：no-pid／tick／json-argv／special-cases（C 隊）

## 這區白話總結

四批條文的大方向都有使用者原話撐著，沒有哪一條把他的意思寫反。C-53 搬移逐字相同；旗標名、欄位名、`auto_restart`、找 daemon 的順序、`responded_at`、`ping` 這些「條文說有」的，程式裡都真的有。

真正要處理的是同一個毛病在四批裡重複出現：**使用者點了「推薦」那個選項，agent 就把推薦旁邊的判準、草稿裡的細則、頂層自己補的理由，一起當成他裁過的寫進條文**。最明顯的三處——special-cases 把「第 3 次升格」一題寫成四條全 repo 通用規矩、把「公開介面」多塞了「README 寫明的」；tick 的 `tick` key 形狀與擇一規則寫成已定；no-pid 的「照原設計」三個字被配上頂層推的理由寫成已定。

另外有一句 K 隊寫反的：hub 變數「設了但指不到照退路走」，使用者裁的是「當第 0 格、不改退路」，同一頁下兩行就寫著對的。還有一處把沒做的事寫成已實作（P-44 說 `aos-agent tools add` 也收 `--envs`，其實 `FlagUnknown`），一處已實作註跟程式對不上（N-67 ② 說信裡期限已是毫秒）。

最後是維護問題：N-17 判卡住疊了六層註、N-28 `_tick` 疊了四層、C-52 例外清單三批各數各的——內容沒錯，但讀的人要自己排時序。

## 最該先處理的 6 條

1. 跟原話不符：四種性質表 `:22` K3「設了但指不到照退路走」，使用者裁「當第 0 格、不改退路」——[02 第 1 條](03-條文-no-pid-tick-json-argv-special-cases/02-tick-time.md)。
2. 方向性代定：「照原設計」只有三個字，N-17 寫已定且理由是頂層推的；P7 拿 `ctl.json` 的 mtime 當刺激時間，跟使用者 11-02「從檔案判斷…不太好」有張力沒攤——[01 第 1 條](03-條文-no-pid-tick-json-argv-special-cases/01-no-pid-P5b.md)。
3. 方向性代定：`DaemonMissing` 兼「找到了但沒回信」，代號語意是使用者定的 C-54——[01 第 2 條](03-條文-no-pid-tick-json-argv-special-cases/01-no-pid-P5b.md)。
4. 方向性代定：升格門檻寫成四條全 repo 規矩、「公開介面」多塞「README 寫明的」——[04 第 1、2 條](03-條文-no-pid-tick-json-argv-special-cases/04-special-cases.md)。
5. 錯誤行為：P-44 寫 `aos-agent tools add` 也收 `--env-file`／`--envs` 已實作，程式是 `FlagUnknown`——[03 第 1 條](03-條文-no-pid-tick-json-argv-special-cases/03-json-argv-J7.md)。
6. 跟原話不符：N-67 ② 標「跨樹信的毫秒 deadline 已實作」，T4 代定不改格式、信裡仍是秒或 ISO——[02 第 2 條](03-條文-no-pid-tick-json-argv-special-cases/02-tick-time.md)。

要使用者裁的（擺了選項）：上面 2、3、4、6，加 tick 的 `interval_ms` 明寫 1000 不往下傳（02 第 4 條）、`--env-file` 存內容還是存路徑（03 第 2 條）。其餘都是可直接修的字面或雜活。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../../STRUCTURE.md) 按 `##` 拆開；no-pid、tick 的「已核對沒問題的」在各自的續檔，json-argv、special-cases 的在 06。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-no-pid-P5b](03-條文-no-pid-tick-json-argv-special-cases/01-no-pid-P5b.md)、[續](03-條文-no-pid-tick-json-argv-special-cases/01-no-pid-P5b-續.md) | 照原設計、`DaemonMissing`、N-17 改讀標籤與六層註（1～4）；ping 經判官過時、12 代定分類、兩處小的、已核對（續） |
| [02-tick-time](03-條文-no-pid-tick-json-argv-special-cases/02-tick-time.md)、[續](03-條文-no-pid-tick-json-argv-special-cases/02-tick-time-續.md) | K3 寫反、N-67 ② 毫秒、剛起誤報 warning、`interval_ms` 1000（1～4）；代定沒標、附錄1 殘句、搬家食譜、`null`、已核對（續） |
| [03-json-argv-J7](03-條文-no-pid-tick-json-argv-special-cases/03-json-argv-J7.md) | 「條文照實作修」對不對、aos-agent tools add 沒做、J3 代定寫成規範句、現行清單三份、子資料夾「已定」 |
| [04-special-cases](03-條文-no-pid-tick-json-argv-special-cases/04-special-cases.md) | 升格門檻擴寫、公開介面多塞 README、K1 讀者擴寫、K7 多一句 |
| [05-四批之間打架](03-條文-no-pid-tick-json-argv-special-cases/05-四批之間打架.md) | K3 對當第 0 格、現行清單三批各數、N-28 四層註、兩個「唯一」、擇一對只吃想吃的與 `null`、核過沒打架的 |
| [06-已核對](03-條文-no-pid-tick-json-argv-special-cases/06-已核對-json-argv與special-cases.md) | json-argv、special-cases 查過沒事的 |

## 覆蓋範圍與做不到的

- 四批的 commit diff 逐檔看過（`85d9bc6d5`、`a858fe1a0`／`2f4e2dc3`、`7a2adf2dc`、`c56e53751`／`5159cc1c3`／`407ee400e`／`3bada8a0a`），加上後來動到同一條的 commit（lift-to-norms、P6～P9、C-52 兩題、11-07 直寄）。N-65 本條沒審（B 隊）。
- 程式現況全部是讀原始碼核對，沒實跑、沒建 C++。
- 「照原設計」那次對話的選項原文 repo 裡沒有（只有 12 與 05 的轉述），無法逐字核對頂層攤了什麼。
- special-cases 從程式側的抽核 F 隊 [06](06-special-cases抽核.md) 已做，這裡只審條文字面對裁定，不重複。
