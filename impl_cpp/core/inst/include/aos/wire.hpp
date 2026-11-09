// wire.hpp：Inst 單子（argv／env／cwd／stdin／timeout_ms）的形狀與 JSON 解析／序列化（搬自 archive/aos-v1/core/wire，只留 Inst 那部分；Outcome／State 沒搬）。
#pragma once

#include <aos/export.h>

#include <cstdint>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace aos::wire {

/* PROTOCOL §2：inbox 底下每個 .json（搬來時改寫這句註解，避開 -Wcomment）。stdin 欄位改名 stdin_data，避開 <cstdio> 的 stdin 巨集。 */
struct Inst {
    std::string id;                             // JSON 缺席時＝parse_inst 的 default_id
    std::vector<std::string> argv;              // 必填、非空
    std::map<std::string, std::string> env;
    std::string cwd;                            // 相對於 <folder>；空＝<folder>（由上層解讀）
    std::string stdin_data;                     // JSON 鍵："stdin"
    std::uint64_t timeout_ms = 0;
};

/* 解析。失敗回 nullopt 並把原因放進 error（JSON 語法錯、缺必填、型別不符、argv 空）。
 * 未知鍵一律忽略。 */
AOS_API std::optional<Inst> parse_inst(const std::string &json_text,
                                       const std::string &default_id,
                                       std::string &error);

/* 序列化。輸出兩空格縮排、鍵順序照協定範例、尾端換行。 */
AOS_API std::string to_json_text(const Inst &inst);

}  // namespace aos::wire
