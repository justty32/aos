agent-bob/
  info.json
  state.json
  prompt.json
  prompts/
    system.json
    history.json
  tools/
    base.json
    team.json
  tools.json
  engine.json

info.json:
{
  "_metainfo":{
    "_type":"agent",
    "_version":1
  }
  "name":"bob"
}

state.json:
{
  "state":"idle"
}

prompt.json:
{
  "system":"prompts/system.json",
  "history":"prompts/history.json"
}
system.json:
{
  
}
