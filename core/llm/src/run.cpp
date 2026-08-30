#include <aos/llm.hpp>

#include <cstdio>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

int usage(const char *program) {
    std::fprintf(stderr,
                 "usage: %s [--system TEXT] [--messages FILE] [--url U] "
                 "[--model M] [--timeout-ms N]\n"
                 "\n"
                 "  stdin             整段作為 user prompt\n"
                 "  --messages FILE   直接送出檔案內的 OpenAI messages 陣列\n"
                 "  --url U           預設 $AOS_LLM_URL 或 http://localhost:1234/v1\n"
                 "  --model M         預設 $AOS_LLM_MODEL 或 qwen/qwen3.5-9b\n"
                 "  --timeout-ms N    預設 120000\n",
                 program);
    return 2;
}

std::string read_stream(std::istream &input) {
    return {std::istreambuf_iterator<char>(input),
            std::istreambuf_iterator<char>()};
}

std::vector<aos::llm::Message> read_messages(
    const aos::llm::CommandOptions &command) {
    if (command.messages_file) {
        std::ifstream input(*command.messages_file, std::ios::binary);
        if (!input) {
            throw std::runtime_error("無法開啟 messages 檔案: " +
                                     *command.messages_file);
        }
        return aos::llm::parse_messages_json(read_stream(input));
    }

    std::vector<aos::llm::Message> messages;
    if (command.system) messages.push_back({"system", *command.system});
    messages.push_back({"user", read_stream(std::cin)});
    return messages;
}

}  // namespace

extern "C" int aos_llm_cli_main(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
        ? argv[0] : "aos llm";
    if (argc < 1 || argv == nullptr) return usage(program);

    try {
        std::vector<std::string> arguments;
        arguments.reserve(static_cast<std::size_t>(argc - 1));
        for (int index = 1; index < argc; ++index) {
            if (argv[index] == nullptr) return usage(program);
            arguments.emplace_back(argv[index]);
        }
        const aos::llm::CommandOptions command =
            aos::llm::parse_arguments(arguments);
        const std::string reply =
            aos::llm::complete(read_messages(command), command.completion);
        if (!reply.empty()) std::fwrite(reply.data(), 1, reply.size(), stdout);
        if (reply.empty() || reply.back() != '\n') std::fputc('\n', stdout);
        return 0;
    } catch (const std::invalid_argument &) {
        return usage(program);
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s: %s\n", program, error.what());
        return 1;
    }
}
