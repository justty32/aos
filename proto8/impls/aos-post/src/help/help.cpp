// help.cpp：【help】aos-post 各子命令的旗標說明與用法字串。
#include "help/help.hpp"

#include <map>

namespace aos::post {

namespace {

// 子命令的用法（錯誤行的 usage 與 SUBCOMMAND --help）
const std::map<std::string, std::string> SUB_USAGE = {
    {"init", "aos-post init MAILBOX"},
    {"send", "aos-post send [FLAGS] MAILBOX [LETTER] < body.json"},
    {"take", "aos-post take MAILBOX"},
    {"take-all", "aos-post take-all MAILBOX"},
    {"see", "aos-post see MAILBOX [LETTER]"},
    {"done", "aos-post done [--keep] [--reply] MAILBOX [LETTER] [< body.json]"},
    {"regret", "aos-post regret MAILBOX LETTER"},
};

const std::map<std::string, std::string> SUB_HELP = {
    {"init", R"(aos-post init - Create a maildir-style mailbox.

usage: aos-post init MAILBOX
       aos-post init --help

flags:
  -h, --help   show this help

Create MAILBOX and its tmp/, new/ and cur/ folders; existing folders are kept.

exit codes: 0 success; 1 error.
more: aos-post/README.md
)"},
    {"send", R"(aos-post send - Send a letter to a mailbox.

usage: aos-post send [FLAGS] MAILBOX [LETTER] < body.json
       aos-post send --help

flags:
  --ordered              prepend a sequence number to the letter name
  --reply-to BOX         set the mailbox for replies
  --in-reply-to LETTER   identify the letter being answered
  -h, --help   show this help

Read the body JSON from stdin and print the sent letter name.

exit codes: 0 sent; 1 error.
more: aos-post/README.md
)"},
    {"take", R"(aos-post take - Claim the next letter.

usage: aos-post take MAILBOX
       aos-post take --help

flags:
  -h, --help   show this help

Move the next letter from new/ to cur/ and print its name.

exit codes: 0 claimed; 10 no letter; 1 error.
more: aos-post/README.md
)"},
    {"take-all", R"(aos-post take-all - Claim all waiting letters.

usage: aos-post take-all MAILBOX
       aos-post take-all --help

flags:
  -h, --help   show this help

Move all waiting letters from new/ to cur/; print one name per line.

exit codes: 0 claimed; 10 no letters; 1 error.
more: aos-post/README.md
)"},
    {"see", R"(aos-post see - Read a claimed letter.

usage: aos-post see MAILBOX [LETTER]
       aos-post see --help

flags:
  -h, --help   show this help

Print letter.json as one JSON line; without LETTER use the first in cur/.

exit codes: 0 found; 10 no letter; 1 error.
more: aos-post/README.md
)"},
    {"done", R"(aos-post done - Finish a claimed letter.

usage: aos-post done [--keep] [--reply] MAILBOX [LETTER] [< body.json]
       aos-post done --help

flags:
  --keep    keep the finished letter in archive/
  --reply   read body JSON from stdin and send it to the letter's reply_to
  -h, --help   show this help

Without LETTER use the first in cur/. Print the reply name when a reply is sent.

exit codes: 0 finished; 10 no letter; 1 error.
more: aos-post/README.md
)"},
    {"regret", R"(aos-post regret - Withdraw a waiting letter.

usage: aos-post regret MAILBOX LETTER
       aos-post regret --help

flags:
  -h, --help   show this help

Remove LETTER from new/; a letter already claimed cannot be withdrawn.

exit codes: 0 withdrawn; 1 error.
more: aos-post/README.md
)"},
};


}  // namespace

const std::string& cli_usage(const std::string& command) {
    return SUB_USAGE.at(command);
}

const std::string& cli_help(const std::string& command) {
    return SUB_HELP.at(command);
}

}  // namespace aos::post
