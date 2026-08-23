#include "run.hpp"

#include <aos/llms.hpp>

#include <cstdio>
#include <new>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>

namespace aos::llms {
namespace {

int usage(const char *program) {
    std::fprintf(stderr,
                 "usage: %s ask [--model M | --preset P] [--stream] [--system S] "
                 "[--url U] [--key K] <prompt>\n"
                 "       %s models [--url U] [--key K]\n"
                 "\n"
                 "  --url   OpenAI 相容端點，預設 http://localhost:4000\n"
                 "          （base url 或整條 /chat/completions 都收）\n"
                 "  --key   API key，沒給就吃 OPENAI_API_KEY\n"
                 "  --preset 自帶端點與參數，不能再配 --model/--url/--key\n",
                 program, program);
    return 2;
}

//: --url／--key 兩條子命令都要，抽出來共用。回 false 代表語法錯了。
bool take_endpoint(const std::string &argument, int &index, int argc,
                   char *argv[], std::optional<std::string> &url,
                   std::optional<std::string> &key) {
    std::optional<std::string> *target =
        argument == "--url" ? &url : argument == "--key" ? &key : nullptr;
    if (target == nullptr) return false;
    if (++index >= argc || argv[index] == nullptr) return false;
    if (target->has_value()) return false;
    *target = argv[index];
    return true;
}

LLM make_llm(const std::optional<std::string> &model,
             const std::optional<std::string> &url,
             const std::optional<std::string> &key) {
    return LLM(model.value_or("deepseek-chat"),
               url.value_or("http://localhost:4000"), key);
}

const char *cap_text(std::optional<bool> value) {
    if (!value) return "?";
    return *value ? "true" : "false";
}

int run_models(const char *program, int argc, char *argv[]) {
    std::optional<std::string> url;
    std::optional<std::string> key;
    for (int index = 2; index < argc; ++index) {
        if (argv[index] == nullptr) return usage(program);
        if (!take_endpoint(argv[index], index, argc, argv, url, key)) {
            return usage(program);
        }
    }

    LLM llm = make_llm(std::nullopt, url, key);
    const std::vector<ModelInfo> models = llm.models();
    if (models.empty()) {
        std::fprintf(stderr, "%s: 端點沒有回傳模型清單\n", program);
        return 1;
    }
    for (const ModelInfo &model : models) {
        std::printf(
            "%s\ttools=%s tool_choice=%s parallel_tools=%s vision=%s "
            "reasoning=%s json_schema=%s caching=%s\n",
            model.name.c_str(), cap_text(model.caps.tools),
            cap_text(model.caps.tool_choice),
            cap_text(model.caps.parallel_tools), cap_text(model.caps.vision),
            cap_text(model.caps.reasoning), cap_text(model.caps.json_schema),
            cap_text(model.caps.caching));
    }
    return 0;
}

int run_ask(const char *program, int argc, char *argv[]) {
    std::optional<std::string> model;
    std::optional<std::string> preset;
    std::optional<std::string> system;
    std::optional<std::string> url;
    std::optional<std::string> key;
    std::optional<std::string> prompt;
    bool stream = false;
    bool options = true;
    for (int index = 2; index < argc; ++index) {
        const std::string argument = argv[index];
        if (options && argument == "--") {
            options = false;
        } else if (options && argument == "--stream") {
            if (stream) return usage(program);
            stream = true;
        } else if (options && (argument == "--url" || argument == "--key")) {
            if (!take_endpoint(argument, index, argc, argv, url, key)) {
                return usage(program);
            }
        } else if (options &&
                   (argument == "--model" || argument == "--preset" ||
                    argument == "--system")) {
            if (++index >= argc || argv[index] == nullptr) {
                return usage(program);
            }
            std::optional<std::string> *target = argument == "--model"
                ? &model : argument == "--preset" ? &preset : &system;
            if (target->has_value()) return usage(program);
            *target = argv[index];
        } else if (options && argument.starts_with('-')) {
            return usage(program);
        } else if (prompt) {
            return usage(program);
        } else {
            prompt = argument;
        }
    }
    // preset 自帶端點與參數，再配 --model/--url/--key 只會讓「這次到底打到哪」
    // 變成要讀原始碼才知道的事，直接擋掉。
    if (!prompt || (preset && (model || url || key))) return usage(program);

    LLM llm = preset ? LLM() : make_llm(model, url, key);
    if (preset) {
        std::string message;
        const PresetState state = load_preset(*preset, llm, message);
        if (state != PresetState::Ok) {
            std::fprintf(stderr, "%s: %s\n", program, message.c_str());
            return 1;
        }
    }
    Bot bot(std::move(llm), std::move(system));
    Ask request;
    request.prompt = *prompt;
    request.stream = stream;
    Reply reply = bot.ask(request);
    if (!reply && !stream) {
        std::fprintf(stderr, "%s: %s: %s\n", program,
                     to_string(reply.err->kind), reply.err->message.c_str());
        return 1;
    }

    bool wrote = false;
    char last = '\0';
    if (stream) {
        reply.set_sink([&](std::string_view part) {
            if (part.empty()) return;
            std::fwrite(part.data(), 1, part.size(), stdout);
            std::fflush(stdout);
            wrote = true;
            last = part.back();
        });
    }
    const std::string &text = reply.all_text();
    if (!stream && !text.empty()) {
        std::fwrite(text.data(), 1, text.size(), stdout);
        wrote = true;
        last = text.back();
    }
    if (!reply) {
        if (wrote && last != '\n') std::fputc('\n', stdout);
        std::fprintf(stderr, "%s: %s: %s\n", program,
                     to_string(reply.err->kind), reply.err->message.c_str());
        return 1;
    }
    if (!wrote || last != '\n') std::fputc('\n', stdout);
    return 0;
}

}  // namespace

int cli_run(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
        ? argv[0] : "aos llms";
    if (argc < 2 || argv == nullptr || argv[1] == nullptr) {
        return usage(program);
    }
    try {
        const std::string operation = argv[1];
        if (operation == "models") return run_models(program, argc, argv);
        if (operation == "ask") return run_ask(program, argc, argv);
        return usage(program);
    } catch (const std::bad_alloc &) {
        std::fprintf(stderr, "%s: out of memory\n", program);
        return 1;
    } catch (const std::length_error &) {
        std::fprintf(stderr, "%s: out of memory\n", program);
        return 1;
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s: %s\n", program, error.what());
        return 1;
    }
}

}  // namespace aos::llms

extern "C" int aos_llms_cli_main(int argc, char *argv[]) {
    return aos::llms::cli_run(argc, argv);
}
