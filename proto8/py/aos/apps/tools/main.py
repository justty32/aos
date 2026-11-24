"""aos-tools [--file F] add|rm|ls|get|call|override … — 管理工具登記（可 $override 另一份只記差異）、環境與小格，三種工具一律經 aos-exec 從 stdin 呼叫。

設計與代定：proto8/thinking/2026-10/28/aos-tools/README.md。白話：tools.json 是「這隻 agent 的工具通訊錄」，
aos agent 想問腦之前先 `aos-tools ls --json` 拿工具清單，腦要叫工具時 `aos-tools call 名`；
claude code 之類經 aos-mcp 吃同一份（aos-mcp 只是包在這支上面的翻譯櫃台）。
這支只留子命令與 main；同夾另有 helps（英文說明）、common（共用小零件）、tooldef（讀工具定義與快取）、registry（登記檔與 $override 疊法）。

    aos-tools [--file F] add [--replace] [--name N] [--no-cache] [--env-file FILE] [--envs K=V]... XXX|--path-json JSON
                                                           登記 XXX（檔或資料夾；相對路徑從 cwd 算），印 added NAME -> 絕對路徑 (寫進的檔: 存的原樣值)
    aos-tools [--file F] rm XXX                            每個拿掉的名字印 removed NAME (寫進的檔)；拿掉（XXX＝工具名；不是登記過的名字就當路徑，拿掉指到那裡的）
    aos-tools [--file F] ls [-l | --json]                  列：預設一行一支「名字 TAB 說明第一句」；-l＝「名字 TAB 種類 TAB 路徑 TAB FROM TAB STORED TAB ENV（只印名）」；--json＝一行 JSON 陣列（11-10 深夜使用者「默認是給出短板，然後用-l才是給長版」）
    aos-tools [--file F] get XXX                           一個工具一行 JSON：name、kind、path、tooldef、metainfo（有才給）
    aos-tools [--file F] call 名 [ARGS_JSON]               叫一次：ARGS_JSON（沒給＝stdin）原樣進工具的 stdin，stdout／結束碼＝工具的
    aos-tools [--file F] override (BASE...|--path-json J)  在 F 寫 "$override"：F 從此只記對 BASE 的差異（BASE 寫法同 XXX；多個＝陣列）
  --file 子命令前後都收（前後不同＝ArgumentsBad）；旗標寫在 XXX／名後面＝ArgumentsBad；沒給 --file 且 ./tools.json 不在＝讀的子命令印一行 warning（11-10 aos-tools-cli 步 1）。

註冊檔：--file ＞ ./tools.json。長這樣：{"tools": {"名": {"path": "/絕對/路徑"}, …}}；沒有這份檔＝沒登記任何工具。
  aos 讀的 JSON 都解指示詞（N-45）：檔裡有 $ref／$env 就交給 aos-json 解（`$ref` 陣列＝把註冊檔拆成好幾份），
  改的時候 aos-json set／del --follow 穿過 $ref 改被參照的那份。add 存路徑保留使用者的寫法（11-10 TC，使用者「要用相對位置、絕對位置、環境變數指定都可」）：
  給絕對＝存絕對；給相對（從 cwd 算）＝存成相對「寫進的那份檔（F）的資料夾」的相對；--path-json JSON＝原樣存（字串或指示詞，例
  '{"$env":"AOS_HOME","$path":"/lib/tools/base/shell"}'；現在解一次只為了驗與取名，解出來的值不寫回）。
  手寫的相對路徑從這份檔的資料夾算。
三種登記對象（種類照 aos-exec 認法，N-61：資料夾；檔有 +x＝可執行檔；檔沒 +x＝JSON）：
  dir   資料夾裡有 _tooldef.json，或 _metainfo.json 裡有 tooldef 鍵；_metainfo.json 有就一起給（11-04 起只認帶 .json 的：
        _ 開頭的資料檔一律帶副檔名，不帶的 _tooldef／_metainfo 不認——兩處都沒有＝ToolDefMissing）。叫＝aos-exec 資料夾，arguments 進 stdin。
        兩處都有（11-12 metainfo，N-69 推薦讀法）＝先讀 _metainfo 裡的 tooldef、再讀獨立的 _tooldef，頂層鍵淺合併、同名整鍵外面贏。
  json  JSON 檔（aos-exec 跑得動的那種）頂層要有 _tooldef 物件或 _metainfo.tooldef（合併同上）；_metainfo key 有就一起給。叫＝aos-exec 檔，arguments 進 stdin。
        也收 檔.json#/指標（11-10 深夜 tools-def，使用者「2.收」）：那個物件要有 _tooldef 或 _metainfo.tooldef（_metainfo 有就給），叫＝aos-exec 檔#/指標
        （照 aos-exec：跑那個物件的 _entry，cwd＝JSON 檔的資料夾，所以 _entry 裡的 python3 x.py 從 JSON 檔的資料夾算）。
        存法同上：只有 #/ 前面那段算相對／絕對，#/ 後面原樣存；預設名字＝指標最後一段（~1、~0 解開）。
  exe   python 或其他可執行檔：`XXX --tooldef` 在 stdout 吐工具定義（JSON 物件，10 秒內、退 0）；結果快取在
        $AOS_STACK/tooldef_cache.json（11-10 aos-tools-cli 步 2：{絕對路徑: {"stamp": "mtime奈秒-大小", "tooldef": …}}；
        stamp 相符就用，不符重跑並寫回（寫的是 stack，不是定義資料夾，P-15）；檔壞＝當沒有、重寫；
        AOS_STACK 沒設或不是資料夾＝不快取、不寫任何檔）。登記檔不再存快取。
        add --no-cache（11-03）＝那一項記 "cache": false：之後 ls／get 每次都重跑 --tooldef、不讀不寫快取檔
        （快取有時候礙事，例如定義是工具 import 的別的檔算出來的、檔本身沒變）。手寫也行（aos-json set …#/tools/名/cache false）。
        cache 只收 false，別的＝RegistryBad；dir／json 項寫 false＝RegistryBad、add --no-cache 給 dir／json＝ArgumentsBad。
        --replace 重登記時沒帶 --no-cache＝回到有快取（整項重寫）。
        叫＝aos-exec 檔，arguments 原樣從 stdin 進；三種工具都不要求呼叫方設 AOS_STACK。
"$override"（11-10 aos-tools-cli 步 4；使用者 Q4「"override":"../another_tools.json"」、N1「跟一般清單同形狀。想要rm的話，就是指定的key : null」、
  K1「現在就寫 $override」、「$override希望能支援array…跟$ref一樣」）：{"$override": BASE, "tools": {"名": {…}, "不要的": null}}（11-10 改口「null就是null，我們不做rm功能」「寫成 null，讀的人當它不是工具」）。
  BASE＝路徑字串（相對從這份檔的資料夾算、絕對）或指示詞物件（每次用到才交 aos-directive 解），或它們的陣列；空陣列＝沒有底檔。
  疊法＝照順序疊，後面蓋前面（使用者 11-10「都按你的建議」）：每個底檔先展開成它自己的序列，照陣列順序接起來，最後接這份自己的，一份一份補丁式往下合；
  物件逐 key 合，其餘（含 null）整個蓋過去——合併沒有刪除，null 只是值。讀的時候值是 null 的工具格不算工具；工具格裡值是 null 的欄位＝當沒設
  （所以只寫 {"env": {…}} 的同名格會沿用底檔的 path；add --replace 要整格換時用 null 蓋過底檔有、這次沒給的欄位）。
  底檔可以再 $override（鏈）；同一份經兩條路被引到＝序列裡出現兩次、照樣疊（菱形不算環）；環以真實路徑判、只看往上那幾層＝RegistryBad。
  底檔指不到（PathMissing）、不是 JSON 或不是物件（RegistryBad）、指示詞解不開（DirectiveBad）＝**只跳過那一份**（11-24，使用者「pack檔壞掉，那我是希望
  就是這個pack檔內的工具不能用，其他都可以用」）：它的工具不在清單上、其他照疊，stderr 每份一行 warning（pack … skipped (代號 原因); its tools are left out…），
  ls 多一行「!檔<TAB>broken pack: …」（--json 不列）；環與 aos-directive／aos-json 起不來照舊整份報錯；F 自己壞照舊 RegistryBad；頂層有 add／rm＝RegistryBad。
  tools 那格先照 lv0 解 $ref／$env（aos-json get --follow --resolve），再做 $override 合併；寫入只寫 F（aos-json set／del --follow），
  rm：只有 F 自己記的名字＝刪那個 key；底檔也有的＝在 F 寫 "名": null（成功行說是哪一種）；底檔一個位元組都不動。
  路徑指不到＝PathMissing，訊息帶工具名、解出的路徑與它來自哪份檔的哪一格（檔#/tools/名/path，檔＝寫那個 path 的那份）。
登記格選填 env（11-05 晚）：{"名": {"path": …, "env": {"LANG": "C.UTF-8"}}}，call 時合進那次呼叫的環境
  （蓋過外面同名的）；值照字面用、不當路徑解（C-56；要相對就靠讀它的工具自己的規則）。
  鍵只收 [A-Za-z_][A-Za-z0-9_]*、值只收字串（不含 NUL，11-05 晚邊緣測試：原本 call 時吐 traceback），別的＝RegistryBad。--envs K=V（可重複）存進 env。
  選填 env_file（11-10 aos-tools-cli 步 3，使用者 Q1「只記位置」）：add --env-file FILE 只記位置（寫法同 XXX：絕對存絕對、相對存相對寫進的那份檔），
  不存內容；add 當下檔在就讀一次只為驗格式與 hub 提醒，不在＝warning 照登記。每次 call 才讀（dotenv 基礎子集，${VAR} 照這次呼叫的環境展開），
  不在＝PathMissing 不跑（N4「報錯不跑」）、壞＝DotenvBad，訊息帶工具名與 檔#/tools/名/env_file。後面的贏：呼叫者環境 < env_file < env < AOS_STACK 小格。
  ls／get 不讀 env 檔、不印 env 值；ls -l 的 ENV 欄印 env 的名字與 @"存的 env_file"。
  用途：這隻自己那份（aos-agent tools add 寫的，$override 定義那份）也能替這一隻換知識庫，不必在定義裡做包裝資料夾。
call 的小格：父 AOS_STACK 非空時，子設成 <父 stack>/tools/<名>/，優先於登記 env；父沒設就不從登記 env 補 stack，交 aos-exec 給預設。
  小格只給路徑、不建（11-11 tool-cells-lazy，使用者「我確實想改成工具真的寫東西時才建資料夾」）：交 aos-exec --stack-lazy，工具要寫自己 mkdir -p。
  同時給 AOS_STACK_IN_CALLER=tools/<名>（11-13 使用者裁 fx-2:A）：小格在叫方 stack 裡的相對位置，每次 call 重設、優先於登記 env 與外面帶進來的；
  工具把自己小格裡的路徑印給叫方時寫成 $AOS_STACK/tools/<名>/…（tool_io.place 照它），叫方照自己的 stack 找得到。父沒設 AOS_STACK＝不給（外面有也拿掉）。
ls --json 保留完整 tooldef；腦／MCP 對模型只取 description／parameters，不把 env 等工具側欄位送給模型。
add 時工具定義 env 陣列列的 hub 若不在當下環境與這次 env-file／envs，印一行 warning，照樣登記退 0。
工具定義（_tooldef）：OpenAI function 物件去掉 name（{"description": 字串, "parameters": JSON Schema 物件}，兩個都可省）；其他 key 照收，只有 add 另驗選填 env 是合法變數名陣列。
工具名：--name ＞ 檔名去掉副檔名（資料夾＝資料夾名），只收 [A-Za-z0-9_-]、最多 64 字（OpenAI／MCP 的限制）。撞名＝ToolExists，--replace 蓋掉（使用者 11-10 N3「旗標改叫 --replace」）。
不符合要求一律報錯、不猜（add／get／call 碰到登記了但壞掉的工具報錯，訊息帶工具名）；ls 例外（11-12 tool-path-broken）：
  一支自己壞（路徑不在、定義缺或壞）＝略過那支、stderr 一行 warning（登記名、代號、怎麼修，不帶絕對路徑），其他照列、退 0；
  文字輸出把它標成 broken（短版「名 TAB broken: …」、-l 的 KIND＝broken），--json 不列。登記檔本身壞照舊整份報錯。
錯：stderr 一行「aos-tools: error: 代號 原因」、退 1（11-05 stdio-unify R1；錯誤行的括號只指那一層，11-06 human-cli H10：缺子命令列子命令名、子命令層接那個子命令的 usage）。代號：ArgumentsBad、FlagUnknown、CommandUnknown、RegistryBad、PathMissing、
  ToolDefMissing、ToolDefBad、NameBad、ToolExists、ToolMissing、DotenvBad、DirectiveBad、CommandMissing、WriteFailed。call 自己沒錯時結束碼是工具的
  （R8：退非 0 時 stderr 有 `aos-tools: error:` 這行＝這支錯；沒有＝工具的碼；工具被訊號殺＝128＋N）。
`--help`＝印該層 HELP／HELPS（英文）到 stdout、退 0（子命令後印該子命令的）；不給子命令＝ArgumentsBad；Ctrl-C＝退 130、不吐 traceback。
"""
import json, os, re, shutil, subprocess, sys, tempfile
from aos import flags as aos_flags
from aos.env_file import Error as EnvFileError, read_env_file
from .common import ENV_KEY_RE, NAME, NAME_RE, Fail, split_ptr, norm_loc, ptr_name
from .helps import HELP, HELPS
from .registry import (OVERRIDE_KEY, SKIPPED, aos_json, base_tools, load_tools, make_dir_of, match, merged_tools, nulled, use_once,
                       own_tools, read_layer, resolve_path_value, write_entry, write_new)
