#pragma once

#include <aos/export.h>

#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace aos::tool {

struct Spec {
    std::string name;
    std::vector<std::string> argv;
    std::string description;
    std::string args = "list";      // list|string|none
    std::string stdin_mode = "none";  // JSON 欄位名是 "stdin"
    std::string cwd;
    std::uint64_t timeout_ms = 0;
    std::string source = "manual";
    std::string lifecycle;
    std::string state;
    std::string guarantee;
    std::string interruptible;
    std::string predictability;
    std::string stage;
    bool network = false;
    bool network_declared = false;
    std::vector<std::string> env_allow;
};

struct Contact {
    std::string name;
    std::string folder;
    std::string agent;
    std::string note;
};

/* 探測結果：ok=false 代表沒探到可用的自述。 */
struct Probe {
    bool ok = false;
    std::string source;       // "metainfo" | "header" | ""
    std::string description;
    Spec spec;                // metainfo 給的欄位（只有 ok 且 source=="metainfo" 時有意義）
    std::string detail;       // 失敗原因，給人看
};

/* given 非空就正規化它；否則 aos::loop::current_folder()。 */
AOS_API std::filesystem::path resolve_folder(
    const std::filesystem::path &given = {});

AOS_API std::filesystem::path tools_dir(const std::filesystem::path &folder);
AOS_API std::filesystem::path spec_path(const std::filesystem::path &folder,
                                        std::string_view name);
AOS_API std::filesystem::path contacts_path(
    const std::filesystem::path &folder);

AOS_API void validate_tool_name(std::string_view name);

/* 純函式，不碰檔案系統：JSON 文字 ↔ Spec。source_hint 只用在錯誤訊息。 */
AOS_API Spec parse_spec(std::string_view json_text,
                        std::string_view source_hint = {});
AOS_API std::string spec_to_json(const Spec &spec);   // dump(2) + "\n"

AOS_API std::optional<Spec> read_spec(const std::filesystem::path &folder,
                                      std::string_view name);
/* tmp + rename 原子寫；會 create_directories(tools_dir)。 */
AOS_API void write_spec(const std::filesystem::path &folder, const Spec &spec);
AOS_API bool remove_spec(const std::filesystem::path &folder,
                         std::string_view name);
/* 依 name 排序；.aos/tools/ 不存在或空＝空 vector；壞檔照樣 throw。 */
AOS_API std::vector<Spec> read_registry(const std::filesystem::path &folder);

/* sh(string) / ls(list) / cat(list) 三項，內容見 §6。 */
AOS_API std::vector<Spec> default_specs();
/* read_registry(folder) 為空時才寫入 default_specs()；回傳是否真的寫了。 */
AOS_API bool install_defaults(const std::filesystem::path &folder);

/* 跑 <argv> <flag>，stdin 關閉、逾時 3000 ms。行為見 §7。 */
AOS_API Probe probe_metainfo(const std::vector<std::string> &argv,
                             std::string_view flag = "--metainfo");

AOS_API std::vector<Contact> read_contacts(const std::filesystem::path &folder);
AOS_API Contact user_contact();
AOS_API void write_contacts(const std::filesystem::path &folder,
                            const std::vector<Contact> &contacts);
/* 同名取代，否則追加；原子寫。 */
AOS_API void add_contact(const std::filesystem::path &folder,
                         const Contact &contact);
AOS_API bool remove_contact(const std::filesystem::path &folder,
                            std::string_view name);
AOS_API std::optional<Contact> find_contact(
    const std::filesystem::path &folder, std::string_view name);

}  // namespace aos::tool
