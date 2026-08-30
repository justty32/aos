#include "internal.hpp"

#include <nlohmann/json.hpp>

#include <array>
#include <charconv>
#include <cstdlib>
#include <iomanip>
#include <limits>
#include <random>
#include <sstream>
#include <stdexcept>

namespace aos::agent {
namespace {

using Json = nlohmann::json;

std::string optional_string(const Json &root, const char *key,
                            const std::filesystem::path &path) {
    if (!root.contains(key)) return {};
    if (!root[key].is_string()) {
        throw std::runtime_error(path.string() + " 欄位 " + key +
                                 " 必須是字串");
    }
    return root[key].get<std::string>();
}

int optional_integer(const Json &root, const char *key,
                     const std::filesystem::path &path) {
    if (!root.contains(key)) return 0;

    const Json &value = root[key];
    bool valid = value.is_number_integer();
    int result = 0;
    if (valid && value.is_number_unsigned()) {
        const auto number = value.get<unsigned long long>();
        valid = number <=
                static_cast<unsigned long long>(std::numeric_limits<int>::max());
        if (valid) result = static_cast<int>(number);
    } else if (valid) {
        const auto number = value.get<long long>();
        valid = number >= std::numeric_limits<int>::min() &&
                number <= std::numeric_limits<int>::max();
        if (valid) result = static_cast<int>(number);
    }
    if (!valid) {
        throw std::runtime_error(path.string() + " 欄位 " + key +
                                 " 必須是整數");
    }
    return result;
}

}  // namespace

Engine read_engine(const std::filesystem::path &folder,
                   std::string_view name) {
    const detail::Paths paths = detail::paths_for(folder, name);
    if (!std::filesystem::exists(paths.engine)) return {};

    Json root;
    try {
        root = Json::parse(detail::read_text(paths.engine));
    } catch (const Json::exception &error) {
        throw std::runtime_error(paths.engine.string() + " JSON 無法解析: " +
                                 error.what());
    }
    if (!root.is_object() || !root.contains("engine") ||
        !root["engine"].is_string()) {
        throw std::runtime_error(paths.engine.string() +
                                 " 缺少字串欄位 engine");
    }

    Engine engine;
    engine.kind = root["engine"].get<std::string>();
    if (engine.kind != "lmstudio" && engine.kind != "pi") {
        throw std::runtime_error("未知的 agent engine: " + engine.kind);
    }
    engine.provider = optional_string(root, "provider", paths.engine);
    engine.model = optional_string(root, "model", paths.engine);
    engine.session_id = optional_string(root, "session_id", paths.engine);
    engine.priority = optional_integer(root, "priority", paths.engine);
    return engine;
}

namespace detail {

void write_engine(const Paths &paths, const Engine &engine) {
    Json root = {{"engine", engine.kind}};
    if (engine.kind == "pi") {
        root["provider"] = engine.provider;
        root["model"] = engine.model;
        root["session_id"] = engine.session_id;
    } else if (engine.kind == "lmstudio") {
        if (!engine.provider.empty()) root["provider"] = engine.provider;
    } else {
        throw std::runtime_error("未知的 agent engine: " + engine.kind);
    }
    if (engine.priority != 0) root["priority"] = engine.priority;
    atomic_write(paths.engine, root.dump(2) + "\n");
}

int llm_priority(const Engine &engine) {
    if (engine.priority != 0) return engine.priority;

    const char *configured = std::getenv("AOS_LLM_PRIORITY");
    if (configured == nullptr) return 0;

    const std::string_view text(configured);
    int priority = 0;
    const auto [end, error] =
        std::from_chars(text.data(), text.data() + text.size(), priority);
    if (error != std::errc{} || end != text.data() + text.size()) return 0;
    return priority;
}

std::string new_uuid() {
    std::array<unsigned char, 16> bytes{};
    std::random_device source;
    for (unsigned char &byte : bytes) {
        byte = static_cast<unsigned char>(source());
    }
    bytes[6] = static_cast<unsigned char>((bytes[6] & 0x0fU) | 0x40U);
    bytes[8] = static_cast<unsigned char>((bytes[8] & 0x3fU) | 0x80U);

    std::ostringstream out;
    out << std::hex << std::setfill('0');
    for (std::size_t index = 0; index < bytes.size(); ++index) {
        if (index == 4 || index == 6 || index == 8 || index == 10) {
            out << '-';
        }
        out << std::setw(2) << static_cast<unsigned int>(bytes[index]);
    }
    return out.str();
}

}  // namespace detail
}  // namespace aos::agent