from .tooldef import describe, inspect, kind_of

TOP_FILE = None                                      # 子命令前的 --file；子命令後也收（11-10 aos-tools-cli 甲1）
DEFAULT_FILE = "tools.json"
aos_flags.HELP = HELP


USAGE_STOP = ("aos-tools ", "echo ")   # help 裡第二種寫法的開頭：usage 接到這裡停


def usage(sub):
    """子命令 help 的第一種 usage 接成一行（規則在 aos_flags.usage_of）。"""
    return aos_flags.usage_of(HELPS[sub], USAGE_STOP)


def parse_sub(sub, args, flags=None, switches=None, multi=None, short=None):
    """子命令的旗標；--file 子命令前後都收，前後都給且不同＝ArgumentsBad（11-10 aos-tools-cli 甲1）。
    回 (登記檔, opts, rest)；兩邊都沒給＝./tools.json，那時 ls／get／call／rm 碰到檔不在印一行提醒（甲3）。"""
    opts, rest = aos_flags.parse(args, dict(flags or {}, **{"--file": "file"}), switches, multi,
                                 help=HELPS[sub], short=short)
    here = opts.pop("file", None)
    if here is not None and not here:
        raise Fail("ArgumentsBad", "--file must not be empty")
    if here is not None and TOP_FILE is not None and os.path.abspath(here) != os.path.abspath(TOP_FILE):
        raise Fail("ArgumentsBad", "--file given before and after %s with different values (%s, %s)" % (sub, TOP_FILE, here))
    reg = here or TOP_FILE
    if reg is None:
        reg = DEFAULT_FILE
        if sub not in ("add", "override") and not os.path.exists(reg):
            aos_flags.warn(NAME, "./%s not found; no tools (use --file F)" % DEFAULT_FILE)
    return reg, opts, rest


