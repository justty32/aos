#pragma once

#include <aos/export.h>

#include <cstddef>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace aos::tooljson {

enum class SpecState {
    Ok,
    InvalidArgument,
    JsonSyntax,
    InvalidFormat,
    UnknownType,
    DuplicateName,
    IoError,
};

AOS_API const char *to_string(SpecState state) noexcept;
AOS_API const char *format_version() noexcept;

class Spec;

class AOS_API Body {
public:
    AOS_API virtual ~Body();

    AOS_API virtual std::string run(const char *args_json,
                                    std::size_t size) const = 0;
    AOS_API virtual std::string target() const = 0;
};

using BodyPtr = std::shared_ptr<const Body>;
using Parser = std::function<SpecState(const Spec &, BodyPtr &, std::string &)>;

namespace detail {
struct SpecAccess;
}

class Spec {
public:
    struct Impl;

    AOS_API Spec() noexcept;
    AOS_API Spec(const Spec &) noexcept;
    AOS_API Spec(Spec &&) noexcept;
    AOS_API Spec &operator=(const Spec &) noexcept;
    AOS_API Spec &operator=(Spec &&) noexcept;
    AOS_API ~Spec();

    AOS_API explicit operator bool() const noexcept;
    AOS_API std::string name() const;
    AOS_API std::string description() const;
    AOS_API std::string type() const;
    AOS_API std::string path() const;
    AOS_API std::string schema_json() const;
    AOS_API std::string extra_json() const;
    AOS_API std::string run(const char *args_json, std::size_t size) const;
    AOS_API std::string target() const;
    AOS_API std::optional<bool> stale() const;

private:
    std::shared_ptr<const Impl> impl_;

    AOS_API explicit Spec(std::shared_ptr<const Impl> impl) noexcept;
    friend struct detail::SpecAccess;
};

/* 讀記憶體時，base_dir 是相對路徑的中心；傳 nullptr 代表呼叫端目前的 cwd。 */
AOS_API SpecState load_all(const char *data, std::size_t size,
                           const char *base_dir, std::vector<Spec> &out,
                           std::string &message);
AOS_API SpecState load(const char *data, std::size_t size,
                       const char *base_dir, Spec &out,
                       std::string &message);

/* 讀檔版本會以 JSON 檔本身所在的資料夾作為相對路徑中心。 */
AOS_API SpecState load_all(const char *path, std::vector<Spec> &out,
                           std::string &message);
AOS_API SpecState load(const char *path, Spec &out, std::string &message);

/* 多檔依序載入；跨檔 function.name 撞名時保留較早路徑的版本。 */
AOS_API SpecState load_all(const std::vector<std::string> &paths,
                           std::vector<Spec> &out, std::string &message);

/* 把一個 JSON 值以兩格縮排、UTF-8 原字元寫入檔案。 */
AOS_API SpecState save(const char *data, std::size_t size, const char *path,
                       std::string &message);

/* 同名登記會覆蓋舊解析器，方便互動式開發與第三方擴充。 */
AOS_API SpecState register_type(const std::string &type, Parser parser,
                                std::string &message);
AOS_API std::vector<std::string> registered_types();

struct ExpandedArgs {
    std::vector<std::string> argv;
    std::optional<std::string> stdin_text;
};

/* 成功回空字串；模型參數有誤則回可直接送回模型的 Error: ... 字串。 */
AOS_API std::string expand_args(const Spec &spec, const char *args_json,
                                std::size_t size, ExpandedArgs &out);

AOS_API std::string decode_output(const char *data, std::size_t size);
AOS_API std::string clip_output(const std::string &text,
                                const std::string &where = "head",
                                std::size_t limit = 30000);

}  // namespace aos::tooljson
