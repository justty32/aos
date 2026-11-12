// cmd.hpp：【cmd】每個子命令一個函數：拿到子命令後面的參數（不含 `aos-json 子命令`），回退出碼；錯丟 aos::Error。
//
//   read.cpp   get、where；get_value（get、ls、search 共用的取值）
//   peek.cpp   peek（漸進展開：一次只看一層，大的值摺起來）
//   list.cpp   ls（列一格底下的孩子，可附型別與大小）、search（找 key／value，往下或往上）
//   edit.hpp   寫入共用狀態與位置；edit.cpp 讀取值、找位置與放入值
//   write.cpp  set、batch、del、append、merge、add（找位置 → 改 → 有變才原子寫回）
//   ref.cpp    env、ref（ref --move 搬值並重算相對 $ref）
//   check.cpp  check
#pragma once

#include "doc/doc.hpp"

#include <string>
#include <vector>

namespace aos::json {

using Args = std::vector<std::string>;

int cmd_get(const Args& args);
int cmd_peek(const Args& args);
int cmd_where(const Args& args);
int cmd_set(const Args& args);
int cmd_batch(const Args& args);
int cmd_del(const Args& args);
int cmd_append(const Args& args);
int cmd_merge(const Args& args);
int cmd_env(const Args& args);
int cmd_ref(const Args& args);
int cmd_check(const Args& args);
int cmd_add(const Args& args);
int cmd_ls(const Args& args);
int cmd_search(const Args& args);

// get 的取值：follow＝路上的 $ref 穿過去；resolve＝把值裡的指示詞解開。指不到＝PointerMissing（get、ls、search 共用）。
Json get_value(const std::string& spec, bool follow, bool resolve);

// check 的本體：從 spec 往下驗（docs 裡已經讀的檔用記憶體裡的版本，set --check 拿來驗改完、還沒寫的樣子）。回每個問題一行。
std::vector<std::string> problems_of(Docs& docs, const std::string& spec, bool env);

}  // namespace aos::json