def tools_of(reg):
    """load_tools，加上 11-24：$override 疊進來壞掉而被跳過的那幾份，stderr 各一行 warning（一次執行只說一次）。"""
    tools = load_tools(reg)
    for rec in SKIPPED:
        if not rec.get("warned"):
            rec["warned"] = True
            aos_flags.warn(NAME, skipped_text(rec))
    return tools


def skipped_text(rec):
    where = "%s (from %s)" % (rec["file"], rec["at"]) if rec.get("file") else rec["at"]
    return "pack %s skipped (%s %s); its tools are left out, the other tools work; fix that file or take it out of %s" % (
        where, rec["code"], rec["reason"], OVERRIDE_KEY)


def cmd_add(args):
    reg, opts, rest = parse_sub("add", args, {"--name": "name", "--env-file": "env_file", "--path-json": "path_json", "--uses": "uses"},
                                {"--replace": "replace", "--no-cache": "no_cache"},
                                {"--envs": "envs"}, short=("-n",))
    if "path_json" in opts:
        if rest:
            raise Fail("ArgumentsBad", "add takes either XXX or --path-json, not both")
    elif len(rest) != 1:
        raise Fail("ArgumentsBad", "add needs one XXX (or --path-json JSON)")
    uses = None
    if "uses" in opts:                               # 11-24：成功叫過 N 次就從清單拿掉（1＝once、2＝twice）
        if not re.fullmatch(r"[1-9][0-9]{0,8}", opts["uses"]):
            raise Fail("ArgumentsBad", "--uses needs a whole number >= 1 (successful calls before it is taken off the list), got %r" % opts["uses"])
        uses = int(opts["uses"])
    env = {}
    for kv in opts.get("envs", []):
        k, eq, v = kv.partition("=")
        if not eq or not ENV_KEY_RE.match(k) or "\0" in v:
            raise Fail("ArgumentsBad", "--envs needs NAME=VALUE with a valid name and no NUL")
        env[k] = v
    folder = os.path.dirname(os.path.abspath(reg))   # 存的相對路徑從這裡算（讀的時候也是）
    env_file, file_names = None, {}                  # 11-10 步 3（使用者 Q1）：--env-file 只記位置，寫法同 XXX；call 才讀
    if "env_file" in opts:
        given = opts["env_file"]
        if not given or "\0" in given:
            raise Fail("ArgumentsBad", "--env-file needs a non-empty path")
        absf = os.path.normpath(os.path.abspath(given))
        env_file = absf if os.path.isabs(given) else os.path.relpath(absf, folder)
        if os.path.exists(absf):
            try:
                file_names = read_env_file(absf)     # 只為驗格式與下面的 hub 提醒，內容不存
            except EnvFileError as e:
                raise Fail(e.code, str(e)) from None
        else:
            aos_flags.warn(NAME, "env file %s not found yet; registered anyway (it is read on every call)" % absf)
    if "path_json" in opts:                          # 指示詞（或字串）原樣存；現在解一次只為了驗與取名
        try:
            stored = json.loads(opts["path_json"])
        except ValueError as e:
            raise Fail("ArgumentsBad", "--path-json is not JSON: %s" % e)
        path = resolve_path_value(stored, folder)
    else:
        given = rest[0]
        path = norm_loc(os.getcwd(), given)
        if os.path.isabs(given):
            stored = path                            # 給絕對＝存絕對
        else:                                        # 給相對（從 cwd 算）＝存相對登記檔資料夾的相對；#/ 後面原樣
            f, ptr = split_ptr(path)
            stored = os.path.relpath(f, folder) + ("" if ptr is None else "#" + ptr)
    if opts.get("no_cache") and kind_of(path) != "exe":
        raise Fail("ArgumentsBad", "--no-cache is only for executables (exe); %s is %s, which has no cache anyway" % (path, kind_of(path)))
    info = inspect(path, False if opts.get("no_cache") else None)
    hubs = info["tooldef"].get("env", [])
    if not isinstance(hubs, list) or not all(isinstance(k, str) and ENV_KEY_RE.match(k) for k in hubs):
        raise Fail("ToolDefBad", "%s: tool definition env must be an array of variable names" % path)
    name = opts.get("name") or (os.path.basename(path) if info["kind"] == "dir"
                                else ptr_name(split_ptr(path)[1]) if split_ptr(path)[1] is not None
                                else os.path.splitext(os.path.basename(path))[0])
    if not NAME_RE.fullmatch(name):
        raise Fail("NameBad", "tool name %r is invalid (only [A-Za-z0-9_-], at most 64 chars; pick another with --name)" % name)
    tools = tools_of(reg)
    if name in tools and not opts.get("replace"):
        raise Fail("ToolExists", "%s is already registered (points to %s); add --replace to replace it" % (name, tools[name]["path"]))
    entry = {"path": stored}
    if env:
        entry["env"] = env
    if env_file is not None:
        entry["env_file"] = env_file
    if opts.get("no_cache"):                         # 只有 --no-cache 才寫；定義快取在 stack，不進登記檔（步 2）
        entry["cache"] = False
    if uses is not None:
        entry["uses"] = uses
    below = base_tools(reg).get(name)                # 步 4：補丁式往下合，要整格換就用 null 蓋過底檔那格有、這次沒給的欄位
    if below is not None:
        for k, v in below["entry"].items():
            if v is not None:
                entry.setdefault(k, None)
    write_entry(reg, name, entry)
    written = reg
    missing = [k for k in dict.fromkeys(hubs) if k not in os.environ and k not in env and k not in file_names]
    if missing:
        aos_flags.warn(NAME, "tool %s has unset hub variables: %s" % (name, ", ".join(missing)))
    # 甲4：說出寫進哪份檔、存的原樣值（指示詞就印那段 JSON）
    print("added %s -> %s (%s: %s)" % (name, path, written, json.dumps(stored, ensure_ascii=False)))


