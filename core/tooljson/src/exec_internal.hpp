#pragma once

/* exec 配方解析（exec_type.cpp / exec_argv.cpp / exec_io.cpp /
   exec_limits.cpp）共用的內部宣告。 */

#include "tooljson_internal.hpp"

#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <string>
#include <string_view>
#include <vector>

namespace aos::tooljson::detail {

constexpr std::size_t kArgMaxBytes = 128 * 1024;

SpecState bad(std::string text, std::string &message);
std::vector<std::string> unknown_keys(
    const nlohmann::json &object,
    std::initializer_list<std::string_view> allowed);
bool integer_value(const nlohmann::json &value, std::int64_t &out);
bool finite_number(const nlohmann::json &value, double &out);

/* _extra.exec 與 _extra.argv：程式本身與各參數的 argv 綁定。 */
SpecState parse_exec_argv(const Spec::Impl *impl, ExecBody *body,
                          std::string &message);
/* _extra.stdin / stdout / stderr：三條標準串流的接法。 */
SpecState parse_exec_io(const Spec::Impl *impl, ExecBody *body,
                        std::string &message);
/* _extra.ok_exit / timeout / cwd / limits / source：跑起來的邊界條件。 */
SpecState parse_exec_limits(const Spec::Impl *impl, ExecBody *body,
                            std::string &message);

}  // namespace aos::tooljson::detail
