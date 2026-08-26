#include <aos/tooljson.hpp>

#include "spec_internal.hpp"
#include "tooljson_internal.hpp"

#include <cerrno>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <set>
#include <system_error>
#include <utility>

namespace aos::tooljson {

using detail::fail;

namespace {

using json = nlohmann::json;

SpecState load_all_impl(const char *data, std::size_t size,
                        const std::string &source_path,
                        const std::string &base_dir, std::vector<Spec> &out,
                        std::string &message) {
    out.clear();
    message.clear();
    if (data == nullptr) {
        return fail(SpecState::InvalidArgument,
                    "JSON 資料指標不可是 null", message);
    }

    json document;
    try {
        document = json::parse(data, data + size);
    } catch (const json::parse_error &error) {
        return fail(SpecState::JsonSyntax,
                    (source_path.empty() ? std::string("JSON 讀不起來：")
                                         : source_path + " 讀不起來：") +
                        error.what(),
                    message);
    }

    const bool array = document.is_array();
    const std::size_t count = array ? document.size() : 1;
    if (array && count == 0) {
        return fail(SpecState::InvalidFormat,
                    (source_path.empty() ? std::string("這份 JSON") : source_path) +
                        " 是空的 array，一個 tool 都沒有",
                    message);
    }

    std::vector<Spec> parsed;
    parsed.reserve(count);
    for (std::size_t index = 0; index < count; ++index) {
        const json &one = array ? document[index] : document;
        Spec spec;
        std::string detail_message;
        const SpecState state = detail::parse_one(one, source_path, base_dir, spec,
                                          detail_message);
        if (state != SpecState::Ok) {
            const std::string prefix = source_path.empty() ? std::string()
                                                            : source_path + " ";
            return fail(state, prefix + "第 " + std::to_string(index + 1) +
                                   " 個：" + detail_message,
                        message);
        }
        parsed.push_back(std::move(spec));
    }

    std::map<std::string, std::size_t> counts;
    for (const Spec &spec : parsed) {
        ++counts[spec.name()];
    }
    std::vector<std::string> duplicates;
    for (const auto &[name, count_value] : counts) {
        if (count_value > 1) {
            duplicates.push_back(name);
        }
    }
    if (!duplicates.empty()) {
        return fail(SpecState::DuplicateName,
                    (source_path.empty() ? std::string("這份 JSON") : source_path) +
                        " 裡有重複的 function.name " +
                        detail::string_list_repr(duplicates),
                    message);
    }

    out.swap(parsed);
    return SpecState::Ok;
}

SpecState read_file(const char *path, std::string &data,
                    std::string &absolute, std::string &message) {
    if (path == nullptr || path[0] == '\0') {
        return fail(SpecState::InvalidArgument,
                    "spec 路徑要是非空字串", message);
    }
    std::error_code error;
    absolute = std::filesystem::absolute(path, error).lexically_normal().string();
    if (error) {
        return fail(SpecState::IoError,
                    std::string(path) + " 讀不起來：" + error.message(),
                    message);
    }

    errno = 0;
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        const int saved = errno;
        return fail(SpecState::IoError,
                    std::string(path) + " 讀不起來：" +
                        (saved == 0 ? "無法開啟檔案" : std::strerror(saved)),
                    message);
    }
    data.assign(std::istreambuf_iterator<char>(input),
                std::istreambuf_iterator<char>());
    if (input.bad()) {
        return fail(SpecState::IoError,
                    std::string(path) + " 讀不起來：讀取失敗", message);
    }
    return SpecState::Ok;
}
}  // namespace

SpecState load_all(const char *data, std::size_t size, const char *base_dir,
                   std::vector<Spec> &out, std::string &message) {
    std::error_code error;
    std::filesystem::path base =
        base_dir == nullptr ? std::filesystem::current_path(error)
                            : std::filesystem::path(base_dir);
    if (error) {
        out.clear();
        return fail(SpecState::IoError,
                    "目前工作目錄讀不起來：" + error.message(), message);
    }
    if (!base.is_absolute()) {
        base = std::filesystem::absolute(base, error);
    }
    if (error) {
        out.clear();
        return fail(SpecState::IoError,
                    "base_dir 讀不起來：" + error.message(), message);
    }
    return load_all_impl(data, size, {}, base.lexically_normal().string(), out,
                         message);
}