def cmd_rm(args):
    reg, opts, rest = parse_sub("rm", args)
    if len(rest) != 1:
        raise Fail("ArgumentsBad", "rm needs one XXX")
    names = match(tools_of(reg), rest[0])
    below, own = base_tools(reg), own_tools(reg)     # 步 4：只寫 reg，底檔位元組不動
    done = []
    for n in names:
        if n in below:                               # 底檔有同名＝在 reg 寫 "名": null（值是 null 的那格不算工具）
            write_entry(reg, n, None)
            done.append((n, "set to null over %s" % below[n]["last"]))
        else:                                        # 只有 reg 自己記的＝刪那個 key
            aos_json(["del", "--follow", "%s#/tools/%s" % (reg, n)])
            done.append((n, "key deleted"))
    for n, how in done:
        print("removed %s (%s: %s)" % (n, reg, how))


def cmd_override(args):
    """override (BASE... | --path-json JSON)：在 F 寫 "$override"（11-10 步 4，使用者 Q4／N1）。F 不在＝新建；
    F 已有 $override＝改指標；F 沒有 $override 卻有自己的工具＝RegistryBad。寫之前先照新指標整份讀一次（指不到、環、壞檔都先報）。"""
    reg, opts, rest = parse_sub("override", args, {"--path-json": "path_json"})
    folder = os.path.dirname(os.path.abspath(reg))
    if "path_json" in opts:
        if rest:
            raise Fail("ArgumentsBad", "override takes either BASE... or --path-json, not both")
        try:
            pointer = json.loads(opts["path_json"])
        except ValueError as e:
            raise Fail("ArgumentsBad", "--path-json is not JSON: %s" % e)
    else:
        if not rest:
            raise Fail("ArgumentsBad", "override needs at least one BASE (or --path-json JSON)")
        stored = [os.path.normpath(os.path.abspath(b)) if os.path.isabs(b)
                  else os.path.relpath(os.path.abspath(b), folder) for b in rest]
        pointer = stored[0] if len(stored) == 1 else stored
    if os.path.exists(reg):
        raw = read_layer(reg)[0]
        own = raw.get("tools")
        if OVERRIDE_KEY not in raw and own not in (None, {}):
            raise Fail("RegistryBad", "%s lists tools of its own and has no %s; override would change what it means "
                       "(start a new file with --file NEW override BASE)" % (reg, OVERRIDE_KEY))
        new = dict({OVERRIDE_KEY: pointer}, **{k: v for k, v in raw.items() if k != OVERRIDE_KEY})
    else:
        new = {OVERRIDE_KEY: pointer, "tools": {}}
    del SKIPPED[:]
    merged_tools(reg, dict(new, tools={}))           # 只驗底檔：指不到＝PathMissing、環＝RegistryBad、底檔壞＝帶來源的錯
    if SKIPPED:                                      # 讀的時候壞的那份只跳過（11-24）；寫新指標時照舊先報、不寫
        r = SKIPPED[0]
        raise Fail(r["code"], r["reason"] if "file" not in r else "%s (from %s)" % (r["reason"], r["at"]))
    make_dir_of(reg)
    write_new(reg, new)
    print("%s %s -> %s" % (reg, OVERRIDE_KEY, json.dumps(pointer, ensure_ascii=False)))


