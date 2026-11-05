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
