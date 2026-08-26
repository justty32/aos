#pragma once

/* 模型資訊與 LLM 值型別。 */

#include <aos/export.h>

#include <aos/llms/caps.hpp>
#include <aos/llms/transport.hpp>

#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace aos::llms {

struct ModelInfo {
    std::string name;
    Caps caps;
};

class LLM {
public:
    struct Impl;

    AOS_API explicit LLM(std::string model = "deepseek-chat",
                         std::string url = "http://localhost:4000",
                         std::optional<std::string> key = std::nullopt,
                         Params params = {}, long timeout_ms = 60000,
                         Caps caps_override = {}, Transport transport = {},
                         StreamTransport stream_transport = {});
    AOS_API LLM(const LLM &) noexcept;
    AOS_API LLM(LLM &&) noexcept;
    AOS_API LLM &operator=(const LLM &) noexcept;
    AOS_API LLM &operator=(LLM &&) noexcept;
    AOS_API ~LLM();

    AOS_API std::string model() const;
    AOS_API void set_model(std::string model);
    AOS_API Params params() const;
    AOS_API void set_params(Params params);
    AOS_API std::string base_url() const;
    AOS_API std::string root_url() const;
    AOS_API std::string key() const;

    AOS_API Caps caps() const;
    AOS_API std::optional<bool> supports(Capability capability) const;
    AOS_API std::vector<ModelInfo> models() const;
    AOS_API std::optional<ReplyError> check(bool has_images, bool has_tools,
                                            bool has_tool_choice) const;

    AOS_API static void clear_caps_cache();

private:
    std::shared_ptr<Impl> impl_;
    friend struct detail_LLMAccess;
};

}  // namespace aos::llms
