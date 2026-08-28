# inst 與序列化定案 — 規劃 spec

← [build-cycle](../README.md)｜[roadmap M0](../../roadmap.md)｜[verdicts](../../ideas/verdicts.md)

**閘門 ①**。只講**要做成什麼樣**與**怎樣算做完**；動哪些檔、分幾步是 `plan.md` 的事。

> 使用者已定的範圍（2026-08-28）：**先把 inst 和其序列化定下來，loop 是下一步**；
> 深度＝**收編現況＋裁 header**（§22＋B1 現在裁，格式一次凍結）；**序列化拷問不解禁**
> （數字精度／串流解析／攻擊面仍是 M5 存貨，本步只把現況寫成法）。

## 一句話

立起 `docs/SPEC.md`（唯一 normative 的殼），把 **inst 側**已成文的現況收編成條款，
並且**現在就裁掉 §22 與 B1**，讓 inst 的格式——含批 header——一次凍結。
**loop 側（命名標準、版面、交接協定、git 政策）一律出範圍**；header 只立法、不實作。

## 做完之後長什麼樣（結果狀態）

### 1. `docs/SPEC.md` 存在，開頭三段定地位

- **地位**：SPEC 是唯一 normative；parser／docs／餵 LLM 的 prompt 從它派生；與實作衝突
  時**以 SPEC 為準，實作視為 bug**（除非條款帶 planned 標記）。[verdicts](../../ideas/verdicts.md)
  是**判例索引**，SPEC 是**法典**（§30 原話）。
- **裁決如何進入 SPEC**：新裁決 → 記回 ideas ＋ verdicts → **同一 commit** 補條款；
  條款新增／改位階**要經使用者點頭**；編號**永不重用**，廢止標 `(deprecated)` 留原文。
- **三向標記規則**（漂移處理）：已裁且已實作＝直接寫；已裁未實作＝`(planned, 步驟名)`；
  **規格與實作矛盾且未拍板＝不入法**，列進文末「已知未決」附錄。

### 2. 分區骨架全開、條款只填 inst 側

六區的**區號與名稱**這次就定死（A 機器模型／B 命名與版面／C 指令格式／D 交接協定／
E 世界與 git／F 版本），B、D、E 只放一行「本區待收編（loop 步）」。條款形式：
`§A-1` 編號、位階用英文原字 `MUST`／`MUST NOT`／`SHOULD`／`MAY`、**每條一行「來源」**
（哪一輪拷問／哪份文件）。

### 3. inst 側的條款，逐條有家

| 條款 | 位階 | 來源 |
|---|---|---|
| 真正的指令是**批**；一回合＝一整批，整批驗證通過才執行任何一筆 | MUST | 已裁決／aos-folder 五 |
| **一回合內沒有資料流**：`$ref` 引不到同批前一筆的產物，所有鏈接跨回合 | MUST | §18 第九輪實測 |
| **嚴解析、鬆執行**：序列化嚴格（未知 key 拒絕）、執行故意鬆 | MUST | verdicts A 表 |
| 欄位表與型別、指示詞（`$env`／`$ref`／`$opt`）、驗證狀態表 | MUST | format.md（**搬家**） |
| **沒有任何上限**及其代價（深巢爆堆疊；指令檔等同可執行碼，只收信任來源） | 陳述＋MUST NOT（不可餵不可信輸入） | format.md |
| 沒有 `inst.json` ＝停留在本回合，退出碼 0 | MUST | aos-folder 五 |
| **批 header**：欄位 v1、放哪、誰讀誰寫 | MUST `(planned, loop 步實作)` | 本步裁決（§22＋B1） |
| **格式版本**：header 的 `version` 就是它；與版面版本（`.aos/version`）是兩件事 | MUST `(planned)` | B10／instruction §2 |

### 4. 搬家不複製（防止第四份真相）

