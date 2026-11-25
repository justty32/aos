// util/io.hpp: the Json type, one-line JSON printing (dumps) and the error line (fail) (trimmed copy of proto8 aos-util aos/util/io.hpp).
//
//   dumps(v)       JSON → 一行字，排版同 Python 的 json.dumps(v, ensure_ascii=False)：", "、": "、key 照原順序
//   fail(prog, e)  錯誤行：先 flush stdout，stderr 印一行「prog: error: 代號 原因」、馬上 flush，回退出碼 1
//
// Json 用 nlohmann::ordered_json：物件的 key 照讀進來的順序留著（跟 Python 的 dict 一樣），印出來不會被排序。
// proto9: read_stdin, emit, warn, is_count are not brought in (aos-exec does not use them).
#pragma once

#include "util/error.hpp"

#include <nlohmann/json.hpp>

#include <string>

namespace aos {

using Json = nlohmann::ordered_json;

std::string dumps(const Json& v);
int fail(const std::string& prog, const Error& e);
int fail(const std::string& prog, const std::string& code, const std::string& msg);

}  // namespace aos
