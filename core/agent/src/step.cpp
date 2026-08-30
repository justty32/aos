#include "internal.hpp"

#include <aos/llm.hpp>
#include <aos/slot.hpp>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <cctype>
#include <charconv>
#include <cstdlib>
#include <stdexcept>

namespace aos::agent {
namespace {

using Json = nlohmann::json;

std::uint64_t parse_turn(std::string_view text) {
    while (!text.empty() &&
           std::isspace(static_cast<unsigned char>(text.back()))) {
        text.remove_suffix(1);
    }
    std::uint64_t turn = 0;
    const auto [end, error] =
        std::from_chars(text.data(), text.data() + text.size(), turn);
    if (error != std::errc{} || end != text.data() + text.size()) {
        throw std::runtime_error("回合號格式錯誤");
    }
    return turn;
}

std::uint64_t current_turn(const detail::Paths &paths) {
    if (const char *turn = std::getenv("AOS_TURN")) return parse_turn(turn);
    const auto path = paths.aos / "turn";
    return std::filesystem::exists(path) ? parse_turn(detail::read_text(path))
                                         : 0;
}

struct ClippedText {
    std::string text;
    bool truncated = false;
};

ClippedText clip_utf8(std::string text) {
    std::size_t bytes = 0;
    std::size_t characters = 0;
    while (bytes < text.size() && characters < 4000) {
        const unsigned char first = static_cast<unsigned char>(text[bytes]);
        std::size_t width = 1;
        if ((first & 0xe0U) == 0xc0U)
            width = 2;
        else if ((first & 0xf0U) == 0xe0U)
            width = 3;
        else if ((first & 0xf8U) == 0xf0U)
            width = 4;
        if (bytes + width > text.size()) width = 1;
        for (std::size_t index = 1; index < width; ++index) {
            if ((static_cast<unsigned char>(text[bytes + index]) & 0xc0U) !=
                0x80U) {
                width = 1;
                break;
            }
        }
        bytes += width;
        ++characters;
    }
    const bool truncated = bytes < text.size();
    text.resize(bytes);
    return {std::move(text), truncated};
}

ClippedText clipped(const Json &result, const char *key) {
    if (!result.contains(key) || !result[key].is_string()) {
        throw std::runtime_error(std::string("工具結果缺少 ") + key);
    }
    return clip_utf8(result[key].get<std::string>());
}

std::string one_line(std::string text) {
    std::replace(text.begin(), text.end(), '\n', ' ');
    std::replace(text.begin(), text.end(), '\r', ' ');
    return text;
}

Json pending_args(const PendingCall &call) {
    try {
        return Json::parse(call.args_json);
    } catch (const Json::exception &) {
        return nullptr;
    }
}

std::string execution_tool_result(const PendingCall &call, const Json &result) {
    if (!result.contains("exit")) throw std::runtime_error("工具結果缺少 exit");
    if (!result.contains("signal")) {
        throw std::runtime_error("工具結果缺少 signal");
    }
    const ClippedText stdout_text = clipped(result, "stdout");
    const ClippedText stderr_text = clipped(result, "stderr");
    Json result_body = {{"exit", result["exit"]},
                        {"signal", result["signal"]},
                        {"stdout", stdout_text.text},
                        {"stderr", stderr_text.text}};
    if (stdout_text.truncated || stderr_text.truncated) {
        result_body["truncated"] = true;
    }

    const bool signaled = !result["signal"].is_null();
    if (signaled && !result["signal"].is_number_integer()) {
        throw std::runtime_error("工具結果的 signal 必須是數字或 null");
    }
    if (!signaled && !result["exit"].is_number_integer()) {
        throw std::runtime_error("工具結果的 exit 必須是數字");
    }
    const int signal = signaled ? result["signal"].get<int>() : 0;
    const int exit_code = !signaled ? result["exit"].get<int>() : 0;
    const bool ok = !signaled && exit_code == 0;
    Json content = {{"call_id", call.id},
                    {"tool", call.tool},
                    {"args", pending_args(call)},
                    {"ok", ok},
                    {"result", std::move(result_body)}};
    if (!ok) {
        std::string type;
        std::string message;
        bool retryable = false;
        if (signal == 9) {
            type = "timeout";
            message = "工具逾時被殺";
            retryable = true;
        } else if (signaled) {
            type = "signal";
            message = "工具收到 signal " + std::to_string(signal);
        } else if (exit_code == 126) {
            type = "not_executable";
            message = "工具不可執行";
        } else if (exit_code == 127) {
            type = "not_found";
            message = "找不到工具程式";
        } else {
            type = "exit_nonzero";
            message = "工具以 exit " + std::to_string(exit_code) + " 結束";
        }
        content["error"] = {
            {"type", type}, {"message", message}, {"retryable", retryable}};
    }
    return content.dump();
}

std::string_view trim(std::string_view text) {
    while (!text.empty() &&
           std::isspace(static_cast<unsigned char>(text.front()))) {
        text.remove_prefix(1);
    }
    while (!text.empty() &&
           std::isspace(static_cast<unsigned char>(text.back()))) {
        text.remove_suffix(1);
    }
    return text;
}

Json original_call_args(std::string_view reply) {
    std::vector<std::string_view> lines;
    while (true) {
        const std::size_t newline = reply.find('\n');
        lines.push_back(reply.substr(0, newline));
        if (newline == std::string_view::npos) break;
        reply.remove_prefix(newline + 1);
    }
    for (auto line = lines.rbegin(); line != lines.rend(); ++line) {
        const std::string_view candidate = trim(*line);
        if (candidate.size() < 2 || candidate.front() != '{' ||
            candidate.back() != '}') {
            continue;
        }
        try {
            const Json value = Json::parse(candidate);
            if (!value.is_object() || !value.contains("tool") ||
                !value["tool"].is_string()) {
                continue;
            }
            return value.contains("args") ? value["args"] : Json(nullptr);
        } catch (const Json::exception &) {
        }
    }
    return nullptr;
}

std::string call_error_result(std::string_view id, const ToolCallError &error,
                              const Json &args) {
    const Json content = {{"call_id", id},
                          {"tool", error.tool},
                          {"args", args},
                          {"ok", false},
                          {"result", nullptr},
                          {"error",
                           {{"type", error.type},
                            {"message", error.message},
                            {"retryable", false}}}};
    return content.dump();
}

std::string call_args_json(const ToolCall &call) {
    if (call.shape == "list") return Json(call.args).dump();
    if (call.shape == "string") return Json(call.args_text).dump();
    return "null";
}

std::string complete_locally(const std::vector<Message> &messages,
                             const Engine &engine) {
    std::vector<aos::llm::Message> request;
    request.reserve(messages.size());
    for (const Message &message : messages) {
        request.push_back({message.role, message.content});
    }
    aos::llm::Options options = aos::llm::options_from_env();
    if (!engine.model.empty()) options.model = engine.model;
    return aos::llm::complete(request, options);
}

std::string lmstudio_cpu_name(const Engine &engine) {
    if (!engine.provider.empty()) return engine.provider;
    const char *configured = std::getenv("AOS_LLM_ENGINE");
    return configured != nullptr && configured[0] != '\0' ? configured
                                                           : "lmstudio";
}

}  // namespace

int step(const std::filesystem::path &folder, std::string_view name,
         Completion completion, std::string *error) {
    std::optional<detail::Paths> paths;
    std::uint64_t turn = 0;
    try {
        paths = detail::paths_for(folder, name);
        turn = current_turn(*paths);
        detail::write_status(*paths, "thinking", "處理本回合", turn);

        const Engine engine = read_engine(paths->folder, name);
        if (engine.kind == "pi") {
            const int result = detail::step_pi(*paths, name, turn, engine);
            /* pi 的失敗原文寫在 status 與 log，順手也交給呼叫端，
             * 這樣 batch out 的 stderr 才不會是空白的一行。 */
            if (result != 0 && result != 75 && error != nullptr) {
                try {
                    *error = read_status(paths->folder, name).detail;
                } catch (const std::exception &) {
                }
            }
            return result;
        }

        std::vector<Message> history = read_history(paths->folder, name);
        bool received_tools = !history.empty() && history.back().role == "tool";
        Pending pending = read_pending(paths->folder, name);
        if (!pending.calls.empty()) {
            const auto out =
                paths->aos / "batch" / std::to_string(pending.turn + 1) / "out";
            const bool ready = std::all_of(
                pending.calls.begin(), pending.calls.end(),
                [&](const PendingCall &call) {
                    return std::filesystem::exists(out / (call.id + ".json"));
                });
            if (!ready) {
                detail::write_status(*paths, "tool", "等工具結果", turn);
                return 0;
            }
            for (const PendingCall &call : pending.calls) {
                const Json result =
                    Json::parse(detail::read_text(out / (call.id + ".json")));
                const std::string content = execution_tool_result(call, result);
                history.push_back({"tool", content});
                detail::append_log(*paths, turn, "tool", content);
            }
            detail::write_history(*paths, history);
            detail::write_pending(*paths, {});
            received_tools = true;
        }

        std::vector<std::filesystem::path> message_paths;
        for (const auto &entry :
             std::filesystem::directory_iterator(paths->say)) {
            if (entry.is_regular_file() && entry.path().extension() == ".md") {
                message_paths.push_back(entry.path());
            }
        }
        std::sort(message_paths.begin(), message_paths.end());

        const bool received_user = !message_paths.empty();
        const bool will_call = received_tools || received_user;
        std::optional<aos::llm::Slot> slot;
        if (will_call) {
            try {
                slot = aos::llm::acquire(lmstudio_cpu_name(engine),
                                         detail::llm_priority(engine),
                                         paths->folder);
            } catch (const aos::llm::WaitingLlm &) {
                detail::write_status(*paths, "waiting-llm", "等 llm 槽", turn);
                return 75;
            }
        }

        std::string next_status = "idle";
        std::string detail_text = "等待訊息";
        if (received_user || received_tools) {
            const std::vector<aos::tool::Spec> tools =
                read_tools(paths->folder, name);
            std::vector<Message> request;
            request.push_back(
                {"system", detail::system_prompt(*paths, name, turn, tools)});
            request.insert(request.end(), history.begin(), history.end());
            std::vector<Message> new_messages;
            new_messages.reserve(message_paths.size());
            for (const auto &message_path : message_paths) {
                new_messages.push_back(
                    {"user", detail::read_text(message_path)});
            }
            request.insert(request.end(), new_messages.begin(),
                           new_messages.end());
            const std::string reply =
                completion ? completion(request)
                           : complete_locally(request, engine);
            for (std::size_t index = 0; index < new_messages.size(); ++index) {
                history.push_back(new_messages[index]);
                detail::append_log(*paths, turn, "user",
                                   new_messages[index].content);
                std::filesystem::remove(message_paths[index]);
            }
            history.push_back({"assistant", reply});
            detail::write_history(*paths, history);
            detail::append_log(*paths, turn, "assistant", reply);

            const ToolCallResult extracted = extract_tool_call(reply, tools);
            const std::string id = "agent-" + std::string(name) + "-tool-" +
                                   std::to_string(turn) + "-0";
            if (extracted.call) {
                const auto spec =
                    std::find_if(tools.begin(), tools.end(),
                                 [&](const aos::tool::Spec &item) {
                                     return item.name == extracted.call->tool;
                                 });
                if (spec == tools.end()) {
                    throw std::runtime_error("已驗證的工具呼叫找不到登記");
                }
                const std::vector<std::string> argv =
                    expand_argv(*spec, *extracted.call);
                detail::deliver(
                    *paths, id, argv, spec->cwd.empty() ? "." : spec->cwd,
                    spec->timeout_ms == 0 ? 30000 : spec->timeout_ms);
                detail::write_pending(*paths,
                                      {turn,
                                       {{id, extracted.call->tool,
                                         call_args_json(*extracted.call)}}});
                detail::append_note(*paths, turn,
                                    "> 已投遞工具 " + id + ": " +
                                        Json(argv).dump() +
                                        "，等下下回合的結果");
                next_status = "tool";
                detail_text = "等工具結果";
            } else if (extracted.error) {
                const std::string content = call_error_result(
                    id, *extracted.error, original_call_args(reply));
                history.push_back({"tool", content});
                detail::write_history(*paths, history);
                detail::append_log(*paths, turn, "tool", content);
                detail::append_note(*paths, turn,
                                    "> 工具呼叫錯誤：" +
                                        extracted.error->message);
            }
        }

        detail::write_status(*paths, next_status, detail_text, turn);
        return 0;
    } catch (const std::exception &exception) {
        if (error != nullptr) *error = exception.what();
        if (paths) {
            const std::string detail_text = one_line(exception.what());
            try {
                detail::write_status(*paths, "error", detail_text, turn);
            } catch (...) {
            }
            try {
                std::string note = "> 第 " + std::to_string(turn) +
                                   " 回合失敗：" + detail_text;
                std::string lower = detail_text;
                std::transform(lower.begin(), lower.end(), lower.begin(),
                               [](unsigned char character) {
                                   return static_cast<char>(
                                       std::tolower(character));
                               });
                if (detail_text.find("連線失敗") != std::string::npos ||
                    lower.find("connect") != std::string::npos) {
                    note += "（請確認 LLM 端點 " +
                            aos::llm::options_from_env().url +
                            " 是不是活的，或用 AOS_LLM_URL 指到正確的位址）";
                }
                detail::append_note(*paths, turn, note);
            } catch (...) {
            }
        }
        return 1;
    }
}

}  // namespace aos::agent
