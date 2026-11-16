import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("DASHSCOPE_API_KEY")
base_url = os.getenv("ENDPOINT")
model_name = os.getenv("MODEL_NAME")

print(f"使用的 Endpoint: {base_url}")
print(f"使用的模型名: {model_name}")
print(f"API Key 前几位: {api_key[:10] if api_key else '未读取到'}...")

if not all([api_key, base_url, model_name]):
    print("错误：.env 文件中缺少必要的配置项。")
    exit()

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": model_name,
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": False
}

try:
    response = requests.post(base_url, headers=headers, json=payload, timeout=30)
    print(f"HTTP 状态码: {response.status_code}")
    print("服务器返回内容:")
    print(response.text)
except Exception as e:
    print(f"请求发送失败: {e}")