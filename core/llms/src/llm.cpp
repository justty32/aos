#include <aos/llms.hpp>

#include "llms_internal.hpp"

#include <utility>

namespace aos::llms {

const char *to_string(ErrorKind kind) noexcept {
    switch (kind) {
        case ErrorKind::None: return "none";
        case ErrorKind::InvalidArgument: return "invalid argument";
        case ErrorKind::Capability: return "capability";
        case ErrorKind::Transport: return "transport";
        case ErrorKind::Http: return "http";
        case ErrorKind::Json: return "json";
        case ErrorKind::Response: return "response";
        case ErrorKind::Io: return "io";
    }
    return "unknown";
}

const char *to_string(Capability capability) noexcept {
    switch (capability) {
        case Capability::Tools: return "tools";
        case Capability::ToolChoice: return "tool_choice";
        case Capability::ParallelTools: return "parallel_tools";
        case Capability::Vision: return "vision";
        case Capability::Reasoning: return "reasoning";
        case Capability::JsonSchema: return "json_schema";
        case Capability::Caching: return "caching";
    }
    return "unknown";
}

std::optional<bool> Caps::get(Capability capability) const noexcept {
    switch (capability) {
        case Capability::Tools: return tools;
        case Capability::ToolChoice: return tool_choice;
        case Capability::ParallelTools: return parallel_tools;
        case Capability::Vision: return vision;
        case Capability::Reasoning: return reasoning;
        case Capability::JsonSchema: return json_schema;
        case Capability::Caching: return caching;
    }
    return std::nullopt;
}

LLM::LLM(std::string model, std::string url,
         std::optional<std::string> key, Params params, long timeout_ms,
         Caps caps_override, Transport transport,
         StreamTransport stream_transport)
    : impl_(std::make_shared<Impl>()) {
    impl_->model = std::move(model);
    impl_->params = std::move(params);
    impl_->caps_override = std::move(caps_override);
    impl_->base_url = normalize_base_url(url);
    impl_->root_url = endpoint_root_url(url);
    impl_->key = resolve_key(key);
    impl_->timeout_ms = timeout_ms;
    const bool custom_transport = static_cast<bool>(transport);
    impl_->transport = custom_transport ? std::move(transport) : curl_transport;
    if (stream_transport) {
        impl_->stream_transport = std::move(stream_transport);
    } else if (custom_transport) {
        const Transport buffered = impl_->transport;
        impl_->stream_transport = [buffered](const HttpRequest &request,
                                             const StreamByteSink &sink) {
            HttpResponse response = buffered(request);
            if (response.error.empty() && response.status >= 200 &&
                response.status < 300 && !response.body.empty()) {
                sink(response.body);
                response.body.clear();
            }
            return response;
        };
    } else {
        impl_->stream_transport = curl_stream_transport;
    }
}

LLM::LLM(const LLM &) noexcept = default;
LLM::LLM(LLM &&) noexcept = default;
LLM &LLM::operator=(const LLM &) noexcept = default;
LLM &LLM::operator=(LLM &&) noexcept = default;
LLM::~LLM() = default;

std::string LLM::model() const { return impl_->model; }
void LLM::set_model(std::string model) { impl_->model = std::move(model); }
Params LLM::params() const { return impl_->params; }
void LLM::set_params(Params params) { impl_->params = std::move(params); }
std::string LLM::base_url() const { return impl_->base_url; }
std::string LLM::root_url() const { return impl_->root_url; }
std::string LLM::key() const { return impl_->key; }

Caps LLM::caps() const { return cached_caps(*impl_); }

std::optional<bool> LLM::supports(Capability capability) const {
    return caps().get(capability);
}

std::vector<ModelInfo> LLM::models() const {
    return cached_models(*impl_);
}

std::optional<ReplyError> LLM::check(bool has_images, bool has_tools,
                                     bool has_tool_choice) const {
    if (has_tool_choice && !has_tools) {
        return ReplyError{
            .kind = ErrorKind::InvalidArgument,
            .message = "給了 tool_choice，但這個 bot 沒有 tools，不會有任何效果"};
    }
    if (!has_images && !has_tools) return std::nullopt;
    const Caps available = caps();
    if (has_images && available.vision == false) {
        return ReplyError{.kind = ErrorKind::Capability,
                          .message = "模型 " + impl_->model +
                              " 不支援圖片輸入"};
    }
    if (has_tools && available.tools == false) {
        return ReplyError{.kind = ErrorKind::Capability,
                          .message = "模型 " + impl_->model +
                              " 不支援 tool calling"};
    }
    if (has_tool_choice && available.tool_choice == false) {
        return ReplyError{.kind = ErrorKind::Capability,
                          .message = "模型 " + impl_->model +
                              " 不支援指定 tool_choice"};
    }
    return std::nullopt;
}

void LLM::clear_caps_cache() { clear_cached_caps(); }

}  // namespace aos::llms
