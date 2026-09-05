> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# 版面與交接協定（工作假設，**尚未定案**）
← [turn-based-folder](README.md)｜[ideas](../README.md)｜[WORKFLOWS](../../../WORKFLOWS.md)

> **規格已經抽走，現行正本是 [PROTOCOL](../../dispatch/proto/PROTOCOL.md)。** 版面、命名、
> 交接協定、路徑基準、版本、git 邊界一律以那份為準。下面這幾節留著是**脈絡**——記錄
> 這些形狀是怎麼想出來的、為什麼不是別的樣子。兩邊不一致時以規格為準。

以下是當初推導時的樣子。

## 命名標準（提前訂下來）

普通檔案的名字切成三段：

```text
<名字>.<副檔名>.<狀況>
   │       │        └── 第二個 .xxx：這個檔案／資料夾**目前的狀況**
   │       └────────── 第一個 .xxx：副檔名（.json 是 JSON、.d 是資料夾）
   └────────────────── 名字
```

- `inst.json` — 名叫 inst 的 JSON，沒有特別狀況（＝可以取用了）。
- `inst.json.temp` — 同一份東西，狀況是「還在生成，別碰」。
- `inst.json.runi` — 狀況是「已被取走、正在跑」。
- `inst.tempd` — 投遞匣**資料夾**（`.tempd` ＝ temp directory，是副檔名不是狀況）。
- `inst.d` — 一般的「名叫 inst 的資料夾」，留給「某顆 CPU 需要多份指令」那種用途。

> **狀況只用一個詞表示「還在生成」**：`.temp`（已定）。生產者寫到一半的投遞是
> `<pid>.json.temp`，彙整到一半的下一批是 `inst.json.temp`——兩者是同一種狀況，不必
> 有兩個字。整套狀況字彙目前只有兩個：**`.temp`（還在生成，別碰）**與
> **`.runi`（已取走、正在跑）**。

這條標準是為了 `.aos` 提前訂的，但它不限於 `.aos`；真的落地時應該升格進
[conventions](../../common/conventions.md)。

## 檔案版面

```text
<folder>/.aos/
    inst.json          ← process CPU（aos exec）待執行的批次。最核心，所以放最上層
    inst.json.temp     ← 彙整中的下一批（彙整完 rename 蓋掉 inst.json）
    inst.json.runi     ← 已取走、正在跑的那一批
    inst.tempd/        ← 投遞匣：一個生產者一個檔
        <pid>.json     ← 投遞完成，等彙整
        <pid>.json.temp ← 還在寫，彙整者要略過
    insts/
        llm.json       ← 其他 CPU 各一份（各自配同名的 .temp／.runi／.tempd）
        <name>.json
```

核心 CPU 的 instruction 直接放 `.aos/inst.json`，其餘一律收在 `.aos/insts/` 底下——
**「反正 inst 就是這樣的佈局」**。

## 交接協定：投遞、彙整、取件

```text
P1 ─▶ inst.tempd/<pid>.json.temp ─rename─▶ inst.tempd/<pid>.json ─┐
P2 ─▶ inst.tempd/<pid>.json.temp ─rename─▶ inst.tempd/<pid>.json ─┤
P3 ─▶ inst.tempd/<pid>.json.temp ─rename─▶ inst.tempd/<pid>.json ─┘
                            │
                            └彙整▶ inst.json.temp ─rename▶ inst.json ─rename▶ inst.json.runi
                                                                       （取件）
```

三步，每一步的交接都靠一次 `rename`：

- **投遞**：生產者先寫 `.aos/inst.tempd/<pid>.json.temp`，寫完 `rename` 成
  `<pid>.json`。**檔名帶 pid** 是必要的——`rename` 原子但「寫入」不是，共用檔名會互相
  蓋寫；**`.temp` 這個狀況**則讓彙整者不會讀到寫到一半的投遞。同目錄內的 `rename` 是
  原子的。
- **彙整**：彙整者把 `.aos/inst.tempd/` 底下所有**沒有 `.temp` 狀況**的投遞併成
  `.aos/inst.json.temp`，完成後 `rename` 蓋掉 `.aos/inst.json`。**這就是彙整這個功能的
  全部**——`.aos/next/` 那個另設匯流區的構想被它取代了。
- **取件**：`aos exec` 讀進來之後**立刻**把 `.aos/inst.json` `rename` 成
  `.aos/inst.json.runi`，然後才執行。這就是「先刪再跑」的實作——對 `inst.json` 那個
  位置來說它已經消失了，但現場被保留下來。
- **`.runi` 已存在時拒絕啟動**（已定）。它固定名稱，所以天生就是一把鎖：上一回合
  crash 留下的現場不會被靜靜蓋掉，也不會有兩支 `aos exec` 同時跑同一個資料夾。代價是
  crash 之後要人來處理，這是刻意的。
- **其他子模組（如 llm）最好也遵循同一套慣例，但不強迫**：`.aos/insts/llm.json` 配
  `llm.json.temp`、`llm.json.runi` 與 `llm.tempd/<pid>.json`。

## 一支命令，兩種節奏

```sh
aos exec <folder>            # 跑一回合
aos exec --loop 0 <folder>   # 持續讀、持續跑；數字是隔多久檢查一次
```

`--loop <間隔>` 就是 daemon：**daemon 不是另一支程式，是同一條命令的一個旗標**。
迴圈體就是 fetch–execute：彙整 → 取件 → 執行 → 再來一次。間隔的單位與 `0` 的確切
語意等實作時再定。

## 名詞與動詞

`inst` 是**名詞**（instruction 這個資料格式、`.aos/inst.json`）；`exec` 是**動詞**
（`aos exec` 這條子命令）。子命令改名不代表小專案要跟著改名。

> **2026-08-30 更新**：原文把 `core/inst` **這顆函式庫**也列在名詞側，**那個例子已被
> 使用者拍板推翻**——小專案改名 **`core/exec`**（見
> [core-layering](../core-layering.md)）。**原則沒有被推翻，是被講清楚了**：小專案照
> **它做的事**（動詞）命名，資料格式照**它是什麼**（名詞）命名。所以 `core/exec` 這個
> 專案裡裝著 `inst_t` 是自洽的，不是矛盾。

> 舊文裡「方案 A 的 `aos exec`」（一個吞下所有職責的巨型入口）**和這裡的 `aos exec`
> 合起來了**：`aos exec` 確實是唯一入口，但它只跑核心 CPU 的 `inst.json`，其他處理器
> 是它 `exec` 出去的子行程。理由見 [llm-cpu](../llm-cpu.md)。
