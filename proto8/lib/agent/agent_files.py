"""agent_files - 依 aos-agent 公開宣告取得定義檔與 stack 覆蓋檔的相對位置。"""
import json
import os


def declared_files(folder):
    """未宣告介面＝空表；宣告的 tools／llm 只接受定義內相對檔名。"""
    path = os.path.join(folder, "interfaces.json")
    try:
        with open(path, encoding="utf-8") as stream:
            value = json.load(stream)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        raise ValueError("cannot read %s: %s" % (path, error)) from error
    if not isinstance(value, dict):
        raise ValueError("%s must be a JSON object" % path)
    decl = value.get("aos-agent", {})
    if not isinstance(decl, dict):
        raise ValueError("aos-agent in %s must be a JSON object" % path)
    result = {}
    for key in ("tools", "llm"):
        if key not in decl:
            continue
        rel = decl[key]
        if (not isinstance(rel, str) or not rel or os.path.isabs(rel)
                or ".." in rel.split("/") or os.path.isdir(os.path.join(folder, rel))):
            raise ValueError("%s in %s must name a file by a relative path inside the definition" % (key, path))
        result[key] = rel
    return result
