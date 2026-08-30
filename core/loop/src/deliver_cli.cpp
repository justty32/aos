#include <aos/loop.hpp>

#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace {

void usage(const char *program) {
    std::fprintf(stderr,
                 "usage: %s [folder] <inst.json>\n"
                 "       %s [folder] -- <argv...>\n",
                 program, program);
}

bool read_file(const std::string &path, std::string &text) {
    std::ifstream input(path, std::ios::binary);
    if (!input) return false;
    std::ostringstream buffer;
    buffer << input.rdbuf();
    text = buffer.str();
    return input.eof() || !input.fail();
}

std::string default_id(const std::string &path) {
    std::string name = std::filesystem::path(path).filename().string();
    if (name.ends_with(".json")) name.resize(name.size() - 5);
    return name;
}

}  // namespace

extern "C" int aos_deliver_cli_main(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos deliver";
    if (argv == nullptr || argc < 2 || argv[1] == nullptr) {
        usage(program);
        return 2;
    }

    std::string folder = aos::loop::current_folder();
    int argument = 1;
    std::error_code code;
    if (std::filesystem::is_directory(argv[1], code)) {
        folder = argv[1];
        argument = 2;
    }
    if (argument >= argc || argv[argument] == nullptr) {
        usage(program);
        return 2;
    }

    aos::wire::Inst inst;
    if (std::strcmp(argv[argument], "--") == 0) {
        if (argument + 1 >= argc) {
            usage(program);
            return 2;
        }
        std::vector<std::string> command;
        command.reserve(static_cast<std::size_t>(argc - argument - 1));
        for (int index = argument + 1; index < argc; ++index) {
            if (argv[index] == nullptr) {
                usage(program);
                return 2;
            }
            command.emplace_back(argv[index]);
        }
        inst = aos::loop::inst_from_argv(command);
    } else {
        if (argc != argument + 1) {
            usage(program);
            return 2;
        }
        std::string text;
        if (!read_file(argv[argument], text)) {
            std::fprintf(stderr, "%s: 無法讀取 %s\n", program,
                         argv[argument]);
            return 1;
        }
        std::string error;
        auto parsed = aos::wire::parse_inst(
            text, default_id(argv[argument]), error);
        if (!parsed) {
            std::fprintf(stderr, "%s: %s\n", program, error.c_str());
            return 1;
        }
        inst = std::move(*parsed);
    }

    std::string error;
    const auto layout = aos::loop::layout_of(folder);
    if (!aos::loop::deliver(layout, inst, error)) {
        std::fprintf(stderr, "%s: %s\n", program, error.c_str());
        return 1;
    }
    return 0;
}
