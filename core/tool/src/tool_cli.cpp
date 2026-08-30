#include <aos/tool.hpp>

#include "cli_common.hpp"

#include <charconv>
#include <cstdlib>
#include <cstdio>
#include <exception>
#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <unistd.h>

namespace {

using aos::tool::Probe;
using aos::tool::Spec;

struct AddOptions {
    std::filesystem::path folder;
    std::optional<std::string> description;
    std::optional<std::string> args;
    std::optional<std::string> stdin_mode;
    std::optional<std::string> cwd;
    std::optional<std::uint64_t> timeout_ms;
    std::optional<std::string> predictability;
    std::optional<std::string> guarantee;
    std::optional<std::string> lifecycle;
    std::optional<std::string> state;
    std::optional<std::string> stage;
    std::optional<bool> network;
    bool replace = false;
    bool no_probe = false;
    bool probe_metadata = false;
};

int usage(const char *program, FILE *stream = stderr, int result = 2) {
    std::fprintf(
        stream,
        "usage: %s add <name> [選項...] -- <argv...>\n"
        "       %s ls [--folder F] [--json]\n"
        "       %s rm <name> [--folder F]\n"
        "\n"
        "  add                    登記工具；-- 後方是固定 argv\n"
        "    --folder F           指定世界資料夾\n"
        "    --description TEXT   手動指定工具表述\n"
        "    --args MODE          參數模式：list、string 或 none\n"
        "    --stdin MODE         stdin 模式：none 或 text\n"
        "    --cwd DIR            工具執行目錄\n"
        "    --timeout-ms N       工具逾時毫秒數\n"
        "    --predictability P   high、medium 或 low\n"
        "    --guarantee TEXT     保證說明\n"
        "    --lifecycle TEXT     生命週期說明\n"
        "    --state TEXT         狀態說明\n"
        "    --stage TEXT         階段說明\n"
        "    --network            宣告需要網路\n"
        "    --no-network         宣告不需要網路\n"
        "    --replace            覆寫同名登記\n"
        "    --no-probe           不探測工具表述\n"
        "    --probe metadata     探測失敗時再試 --metadata\n"
        "  ls                     列出工具；可加 --folder F、--json\n"
        "  rm                     移除工具；可加 --folder F\n"
        "\n"
        "  子命令真名是 ls 與 rm，不是 list 與 remove。\n"
        "  -h, --help             顯示這份用法\n",
        program, program, program);
    return result;
}

enum class ExecutableStatus { ready, missing, not_executable };

ExecutableStatus check_executable_path(const std::filesystem::path &path) {
    std::error_code error;
    if (!std::filesystem::is_regular_file(path, error) || error) {
        return ExecutableStatus::missing;
    }
    return ::access(path.c_str(), X_OK) == 0
               ? ExecutableStatus::ready
               : ExecutableStatus::not_executable;
}

ExecutableStatus check_executable(std::string_view argv0) {
    if (argv0.find('/') != std::string_view::npos) {
        return check_executable_path(std::filesystem::path(argv0));
    }

    const char *path_value = std::getenv("PATH");
    if (path_value == nullptr) return ExecutableStatus::missing;

    bool found_non_executable = false;
    const std::string_view paths(path_value);
    std::size_t begin = 0;
    while (begin <= paths.size()) {
        const std::size_t separator = paths.find(':', begin);
        const std::size_t end = separator == std::string_view::npos
                                    ? paths.size()
                                    : separator;
        const std::string_view entry = paths.substr(begin, end - begin);
        const std::filesystem::path candidate =
            entry.empty() ? std::filesystem::path(argv0)
                          : std::filesystem::path(entry) / argv0;
        const ExecutableStatus status = check_executable_path(candidate);
        if (status == ExecutableStatus::ready) return status;
        if (status == ExecutableStatus::not_executable) {
            found_non_executable = true;
        }
        if (separator == std::string_view::npos) break;
        begin = separator + 1;
    }
    return found_non_executable ? ExecutableStatus::not_executable
                                : ExecutableStatus::missing;
}

bool parse_uint64(std::string_view text, std::uint64_t &value) {
    if (text.empty()) return false;
    const char *begin = text.data();
    const char *end = begin + text.size();
    const auto parsed = std::from_chars(begin, end, value);
    return parsed.ec == std::errc{} && parsed.ptr == end;
}

bool parse_add_options(const std::vector<std::string> &words,
                       std::size_t &index, AddOptions &options) {
    while (index < words.size() && words[index] != "--") {
        const std::string &option = words[index++];
        if (option == "--replace") options.replace = true;
        else if (option == "--no-probe") options.no_probe = true;
        else if (option == "--network") options.network = true;
        else if (option == "--no-network") options.network = false;
        else {
            if (index >= words.size()) return false;
            const std::string value = words[index++];
            if (option == "--folder") options.folder = value;
            else if (option == "--description") options.description = value;
            else if (option == "--args" &&
                     (value == "list" || value == "string" || value == "none")) {
                options.args = value;
            } else if (option == "--stdin" &&
                       (value == "none" || value == "text")) {
                options.stdin_mode = value;
            } else if (option == "--cwd") options.cwd = value;
            else if (option == "--timeout-ms") {
                std::uint64_t timeout = 0;
                if (!parse_uint64(value, timeout)) return false;
                options.timeout_ms = timeout;
            } else if (option == "--predictability" &&
                       (value == "high" || value == "medium" || value == "low")) {
                options.predictability = value;
            } else if (option == "--guarantee") options.guarantee = value;
            else if (option == "--lifecycle") options.lifecycle = value;
            else if (option == "--state") options.state = value;
            else if (option == "--stage") options.stage = value;
            else if (option == "--probe" && value == "metadata") {
                options.probe_metadata = true;
            } else {
                return false;
            }
        }
    }
    if (index >= words.size() || words[index] != "--") return false;
    ++index;
    return true;
}

void merge_probe(Spec &spec, const Probe &probe) {
    if (!probe.ok) return;
    spec.description = probe.description;
    spec.source = probe.source;
    if (probe.source != "metainfo") return;
    spec.args = probe.spec.args;
    spec.stdin_mode = probe.spec.stdin_mode;
    spec.cwd = probe.spec.cwd;
    spec.timeout_ms = probe.spec.timeout_ms;
    spec.lifecycle = probe.spec.lifecycle;
    spec.state = probe.spec.state;
    spec.guarantee = probe.spec.guarantee;
    spec.interruptible = probe.spec.interruptible;
    spec.predictability = probe.spec.predictability;
    spec.stage = probe.spec.stage;
    spec.network = probe.spec.network;
    spec.network_declared = probe.spec.network_declared;
    spec.env_allow = probe.spec.env_allow;
}

void merge_cli(Spec &spec, const AddOptions &options) {
    if (options.description) spec.description = *options.description;
    if (options.args) spec.args = *options.args;
    if (options.stdin_mode) spec.stdin_mode = *options.stdin_mode;
    if (options.cwd) spec.cwd = *options.cwd;
    if (options.timeout_ms) spec.timeout_ms = *options.timeout_ms;
    if (options.predictability) spec.predictability = *options.predictability;
    if (options.guarantee) spec.guarantee = *options.guarantee;
    if (options.lifecycle) spec.lifecycle = *options.lifecycle;
    if (options.state) spec.state = *options.state;
    if (options.stage) spec.stage = *options.stage;
    if (options.network) {
        spec.network = *options.network;
        spec.network_declared = true;
    }
    if (options.description) spec.source = "manual";
}

int add(const char *program, const std::vector<std::string> &words) {
    if (words.size() < 3) return usage(program);
    const std::string name = words[1];
    aos::tool::validate_tool_name(name);
    std::size_t index = 2;
    AddOptions options;
    if (!parse_add_options(words, index, options) || index == words.size()) {
        return usage(program);
    }
    std::vector<std::string> command(words.begin() +
                                         static_cast<std::ptrdiff_t>(index),
                                     words.end());
    const ExecutableStatus executable = check_executable(command.front());
    if (executable == ExecutableStatus::missing) {
        std::fprintf(
            stderr,
            "aos tool: 找不到執行檔 %s；它不在 PATH 上，也不是一個可執行的檔案路徑\n",
            command.front().c_str());
        return 1;
    }
    if (executable == ExecutableStatus::not_executable) {
        std::fprintf(stderr, "aos tool: %s 不可執行（chmod +x ?）\n",
                     command.front().c_str());
        return 1;
    }
    const std::filesystem::path folder =
        aos::tool::resolve_folder(options.folder);
    if (std::filesystem::exists(aos::tool::spec_path(folder, name)) &&
        !options.replace) {
        std::fprintf(stderr,
                     "aos tool: %s 已經登記過了；要覆寫請加 --replace\n",
                     name.c_str());
        return 1;
    }

    Probe probe;
    if (!options.no_probe) {
        probe = aos::tool::probe_metainfo(command);
        if (!probe.ok && options.probe_metadata) {
            probe = aos::tool::probe_metainfo(command, "--metadata");
        }
    }

    Spec spec;
    spec.name = name;
    spec.argv = std::move(command);
    merge_probe(spec, probe);
    merge_cli(spec, options);
    if (spec.description.empty()) {
        std::fprintf(stderr,
                     "aos tool: 探測不到表述，請用 --description 手填%s%s\n",
                     probe.detail.empty() ? "" : "；",
                     probe.detail.c_str());
        return 1;
    }
    aos::tool::write_spec(folder, spec);
    std::printf("已登記 %s -> %s\n", name.c_str(),
                aos::tool::spec_path(folder, name).string().c_str());
    return 0;
}

int list(const char *program, const std::vector<std::string> &words) {
    std::filesystem::path folder;
    bool json = false;
    for (std::size_t index = 1; index < words.size(); ++index) {
        if (words[index] == "--json") json = true;
        else if (words[index] == "--folder" && index + 1 < words.size()) {
            folder = words[++index];
        } else {
            return usage(program);
        }
    }
    const std::vector<Spec> registry = aos::tool::read_registry(folder);
    if (json) {
        std::fputs("[", stdout);
        if (!registry.empty()) std::fputc('\n', stdout);
        for (std::size_t index = 0; index < registry.size(); ++index) {
            std::string item = aos::tool::spec_to_json(registry[index]);
            if (!item.empty() && item.back() == '\n') item.pop_back();
            item = aos::tool::cli::indent(item, 2);
            std::fwrite(item.data(), 1, item.size(), stdout);
            std::fputs(index + 1 == registry.size() ? "\n" : ",\n", stdout);
        }
        std::puts("]");
        return 0;
    }
    if (registry.empty()) {
        std::puts("（沒有登記任何工具）");
        return 0;
    }
    std::vector<std::vector<std::string>> rows;
    for (const Spec &spec : registry) {
        rows.push_back({spec.name, spec.args, spec.stdin_mode,
                        aos::tool::cli::join(spec.argv),
                        aos::tool::cli::truncate_utf8(spec.description, 60)});
    }
    aos::tool::cli::print_table(
        {"NAME", "ARGS", "STDIN", "ARGV", "DESCRIPTION"}, rows);
    return 0;
}

int remove(const char *program, const std::vector<std::string> &words) {
    if (words.size() < 2) return usage(program);
    const std::string name = words[1];
    std::filesystem::path folder;
    std::size_t index = 2;
    while (index < words.size()) {
        if (words[index] != "--folder" || index + 1 >= words.size()) {
            return usage(program);
        }
        folder = words[index + 1];
        index += 2;
    }
    if (!aos::tool::remove_spec(folder, name)) {
        std::fprintf(stderr, "aos tool: 沒有登記 %s\n", name.c_str());
        return 1;
    }
    std::printf("已移除 %s\n", name.c_str());
    return 0;
}

int dispatch(int argc, char *argv[]) {
    const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                              ? argv[0]
                              : "aos tool";
    for (int index = 1; argv != nullptr && index < argc; ++index) {
        if (argv[index] != nullptr &&
            (std::string_view(argv[index]) == "--help" ||
             std::string_view(argv[index]) == "-h")) {
            return usage(program, stdout, 0);
        }
    }
    std::vector<std::string> words;
    for (int index = 1; index < argc; ++index) {
        if (argv == nullptr || argv[index] == nullptr) return usage(program);
        words.emplace_back(argv[index]);
    }
    if (words.empty()) return usage(program);
    if (words[0] == "add") return add(program, words);
    if (words[0] == "ls") return list(program, words);
    if (words[0] == "rm") return remove(program, words);
    return usage(program);
}

}  // namespace

extern "C" int aos_tool_cli_main(int argc, char *argv[]) {
    try {
        return dispatch(argc, argv);
    } catch (const std::exception &error) {
        const char *program = argc > 0 && argv != nullptr && argv[0] != nullptr
                                  ? argv[0]
                                  : "aos tool";
        std::fprintf(stderr, "%s: %s\n", program, error.what());
        return 1;
    }
}
