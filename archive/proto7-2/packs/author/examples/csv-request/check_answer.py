"""獨立核對 CSV 答案、完成證據與產物雜湊；路徑相對 node。"""
import csv
import hashlib
import json
import sys
from pathlib import Path


def check_answer(job_dir, input_csv):
    """回傳檢查結果，讀檔或格式錯誤一律列為 issue。"""
    issues = []

    def require(ok, why):
        if not ok:
            issues.append(why)

    def load(path):
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)

    def near(actual, expected):
        return type(actual) in (int, float) and abs(actual - expected) < 1e-9

    try:
        job = Path(job_dir)
        steps = load(job / "steps.json")
        # 步名由候選決定：照 argv 裡的腳本找出 convert／stats 兩步
        name = {}
        for sid, body in steps["steps"].items():
            for script in ("convert", "stats"):
                if f"${{job}}/{script}.py" in body.get("run", []):
                    name[script] = sid
        for script in ("convert", "stats"):
            require(script in name, f"steps.json 缺少跑 {script}.py 的步")

        # 答案只從原始 CSV 計算。
        by_dept, rows = {}, 0
        with Path(input_csv).open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if not {"name", "dept", "amount"}.issubset(reader.fieldnames or []):
                raise ValueError("CSV 缺少 name、dept 或 amount 欄")
            for row in reader:
                if any(row[key] is None for key in ("name", "dept", "amount")):
                    raise ValueError("CSV 列缺少欄位值")
                amount = float(row["amount"])
                group = by_dept.setdefault(row["dept"], {"n": 0, "sum": 0.0})
                group["n"] += 1
                group["sum"] += amount
                rows += 1
        for group in by_dept.values():
            group["avg"] = round(group["sum"] / group["n"], 2)

        report = load(job / "out/report.json")
        require(type(report["rows"]) is int and report["rows"] == rows,
                "report.rows 與 CSV 列數不符")
        require(set(report["by_dept"]) == set(by_dept), "report.by_dept 部門集合不符")
        for dept, expected in by_dept.items():
            actual = report["by_dept"].get(dept, {})
            require(type(actual.get("n")) is int and actual.get("n") == expected["n"],
                    f"{dept}: n 不符")
            for key in ("sum", "avg"):
                require(near(actual.get(key), expected[key]), f"{dept}: {key} 不符")

        frame = load(job / "frame.json")
        require(frame["phase"] == "ended" and frame["end"] == "ok", "frame 尚未成功結束")
        require(report["from"] == frame["accepted"][name["convert"]]["request"],
                "report.from 與採用的 convert request 不符")
        for script, output in (("convert", "data.json"), ("stats", "report.json")):
            step = name[script]
            accepted = frame["accepted"][step]
            files = [p for p in (job / "results" / step).glob("*.json")
                     if not p.name.startswith(".")]
            require(len(files) == 1, f"results/{step} 應恰有一個 JSON 結果檔")
            request = accepted["request"]
            require(frame["tries"][request] == 1, f"{step}: tries 不為 1")
            require(frame.get("resends", {}).get(request, 0) == 0, f"{step}: 曾重送")
            if len(files) != 1:
                continue
            result = load(files[0])
            for key, expected in (("job", frame["job"]), ("inst", frame["inst"]),
                                  ("step", step), ("request", request),
                                  ("attempt", accepted["attempt"])):
                require(result[key] == expected, f"{step}: 結果 {key} 不符")
            require(result["ok"] is True, f"{step}: 結果 ok 不為 true")
            require(type(result["code"]) is int and result["code"] == 0,
                    f"{step}: 結果 code 不為 0")
            artifacts = result["artifacts"]
            target = (job / "out" / output).resolve()
            require(any(Path(p).resolve() == target for p in artifacts),
                    f"{step}: artifacts 缺少 out/{output}")
            for path, expected in artifacts.items():
                digest = hashlib.sha256()
                with Path(path).open("rb") as stream:
                    for chunk in iter(lambda: stream.read(65536), b""):
                        digest.update(chunk)
                require(digest.hexdigest() == expected, f"{step}: {path} sha256 不符")
    except Exception as exc:
        issues.append(f"檢查失敗（{type(exc).__name__}）：{exc}")
    return {"ok": not issues, "issues": issues}


if __name__ == "__main__":
    answer = (check_answer(*sys.argv[1:]) if len(sys.argv) == 3 else
              {"ok": False, "issues": ["用法：check_answer.py <job_dir> <input_csv>"]})
    print(json.dumps(answer, ensure_ascii=False))
    sys.exit(0 if answer["ok"] else 1)
