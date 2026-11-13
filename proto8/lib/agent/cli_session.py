# cli_session.py - 把 claude／codex 的一段對話接成工具：平常 agent 用非互動模式續同一個對話；人用 attach 接進互動畫面（tmux），跳出後畫面留著，agent 改從畫面送字
#
# 一個工具的小格（$AOS_STACK，act 給的是 $AOS_STACK/tools/<工具名>/，11-02 起）裡放：
#   session.txt   這段對話的 id（claude 的 session id／codex 的 thread id）：claude 新對話在交出去那一刻就寫（id 是我們產的）；
#                 codex 新對話讀到輸出的 thread.started 就寫（成敗都寫）；畫面那條路是 hook 收到第一輪時寫（11-10 two-machines 05），
#                 之後畫面上的 CLI 換了對話（/clear、/resume、codex /new）hook 就改記新的（11-12 eca-slash：CLI 為主、aos 跟上）；
#                 claude 畫面的 /clear 另外把 aos 這隻的 history 清掉（clear_history，原文搬到 history_removed.jsonl）；/compact 把 history
#                 換成 claude 的摘要一則（compact_history，SessionStart source compact）；codex 換到剛開的 thread（rollout 只有這一輪，
#                 codex_turns）＝/clear、清 history（剛交出去的 user 留著），換到有舊輪數的＝/resume、只跟 id（使用者 11-12 Q1～Q3）；
#                 codex multi-agent 子 agent 的 thread（rollout 第一行有 parent_thread_id，codex_parent）講完也叫 notify：不是換對話，hook 不理；
#                 session.txt 若已記到子 thread（codex 不給 resume），非互動那條改記、改接它的主對話並提醒一行（codex_main_thread）；
#                 codex 同一段 thread 的 rollout 多了 compacted＝/compact，history 換成從 replacement_history 撈出的對話（codex_sync_compact，Q5）
#   .compact_seen codex 用：{"thread", "compacted"}＝aos 已跟上的壓縮次數（畫面開起來、每輪 notify 時記；Q5）
#   .session_home 記號檔（不進 git）：{"session", "ws", "home", "machine"}——這段對話是在哪台機器（machine_id()）、哪個工作區（realpath）、
#                 哪個帳號資料夾（claude：CLAUDE_CONFIG_DIR 或 ~/.claude；codex：CODEX_HOME 或 ~/.codex）開的；跟 session.txt 一起寫、一起刪
#                 （machine 是 11-10 TS 8 加的：cp -a 時記號檔會跟過去；舊記號檔沒有這個 key＝不比機器）
#   （畫面的 tmux socket 不在小格裡，11-10 TS 10：/mnt/c 上 AF_UNIX bind 不了）實際放 ${XDG_RUNTIME_DIR:-/tmp}/aos-tty-<uid>/<小格 realpath
#                 sha256 前 16 hex>.sock（資料夾 0700），路徑只由 tty_socket() 算（attach＝tmux -S "$(那條)" attach）；小格搬了＝雜湊不同＝
#                 畫面當作沒開（本來就是死的）。11-10 以前開的畫面 socket 在小格的 tty.sock：還找得到就照用（過渡），不再新建
#   tmux.conf     attach 開畫面時寫的 tmux 設定（Ctrl-] 或 Ctrl-\ 跳出、不用 prefix）
#   turns.jsonl   互動畫面每講完一輪，hook 接一行 {"answered_at", "text"}（answered_at＝講完的時間，10-25 前叫 at）（agent 從這裡拿回答，不去解析畫面）
#   busy.txt      claude 的畫面正在跑一輪（有人送出、還沒講完）
#   a2a.json、a2a_acks.jsonl  claude 畫面的收件 socket 路徑（{"socket"}，投了沒回執改成 {"off": 原因}）與回執（一行 {"at", "id"}）；
#                 hook 寫、開畫面時先刪，跟這台機器與這次開的畫面綁在一起（cli_a2a，11-13）
#   lock          同一時間只有一個人用這段對話（agent 的一次呼叫、attach 開畫面）
#   live.jsonl    非互動的即時紀錄兼副產物：claude 的 stream-json、codex 的 --json 事件，一行一事件、只接不重寫（10-28；10-27 是每次重寫）
#   tool.txt、ws.txt  這格屬於哪個工具資料夾、哪個工作區（相對小格；open_cell 叫回畫面時用）
#   stack.txt     給 aos-mcp 的 stack（相對小格；平級形＝那隻 eca 的 $AOS_STACK、工具形＝這格本身；open_cell 叫回畫面時用）
#   mcp.json      claude 的 MCP 設定（11-03 eca-tools）：有登記檔才寫，每次起 claude 前重寫；codex 不寫檔、走 -c
#   transcripts/<kind>-<id>.jsonl  指到 CLI 自己存的這段對話的 symlink（claude ~/.claude/projects/*/<id>.jsonl、
#                 codex ~/.codex/sessions/**/*<id>.jsonl）：拿到 session id 就建（10-30 agent-lifecycle C-15～C-17；
#                 agent 叫的工具格也建，方向題 3）；一直是 symlink（11-02 晚 aos-eca 不再歸檔，freeze_transcripts 拿掉；
#                 CLI 會自己清舊對話，要留的人自己複製）
#
# 兩條路（每次呼叫自己挑）：
#   畫面沒開 → 非互動：claude -p --resume <id>（第一次 --session-id <新 id>）、codex exec resume <id> -（第一次 codex exec -）
#   畫面開著 → claude 身、呼叫者給了一封一項的 parts（aos-eca-turn）、小格記得收件 socket＝往 Claude Code 這個 session 自己的
#             收件口（cross-session messaging 的 Unix socket）寫，一封一行 JSON、一封一個署名信封（寄件人＝信的 name，沒有＝「aos通知中心」）；
#             不看 on_busy、有人接著或正在跑一輪都照投（11-13 使用者「馬上送，eca他會自己處理」）。socket 不回話，靠 UserPromptSubmit hook
#             記的回執認；開畫面時 hook 指令最後帶 a2a、--settings 併進 crossSessionInbound accept，SessionStart hook 把
#             CLAUDE_CODE_MESSAGING_SOCKET 抄進 a2a.json（沒帶 a2a 的舊畫面不記＝照舊貼字）。投不出去＝warning、改貼字；
#             投了、CLI 閒著 30 秒沒回執＝warning、a2a.json 記 off、這個畫面之後都貼字（到下一次 SessionStart）。關掉：cli.json "a2a": false，
#             或 cli_a2a.ENABLED。其餘（codex、工具形、退回時）從 pty 送字：tmux paste-buffer 貼上＋Enter，等 hook 在 turns.jsonl 接一行
#             （有人接著看、或 claude 正在跑一輪＝SessionBad；claude 停在信任資料夾選單＝TrustMissing、不貼不投，11-10 深夜；
#             on_busy="answer" 時不退讓：照樣貼、busy.txt 等它消失，10-31）
# aos 自己會加的旗標（cli.json 的 flags／print_flags 再寫＝CfgBad，cli_cfg.AOS_FLAGS）：codex＝--skip-git-repo-check、--json、-o／--output-last-message
#   （codex 不收重複的，寫第二次它退 2）；claude＝-p／--print、--output-format、--session-id、--resume／-r、--continue／-c。有宣告才加、可以重複的
#   不擋：--mcp-config、--allowedTools、--append-system-prompt-file、--system-prompt-snapshot、--settings、--agents（跟 tools_sub 同寫另有 CfgBad）、--model、codex 的 -c。
# 工具（11-03 eca-tools，thinking 2026-11-03-eca-tools）：cli.json 選填 tools＝aos-tools 的登記檔（相對路徑從 cli.json 的資料夾算；
#   也可寫指示詞，例 {"$env": "AOS_HOME", "$path": "/lib/x/tools.json"}，每次讀才解、不寫回，11-10 two-machines TC；{"$ref": "#/…"} 沒檔名＝cli.json 自己，11-12 ref-hash），
#   沒寫＝cli.json 同層有 tools.json 就用它（使用者 11-03「如果cli.json沒有指定，那就去找默認的tools.json」）、沒有＝不接工具；
#   選填 tools_flags＝字串陣列，原樣插在 aos-mcp 的 args 裡（例 ["--enable-logs"]）。定義的 interfaces.json 宣告了 hooks＝再加 --hooks <定義>
#   （11-10 hook：before_tool／after_tool 在 aos-mcp 跑）。有登記檔時每次起 CLI 前接上
#   aos-mcp --ws <工作區> --stack <stack> [tools_flags…] <登記檔絕對路徑>：claude＝寫小格 mcp.json、加 --mcp-config 它 --allowedTools mcp__aos；
#   codex＝-c mcp_servers.aos.command／args，加 env（MCP_ENV 那幾個 AOS_*，codex 不替 MCP server 帶環境變數，11-11）與
#   default_tools_approval_mode="approve"（只對 aos 這個 server 免核准、codex 自帶的工具照舊；使用者 11-11 選項框裁「aos 工具免核准」：
#   「eca 範本起 codex 時，只對 aos 那組工具關掉核准（跟 claude 那邊已經允許 aos 工具是同一個意思）。codex 自帶的工具照舊要核准。」）。aos-mcp 靠 PATH 找（N-50）；定義資料夾一個字都不寫（P-15）。
#   $AOS_STACK 裡這隻自己的（aos-agent tools／llm 寫的，stack_copies）：tools.json＝這隻自己那份（只存差異、"$override" 指回定義那份，
#   11-10 aos-tools-cli；cli.json 沒明寫 tools 時在就把它給 aos-mcp，疊法歸 aos-tools）、llm.json 的 model。
#   system（11-11 self-system，使用者裁「fsm 取代、eca 附加」）：interfaces.json 宣告了 system＝$AOS_STACK 那份在就用它、否則定義那份，非空就附加給 CLI：
#   claude＝--append-system-prompt-file＋--system-prompt-snapshot off（宣告了就一律 off，--resume 才換得到新的）、codex＝-c developer_instructions；
#   沒宣告＝不碰。畫面開著的 CLI 帶的是開畫面那時的（重開才換）。
# 外部 MCP（11-12 external-mcp 步 1，thinking 2026-11/12/external-mcp）：cli.json 選填 mcp_servers＝server 檔路徑的陣列（相對從 cli.json 的資料夾算、
#   可寫指示詞），一份一台，讀與驗在 lib/mcp_server_file.py。CLI 自己接（不凍結工具說明）、列了＝整台免核准。這版只接 codex 身的 http：
#   -c mcp_servers.<名>.url／bearer_token_env_var／default_tools_approval_mode="approve"／enabled_tools（only）／disabled_tools（except），
#   有 bearer＝自動補 shell_environment_policy.exclude；env_file 在起 codex 那一刻才讀，token 與 ca_file（SSL_CERT_FILE、CODEX_CA_CERTIFICATE）
#   只放進 codex 行程的環境（run_cli 的 env=；畫面那條路前面接 mcp_server_file.py --exec 啟動器，tmux 的環境沒有）。某一台壞＝warning 跳過、其他照接（X8）；
#   claude 身（步 3）：小格 mcp.json 跟 aos 那格並排 {"type": "http", "url", "headersHelper"}（helper＝mcp_server_file.py --headers，token 只經管線、
#   不進 claude 環境＝Bash 看不到）、--allowedTools 加 mcp__<名>（only＝逐支）、except＝--disallowedTools；ca_file＝NODE_EXTRA_CA_CERTS。
#   stdio（步 4）：兩身都經 aos-mcp-launch <server 檔>（PATH 找；它讀 env_file、exec 成 server＝金鑰只進 server 行程）；codex 另帶 env＝MCP_ENV 那幾個。
#   起不來的 server CLI 不說（那台的工具只是不見）：每次起 CLI 前先看 stdio 那幾台的指令解不解得開、找不找得到、能不能執行（cli_mcp.stdio_ready），
#   不過＝warning 跳過那台；claude 非互動那條另外讀開場 init 事件，列的外部 server 不是 connected＝提醒一行（cli_print.warn_unconnected）。
# 子 agent 那台（11-12 eca-task-subagent，thinking 2026-11/12/eca-task-subagent.md）：cli.json 選填 tools_sub＝第二份 aos-tools 登記檔（寫法同 tools；
#   只有 claude 身認，codex 身寫了＝CfgBad）。claude 用 Agent 工具叫出的子 agent 預設繼承主對話所有 MCP 工具；寫了 tools_sub＝
#   --agents 蓋掉內建的 general-purpose：disallowedTools mcp__aos（看不到主 agent 那台）、mcpServers 內嵌 aos_sub（另一隻 aos-mcp 接這份登記檔，
#   只有子 agent 連得到、主對話看不到），--allowedTools 加 mcp__aos_sub。其他類型的子 agent（Explore、Plan、外掛或使用者自己定義的）還是看得到
#   mcp__aos__*，由 PreToolUse hook（--settings，matcher mcp__aos__.*，本檔 guard）擋：hook 的輸入有 agent_id＝子 agent 叫的＝deny。
#   沒寫 tools_sub＝什麼都不加（子 agent 照 CLI 預設繼承全部）。flags 裡自己寫了 --agents 又寫 tools_sub＝CfgBad（兩個 --agents 只會留一個）。
#   模型（11-04 晚 think-as-function 03 § 2）：cli.json 同層的 llm.json（定義）疊 $AOS_STACK/llm.json（副本）的 model＝flags 的 --model（換掉或加在尾）；都沒有＝flags 原樣。
# 換台（11-10 two-machines 05）：要接舊對話前先認「是不是這台的」（session_here：記號檔的 session、home 一樣，claude 再比 ws；
#   不讀 CLI 的任何檔內容、不靠它的錯誤訊息）。不是＝在交出去之前改開新對話：呼叫者給了 reseed（aos-eca-turn）＝把 reseed(上限)
#   整理過的紀錄接在題目前面（上限＝cli.json 選填 reseed_bytes，預設 48000；畫面那條路取 min(它, 8000)）；沒給（工具形）＝stderr
#   一行 warning、照樣開新的。記號檔不在但 transcripts() 找得到＝功能上線前就在跑的，當這台的、補寫記號檔（過渡補丁）。
#   以為是這台的、resume 卻失敗而且 transcripts() 找不到那個 id＝刪 session.txt 與 .session_home 再報錯（那封掉了，下一封開新的）。
#   新對話第一輪就失敗、而 transcripts() 找不到這次的新 id（CLI 沒建出對話）＝同樣刪兩個檔（11-10 TS 9，T3 缺口 1）：
#   下一輪直接開新的，不再拿一封去 --resume 一個不存在的對話。畫面那條路沒這個情況（session.txt 由 hook 在一輪講完才寫）。
#   畫面（start）：session.txt 在但不是這台的＝刪兩個檔、不帶 --resume 開新的。人想重開＝手刪 session.txt（正式用法）。
# 開場白不歸這層（11-04 翻案，使用者「不該在json中指定檔案名稱，應該改成用旗標指定」）：是 aos-eca-turn 的 --prompt FILE；
#   cli.json 寫了 prompt 跟其他沒認的鍵一樣不看。
# 錯：aos-eca-turn --one（call_main）照 lib 契約 stderr 與 stdout 各一行「工具名: error: 代號 原因」、退 1；attach 與 hook 是 stderr 一行「cli_session: error: 代號 原因」、退 1。
#   CLI（claude／codex）與 tmux 自己的 stderr 原樣透到 stderr、不塞進自己的錯（stdio-unify R10）；stdout 只有自己那一行（D2）。
#   給人看的狀態句（attaching、等對話空出來）是提醒行「cli_session: warning: …」（R1、D5）。工具形認 --help（英文說明印 stdout、退 0）、Ctrl-C 退 130。
# 父死子跟著死（11-10 坑-52，Linux）：非互動起的 CLI 設 PR_SET_PDEATHSIG＝SIGTERM——起它的這支（aos-eca-turn、claude／codex 工具）
#   被 kill -9／OOM，CLI 收 SIGTERM 收掉，不留孤兒拿著同一段對話跟下一輪的 --resume 撞；非 Linux 或載不到 libc 就不設。畫面（tmux）不在此列。
#
# 放哪：proto8/lib/agent/cli_session.py；claude、codex 經 agent_tool.py 的 ask_cli 共用 ask，call_main 只給 aos-eca-turn --one；
# 掛它的 agent 根目錄可以放一份 cli_session.py（或捷徑）給 attach 用（原本的例子 demo/agent-fay 11-03 晚刪了）；工具資料夾自帶一份覆寫時，
# 要連同全部 cli_*.py（與 agent_files.py）一起帶（分檔彼此同層 import）。工具資料夾（cli.json 在裡面）由工具入口傳進來、
# agent 資料夾（attach 列 tools/）由 attach 傳進來——這支不再假設自己放在哪隻 agent 底下。
#
# 分檔（11-12 晚 R3 重構拆檔，行為不變）：本檔只留上面的說明與 hook／guard 的執行入口（hook 指令一直指著本檔，不能搬不能改名），
#   本體在同層：cli_base（錯誤行、PROG／ECHO、共用常數）、cli_cfg（cli.json、llm、system）、cli_mcp（aos 與外部 MCP、tools_sub、guard）、
#   cli_cell（小格、畫面 socket、session 記號）、cli_print（非互動）、cli_ask（畫面投信或送字、ask、call_main）、cli_hook（hook、history 同步）、
#   cli_screen（開畫面、attach）、cli_a2a（claude 畫面的收件 socket、署名信封、回執；11-13 加）。呼叫者直接 import 要用的分檔（例 cli_ask.ask、cli_cell.Cell）；執行期會被換掉或設定的只有
#   cli_base 的 die、warn、PROG、ECHO——各分檔一律寫 cli_base.die(…)，所以設 cli_base.X 一處就全部生效（agent_tool 設 PROG／ECHO、
#   aos-eca 換 die；測試 patch 定義那份，例 cli_ask.live、cli_cell.open）。
import sys

if __package__:
    from .cli_base import die
    from .cli_hook import hook_main
    from .cli_mcp import guard_main
else:
    from cli_base import die
    from cli_hook import hook_main
    from cli_mcp import guard_main


if __name__ == "__main__":
    if "--help" in sys.argv[1:2]:
        print("usage: cli_session.py hook claude|codex CELL [PAYLOAD]\n"
              "       cli_session.py guard\n"
              "The hook the CLI's interactive screen calls after each turn (appends to CELL/turns.jsonl; never fails).\n"
              "guard: claude PreToolUse hook (hook JSON on stdin); denies a subagent's call to the main agent's aos tools.\n"
              "The code is in the cli_*.py files next to this one; callers (tool entries, aos-eca) import those.")
    elif sys.argv[1:] == ["guard"]:
        guard_main()
    elif len(sys.argv) >= 4 and sys.argv[1] == "hook":
        hook_main(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    else:
        die("ArgumentsBad", "expected hook claude|codex CELL [PAYLOAD] (usage: cli_session.py hook claude|codex CELL [PAYLOAD]; see --help)")
