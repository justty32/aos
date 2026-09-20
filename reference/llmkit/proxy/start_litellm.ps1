# 啟動 litellm proxy，預設吃同目錄的 litellm.yaml。
# 用 uv run 臨時把 litellm 拉進來跑，不用先裝、也不用維護 venv。
#
# litellm 釘死 1.87.5，原因與舊教訓見 start_litellm.sh 開頭註解（兩支腳本要同步改）。
param([string]$Config = "$PSScriptRoot\litellm.yaml", [int]$Port = 4000)

uv run --no-project --with 'litellm[proxy]==1.87.5' litellm --config $Config --port $Port
exit $LASTEXITCODE
