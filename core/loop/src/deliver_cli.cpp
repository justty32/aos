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

void usage(FILE *stream, const char *program) {
    std::fprintf(stream,
                 "用法：%s [folder] <inst.json>\n"
                 "      %s [folder] -- <argv...>\n"
                 "\n"
                 "  [folder]    要投遞的世界資料夾；省略時從目前位置尋找\n"
                 "  <inst.json> 讀取既有的指令 JSON 並投遞\n"
                 "  --          把後續參數當成新指令的 argv\n"
                 "  -h, --help  顯示這份完整用法\n",
                 program, program);
}

/* `--` 之後是要投遞的 argv，那裡的 --help 屬於被投遞的指令，不是問我們。 */
bool has_help(int argc, char *argv[]) {
    if (argv == nullptr) return false;
    for (int index = 1; index < argc; ++index) {
        if (argv[index] == nullptr) continue;
        if (std::strcmp(argv[index], "--") == 0) return false;
        if (std::strcmp(argv[index], "--help") == 0 ||
            std::strcmp(argv[index], "-h") == 0) {
            return true;
        }
    }
    return false;
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
    if (has_help(argc, argv)) {
        usage(stdout, program);
        return 0;
    }
    if (argv == nullptr || argc < 2 || argv[1] == nullptr) {
        usage(stderr, program);
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
        usage(stderr, program);
        return 2;
    }

    aos::wire::Inst inst;
    if (std::strcmp(argv[argument], "--") == 0) {
        if (argument + 1 >= argc) {
            usage(stderr, program);
            return 2;
        }
        std::vector<std::string> command;
        command.reserve(static_cast<std::size_t>(argc - argument - 1));
        for (int index = argument + 1; index < argc; ++index) {
            if (argv[index] == nullptr) {
                usage(stderr, program);
                return 2;
            }
            command.emplace_back(argv[index]);
        }
        inst = aos::loop::inst_from_argv(command);
    } else {
        if (argc != argument + 1) {
            usage(stderr, program);
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
