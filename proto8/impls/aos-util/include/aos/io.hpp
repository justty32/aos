// aos/io.hpp：【aos-util】aos 這一家命令列工具的「三扇門」——stdin 讀一份 JSON、stdout 印一行 JSON、stderr 印一行錯誤。
//
//   read_stream(t) 一串 JSON 值（空白隔開，可單行可跨行）→ 一個個值；壞掉的尾巴丟掉（前面能解的算），不丟例外。
//                  read_stdin 就是用它；別的工具讀「JSON 串流」的檔（例如子程式的 stdout）也用它
//   read_stdin()   讀 stdin 到底：一份 JSON（空的＝{}、一份都解不出來＝InputBad、多份＝InputExtra、壞尾丟掉）
//   dumps(v)       JSON → 一行字，排版同 Python 的 json.dumps(v, ensure_ascii=False)：", "、": "、key 照原順序
//   emit(v)        stdout 印一行 dumps(v)、馬上 flush，回退出碼 0
//   emit_error(e)  stderr 印一行 {"error": {"code", "msg"}}、馬上 flush，回退出碼 1
//   is_count(v)    JSON 非負整數（true／false、1.0 不算）
//
// Json 用 nlohmann::ordered_json：物件的 key 照讀進來的順序留著（跟 Python 的 dict 一樣），印出來不會被排序。
#pragma once

#include "aos/error.hpp"

#include <nlohmann/json.hpp>

#include <string>
#include <vector>

namespace aos {

using Json = nlohmann::ordered_json;

std::vector<Json> read_stream(const std::string& text);

Json read_stdin();
std::string dumps(const Json& v);
int emit(const Json& v);
int emit_error(const Error& e);

bool is_count(const Json& v);

}  // namespace aos
