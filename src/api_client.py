import sys
import requests
from pathlib import Path
from dotenv import dotenv_values

# 定位到根目录（因为 api_client.py 在 src/ 里，所以要找它的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent

def get_config():
    """读取并校验 .env 配置"""
    env_path = BASE_DIR / ".env"
    config = dotenv_values(env_path)
    
    model_name = (config.get("MODEL_NAME") or "").strip()
    endpoint = (config.get("ENDPOINT") or "").strip()
    
    # 赛题要求：配置缺失必须返回退出码 2
    if not model_name or not endpoint:
        print("错误：.env 必须提供非空的 MODEL_NAME 和 ENDPOINT")
        sys.exit(2) 
        
    return model_name, endpoint

def call_llm(messages, retries=3, timeout=120):
    """封装大模型调用，带重试机制"""
    model_name, endpoint = get_config()
    
    # 关键：强制不走系统代理，防止封闭网络环境被代理拦截
    session = requests.Session()
    session.trust_env = False
    
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False
    }
    
    for attempt in range(retries):
        try:
            # 赛题要求：不能发 Authorization 头
            response = session.post(
                endpoint, 
                json=payload, 
                timeout=timeout,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            # 按 OpenAI 兼容格式提取文本
            content = response.json()["choices"][0]["message"]["content"]
            return content
            
        except Exception as e:
            print(f"模型请求失败 (尝试 {attempt+1}/{retries}): {e}")
            
    # 重试 3 次都失败，抛出异常，让主程序把该病例标记为 failed
    raise Exception("MODEL_TIMEOUT: 模型请求超时或失败")