#include "internal.hpp"

#include <aos/exec.hpp>
#include <aos/slot.hpp>
#include <aos/tool.hpp>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <sstream>

namespace aos::agent {
namespace {

using Json = nlohmann::json;

std::string pi_cpu_name(const Engine &engine) {
    return engine.provider.empty() ? "deepseek" : engine.provider;
}

std::string argument_summary(const Json &args) {
    if (args.is_object() && args.contains("path")) {
        return args["path"].is_string() ? args["path"].get<std::string>()
                                        : args["path"].dump();
    }
    if (args.is_object() && args.contains("command")) {
        return args["command"].is_string()
                   ? args["command"].get<std::string>()
                   : args["command"].dump();
    }
    std::string summary = args.dump();
    if (summary.size() > 120) summary.resize(120);
    return summary;
}

std::string pi_prompt_field(std::string text) {
    std::replace(text.begin(), text.end(), '\n', ' ');
    std::replace(text.begin(), text.end(), '\r', ' ');
    return text;
}

std::vector<aos::tool::Contact>
pi_prompt_contacts(const std::filesystem::path &folder) {
    std::vector<aos::tool::Contact> contacts = aos::tool::read_contacts(folder);
    const bool has_user = std::any_of(
        contacts.begin(), contacts.end(),
        [](const aos::tool::Contact &contact) { return contact.name == "~"; });
    if (!has_user) {
        aos::tool::Contact user = aos::tool::user_contact();
        if (!user.folder.empty()) contacts.insert(contacts.begin(), user);
    }
    return contacts;
}

std::string pi_system_prompt(const detail::Paths &paths, std::string_view name,
                             std::uint64_t turn) {
    std::ostringstream prompt;
    prompt
        << "你是一個名叫 " << name
        << " 的 agent，活在一個以回合推進的資料夾世界裡。現在是第 " << turn
        << " 回合。\n"
           "你的工作目錄就是這個世界資料夾，你可以直接用你自己的工具讀寫這裡的"
           "檔案。\n"
           "不要去動 .aos/ 這個資料夾，那是系統用的。\n\n"
           "人格：\n"
        << detail::read_text(paths.persona);
    const std::vector<aos::tool::Contact> contacts =
        pi_prompt_contacts(paths.folder);
    if (contacts.empty()) return prompt.str();
    prompt << "\n\n你可以聯絡這些人：\n";
    for (const aos::tool::Contact &contact : contacts) {
        prompt << "- " << pi_prompt_field(contact.name) << " —";
        if (!contact.note.empty()) {
            prompt << ' ' << pi_prompt_field(contact.note);
        }
        prompt << "（" << pi_prompt_field(contact.folder) << "）\n";
    }
    prompt
        << "要寄訊息給他們，在世界資料夾裡執行：aos say --to <名字> \"<訊息>\"";
    return prompt.str();
}

PiRun run_pi(const detail::Paths &paths, std::string_view name,
             std::uint64_t turn, const Engine &engine,
             std::string_view prompt) {
    const char *configured = std::getenv("AOS_PI_BIN");
    const std::string executable = configured == nullptr ? "pi" : configured;
    aos::exec::Spawn spawn;
    spawn.argv = {executable,
                  "-p",
                  "--mode",
                  "json",
                  "--no-context-files",
                  "--no-skills",
                  "--no-prompt-templates",
                  "--no-extensions",
                  "--thinking",
                  "off",
                  "--session-id",
                  engine.session_id,
                  "--provider",
                  engine.provider,
                  "--model",
                  engine.model,
                  "--append-system-prompt",
                  pi_system_prompt(paths, name, turn)};
    spawn.cwd = paths.folder.string();
    spawn.stdin_data = prompt;
    spawn.timeout_ms = 600000;

    std::vector<aos::exec::Running> running = aos::exec::start_all({spawn});
    const std::vector<aos::exec::Result> results =
        aos::exec::wait_all(running);
    PiRun run = parse_pi_stream(results.front().stdout_text);
    run.stderr_text = results.front().stderr_text;
    if (!results.front().error.empty()) {
        if (!run.stderr_text.empty()) run.stderr_text.push_back('\n');
        run.stderr_text += results.front().error;
    }
    if (!results.front().error.empty() || results.front().signal != 0) {
        run.exit_code = results.front().signal != 0
                            ? 128 + results.front().signal
                            : 1;
    } else {
        run.exit_code = results.front().exit;
    }
    return run;
}

std::string joined(const std::vector<std::string> &items) {
    std::string result;
    for (const std::string &item : items) {
        if (!result.empty()) result += ", ";
        result += item;
    }
    return result;
}

std::string failure_detail(std::string text) {
    if (text.size() > 500) text.resize(500);
    std::replace(text.begin(), text.end(), '\n', ' ');
    std::replace(text.begin(), text.end(), '\r', ' ');
    return text;
}

std::string failure_first_line(std::string_view text) {
    const std::size_t newline = text.find_first_of("\r\n");
    std::string line(text.substr(0, newline));
    if (line.size() > 500) line.resize(500);
    return line;
}

std::string api_key_name(const Engine &engine) {
    std::string provider = engine.provider.empty() ? "deepseek" : engine.provider;
    std::transform(provider.begin(), provider.end(), provider.begin(),
                   [](unsigned char character) {
                       return static_cast<char>(std::toupper(character));
                   });
    return provider + "_API_KEY";
}

}  // namespace

PiRun parse_pi_stream(std::string_view jsonl) {
    PiRun run;
    std::istringstream input{std::string(jsonl)};
    std::string line;
    while (std::getline(input, line)) {
        try {
            const Json event = Json::parse(line);
            if (!event.is_object() || !event.contains("type") ||
                !event["type"].is_string()) {
                continue;
            }
            const std::string type = event["type"].get<std::string>();
            if (type == "turn_end" && event.contains("message") &&
                event["message"].is_object() &&
                event["message"].contains("content") &&
                event["message"]["content"].is_array()) {
                std::string reply;
                for (const Json &content : event["message"]["content"]) {
                    if (content.is_object() && content.value("type", "") == "text" &&
                        content.contains("text") && content["text"].is_string()) {
                        reply += content["text"].get<std::string>();
                    }
                }
                run.reply = std::move(reply);
            } else if (type == "tool_execution_start" &&
                       event.contains("toolName") &&
                       event["toolName"].is_string() &&
                       event.contains("args")) {
                run.tool_calls.push_back(
                    event["toolName"].get<std::string>() + " " +
                    argument_summary(event["args"]));
            }
        } catch (const Json::exception &) {
        }
    }
    return run;
}

namespace detail {

int step_pi(const Paths &paths, std::string_view name, std::uint64_t turn,
            const Engine &engine) {
    std::vector<std::filesystem::path> messages;
    for (const auto &entry : std::filesystem::directory_iterator(paths.say)) {
        if (entry.is_regular_file() && entry.path().extension() == ".md") {
            messages.push_back(entry.path());
        }
    }
    std::sort(messages.begin(), messages.end());
    if (messages.empty()) {
        write_status(paths, "idle", "等待訊息", turn);
        return 0;
    }

    // 先取到槽才吃訊息，逾時退回時 say/ 內容才不會消失。
    aos::llm::Slot slot;
    try {
        slot = aos::llm::acquire(pi_cpu_name(engine), llm_priority(engine),
                                 paths.folder);
    } catch (const aos::llm::WaitingLlm &) {
        write_status(paths, "waiting-llm", "等 llm 槽", turn);
        return 75;
    }

    std::vector<Message> history = read_history(paths.folder, name);
    std::string prompt;
    std::vector<Message> new_messages;
    new_messages.reserve(messages.size());
    bool first_message = true;
    for (const auto &message_path : messages) {
        const std::string content = read_text(message_path);
        new_messages.push_back({"user", content});
        if (!first_message) prompt += "\n\n";
        prompt += content;
        first_message = false;
    }

    const PiRun run = run_pi(paths, name, turn, engine, prompt);
    if (run.exit_code == 0) {
        for (std::size_t index = 0; index < new_messages.size(); ++index) {
            append_log(paths, turn, "user", new_messages[index].content);
            history.push_back(new_messages[index]);
            std::filesystem::remove(messages[index]);
        }
        append_log(paths, turn, "assistant", run.reply);
        history.push_back({"assistant", run.reply});
        write_history(paths, history);
        if (!run.tool_calls.empty()) {
            append_note(paths, turn,
                        "> pi 用了工具：" + joined(run.tool_calls));
        }
        write_status(paths, "idle", "等待訊息", turn);
        return 0;
    }

    std::string note = "> pi 失敗（exit=" +
                       std::to_string(run.exit_code) + "）：" +
                       failure_detail(run.stderr_text);
    if (run.stderr_text.find("No API key") != std::string::npos) {
        const std::string key = api_key_name(engine);
        note += "（pi 叫你跑 /login，但 aos 這條路走環境變數：請設定 " + key +
                "）";
    }
    append_note(paths, turn, note);
    write_status(paths, "error",
                 "pi 失敗（exit=" + std::to_string(run.exit_code) +
                     "）：" + failure_first_line(run.stderr_text),
                 turn);
    return 1;
}

}  // namespace detail
}  // namespace aos::agent
