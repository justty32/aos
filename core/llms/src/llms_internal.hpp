#pragma once

#include <aos/llms.hpp>

#include <nlohmann/json.hpp>

#include <functional>
#include <string>
#include <utility>
#include <vector>

namespace aos::llms {

using json = nlohmann::ordered_json;

struct ToolSet::Impl {
    json schemas = json::array();
    DispatchMap dispatch;
};

struct detail_ToolSetAccess {
    static ToolSet make(std::shared_ptr<const ToolSet::Impl> impl) {
        return ToolSet(std::move(impl));
    }

    static const ToolSet::Impl &get(const ToolSet &tools) {
        return *tools.impl_;
    }
};

struct LLM::Impl {
    std::string model;
    Params params;
    Caps caps_override;
    std::string base_url;
    std::string root_url;
    std::string key;
    long timeout_ms = 60000;
    Transport transport;
    StreamTransport stream_transport;
};

struct detail_LLMAccess {
    static LLM::Impl &get(LLM &llm) { return *llm.impl_; }
    static const LLM::Impl &get(const LLM &llm) { return *llm.impl_; }
};

struct Reply::Impl {
    std::string buffer;
    std::string reasoning_buffer;
    std::vector<RawToolCall> raw_calls;
    ToolCallAccumulator accumulator;
    ReplySink sink;
    ReplyPartSink part_sink;
    std::function<void(Reply &)> drain_action;
    std::function<void()> close_action;
    std::function<void(const Reply &)> finish_action;
    bool done = false;
    bool started = false;
};

struct detail_ReplyAccess {
    static Reply make_error(ErrorKind kind, std::string message,
                            std::size_t checkpoint = 0);
    static Reply absorb(const json &response, std::size_t checkpoint,
                        std::function<void(const Reply &)> finish_action);
    static Reply stream(HttpRequest request, StreamTransport transport,
                        std::size_t checkpoint,
                        std::function<void(const Reply &)> finish_action);
};

HttpResponse curl_transport(const HttpRequest &request);
HttpResponse curl_stream_transport(const HttpRequest &request,
                                   const StreamByteSink &sink);
json params_value(const Params &params);
json content_value(const std::optional<std::string> &prompt,
                   const std::vector<std::string> &images);
json raw_calls_history(const std::string &content,
                       const std::vector<RawToolCall> &calls);

Caps cached_caps(const LLM::Impl &llm);
std::vector<ModelInfo> cached_models(const LLM::Impl &llm);
void clear_cached_caps();

}  // namespace aos::llms
