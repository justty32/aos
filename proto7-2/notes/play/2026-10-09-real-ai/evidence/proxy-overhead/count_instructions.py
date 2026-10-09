"""數 LiteLLM 內建 Codex 系統提示的 token（o200k_base）。只讀，不連網路以外的東西。
用法：<litellm 的 venv>/bin/python -I count_instructions.py <site-packages 路徑>
"""
import sys
import tiktoken

site = sys.argv[1]
src = open(f'{site}/litellm/llms/chatgpt/common_utils.py', encoding='utf-8').read()
start = src.index('CHATGPT_DEFAULT_INSTRUCTIONS = ')
end = src.index('"""', start + 35) + 3
ns = {}
exec(src[start:end], ns)
text = ns['CHATGPT_DEFAULT_INSTRUCTIONS']
enc = tiktoken.get_encoding('o200k_base')
short = 'You are a helpful assistant. You have no tools; answer directly.'
print(f'default: {len(text)} chars, {len(enc.encode(text))} tokens')
print(f'short:   {len(short)} chars, {len(enc.encode(short))} tokens')
