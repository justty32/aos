#include <aos/tool.hpp>

#include "internal.hpp"

#include <aos/loop.hpp>

#include <algorithm>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <system_error>

namespace aos::tool {
namespace detail {

std::string read_text(const std::filesystem::path &path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("無法讀取 " + path.string());
    return {std::istreambuf_iterator<char>(input),
            std::istreambuf_iterator<char>()};
}

void atomic_write(const std::filesystem::path &path, std::string_view text) {
    std::filesystem::create_directories(path.parent_path());
    const std::filesystem::path temporary = path.string() + ".tmp";
    {
        std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
        if (!output) throw std::runtime_error("無法寫入 " + temporary.string());
        output.write(text.data(), static_cast<std::streamsize>(text.size()));
        output.close();
        if (!output) throw std::runtime_error("寫入失敗 " + temporary.string());
    }
    std::filesystem::rename(temporary, path);
}

}  // namespace detail

std::filesystem::path resolve_folder(const std::filesystem::path &given) {
    const std::filesystem::path folder =
        given.empty() ? std::filesystem::path(aos::loop::current_folder())
                      : given;
    return std::filesystem::absolute(folder).lexically_normal();
}

std::filesystem::path tools_dir(const std::filesystem::path &folder) {
    return resolve_folder(folder) / ".aos" / "tools";
}

std::filesystem::path spec_path(const std::filesystem::path &folder,
                                std::string_view name) {
    validate_tool_name(name);
    return tools_dir(folder) / (std::string(name) + ".json");
}

std::filesystem::path contacts_path(const std::filesystem::path &folder) {
    return resolve_folder(folder) / ".aos" / "contacts.json";
}

std::optional<Spec> read_spec(const std::filesystem::path &folder,
                              std::string_view name) {
    const std::filesystem::path path = spec_path(folder, name);
    if (!std::filesystem::exists(path)) return std::nullopt;
    Spec spec = parse_spec(detail::read_text(path), path.string());
    if (spec.name != name) {
        throw std::runtime_error(path.string() + ": name 必須等於檔名 " +
                                 path.stem().string());
    }
    return spec;
}

void write_spec(const std::filesystem::path &folder, const Spec &spec) {
    detail::atomic_write(spec_path(folder, spec.name), spec_to_json(spec));
}

bool remove_spec(const std::filesystem::path &folder, std::string_view name) {
    std::error_code error;
    const bool removed = std::filesystem::remove(spec_path(folder, name), error);
    if (error) {
        throw std::runtime_error("無法移除工具 " + std::string(name) + ": " +
                                 error.message());
    }
    return removed;
}

std::vector<Spec> read_registry(const std::filesystem::path &folder) {
    const std::filesystem::path directory = tools_dir(folder);
    if (!std::filesystem::is_directory(directory)) return {};

    std::vector<Spec> registry;
    for (const auto &entry : std::filesystem::directory_iterator(directory)) {
        if (!entry.is_regular_file() || entry.path().extension() != ".json") {
            continue;
        }
        Spec spec = parse_spec(detail::read_text(entry.path()),
                               entry.path().string());
        if (spec.name != entry.path().stem().string()) {
            throw std::runtime_error(entry.path().string() +
                                     ": name 必須等於檔名 " +
                                     entry.path().stem().string());
        }
        registry.push_back(std::move(spec));
    }
    std::sort(registry.begin(), registry.end(),
              [](const Spec &left, const Spec &right) {
                  return left.name < right.name;
              });
    return registry;
}

std::vector<Spec> default_specs() {
    Spec shell;
    shell.name = "sh";
    shell.argv = {"sh", "-lc", "{args}"};
    shell.description =
        "用 sh -lc 執行一行 shell 指令。args 就是整行指令字串。";
    shell.args = "string";
    shell.timeout_ms = 30000;
    shell.predictability = "medium";

    Spec list;
    list.name = "ls";
    list.argv = {"ls"};
    list.description =
        "列出資料夾內容。args 是選項與路徑 token，例如 [\"-la\", \".\"]。";
    list.timeout_ms = 30000;
    list.guarantee = "idempotent";
    list.predictability = "high";

    Spec cat;
    cat.name = "cat";
    cat.argv = {"cat"};
    cat.description = "印出檔案內容。args 是一個或多個檔案路徑 token。";
    cat.timeout_ms = 30000;
    cat.guarantee = "idempotent";
    cat.predictability = "high";
    return {shell, list, cat};
}

bool install_defaults(const std::filesystem::path &folder) {
    if (!read_registry(folder).empty()) return false;
    for (const Spec &spec : default_specs()) write_spec(folder, spec);
    return true;
}

}  // namespace aos::tool
