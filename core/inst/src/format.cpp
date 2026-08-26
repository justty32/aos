// format 層的公開進入點：validate 與 read_*／write_*。
// 實際的 JSON schema 在 format_decode.cpp（讀）與 format_encode.cpp（寫）。
// read_all／write_all 保持整批原子性：任何一筆失敗就整批不動 out。

#include "format_internal.hpp"

#include <string>
#include <utility>
#include <vector>

namespace aos {
namespace detail {

const PendingDirective *find_directive(const inst_t &inst,
                                       DirectiveField field,
                                       std::size_t argv_index,
                                       std::string_view env_key) {
    for (const auto &directive : inst.pending_directives) {
        if (directive.field != field) continue;
        if (field == DirectiveField::Argv &&
            directive.argv_index != argv_index) continue;
        if (field == DirectiveField::EnvValue &&
            directive.env_key != env_key) continue;
        return &directive;
    }
    return nullptr;
}

}  // namespace detail

namespace {

using json = nlohmann::json;

json parse_json(const char *data, std::size_t size) {
    return json::parse(data, data + size);
}

}  // namespace

InstState validate(const inst_t &inst) {
    if (inst.argv.empty()) return InstState::EmptyArgv;
    if (inst.argv.front().empty() &&
        detail::find_directive(inst, DirectiveField::Argv, 0) == nullptr) {
        return InstState::EmptyArgv;
    }
    for (const auto &entry : inst.env) {
        if (entry.first.empty() || entry.first.find('=') != std::string::npos) {
            return InstState::EnvKeyInvalid;
        }
    }
    return InstState::Ok;
}

InstState read_one(const char *data, std::size_t size, inst_t &out) {
    out.clear();
    if (data == nullptr) {
        return InstState::InvalidArgument;
    }

    try {
        const json value = parse_json(data, size);
        inst_t parsed;
        const InstState state = detail::decode(value, parsed);
        if (state == InstState::Ok) {
            out = std::move(parsed);
        }
        return state;
    } catch (const json::parse_error &) {
        return InstState::JsonSyntax;
    }
}

InstState read_all(const char *data, std::size_t size,
                   std::vector<inst_t> &out, std::size_t *error_record) {
    out.clear();
    if (error_record != nullptr) {
        *error_record = 0;
    }
    if (data == nullptr) {
        return InstState::InvalidArgument;
    }

    try {
        const json document = parse_json(data, size);
        const bool single = document.is_object();
        if (!single && !document.is_array()) {
            return InstState::NotAnObject;
        }

        const std::size_t count = single ? 1 : document.size();
        std::vector<inst_t> parsed;
        parsed.reserve(count);
        for (std::size_t index = 0; index < count; ++index) {
            const json &value = single ? document : document[index];
            if (error_record != nullptr) {
                *error_record = index + 1;
            }
            inst_t inst;
            const InstState state = detail::decode(value, inst);
            if (state != InstState::Ok) {
                return state;
            }
            parsed.push_back(std::move(inst));
        }
        out.swap(parsed);
        if (error_record != nullptr) {
            *error_record = 0;
        }
        return InstState::Ok;
    } catch (const json::parse_error &) {
        return InstState::JsonSyntax;
    }
}

InstState write_one(const inst_t &inst, std::string &out) {
    const InstState state = validate(inst);
    if (state != InstState::Ok) {
        return state;
    }

    std::string record = detail::encode(inst).dump();
    record.push_back('\n');
    out.append(record);
    return InstState::Ok;
}

InstState write_all(const std::vector<inst_t> &insts, std::string &out,
                    std::size_t *error_record) {
    if (error_record != nullptr) {
        *error_record = 0;
    }
    for (std::size_t index = 0; index < insts.size(); ++index) {
        const InstState state = validate(insts[index]);
        if (state != InstState::Ok) {
            if (error_record != nullptr) {
                *error_record = index + 1;
            }
            return state;
        }
    }

    nlohmann::ordered_json document = nlohmann::ordered_json::array();
    for (const auto &inst : insts) {
        document.push_back(detail::encode(inst));
    }
    std::string batch = document.dump();
    batch.push_back('\n');
    out.append(batch);
    return InstState::Ok;
}

}  // namespace aos