def env_column(t):
    """ls -l 的 ENV 欄：只印變數名（值不印，維持「值不給腦看」）；沒有＝-。"""
    names = sorted(t["entry"].get("env", {}))
    if "env_file_stored" in t:                       # 步 3：env 檔印存的原樣位置（JSON），不讀它
        names.append("@" + json.dumps(t["env_file_stored"], ensure_ascii=False))
    return ",".join(names) or "-"


def first_sentence(tooldef):
    """ls 預設用（11-10 使用者「好，有需要的再自己去看細項」；深夜「默認是給出短板」）：description 第一行、到第一個「. 接大寫」為止（含句點，e.g. 不算）；沒有＝-。"""
    d = tooldef.get("description") if isinstance(tooldef, dict) else None
    if not isinstance(d, str) or not d.strip():
        return "-"
    line = d.strip().splitlines()[0].strip()
    m = re.search(r"\.\s+(?=[A-Z])", line)
    return line[:m.start() + 1] if m else line


BROKEN_WHY = {"PathMissing": "its path does not exist", "ToolDefMissing": "no tool definition there",
              "ToolDefBad": "its tool definition is broken", "DirectiveBad": "its path directive cannot be resolved",
              "RegistryBad": "its entry is invalid"}


def broken_text(name, code):
    """壞掉那支的一句（11-12 tool-path-broken）：登記名、代號、白話原因、怎麼修；不帶絕對路徑（完整原因看 get NAME）。"""
    return "%s (%s); correct its path or take it off the list with rm %s (get %s shows the full error)" % (
        code, BROKEN_WHY.get(code, "it cannot be read"), name, name)


