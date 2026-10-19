import json, os, sys, urllib.request
body = {"model": os.environ.get("AOS_BRAIN_MODEL", "default"),
        "messages": [{"role": "user", "content": open(sys.argv[1]).read()}]}
req = urllib.request.Request(os.environ["AOS_BRAIN_URL"].rstrip("/") + "/chat/completions",
    json.dumps(body).encode(), {"Content-Type": "application/json",
    "Authorization": "Bearer " + os.environ.get("AOS_BRAIN_KEY", "none")})
print(json.load(urllib.request.urlopen(req, timeout=120))["choices"][0]["message"]["content"])