`core/inst/docs/format.md` 的**欄位表與拒絕條件表搬進 SPEC**，format.md 保留敘事、
理由、範例，開頭聲明「normative 在 SPEC」。`docs/aos-folder.md` 這步**只在開頭加一行**
「回合語意與 instruction 格式的 normative 在 SPEC；版面與交接協定的收編在 loop 步」——
它主體是 loop 側，降級等下一步。**同一張表不得同時活在兩處。**

### 5. 入口指得到

`docs/README.md` 的表加 SPEC 一列；[roadmap](../../roadmap.md) 標記本階段完成。

## 動工前必須拍板的（先裁）——這次的正菜

1. **§30**：接受「SPEC 唯一 normative、衝突以 SPEC 為準」。做本步＝裁它，但要明講。
2. **§22 凍結的矽**：建議**接受**可證偽版本——exec 層永不長新機制，演化只發生在指令
   內容。直接推論：**`$ref` 的值域不擴到指令**（連結器不進 decode，instruction §3 那條
   路封死）、**exec 永不認識 header**。
3. **header 放哪**：exec 不認識 header ＋ 嚴解析不容未知 key ⇒ header **不能**塞進
   exec 要讀的同一份 JSON。建議 **sidecar 檔**（與 `inst.json` 同層、命名照現行標準，
   確切檔名在 SPEC 草擬時定）；由彙整層寫、loop 讀，exec 一行不改。備選：wrapper 物件
   讓 exec 學著跳過——但那就是動矽，與第 2 條裁決矛盾，不推薦。
4. **B1 欄位 v1**：`version`（格式版本）、批 id（去重用）、來源（祝福標記：經彙整 or
   直寫）、彙總狀態欄**位置**（欄位存在即可，寫入歸 loop 步）。環境指紋／manifest
   （§23）**留 v2**。
5. **三向標記規則**（上面 1.3 那條）：批准它成為 SPEC 的常備規則。

沒裁完也可以開始寫，寫到那條就停下來問（build-cycle 常備規則 3）。

## 驗收條件（可機械檢查）

1. `docs/SPEC.md` 存在；每條有 `§<區>-<號>`、位階關鍵字、一行來源；六區骨架齊。
2. 上表八條逐條能在 SPEC 找到編號（plan 收尾列對照表）。
3. 欄位表／拒絕條件表**只在 SPEC 有**；format.md 開頭有主從聲明、表格已移走。
4. aos-folder.md 開頭有那一行指向 SPEC 的聲明。
5. 全 repo grep：除 SPEC 外沒有第二份自稱 normative／唯一真源。
6. header 條款帶 `(planned)`；SPEC 沒有描述任何**不帶標記**的不存在行為。
7. 未拍板的矛盾（若寫作中浮出）都在「已知未決」附錄，不在條款裡。
8. `git diff --stat` 只有 `.md`（本步零 C++）。
9. 從 repo 根 `cmake --build --preset default && ctest --preset default` 全綠（鐵律）。

## 明確不做

| 不做 | 歸誰 |
|---|---|
| 命名標準／版面／交接協定／footprint／`.gitignore` 政策／`.aos/turn` 的**立法** | **loop 步**（B、D、E 區屆時收編） |
| header 的**實作**（彙整層產、loop 讀、去重） | loop 步及其後 |
| `deliver`／`status`／`recover`／`check`、修 gotchas D 表 bug | loop 步及其後 |
| 序列化拷問（數字精度、串流解析、攻擊面） | **M5 存貨，未解禁** |
| JSON Schema | `aos check` 那步 |
| 裁 §25／§26／§29 | 各自階段 |

**防線**：寫作中發現某條其實沒被裁過——不當場裁，進 plan 的「浮出的新問題」交使用者。

## 動工前讀

[verdicts](../../ideas/verdicts.md) A 表＋[keep](../../ideas/call-format/keep.md)（argv 陣列、
未知 key 拒絕**別動**）、[instruction](../../ideas/machine-shape/instruction.md) 全檔、
[format-gaps](../../ideas/call-format/format-gaps.md)、`core/inst/docs/format.md` 全文、
`docs/aos-folder.md` 五／七、[layout-and-spec](../../ideas/machine-shape/layout-and-spec.md) §12／§30。