def listed(tools):
    """ls 用：逐支 describe；一支自己的問題（路徑不在、定義缺或壞…）＝略過那支、stderr 一行 warning，其他照常
    （11-12 tool-path-broken，比照使用者 11-12 對 index_view 的裁定「_metainfo.json 壞掉時，index_view 對那個資料夾不該直接報錯。」）。
    CommandMissing（aos-json 起不來）不是那支自己的問題，照舊整份報錯。回 (好的 [describe…], {壞的名: 代號})。"""
    good, broken = [], {}
    for n in sorted(tools):
        try:
            good.append(describe(n, tools[n]))
        except Fail as e:
            if e.code == "CommandMissing":
                raise
            broken[n] = e.code
            aos_flags.warn(NAME, "tool %s skipped: %s" % (n, broken_text(n, e.code)))
    return good, broken


def cmd_ls(args):
    reg, opts, rest = parse_sub("ls", args, None, {"--json": "json", "--long": "long"},
                                short={"-j": "--json", "-l": "--long"})
    if rest:
        raise Fail("ArgumentsBad", "ls takes no arguments")
    if opts.get("json") and opts.get("long"):
        raise Fail("ArgumentsBad", "ls takes one of -l, --json")
    tools = tools_of(reg)
    found, broken = listed(tools)                    # 壞的那支：--json 不列（叫得到的才列），文字兩種標 broken
    if opts.get("json"):
        print(json.dumps(found, ensure_ascii=False))
    elif opts.get("long"):                           # 甲5：FROM（檔#/格/名）、STORED（存的原樣值）、ENV（只印名）
        off = nulled(reg)
        rows = [(t["name"], t) for t in found] + [(n, None) for n in off] + [(n, "broken") for n in broken]
        for name, t in sorted(rows, key=lambda r: r[0]):
            if t is None:                            # 被 null 關掉的格：KIND null、PATH＝它蓋掉的那支（不知道＝-）、FROM＝寫 null 的那份
                f, hid = off[name]
                print("\t".join((name, "null", hid or "-", "%s#/tools/%s" % (f, name), "null", "-")))
                continue
            src = tools[name]                        # 壞的那支：KIND＝broken，其餘欄照登記格（路徑是解出來、指不到的那個）
            print("\t".join((name, "broken" if t == "broken" else t["kind"], src["path"], src["src"],
                             json.dumps(src["stored"], ensure_ascii=False), env_column(src))))
    else:
        rows = [(t["name"], first_sentence(t["tooldef"]) + (" [uses left: %d]" % t["uses"] if "uses" in t else "")) for t in found] + \
               [("!" + (r.get("file") or r["at"]), "broken pack: " + skipped_text(r)) for r in SKIPPED] + \
               [(n, "broken: " + broken_text(n, c)) for n, c in broken.items()]
        for name, line in sorted(rows):
            print("%s\t%s" % (name, line))


