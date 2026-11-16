import sys
import json
import re
import time
import requests
from pathlib import Path
from dotenv import dotenv_values

# 定位到根目录 (src的上一级)
BASE_DIR = Path(__file__).resolve().parent.parent

# 全局日志记录器
RUN_LOGS = []

def get_config():
    """读取并校验 .env 配置"""
    env_path = BASE_DIR / ".env"
    config = dotenv_values(env_path)
    
    model_name = (config.get("MODEL_NAME") or "").strip()
    endpoint = (config.get("ENDPOINT") or "").strip()
    
    if not model_name or not endpoint:
        print("错误：.env 必须提供非空的 MODEL_NAME 和 ENDPOINT")
        sys.exit(2) 
        
    return model_name, endpoint

def parse_json_response(raw_text):
    """清洗大模型的回答并解析为 JSON (防止Markdown干扰)"""
    raw_text = raw_text.strip()
    # 去除可能存在的 Markdown 代码块标记
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    
    raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        # 正则兜底，提取第一个 { 到最后一个 }
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        raise ValueError("模型返回的内容无法解析为合法 JSON")

def call_llm(case_id, messages, retries=3, timeout=120):
    """封装大模型调用，带重试机制与日志记录"""
    model_name, endpoint = get_config()
    
    # 强制不走系统代理 (赛题要求)
    session = requests.Session()
    session.trust_env = False
    
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False
    }
    
    for attempt in range(retries):
        start_time = time.time()
        try:
            response = session.post(
                endpoint, 
                json=payload, 
                timeout=timeout,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            content = response.json()["choices"][0]["message"]["content"]
            
            # 记录成功日志
            RUN_LOGS.append({
                "case_id": case_id,
                "timestamp": start_time,
                "duration_seconds": round(time.time() - start_time, 2),
                "status": "success",
                "attempt": attempt + 1
            })
            return content
            
        except Exception as e:
            print(f"[{case_id}] 模型请求失败 (尝试 {attempt+1}/{retries}): {e}")
            # 最后一次重试失败也记录下来
            if attempt == retries - 1:
                RUN_LOGS.append({
                    "case_id": case_id,
                    "timestamp": start_time,
                    "duration_seconds": round(time.time() - start_time, 2),
                    "status": "failed",
                    "error": str(e)
                })
                raise Exception(f"MODEL_ERROR: {str(e)}")