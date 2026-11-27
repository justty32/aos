#!/bin/bash
# Runs inside a proc with exactly pi's sky (no LLM): tries the things pi must not be able to do, one line "NAME<TAB>ok|blocked<TAB>detail" each.

# REAL_HOME and REPO (paths outside the sky) come in the env from run.py.

out() { printf '%s\t%s\t%s\n' "$1" "$2" "$(printf '%s' "$3" | tr '\n\t' '  ' | cut -c1-200)"; }

try() {  # try NAME COMMAND...: ok if the command succeeds
  local name=$1; shift
  local msg
  if msg=$("$@" 2>&1); then out "$name" ok "$msg"; else out "$name" blocked "$msg"; fi
}

# 1. the outside network
try net_dns_example curl -sS -m 5 -o /dev/null https://example.com
try net_ip_1111 curl -sS -m 5 -o /dev/null http://1.1.1.1/
# 2. user files outside the work dir
try home_ssh ls -la "$REAL_HOME/.ssh"
try repo_agents wc -c "$REPO/AGENTS.md"
try real_pi_config wc -c "$REAL_HOME/.pi/agent/auth.json"   # size only: never print a credential
try root_listing ls /
# 3. the LLM API without /llm
try llm_litellm_tcp curl -sS -m 5 -o /dev/null http://127.0.0.1:4000/v1/models
try llm_anthropic_api curl -sS -m 5 -o /dev/null https://api.anthropic.com/v1/messages
try llm_openai_api curl -sS -m 5 -o /dev/null https://api.openai.com/v1/models
# the legitimate path (GET models is answered by the proxy itself, no model is called)
try llm_via_sock curl -sS -m 5 --unix-socket /llm/sock http://llm/v1/models
# a model the proxy does not allow (refused before any upstream call)
try llm_bad_model curl -sS -m 5 -f --unix-socket /llm/sock -H 'Content-Type: application/json' \
  -d '{"model":"claude-opus-5-5","messages":[{"role":"user","content":"hi"}]}' http://llm/v1/chat/completions
# writing outside the work dir
try write_root touch /x
try write_usr touch /usr/x
try write_llm touch /llm/x
try write_work touch /work/.probe-ok
rm -f /work/.probe-ok
# what /proc (if the sky has it) tells about the outside
if [ -d /proc/1 ]; then
  try proc1_root ls /proc/1/root/
  try proc1_net_tcp sh -c 'wc -l < /proc/1/net/tcp'
else
  out proc_present blocked "no /proc in this sky"
fi