def cmd_get(args):
    reg, opts, rest = parse_sub("get", args)
    if len(rest) != 1:
        raise Fail("ArgumentsBad", "get needs one XXX")
    tools = tools_of(reg)
    for n in match(tools, rest[0]):
        print(json.dumps(describe(n, tools[n]), ensure_ascii=False))


def stdin_from(text):
    """call NAME ARGS_JSON（甲6）：把 ARGS_JSON 原樣（不驗）放進一個已刪掉名字的暫存檔，接到 fd 0，exec 後工具照常從 stdin 讀。"""
    try:
        f = tempfile.TemporaryFile()
        f.write(text.encode("utf-8", "surrogateescape"))
        f.seek(0)
        os.dup2(f.fileno(), 0)
        f.close()
    except OSError as e:
        raise Fail("WriteFailed", "cannot hand ARGS_JSON to the tool's stdin: %s" % e)


def cmd_call(args):
    reg, opts, rest = parse_sub("call", args)
    if len(rest) not in (1, 2):
        raise Fail("ArgumentsBad", "call needs NAME and optional ARGS_JSON (else stdin = arguments)")
    tools = tools_of(reg)
    name = rest[0]
    if name not in tools:
        raise Fail("ToolMissing", "%s is not registered (available: %s)" % (name, ", ".join(sorted(tools)) or "none"))
    if not NAME_RE.fullmatch(name):
        raise Fail("RegistryBad", "registered tool name %r is invalid (only [A-Za-z0-9_-], at most 64 chars)" % name)
    path = tools[name]["path"]
    try:
        kind_of(path)                                # 只驗路徑；三種工具走同一條執行路，不擴充登記對象
    except Fail as e:
        raise Fail(e.code, "tool %s (from %s): %s" % (name, tools[name].get("field", "?"), e))
    env = dict(os.environ)                           # 後面的贏：呼叫者環境 < env_file < env < AOS_STACK 小格
    ef = tools[name].get("env_file")
    if ef is not None:                               # 步 3：每次 call 才讀；不在＝報錯不跑（使用者 11-10 N4「報錯不跑」）
        where = tools[name]["src"] + "/env_file"
        if not os.path.isfile(ef):
            raise Fail("PathMissing", "tool %s: env file %s (from %s) does not exist" % (name, ef, where))
        try:
            env.update(read_env_file(ef))
        except EnvFileError as e:
            raise Fail(e.code, "tool %s (from %s): %s" % (name, where, e))
    env.update(tools[name]["entry"].get("env", {}))
    stack = os.environ.get("AOS_STACK")
    lazy = []
    if stack:
        env["AOS_STACK"] = os.path.join(os.path.abspath(stack), "tools", name, "")
        lazy = ["--stack-lazy"]                       # 11-11 tool-cells-lazy：小格只給路徑、不先建，工具真的要寫才自己建
        env["AOS_STACK_IN_CALLER"] = os.path.join("tools", name)   # 11-13 fx-2：小格在叫方 stack 裡的相對位置，工具印路徑照它（tool_io.place）
    else:
        env.pop("AOS_STACK", None)                    # 登記格不能代替父 stack；沒設交 aos-exec 給預設
        env.pop("AOS_STACK_IN_CALLER", None)          # 沒有父 stack＝沒有「在叫方裡的位置」；外面帶進來的舊值不往下傳
    exe = shutil.which("aos-exec")                    # 自己找：避免 execvp 只報 PATH 最後一格
    if exe is None:
        raise Fail("CommandMissing", "no executable aos-exec on PATH")
    if len(rest) == 2:
        stdin_from(rest[1])
    if "uses" in tools[name]:                         # 11-24 add --uses：要知道成功沒，所以當子行程跑、等它，成功才倒數
        if os.path.realpath(tools[name]["uses_file"]) != os.path.realpath(reg):
            raise Fail("RegistryBad", "tool %s: uses is written in %s, which %s only overrides; it is counted down only in the "
                       "registry given to aos-tools (add it with --uses there)" % (name, tools[name]["uses_file"], reg))
        counted_call(exe, lazy, path, env, tools[name]["uses_file"], name)
    try:
        os.execve(exe, ["aos-exec"] + lazy + [path], env)         # 三種工具都原樣保留 stdin、stdout 與結束碼
    except OSError as e:
        raise Fail("CommandMissing", "%s cannot start: %s" % (exe, e.strerror or e))


