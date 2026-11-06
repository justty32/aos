// aos/util/io.hpp：【aos-util】aos 這一家命令列工具的「三扇門」——stdin 讀一份 JSON、stdout 印一行 JSON、stderr 只有兩種行。
//
//   read_stream(t) 一串 JSON 值（空白隔開，可單行可跨行）→ 一個個值；壞掉的尾巴丟掉（前面能解的算），不丟例外。
//                  read_stdin 就是用它；別的工具讀「JSON 串流」的檔（例如子程式的 stdout）也用它
//   require_stdin_body()  要 stdin 內容時拒絕終端（ArgumentsBad），不等 EOF。
//   read_stdin()   先拒絕終端，再讀 stdin 到底：一份 JSON（空的＝{}、一份都解不出來＝InputBad、多份＝InputExtra、壞尾丟掉）
//   dumps(v)       JSON → 一行字，排版同 Python 的 json.dumps(v, ensure_ascii=False)：", "、": "、key 照原順序
//   emit(v)        stdout 印一行 dumps(v)、馬上 flush，回退出碼 0
//   fail(prog, e)  錯誤行：先 flush stdout，stderr 印一行「prog: error: 代號 原因」、馬上 flush，回退出碼 1
//                  （11-05 stdio-unify R1；有錯誤行就不准退 0。舊的 emit_error〔印 {"error": …}〕沒人用，刪了）
//   warn(prog, m)  提醒行：stderr 印一行「prog: warning: 句子」（不帶代號、不退出；退 0 也可以有）
//   is_count(v)    JSON 非負整數（true／false、1.0 不算）
//
// Json 用 nlohmann::ordered_json：物件的 key 照讀進來的順序留著（跟 Python 的 dict 一樣），印出來不會被排序。
#pragma once

#include "aos/util/error.hpp"

#include <nlohmann/json.hpp>

#include <string>
#include <vector>

namespace aos {

using Json = nlohmann::ordered_json;

std::vector<Json> read_stream(const std::string& text);

void require_stdin_body();
Json read_stdin();
std::string dumps(const Json& v);
int emit(const Json& v);
int fail(const std::string& prog, const Error& e);
int fail(const std::string& prog, const std::string& code, const std::string& msg);
void warn(const std::string& prog, const std::string& msg);

bool is_count(const Json& v);

}  // namespace aos