SpecState load(const char *data, std::size_t size, const char *base_dir,
               Spec &out, std::string &message) {
    out = Spec{};
    std::vector<Spec> found;
    SpecState state = load_all(data, size, base_dir, found, message);
    if (state != SpecState::Ok) return state;
    if (found.size() != 1) {
        return fail(SpecState::InvalidFormat,
                    "這份 JSON 裡有 " + std::to_string(found.size()) +
                        " 個 tool，用 load_all() 讀",
                    message);
    }
    out = std::move(found.front());
    return SpecState::Ok;
}

SpecState load_all(const char *path, std::vector<Spec> &out,
                   std::string &message) {
    out.clear();
    std::string data;
    std::string absolute;
    SpecState state = read_file(path, data, absolute, message);
    if (state != SpecState::Ok) return state;
    const std::filesystem::path file(absolute);
    return load_all_impl(data.data(), data.size(), path, file.parent_path().string(),
                         out, message);
}

SpecState load(const char *path, Spec &out, std::string &message) {
    out = Spec{};
    std::vector<Spec> found;
    SpecState state = load_all(path, found, message);
    if (state != SpecState::Ok) return state;
    if (found.size() != 1) {
        return fail(SpecState::InvalidFormat,
                    std::string(path) + " 裡有 " +
                        std::to_string(found.size()) +
                        " 個 tool，用 load_all() 讀",
                    message);
    }
    out = std::move(found.front());
    return SpecState::Ok;
}

SpecState load_all(const std::vector<std::string> &paths,
                   std::vector<Spec> &out, std::string &message) {
    out.clear();
    message.clear();
    std::set<std::string> names;
    std::vector<Spec> merged;
    for (const std::string &path : paths) {
        std::vector<Spec> one_file;
        SpecState state = load_all(path.c_str(), one_file, message);
        if (state != SpecState::Ok) return state;
        for (Spec &spec : one_file) {
            if (names.insert(spec.name()).second) {
                merged.push_back(std::move(spec));
            }
        }
    }
    out.swap(merged);
    return SpecState::Ok;
}

SpecState save(const char *data, std::size_t size, const char *path,
               std::string &message) {
    message.clear();
    if (data == nullptr || path == nullptr || path[0] == '\0') {
        return fail(SpecState::InvalidArgument,
                    "JSON 資料與輸出路徑不可是 null 或空字串", message);
    }

    json value;
    try {
        value = json::parse(data, data + size);
    } catch (const json::parse_error &error) {
        return fail(SpecState::JsonSyntax,
                    std::string("JSON 讀不起來：") + error.what(), message);
    }

    std::error_code error;
    const std::filesystem::path output(path);
    const std::filesystem::path parent =
        std::filesystem::absolute(output, error).parent_path();
    if (error) {
        return fail(SpecState::IoError,
                    std::string(path) + " 寫不出去：" + error.message(),
                    message);
    }
    std::filesystem::create_directories(parent, error);
    if (error) {
        return fail(SpecState::IoError,
                    std::string(path) + " 寫不出去：" + error.message(),
                    message);
    }

    errno = 0;
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    if (!stream) {
        const int saved = errno;
        return fail(SpecState::IoError,
                    std::string(path) + " 寫不出去：" +
                        (saved == 0 ? "無法開啟檔案" : std::strerror(saved)),
                    message);
    }
    stream << value.dump(2, ' ', false, json::error_handler_t::replace) << '\n';
    if (!stream) {
        return fail(SpecState::IoError,
                    std::string(path) + " 寫不出去：寫入失敗", message);
    }
    return SpecState::Ok;
}

}  // namespace aos::tooljson
