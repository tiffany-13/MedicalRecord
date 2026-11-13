import sys
import json
import re
import time
import requests
from pathlib import Path
from dotenv import dotenv_values
import os

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

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('DASHSCOPE_API_KEY')}"
    }
    
    for attempt in range(retries):
        start_time = time.time()
        try:
            response = session.post(
                endpoint, 
                json=payload, 
                timeout=timeout,
                headers=headers
            )

            print(f"\n【DEBUG服务器返回】: {response.text}\n") 
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

def mock_llm_success(case_id, messages):
    """
    一个专门用来本地测试的模拟函数。
    它不发送网络请求，而是直接返回一个预先写好的、格式合规的 JSON 字符串。
    """
    # 记录一条成功的运行日志，模拟真实调用的痕迹
    RUN_LOGS.append({
        "case_id": case_id,
        "timestamp": time.time(),
        "duration_seconds": 0.1,
        "status": "success",
        "attempt": 1
    })
    
    # 这是根据 DEMO001 案例，完全按照赛题要求（5个字段）手写的标准答案
    # 注意：它是一个字符串，不是 Python 字典
    mock_response_json = """
    {
      "case_features": "成人，近2周乏力、活动后心悸，现有记录显示结膜苍白和双下肢轻度水肿。血红蛋白 82 g/L、肌酐 185 μmol/L。现有记录未见明确出血表现；血压和尿量不详。",
      "diagnostic_discussion": "现有资料支持贫血及肾功能异常。贫血需结合红细胞指数等进一步分析，不能排除隐匿失血；单次肌酐升高不足以确定急慢性过程，不能直接归因为肾性贫血。病因待查。",
      "plan": "建议临床医生补充既往检查、用药史，核实血压和容量状态；拟复查血常规及肾功能，按鉴别需要安排进一步检查。观察症状和指标变化。",
      "evidence": [
        {
          "statement": "近 2 周乏力、活动后心悸",
          "source_ids": ["S01"],
          "kind": "fact"
        },
        {
          "statement": "血红蛋白 82 g/L，肌酐 185 μmol/L",
          "source_ids": ["S03"],
          "kind": "fact"
        }
      ],
      "review_items": [
        "既往肾功能及贫血病程",
        "血压、尿量及用药史"
      ]
    }
    """
    return mock_response_json