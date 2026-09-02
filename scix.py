# ========== SciX / ADS 论文检索 ==========
import datetime
import re

import requests

from config import FIELDS, SCIx_URL
from utils import title_similarity, transcribe_math


def _paper_entry(doc):
    """把 SciX 文档转为前端需要的论文信息 dict（标题/摘要/作者/年份/引用/bibcode/bibstem）。
    注意：SciX/ADS 的 abstract 字段是**字符串**（title/author 才是列表），
    不能用 [''] [0] 取——那样会把整段摘要截成第一个字符（如 "R"）。"""
    authors = doc.get('author', []) or []
    title = doc.get('title', [''])[0] if doc.get('title') else '无标题'
    raw_abstract = doc.get('abstract') or ''
    if isinstance(raw_abstract, list):   # 个别网关返回单元素列表时兜底
        raw_abstract = raw_abstract[0] if raw_abstract else ''
    abstract = transcribe_math(raw_abstract) if raw_abstract else '（无摘要）'
    return {
        'title': title,
        'abstract': abstract,
        'authors': ', '.join(authors[:3]) + (' ...' if len(authors) > 3 else ''),
        'first_author': authors[0] if authors else '',
        'year': doc.get('year', ''),
        'citations': doc.get('citation_count', 0),
        'bibcode': doc.get('bibcode', ''),
        'bibstem': doc.get('bibstem', '')
    }


def lookup_paper_by_title(title, ads_token, timeout=8):
    """按标题在 SciX 兜底查找论文（用于 AI 转写的标题与论文列表不完全一致时）。
    返回论文信息 dict；失败或相似度过低返回 None。"""
    safe = str(title or '').replace('"', '')
    params = {
        'q': f'abs:"{safe}"',
        'fl': FIELDS,
        'rows': 1,
        'sort': 'citation_count desc'
    }
    headers = {'Authorization': f'Bearer {ads_token}'}
    try:
        r = requests.get(SCIx_URL, params=params, headers=headers, timeout=timeout)
        if r.status_code != 200:
            return None
        docs = r.json().get('response', {}).get('docs', [])
        if not docs:
            return None
        entry = _paper_entry(docs[0])
        # 校验返回论文与目标标题足够接近，避免链接到无关论文
        if title_similarity(entry['title'], title) < 0.6:
            return None
        return entry
    except Exception:
        return None


def fetch_papers(query, max_results=25, ads_token=None):
    """按关键词检索最近 5 年、有引用量的论文。"""
    current_year = datetime.datetime.now().year
    start_year = current_year - 5
    user_query = query.strip()
    has_quotes = '"' in user_query
    has_logic = re.search(r'\b(OR|AND)\b', user_query, re.IGNORECASE) is not None
    abs_query = f'abs:({user_query})' if (has_quotes or has_logic) else f'abs:"{user_query}"'
    full_query = f'{abs_query} AND year:{start_year}-{current_year} AND citation_count:[1 TO *]'
    print(f"执行查询: {full_query}")

    if not ads_token:
        raise ValueError("未提供 ADS Token")

    params = {
        'q': full_query,
        'fl': FIELDS,
        'rows': max_results,
        'sort': 'date desc'
    }
    headers = {'Authorization': f'Bearer {ads_token}'}
    try:
        response = requests.get(SCIx_URL, params=params, headers=headers, timeout=30)
    except requests.exceptions.RequestException as e:
        raise Exception(f"请求 SciX API 失败: {str(e)}")

    # 注意：401 判断必须放在通用错误判断之前，否则永远不会触发
    if response.status_code == 401:
        raise Exception("ADS Token 无效或已过期，请检查设置")
    if response.status_code != 200:
        raise Exception(f"SciX API 返回错误: {response.status_code}, {response.text}")

    docs = response.json().get('response', {}).get('docs', [])
    return [_paper_entry(doc) for doc in docs[:max_results]]
