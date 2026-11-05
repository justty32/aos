#include <aos/llm.hpp>
#include <aos/slot.hpp>

#include <algorithm>
#include <cstdio>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {

int usage(const char *program, FILE *stream = stderr, int result = 2) {
    std::fprintf(stream,
                 "usage: %s [--system TEXT] [--messages FILE] [--url U] "
                 "[--model M] [--timeout-ms N] [--engine CPU] "
                 "[--priority N] [--slots] [-h|--help]\n"
                 "\n"
                 "  stdin             the whole input is the user prompt\n"
                 "  --messages FILE   send the OpenAI messages array in FILE as is\n"
                 "  --url U           default $AOS_LLM_URL or http://localhost:1234/v1\n"
                 "  --model M         default $AOS_LLM_MODEL or qwen/qwen3.5-9b\n"
                 "  --timeout-ms N    default 120000\n"
                 "  --engine CPU      default $AOS_LLM_ENGINE or lmstudio\n"
                 "  --priority N      default $AOS_LLM_PRIORITY or 0\n"
                 "  --slots           show slot status per CPU without calling the endpoint\n"
                 "  -h, --help        show this usage\n",
                 program);
    return result;
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
            throw std::runtime_error("cannot open messages file: " +
                                     *command.messages_file);
        }
        return aos::llm::parse_messages_json(read_stream(input));
    }

    std::vector<aos::llm::Message> messages;
    if (command.system) messages.push_back({"system", *command.system});
    messages.push_back({"user", read_stream(std::cin)});
    return messages;
}

void print_slot_status() {
    const std::vector<aos::llm::SlotStatus> statuses =
        aos::llm::slot_status();
    if (statuses.empty()) {
        std::cout << "(no CPU has a concurrency limit; see "
                  << (aos::llm::aos_home() / "cpus.json").string()
                  << ")\n";
        return;
    }

    std::size_t cpu_width = 3;
    for (const aos::llm::SlotStatus &status : statuses) {
        cpu_width = std::max(cpu_width, status.cpu.size());
    }
    std::cout << std::left << std::setw(static_cast<int>(cpu_width)) << "CPU"
              << "  " << std::right << std::setw(4) << "HELD"
              << "  " << std::setw(7) << "WAITING"
              << "  " << std::setw(3) << "MAX"
              << "  " << std::setw(7) << "WAIT_MS" << '\n';
    for (const aos::llm::SlotStatus &status : statuses) {
        std::cout << std::left << std::setw(static_cast<int>(cpu_width))
                  << status.cpu << "  " << std::right << std::setw(4)
                  << status.held << "  " << std::setw(7) << status.waiting
                  << "  " << std::setw(3) << status.max_inflight << "  "
                  << std::setw(7) << status.wait_ms << '\n';
    }
}

}  // namespace

extern "C" int aos_llm_cli_main(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
        ? argv[0] : "aos llm";
    if (argc < 1 || argv == nullptr) return usage(program);

    for (int index = 1; index < argc; ++index) {
        if (argv[index] != nullptr &&
            (std::string_view(argv[index]) == "--help" ||
             std::string_view(argv[index]) == "-h")) {
            return usage(program, stdout, 0);
        }
    }

    try {
        std::vector<std::string> arguments;
        arguments.reserve(static_cast<std::size_t>(argc - 1));
        for (int index = 1; index < argc; ++index) {
            if (argv[index] == nullptr) return usage(program);
            arguments.emplace_back(argv[index]);
        }
        const aos::llm::CommandOptions command =
            aos::llm::parse_arguments(arguments);
        if (command.slots) {
            print_slot_status();
            return 0;
        }

        const std::vector<aos::llm::Message> messages =
            read_messages(command);
        aos::llm::Slot slot =
            aos::llm::acquire(command.engine, command.priority);
        (void)slot;
        std::string served_model;
        const std::string reply = aos::llm::complete(
            messages, command.completion, &served_model);
        if (!reply.empty()) std::fwrite(reply.data(), 1, reply.size(), stdout);
        if (reply.empty() || reply.back() != '\n') std::fputc('\n', stdout);
        if (!served_model.empty() &&
            served_model != command.completion.model) {
            std::fflush(stdout);
            std::fprintf(
                stderr,
                "aos llm: the endpoint answered with %s, not the requested %s; it does not serve that model (check with aos llm --slots or the endpoint's /v1/models)\n",
                served_model.c_str(), command.completion.model.c_str());
            return 1;
        }
        return 0;
    } catch (const std::invalid_argument &) {
        return usage(program);
    } catch (const aos::llm::WaitingLlm &) {
        std::fputs("waiting-llm\n", stderr);
        return 75;
    } catch (const std::exception &error) {
        std::fprintf(stderr, "%s: %s\n", program, error.what());
        return 1;
    }
}
