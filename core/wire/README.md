# core/wire — 指令／結果／state 的 JSON 序列化（純函式庫，無子命令）

← [core/README](../README.md)｜協定 [PROTOCOL](../../wf/workflows/dispatch/proto/PROTOCOL.md) §2–§4｜慣例 [conventions](../../wf/workflows/common/conventions.md)

## 這個小專案做什麼

唯一懂協定 JSON 形狀的一層：三組 struct（`Inst`＝§2、`Outcome`＝§3、`State`＋`RunningEntry`＝§4）
與 JSON 文字互轉。**公開 API 一律 string 進 string 出**，nlohmann::json 只出現在 `src/` 裡——
這樣 CMake 不需要 `PUBLIC_DEPS`／`PUBLIC_PACKAGES`，nlohmann 走 `aos_common_private` 就好，
外部消費者 `find_package(aos)` 也不會被要求先找 nlohmann。錯誤走 `optional` 回傳＋ `std::string &error`
側通道，不丟例外。不做 `$` 指示詞、不做 schema 以外的驗證。

## 公開標頭草稿：`include/aos/wire.hpp`

```cpp
#pragma once

#include <aos/export.h>

#include <cstdint>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace aos::wire {

/* PROTOCOL §2：inbox/*.json。stdin 欄位改名 stdin_data，避開 <cstdio> 的 stdin 巨集。 */
struct Inst {
    std::string id;                             // JSON 缺席時＝parse_inst 的 default_id
    std::vector<std::string> argv;              // 必填、非空
    std::map<std::string, std::string> env;
    std::string cwd;                            // 相對於 <folder>；空＝<folder>（由上層解讀）
    std::string stdin_data;                     // JSON 鍵："stdin"
    std::uint64_t timeout_ms = 0;
};

/* PROTOCOL §3：batch/<turn>/out/<id>.json。exit / signal 二擇一非 null。 */
struct Outcome {
    std::string id;
    std::optional<int> exit;
    std::optional<int> signal;
    std::string stdout_text;                    // JSON 鍵："stdout"
    std::string stderr_text;                    // JSON 鍵："stderr"
    std::string started_at;                     // ISO8601
    std::string ended_at;
};

/* PROTOCOL §4：state.json 的 running[] 一項。 */
struct RunningEntry {
    std::string id;
    std::string argv0;
    std::int64_t pid = -1;                      // JSON 鍵："pid"；-1 序列化成 null
    std::string started_at;
    std::string status;                         // "running" | "done"
    std::optional<int> exit;                    // done 且正常結束才有值
};

/* PROTOCOL §4：整份 state.json。agents 的 value 是 agents/<name>/status.json 的原始 JSON 文字，
 * 原樣鏡射、不解讀；序列化時以 JSON 物件內嵌（不是字串）。 */
struct State {
    std::uint64_t turn = 1;
    std::string phase = "idle";                 // "running" | "idle"
    std::vector<RunningEntry> running;
    std::map<std::string, std::string> agents;  // name → status.json 原文
};

/* 解析。失敗回 nullopt 並把原因放進 error（JSON 語法錯、缺必填、型別不符、argv 空）。
 * 未知鍵一律忽略。 */
AOS_API std::optional<Inst> parse_inst(const std::string &json_text,
                                       const std::string &default_id,
                                       std::string &error);
AOS_API std::optional<Outcome> parse_outcome(const std::string &json_text,
                                             std::string &error);
AOS_API std::optional<State> parse_state(const std::string &json_text,
                                         std::string &error);

/* 序列化。輸出兩空格縮排、鍵順序照協定範例、尾端換行。
 * State::agents 中解析失敗的 value 以 null 代替（不整份失敗）。 */
AOS_API std::string to_json_text(const Inst &inst);
AOS_API std::string to_json_text(const Outcome &outcome);
AOS_API std::string to_json_text(const State &state);

}  // namespace aos::wire
```

## 檔案切分（`src/`，單檔 ≤ 300 行）

三個型別各一檔，互不相識；共用的取值小工具放內部標頭。

| 檔案 | 職責 | 預估行數 |
|---|---|---|
| `src/json_io.hpp` | 內部標頭：`take_string(obj, key, out, err)`、`take_uint(...)`、`take_string_array(...)`、`take_string_map(...)`、`take_opt_int(...)`（缺席／null → nullopt），以及 `parse_object(text, obj, err)`（語法錯與非物件統一報錯）。全 `inline`，只給本專案 `.cpp` 用 | 110 |
| `src/inst.cpp` | `parse_inst`／`to_json_text(Inst)`：`argv` 必填非空、`id` 缺席取 `default_id`、`env` 值必須是字串、`timeout_ms` 非負整數；序列化省略空的 `env`/`cwd`/`stdin`，`timeout_ms` 一律寫 | 120 |
| `src/outcome.cpp` | `parse_outcome`／`to_json_text(Outcome)`：`exit`/`signal` 兩者皆 null 或皆非 null 都算錯；序列化時 nullopt → `null` | 90 |
| `src/state.cpp` | `parse_state`／`to_json_text(State)`：`running[]` 逐項；`agents` 解析時把每個 value `dump()` 回文字，序列化時 `json::parse` 每個 value（失敗填 `null`）；`pid == -1` → `null` | 150 |

CMake：`aos_add_subproject(wire SOURCES src/inst.cpp src/outcome.cpp src/state.cpp HEADERS include/aos/wire.hpp)`。
**不寫** `PUBLIC_DEPS`／`PRIVATE_DEPS`——nlohmann 從 `aos_common_private` 自動來。

## 已知不管

- 不驗 ISO8601 字串格式、不驗 `phase`/`status` 是否在枚舉內：字串照收照吐。
- `timeout_ms` 超過 `uint64` 或給負數 → 報型別錯；不 clamp。
- `agents` 的 value 若不是 JSON 物件（例如純數字）也照鏡射，不檢查四個欄位。
- `env` 的 key 含 `=` 或為空字串不在這層擋，交給 `core/exec` 的 `spawn_prep` 拒絕。
- 非 UTF-8 的 stdout／stderr 交給 nlohmann 的預設行為（會丟例外 → 我們在 `to_json_text` 內以 `error_handler_t::replace` 吞掉，換成 U+FFFD）。
- `parse_*` 對超大文件沒有大小上限。