def counted_call(exe, lazy, path, env, holder, name):
    """登記格有 uses 的那支：子行程跑（stdin、stdout、stderr 原樣接著），TERM／INT／HUP 轉給它；退 0＝寫著 uses 的那份檔倒數一
    （到 0 刪那格，registry.use_once）；退非 0、被訊號殺＝不算。結束碼照工具的（訊號 N＝128+N），跟 execve 那條一樣。"""
    import signal
    try:
        proc = subprocess.Popen(["aos-exec"] + lazy + [path], executable=exe, env=env)
    except OSError as e:
        raise Fail("CommandMissing", "%s cannot start: %s" % (exe, e.strerror or e))
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, lambda s, _f: proc.send_signal(s))
    code = proc.wait()
    if code == 0:
        try:
            left = use_once(holder, name)
        except (Fail, OSError) as e:
            aos_flags.warn(NAME, "tool %s ran, but its uses could not be counted down in %s: %s" % (name, holder, e))
        else:
            if left == 0:
                aos_flags.warn(NAME, "tool %s is used up and was taken off the list (%s)" % (name, holder))
    sys.stdout.flush()
    os._exit(code if code >= 0 else 128 - code)


COMMANDS = {"add": cmd_add, "rm": cmd_rm, "ls": cmd_ls, "get": cmd_get, "call": cmd_call, "override": cmd_override}


def main():
    global TOP_FILE
    sub = None
    try:
        try:
            opts, rest = aos_flags.parse(sys.argv[1:], {"--file": "file"}, sub="root")   # 11-10 Q1：子命令的旗標寫在 XXX／NAME 後也收
        except aos_flags.Error as e:
            reason = str(e) if e.code == "FlagUnknown" else "%s (see %s --help)" % (e, NAME)
            raise Fail(e.code, reason)
        if opts.get("file") is not None:
            if not opts["file"]:
                raise Fail("ArgumentsBad", "--file must not be empty (see %s --help)" % NAME)
            TOP_FILE = opts["file"]
        choices = ", ".join(COMMANDS) + "; see " + NAME + " --help"
        if not rest:
            raise Fail("ArgumentsBad", "missing subcommand (%s)" % choices)
        if rest[0] not in COMMANDS:
            raise Fail("CommandUnknown", "unknown subcommand %s (%s)" % (rest[0], choices))
        sub = rest[0]
        try:
            COMMANDS[sub](rest[1:])
        except aos_flags.Error as e:
            if e.code == "FlagUnknown":
                raise Fail(e.code, "%s (see %s %s --help)" % (e, NAME, sub))
            raise Fail(e.code, "%s (usage: %s)" % (e, usage(sub)))
    except Fail as e:
        reason = str(e)
        if sub is not None:
            reason = aos_flags.with_usage(HELPS[sub], e.code, reason, USAGE_STOP)
        aos_flags.die(NAME, e.code, reason)


if __name__ == "__main__":
    aos_flags.run(main)
