#include <aos/tick.hpp>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <system_error>
#include <unordered_set>
#include <utility>
#include <nlohmann/json.hpp>
namespace aos::tick {
namespace {
using Json = nlohmann::ordered_json;
bool load_json(const std::string &path, Json &document, bool &missing,
               std::string &error) {
    std::error_code code;
    missing = !std::filesystem::exists(path, code);
    if (code) {
        error = "無法檢查 " + path + "：" + code.message();
        return false;
    }
    if (missing) return true;
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        error = "無法讀取 " + path;
        return false;
    }
    try {
        input >> document;
    } catch (const nlohmann::json::exception &exception) {
        error = path + "：JSON 解析失敗：" + exception.what();
        return false;
    }
    return true;
}
bool take_string(const Json &object, const char *key, std::string &value,
                 const std::string &path, std::string &error,
                 bool keep_missing = false) {
    const auto item = object.find(key);
    if (item == object.end()) {
        if (!keep_missing) value.clear();
        return true;
    }
    if (!item->is_string()) {
        error = path + "：欄位「" + key + "」必須是字串";
        return false;
    }
    value = item->get<std::string>();
    return true;
}
Run read_run(const Json &row) {
    Run run;
    const auto field = row.find("run");
    if (field == row.end() || !field->is_object()) return run;
    const auto argv = field->find("argv");
    if (argv != field->end() && argv->is_array() && !argv->empty()) {
        std::vector<std::string> values;
        for (const auto &value : *argv) {
            if (!value.is_string()) {
                values.clear();
                break;
            }
            values.push_back(value.get<std::string>());
        }
        if (!values.empty()) {
            run.argv = std::move(values);
            return run;
        }
    }
    const auto ask = field->find("ask");
    if (ask != field->end() && ask->is_string()) {
        const std::string value = ask->get<std::string>();
        if (!value.empty()) run.ask = value;
    }
    return run;
}
bool parse_routine(const Json &object, Routine &row, const std::string &path,
                   std::string &error) {
    if (!take_string(object, "id", row.id, path, error) ||
        !take_string(object, "kind", row.kind, path, error) ||
        !take_string(object, "every", row.every, path, error) ||
        !take_string(object, "slot", row.slot, path, error) ||
        !take_string(object, "last_run", row.last_run, path, error) ||
        !take_string(object, "note", row.note, path, error)) {
        return false;
    }
    row.run = read_run(object);
    return true;
}
bool parse_schedule(const Json &object, ScheduleItem &row,
                    const std::string &path, std::string &error) {
    if (!take_string(object, "id", row.id, path, error) ||
        !take_string(object, "at", row.at, path, error) ||
        !take_string(object, "note", row.note, path, error)) {
        return false;
    }
    row.run = read_run(object);
    return true;
}
template <typename Row, typename Parse>
bool read_table(const std::string &path, std::vector<Row> &rows,
                std::string &error, Parse parse) {
    rows.clear();
    Json document;
    bool missing = false;
    if (!load_json(path, document, missing, error)) return false;
    if (missing) {
        error.clear();
        return true;
    }
    if (!document.is_object()) {
        error = path + "：表格頂層必須是物件";
        return false;
    }
    const auto values = document.find("rows");
    if (values == document.end() || !values->is_array()) {
        error = path + "：欄位「rows」必須是陣列";
        return false;
    }
    std::vector<Row> parsed;
    std::unordered_set<std::string> ids;
    parsed.reserve(values->size());
    for (const auto &value : *values) {
        if (!value.is_object()) {
            error = path + "：rows 的每一列都必須是物件";
            return false;
        }
        Row row;
        if (!parse(value, row, path, error)) return false;
        if (!ids.insert(row.id).second) {
            error = path + "：表內 id 重複：「" + row.id + "」";
            return false;
        }
        parsed.push_back(std::move(row));
    }
    rows = std::move(parsed);
    error.clear();
    return true;
}
Json encode_run(const Run &run) {
    Json value = Json::object();
    if (!run.argv.empty()) {
        value["argv"] = run.argv;
    } else if (!run.ask.empty()) {
        value["ask"] = run.ask;
    }
    return value;
}
bool mkdir_parent(const std::string &path, std::string &error) {
    const std::filesystem::path parent = std::filesystem::path(path).parent_path();
    if (parent.empty()) return true;
    std::error_code code;
    std::filesystem::create_directories(parent, code);
    if (code) {
        error = "無法建立 " + parent.string() + "：" + code.message();
        return false;
    }
    return true;
}
bool write_atomic(const std::string &path, const std::string &text,
                  std::string &error) {
    if (!mkdir_parent(path, error)) return false;
    const std::string temporary = path + ".tmp";
    std::FILE *output = std::fopen(temporary.c_str(), "wb");
    if (output == nullptr) {
        error = "無法寫入 " + temporary + "：" + std::strerror(errno);
        return false;
    }
    bool okay = std::fwrite(text.data(), 1, text.size(), output) == text.size();
    if (okay && std::fflush(output) != 0) okay = false;
    int saved_errno = errno;
    if (std::fclose(output) != 0) {
        if (okay) saved_errno = errno;
        okay = false;
    }
    if (!okay) {
        error = "寫入失敗 " + temporary + "：" + std::strerror(saved_errno);
        std::remove(temporary.c_str());
        return false;
    }
    if (std::rename(temporary.c_str(), path.c_str()) != 0) {
        error = "無法發佈 " + path + "：" + std::strerror(errno);
        std::remove(temporary.c_str());
        return false;
    }
    error.clear();
    return true;
}
bool write_table(const std::string &path, const Json &columns, Json rows,
                 Instant now, const std::string &tz, std::string &error) {
    const std::string local = format_at(now, tz);
    if (local.size() < 10) {
        error = path + "：無法用時區「" + tz + "」產生日期";
        return false;
    }
    Json document = Json::object();
    document["contract"] = "wf-table/1";
    document["source"] = "";
    document["extracted"] = local.substr(0, 10);
    document["columns"] = columns;
    document["link_columns"] = Json::array();
    document["rows"] = std::move(rows);
    return write_atomic(path, document.dump(2) + '\n', error);
}
bool exists(const std::string &path, bool &result, std::string &error) {
    std::error_code code;
    result = std::filesystem::exists(path, code);
    if (code) {
        error = "無法檢查 " + path + "：" + code.message();
        return false;
    }
    return true;
}
}  // namespace
bool read_routines(const std::string &path, std::vector<Routine> &rows,
                   std::string &error) {
    return read_table(path, rows, error, parse_routine);
}
bool read_schedule(const std::string &path, std::vector<ScheduleItem> &rows,
                   std::string &error) {
    return read_table(path, rows, error, parse_schedule);
}
bool write_routines(const std::string &path, const std::vector<Routine> &rows,
                    Instant now, const std::string &tz, std::string &error) {
    try {
        Json values = Json::array();
        for (const auto &row : rows) {
            values.push_back({{"id", row.id}, {"kind", row.kind},
                              {"every", row.every}, {"slot", row.slot},
                              {"last_run", row.last_run},
                              {"run", encode_run(row.run)}, {"note", row.note}});
        }
        return write_table(path,
                           {"id", "kind", "every", "slot", "last_run", "run", "note"},
                           std::move(values), now, tz, error);
    } catch (const nlohmann::json::exception &exception) {
        error = path + "：JSON 寫入失敗：" + exception.what();
        return false;
    }
}
bool write_schedule(const std::string &path,
                    const std::vector<ScheduleItem> &rows, Instant now,
                    const std::string &tz, std::string &error) {
    try {
        Json values = Json::array();
        for (const auto &row : rows) {
            values.push_back({{"id", row.id}, {"at", row.at},
                              {"run", encode_run(row.run)}, {"note", row.note}});
        }
        return write_table(path, {"id", "at", "run", "note"},
                           std::move(values), now, tz, error);
    } catch (const nlohmann::json::exception &exception) {
        error = path + "：JSON 寫入失敗：" + exception.what();
        return false;
    }
}
bool read_config(const std::string &path, Config &config, std::string &error) {
    Config parsed;
    Json document;
    bool missing = false;
    if (!load_json(path, document, missing, error)) return false;
    if (missing) {
        config = std::move(parsed);
        error.clear();
        return true;
    }
    if (!document.is_object()) {
        error = path + "：設定檔頂層必須是物件";
        return false;
    }
    if (!take_string(document, "tz", parsed.tz, path, error, true) ||
        !take_string(document, "missed_after", parsed.missed_after, path,
                     error, true)) return false;
    config = std::move(parsed);
    error.clear();
    return true;
}
bool ensure_heartbeat(const Paths &paths, Instant now, const std::string &tz,
                      std::string &error) {
    std::error_code code;
    std::filesystem::create_directories(paths.heartbeat, code);
    if (code) {
        error = "無法建立 " + paths.heartbeat + "：" + code.message();
        return false;
    }
    bool present = false;
    if (!exists(paths.routines_file, present, error)) return false;
    if (!present && !write_routines(paths.routines_file, {}, now, tz, error)) {
        return false;
    }
    if (!exists(paths.schedule_file, present, error)) return false;
    if (!present && !write_schedule(paths.schedule_file, {}, now, tz, error)) {
        return false;
    }
    error.clear();
    return true;
}
}  // namespace aos::tick
