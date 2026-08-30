#include "internal.hpp"

#include <aos/llm.hpp>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <charconv>
#include <cctype>
#include <cstdlib>
#include <stdexcept>

namespace aos::agent {
namespace {

std::uint64_t parse_turn(std::string_view text) {
    while (!text.empty() && std::isspace(static_cast<unsigned char>(text.back()))) {
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
    return std::filesystem::exists(path) ? parse_turn(detail::read_text(path)) : 0;
}

std::string clip_utf8(std::string text) {
    std::size_t bytes = 0;
    std::size_t characters = 0;
    while (bytes < text.size() && characters < 4000) {
        const unsigned char first = static_cast<unsigned char>(text[bytes]);
        std::size_t width = 1;
        if ((first & 0xe0U) == 0xc0U) width = 2;
        else if ((first & 0xf0U) == 0xe0U) width = 3;
        else if ((first & 0xf8U) == 0xf0U) width = 4;
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
    text.resize(bytes);
    return text;
}

std::string clipped(const nlohmann::json &result, const char *key) {
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

std::string tool_result(const PendingCall &call,
                        const nlohmann::json &result) {
    if (!result.contains("exit")) throw std::runtime_error("工具結果缺少 exit");
    return "$ " + call.tool + " " + call.args + "\nexit=" +
           result["exit"].dump() + "\nstdout:\n" + clipped(result, "stdout") +
           "\nstderr:\n" + clipped(result, "stderr");
}

std::string complete_locally(const std::vector<Message> &messages) {
    std::vector<aos::llm::Message> request;
    request.reserve(messages.size());
    for (const Message &message : messages) {
        request.push_back({message.role, message.content});
    }
    return aos::llm::complete(request, aos::llm::options_from_env());
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
            detail::step_pi(*paths, name, turn, engine);
            return 0;
        }

        std::vector<Message> history = read_history(paths->folder, name);
        Pending pending = read_pending(paths->folder, name);
        bool received_tools = false;
        if (!pending.calls.empty()) {
            const auto out = paths->aos / "batch" /
                             std::to_string(pending.turn + 1) / "out";
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
                const auto result = nlohmann::json::parse(
                    detail::read_text(out / (call.id + ".json")));
                const std::string content = tool_result(call, result);
                history.push_back({"tool", content});
                detail::append_log(*paths, turn, "tool", content);
            }
            detail::write_history(*paths, history);
            detail::write_pending(*paths, {});
            received_tools = true;
        }

        bool received_user = false;
        std::vector<std::filesystem::path> messages;
        for (const auto &entry : std::filesystem::directory_iterator(paths->say)) {
            if (entry.is_regular_file() && entry.path().extension() == ".md") {
                messages.push_back(entry.path());
            }
        }
        std::sort(messages.begin(), messages.end());
        for (const auto &message_path : messages) {
            const std::string content = detail::read_text(message_path);
            history.push_back({"user", content});
            detail::write_history(*paths, history);
            detail::append_log(*paths, turn, "user", content);
            std::filesystem::remove(message_path);
            received_user = true;
        }

        std::string next_status = "idle";
        std::string detail_text = "等待訊息";
        if (received_user || received_tools) {
            const std::vector<Tool> tools = read_tools(paths->folder, name);
            std::vector<Message> request;
            request.push_back(
                {"system", detail::system_prompt(*paths, name, turn, tools)});
            request.insert(request.end(), history.begin(), history.end());
            const std::string reply = completion ? completion(request)
                                                 : complete_locally(request);
            history.push_back({"assistant", reply});
            detail::write_history(*paths, history);
            detail::append_log(*paths, turn, "assistant", reply);

            std::string unknown;
            const auto call = extract_tool_call(reply, tools, &unknown);
            if (call) {
                const auto tool = std::find_if(
                    tools.begin(), tools.end(), [&](const Tool &candidate) {
                        return candidate.name == call->tool;
                    });
                const std::string id = "agent-" + std::string(name) +
                                       "-tool-" + std::to_string(turn) + "-0";
                const std::vector<std::string> argv =
                    expand_argv(tool->argv, call->args);
                detail::deliver(*paths, id, argv, true);
                detail::write_pending(
                    *paths, {turn, {{id, call->tool, call->args}}});
                detail::append_note(
                    *paths, "> 已投遞工具 " + id + ": " +
                                nlohmann::json(argv).dump() +
                                "，等下下回合的結果");
                next_status = "tool";
                detail_text = "等工具結果";
            } else if (!unknown.empty()) {
                detail::append_note(*paths,
                                    "> 未知的工具 " + unknown + "，已忽略");
            }
        }

        detail::write_status(*paths, next_status, detail_text, turn);
        return 0;
    } catch (const std::exception &exception) {
        if (error != nullptr) *error = exception.what();
        if (paths) {
            try {
                detail::write_status(*paths, "idle", one_line(exception.what()),
                                     turn);
            } catch (...) {
            }
        }
        return 1;
    }
}

}  // namespace aos::agent
