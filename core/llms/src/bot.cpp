#include <aos/llms.hpp>

#include "llms_internal.hpp"

#include <new>
#include <stdexcept>
#include <utility>

namespace aos::llms {

struct Bot::Impl {
    LLM llm;
    std::optional<std::string> system;
    ToolSet tools;
    json history = json::array();

    Impl(LLM engine, std::optional<std::string> instruction,
         ToolSet tool_set)
        : llm(std::move(engine)),
          system(std::move(instruction)),
          tools(std::move(tool_set)) {}
};

namespace {

void rollback(const std::shared_ptr<Bot::Impl> &bot,
              std::size_t checkpoint) {
    if (bot->history.size() > checkpoint) {
        bot->history.erase(bot->history.begin() +
                               static_cast<json::difference_type>(checkpoint),
                           bot->history.end());
    }
}

Reply fail(const std::shared_ptr<Bot::Impl> &bot, std::size_t checkpoint,
           ErrorKind kind, std::string message) {
    rollback(bot, checkpoint);
    return detail_ReplyAccess::make_error(kind, std::move(message), checkpoint);
}

void extend_messages(json &messages, const json &extra,
                     const std::shared_ptr<Bot::Impl> &bot, bool remember) {
    for (const json &message : extra) {
        messages.push_back(message);
        if (remember) bot->history.push_back(message);
    }
}

json tool_result_messages(const std::string &text) {
    const json results = json::parse(text);
    if (!results.is_object()) {
        throw std::invalid_argument("tool_results_json 要是 JSON object");
    }
    json messages = json::array();
    for (auto it = results.begin(); it != results.end(); ++it) {
        if (!it.value().is_string()) {
            throw std::invalid_argument(
                "tool_results_json 的每個值都要是字串");
        }
        messages.push_back({{"role", "tool"},
                            {"tool_call_id", it.key()},
                            {"content", it.value()}});
    }
    return messages;
}

std::vector<RawToolCall> raw_from_reply(const Reply &reply) {
    std::vector<RawToolCall> result;
    result.reserve(reply.calls.size());
    for (const ToolCall &call : reply.calls) {
        result.push_back({.id = call.id,
                          .name = call.name,
                          .arguments = call.args_raw.value_or(call.args)});
    }
    return result;
}

std::string http_message(long status, const std::string &body) {
    std::string message = "HTTP " + std::to_string(status);
    if (!body.empty()) message += ": " + body;
    return message;
}

}  // namespace

Bot::Bot(LLM llm, std::optional<std::string> system, ToolSet tools)
    : impl_(std::make_shared<Impl>(std::move(llm), std::move(system),
                                   std::move(tools))) {}
Bot::Bot(Bot &&) noexcept = default;
Bot &Bot::operator=(Bot &&) noexcept = default;
Bot::~Bot() = default;

LLM &Bot::llm() noexcept { return impl_->llm; }
const LLM &Bot::llm() const noexcept { return impl_->llm; }
void Bot::set_llm(LLM llm) { impl_->llm = std::move(llm); }
std::optional<std::string> Bot::system() const { return impl_->system; }
void Bot::set_system(std::optional<std::string> system) {
    impl_->system = std::move(system);
}
void Bot::reset() { impl_->history = json::array(); }
std::string Bot::history_json() const { return impl_->history.dump(); }

std::vector<ToolCall> Bot::pending_calls() const {
    std::vector<ToolCall> result;
    if (impl_->history.empty()) return result;
    const json &last = impl_->history.back();
    const auto role = last.find("role");
    const auto calls = last.find("tool_calls");
    if (role == last.end() || !role->is_string() || *role != "assistant" ||
        calls == last.end() || !calls->is_array()) {
        return result;
    }
    for (const json &call : *calls) {
        const auto id = call.find("id");
        const auto function = call.find("function");
        if (id == call.end() || !id->is_string() ||
            function == call.end() || !function->is_object()) {
            continue;
        }
        const auto name = function->find("name");
        const auto arguments = function->find("arguments");
        if (name == function->end() || !name->is_string() ||
            arguments == function->end() || !arguments->is_string()) {
            continue;
        }
        result.push_back(tool_call_entry(
            {.id = id->get<std::string>(),
             .name = name->get<std::string>(),
             .arguments = arguments->get<std::string>()}));
    }
    return result;
}

Reply Bot::ask(const Ask &request) {
    const std::size_t checkpoint = impl_->history.size();
    ErrorKind stage = ErrorKind::InvalidArgument;
    try {
        const std::optional<ReplyError> check = impl_->llm.check(
            !request.images.empty(), !impl_->tools.empty(),
            request.tool_choice_json.has_value());
        if (check) {
            return fail(impl_, checkpoint, check->kind, check->message);
        }

        json messages = json::array();
        if (impl_->system && !impl_->system->empty()) {
            messages.push_back(
                {{"role", "system"}, {"content", *impl_->system}});
        }
        for (const json &message : impl_->history) {
            messages.push_back(message);
        }
        if (request.tool_results_json) {
            extend_messages(messages,
                            tool_result_messages(*request.tool_results_json),
                            impl_, request.remember);
        }
        if (request.prompt.has_value() || !request.images.empty()) {
            stage = ErrorKind::Io;
            const json user = {{"role", "user"},
                               {"content", content_value(request.prompt,
                                                         request.images)}};
            extend_messages(messages, json::array({user}), impl_,
                            request.remember);
        }

        stage = ErrorKind::InvalidArgument;
        const LLM::Impl &engine = detail_LLMAccess::get(impl_->llm);
        json body = params_value(engine.params);
        if (!impl_->tools.empty()) {
            body["tools"] = detail_ToolSetAccess::get(impl_->tools).schemas;
            if (request.tool_choice_json) {
                body["tool_choice"] = json::parse(*request.tool_choice_json);
            }
        }
        /* 這三個一定最後寫，Params.extra_json 無法蓋掉。 */
        body["model"] = engine.model;
        body["messages"] = messages;
        body["stream"] = false;

        HttpRequest http;
        http.url = engine.base_url + "/chat/completions";
        http.body = body.dump();
        http.headers = {"Authorization: Bearer " + engine.key,
                        "Content-Type: application/json"};
        http.timeout_ms = engine.timeout_ms;

        stage = ErrorKind::Transport;
        const HttpResponse response = engine.transport(http);
        if (!response.error.empty()) {
            return fail(impl_, checkpoint, ErrorKind::Transport,
                        response.error);
        }
        if (response.status == 0) {
            return fail(impl_, checkpoint, ErrorKind::Transport,
                        "HTTP transport 沒有回傳狀態碼");
        }
        if (response.status < 200 || response.status >= 300) {
            return fail(impl_, checkpoint, ErrorKind::Http,
                        http_message(response.status, response.body));
        }

        stage = ErrorKind::Json;
        const json parsed = json::parse(response.body);
        stage = ErrorKind::Response;
        const std::weak_ptr<Impl> weak = impl_;
        return detail_ReplyAccess::absorb(
            parsed, checkpoint,
            [weak, remember = request.remember, checkpoint](const Reply &reply) {
                const std::shared_ptr<Impl> bot = weak.lock();
                if (!bot || !remember) return;
                if (reply.text.empty() && reply.calls.empty() &&
                    !reply.finish_reason.has_value()) {
                    rollback(bot, checkpoint);
                    return;
                }
                bot->history.push_back(
                    raw_calls_history(reply.text, raw_from_reply(reply)));
            });
    } catch (const std::bad_alloc &) {
        rollback(impl_, checkpoint);
        throw;
    } catch (const json::parse_error &error) {
        return fail(impl_, checkpoint, stage, error.what());
    } catch (const std::exception &error) {
        return fail(impl_, checkpoint, stage, error.what());
    } catch (...) {
        return fail(impl_, checkpoint, stage, "發生未知錯誤");
    }
}

Reply Bot::ask(const std::string &prompt) {
    Ask request;
    request.prompt = prompt;
    return ask(request);
}

}  // namespace aos::llms
