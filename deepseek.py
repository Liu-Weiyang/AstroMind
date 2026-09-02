# ========== DeepSeek 客户端 ==========
import json
import re

import requests

from config import DEEPSEEK_MODEL, DEEPSEEK_URL


def _call_deepseek(messages, api_key, temperature=0.3, max_tokens=3000, timeout=90, retries=2):
    """调用 DeepSeek 并返回内容文本。连接中断 / 超时 / 5xx / 429 时自动重试（指数退避），
    400/401/403（参数错误 / Key 无效 / 无权限）不重试、直接报出明确错误——重试不可能成功，只会浪费 token。"""
    import time as _time
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": DEEPSEEK_MODEL, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 401:
                # Key 无效/未授权。若 Key 无误，多半是模型名不被账号支持，提示切换模型
                raise requests.exceptions.RequestException(
                    "DeepSeek API Key 无效或未授权（HTTP 401），请检查设置中的 Key；"
                    "若 Key 无误，可能是模型 deepseek-v4-flash 不被该账号支持，可设 DEEPSEEK_MODEL=deepseek-chat")
            if resp.status_code in (400, 403):
                # 请求本身被拒（如模型不存在）：附上服务端原因，便于定位
                raise requests.exceptions.RequestException(
                    f"DeepSeek 拒绝请求（HTTP {resp.status_code}）：{resp.text[:200]}")
            if resp.status_code in (429, 500, 502, 503, 504):
                last_err = f"DeepSeek 服务暂不可用（HTTP {resp.status_code}），请稍后重试"
                if attempt < retries:
                    _time.sleep(1.5 * (attempt + 1))
                    continue
                raise requests.exceptions.RequestException(last_err)
            if resp.status_code != 200:
                raise requests.exceptions.RequestException(f"AI调用失败: {resp.status_code}")
            try:
                data = resp.json()
                return data['choices'][0]['message']['content']
            except (ValueError, KeyError, IndexError, TypeError):
                raise requests.exceptions.RequestException("AI 返回内容异常，请重试")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_err = f"与 DeepSeek 的连接中断，请检查网络后重试（{type(e).__name__}）"
            if attempt < retries:
                _time.sleep(1.5 * (attempt + 1))
                continue
            raise requests.exceptions.ConnectionError(last_err)
    raise requests.exceptions.RequestException(f"DeepSeek 调用失败: {last_err}")


def _parse_json(content):
    """从模型输出中提取 JSON 对象；兼容 markdown 代码块围栏与前后杂讯；失败返回 None。"""
    if not content:
        return None
    text = content.strip()
    # 去掉 markdown 代码块围栏（```json ... ```）
    text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    # 先尝试整体解析（模型可能直接输出纯 JSON）
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 兜底：取首个 { 到最末 } 的片段（贪婪匹配，兼容末尾补充说明文字）
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


_REPAIR_HINT = "你上一条输出不是合法 JSON。请只重新输出完整的合法 JSON 结果，不要代码块围栏，不要任何解释文字。"


def _repair_json(messages, bad_content, api_key, max_tokens):
    """模型输出不是合法 JSON 时，让其重写为纯 JSON（仅失败时多一次调用）。失败返回 None。"""
    try:
        repair = _call_deepseek(messages + [
            {"role": "assistant", "content": bad_content},
            {"role": "user", "content": _REPAIR_HINT}
        ], api_key, temperature=0.2, max_tokens=max_tokens, timeout=90)
        return _parse_json(repair)
    except requests.exceptions.RequestException:
        return None
