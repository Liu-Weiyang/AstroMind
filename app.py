from flask import Flask, render_template, request, jsonify
import requests
import re
import json
import os
import datetime
import unicodedata
from concurrent.futures import ThreadPoolExecutor
import networkx as nx
from pyvis.network import Network

app = Flask(__name__)


@app.errorhandler(Exception)
def handle_unhandled(e):
    """兜底：任何未捕获异常都返回 JSON 而非 HTML 页面，
    避免前端 res.json() 遇到 HTML 时报 "Unexpected token '<'"。"""
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    import traceback
    traceback.print_exc()
    return jsonify({'error': f'服务器内部错误: {type(e).__name__}'}), 500

# ========== 缓存 ==========
# 缓存完整搜索结果（论文列表 + 分类），供 /graph 知识图谱直接复用，
# 避免图谱每次都要重新请求 SciX（慢）且依赖分类缓存（易失）。
result_cache = {}
MAX_RESULT_CACHE = 50
_cache_keys = []  # 记录关键词插入顺序，用于LRU

def set_result_cache(key, value):
    global _cache_keys
    if key in result_cache:
        _cache_keys.remove(key)
        _cache_keys.append(key)
    else:
        if len(_cache_keys) >= MAX_RESULT_CACHE:
            del result_cache[_cache_keys.pop(0)]
        _cache_keys.append(key)
    result_cache[key] = value

# ========== 辅助函数 ==========
def extract_title(item):
    if isinstance(item, str):
        return item.strip()
    elif isinstance(item, list):
        if item:
            return extract_title(item[0])
        else:
            return None
    elif isinstance(item, dict):
        return item.get('title', '').strip()
    else:
        return None

def norm_title(t):
    """规范化标题用于模糊匹配：转小写、标点与连字符统一为空格、压缩空白。
    例如 "Single Field Slow-Roll Inflation With Step Uplift to ns=1"
    与 "Single field slow-roll inflation with step uplift to ns=1" 视为相同。"""
    s = re.sub(r'[^\w\s-]', ' ', str(t or '').lower())
    s = re.sub(r'[\s-]+', ' ', s)
    return s.strip()

def title_similarity(a, b):
    """标题词级相似度：共同词数 / 较短标题的词数，范围 0~1。"""
    ta = [w for w in norm_title(a).split(' ') if w]
    tb = [w for w in norm_title(b).split(' ') if w]
    if not ta or not tb:
        return 0.0
    sa, sb = set(ta), set(tb)
    inter = len(sa & sb)
    return inter / min(len(sa), len(sb))

SCIx_URL = "https://scixplorer.org/v1/search/query"
FIELDS = 'title,abstract,author,year,citation_count,bibcode,bibstem'


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


# ========== 数学符号转写 ==========
# 把 Unicode 上下标/数学符号转写成 DeepSeek 易识读的 ASCII 形式，避免模型漏读
# （如 H₀→H_0、Ωₘ→Ω_m、σ₈→σ_8、10⁵→10^5、s⁻¹→s^-1、≈→~、×→x、−→-）。
_SUB2ASCII = str.maketrans('₀₁₂₃₄₅₆₇₈₉₊₋ₐₑₘₙₚₛₜₓᵢⱼₖₗᵣᵤᵥ', '0123456789+-aemnpstxijklruv')
_SUP2ASCII = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻', '0123456789+-')
_SYMBOL_MAP = {
    # 数学运算符/易错符号
    '×': 'x', '−': '-', '–': '-', '—': '-', '‐': '-',
    '≈': '~', '≃': '~', '∼': '~', '≲': '<=', '≳': '>=',
    '±': '+/-', '∓': '-/+', '≤': '<=', '≥': '>=', '≠': '!=', '≡': '==',
    '⟨': '<', '⟩': '>', 'ℓ': 'l',
    '½': '1/2', '¼': '1/4', '¾': '3/4', '…': '...',
    '‘': "'", '’': "'", '“': '"', '”': '"',
    # 上下标中的特殊字符（不参与连续串替换）
    '⁽': '(', '⁾': ')', 'ⁿ': '^n', 'ⁱ': '^i', 'ˣ': '^x',
}


def transcribe_math(text):
    """把文本中的 Unicode 数学符号转写为 ASCII 可读形式；再做 NFKC 收尾（全角、µ→μ 等）。"""
    if not text:
        return text
    s = str(text)
    # 上下标连续串一次转写（如 ⁻¹ → ^-1、ₘ → _m），避免逐个替换拼出 ^-^1 这类错误
    s = re.sub(r'[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+',
               lambda m: '^' + m.group(0).translate(_SUP2ASCII), s)
    s = re.sub(r'[₀₁₂₃₄₅₆₇₈₉₊₋ₐₑₘₙₚₛₜₓᵢⱼₖₗᵣᵤᵥ]+',
               lambda m: '_' + m.group(0).translate(_SUB2ASCII), s)
    for ch, rep in _SYMBOL_MAP.items():
        s = s.replace(ch, rep)
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


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

# ========== 获取论文（使用 requests 直接调用 SciX API） ==========
def fetch_papers(query, max_results=25, ads_token=None):
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

# ========== 生成主综述 ==========
def _paper_texts(papers):
    """把论文列表格式化为提示词中的「论文X: 标题 （作者, 年份）\n摘要: ...」文本块。"""
    lines = []
    for i, p in enumerate(papers, 1):
        abstract = transcribe_math(p.get('abstract', '无摘要'))[:500]
        if len(p.get('abstract', '')) > 500:
            abstract += '...'
        lines.append(f"论文{i}: {p.get('title', '无标题')} （{p.get('authors', '')}, {p.get('year', '')}）\n摘要: {abstract}")
    return lines


def build_summary_prompt(papers, lang='zh', topic=None):
    lang_instruction = ('请使用中文撰写全部内容（包括小标题、正文、分类名称）。'
                        if lang == 'zh'
                        else 'Please write ALL content in English (including section titles, body text, and category names).')
    # 「关键困难」小节标题必须与语言严格一致（前端靠它定位该板块）
    difficulty_title = ('当前关键困难与待解问题' if lang == 'zh'
                        else 'Current Key Difficulties and Open Problems')
    paper_texts = _paper_texts(papers)
    # 卡片定位是「对某个特定概念的介绍」：开头先用关键词的通俗译名（目标语言），英文原文用括号附后
    opening_inst = (f'正文第一句必须用搜索关键词「{topic}」的通俗译名开头'
                    '（若关键词是英文，先给出其中文译名，并把英文原文用括号附在后面，'
                    '例如关键词 little red dot 时，开头应为「小红点（little red dot）是…」），'
                    '然后展开对这个关键词的总体论述；不要机械地把英文关键词原样当作开头，'
                    '也不要使用「本综述」「本文」等开头。'
                    if topic else '')

    return f"""你是一位专业的天文学研究助理。请阅读下面 {len(papers)} 篇论文的摘要，完成两个简单任务。

**{lang_instruction}**
**引用编号「论文X」的格式在所有语言下保持不变**（X为论文编号，从1开始）。
**{opening_inst}**

**任务一：写一篇简单的研究介绍**
- **正文必须以「总体介绍」小节开头**：第一个加粗小标题就是「总体介绍」（英文为 Overall Introduction，独占一行），其前面不得出现任何总标题、开头语、引言段落或其它小标题；不要为整篇内容添加「XX研究综述」之类的大标题。
- 「总体介绍」小节用一段话介绍搜索关键词「{topic}」的总体情况：这个概念是什么、为什么重要、目前整体研究进展如何。
- 正文以搜索关键词本身开头（见上文开头要求），读取全部论文的摘要，据此继续写；总体介绍之后可按主题分成 **3-4 个**小分区（小标题要**简短**（2-6 字，如 **观测进展**、**理论模型**），用 **加粗** 包裹并独占一行，**标题中不要出现「论文X」编号或作者名**），每个小分区里引用相关论文（用「论文X」格式），简单说明该论文做了什么、得出什么结论；分区数量要足够多，让每篇论文都能放进主题贴切的小分区，避免某个分区塞下过多论文。
- 引用论文后不加括号注明作者。
- **引用与文字之间要分隔清晰**：作者引用（如 Paquereau et al. 2025）与前后文字之间用空格或标点隔开，数字与作者名之间不得粘连（不要出现「0.2Paquereau et al. 2025」这种形式）。
- **正文必须覆盖并引用全部 {len(papers)} 篇论文**：每篇论文至少用「论文X」编号引用一次，不得遗漏任何一篇；与主题相关度较弱的论文也要在合适的小节简要提及，保证每篇论文都出现在正文中（而不只是末尾的分类抽屉里）。
- 最后加一个小节，小标题必须严格为「{difficulty_title}」（独占一行），用项目符号（-）列出当前该领域 3-5 条主要困难，每条一句话。

**任务二：给论文分类**
把全部论文按主题分成 3-6 组（如理论、观测、数据分析、数值模拟等），每篇论文恰好归入一组，不得遗漏；每组给出分类名称和对应的论文标题列表（标题**逐字抄写**上方「论文X:」条目中括号「（」之前的原文，不得改写）。

请以**纯JSON格式**返回结果，结构如下：
{{
  "overview": "研究介绍的完整文本...",
  "categories": [
    {{"name": "分类名称", "papers": ["论文标题1", "论文标题2"]}}
  ]
}}

**重要**：只输出JSON，不要包含其他文字。

以下是论文摘要：
{chr(10).join(paper_texts)}
"""

def summarize_papers(papers, api_key, lang='zh', topic=None):
    prompt = build_summary_prompt(papers, lang, topic)

    messages = [
        {"role": "system", "content": "你是一位专业的天文学研究助理，必须只输出合法的JSON格式。每个小节必须有加粗小标题（用**包裹），小标题独占一行。"},
        {"role": "user", "content": prompt}
    ]
    try:
        content = _call_deepseek(messages, api_key, temperature=0.3, max_tokens=3000, timeout=90)
        print("=== AI原始输出 ===")
        print(content)
        print("=== 输出结束 ===")
        parsed = _parse_json(content)
        if parsed is None:
            return {"error": "未找到JSON格式，原始内容: " + content}
        return parsed
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

# ========== 跨领域连接（他山之石，可以攻玉） ==========
# 多困难输入走并行流水线：每个困难独立执行 阶段一(多视角候选生成)+阶段二(独立评分排序)，
# 多个困难并发调用，最后一个小调用生成整体 summary —— 单次调用输出短、墙钟时间约为串行的 1/2~1/3。
CONNECT_SYSTEM = "你是一位跨学科方法迁移专家，核心理念是「他山之石，可以攻玉」。必须只输出合法的JSON格式。"

# 可用环境变量覆盖（无需改代码）：DEEPSEEK_URL 指向其它 OpenAI 兼容网关、DEEPSEEK_MODEL 切换模型
DEEPSEEK_URL = os.environ.get('DEEPSEEK_URL', "https://api.deepseek.com/v1/chat/completions")
# 官方 api.deepseek.com 的通用模型是 deepseek-chat（快且省）；deepseek-reasoner 是慢速推理模型，不要用。
# 注意：deepseek-v4-flash 不是官方 API 的模型名（会返回 401/400），仅当 DEEPSEEK_URL 指向支持它的网关时才用。
DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL', "deepseek-chat")


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

def build_connect_stage1_prompt(topic, context, lang='zh', problems=None):
    lang_instruction = ('请使用中文输出全部内容。'
                        if lang == 'zh'
                        else 'Please output ALL content in English.')
    # 数学符号统一转写，避免模型漏读
    topic = transcribe_math(topic)
    context = transcribe_math(context)
    if problems:
        problems = [transcribe_math(p) for p in problems]
        user_input = "用户正在研究的天文学问题清单（每个编号是一项独立困难，需要分开分析）：\n" + \
            "\n".join(f"{i + 1}. {p}" for i, p in enumerate(problems))
        per_problem = True
    else:
        user_input = context if context and len(context) > 100 else topic
        per_problem = False
    essence_inst = (
        "输入中列了多个独立困难：**必须对每一个困难分别执行下面的任务**，每个困难生成一个 section，"
        "且 section 的 problem 字段原样抄写该困难条目，不得合并、不得遗漏。"
        if per_problem else
        "把输入中的具体科学/工程困难提炼为一个 section（problem 字段概括该困难）。"
    )
    return f"""你是一位跨学科方法挖掘专家，核心理念是「他山之石，可以攻玉」。

用户正在研究以下天文学问题/主题：
--- 输入开始 ---
{user_input}
--- 输入结束 ---

**{lang_instruction}**

**任务分两步：**

第一步，提炼抽象本质（essence）：{essence_inst} 把该困难剥离掉天文学属性，用纯粹的数学/物理/工程语言重述，指出它属于哪一类通用问题（例如参数强简并估计、多源信号分离、非高斯噪声逆问题、约束优化、时序异常检测、多尺度建模、振荡同步等）。

第二步，多视角候选生成：对每个困难，**不要**沿着单一联想路径（如"天文学→物理学→统计学"）找答案，而是从以下四个独立"透镜"分别联想，每个透镜给出 1-2 个候选：
- 数学结构透镜：代数、几何、拓扑、泛函分析、数论中的结构
- 数据处理透镜：信号处理、统计、机器学习、优化、信息论中的方法
- 系统动力学透镜：振荡器、控制论、同步、网络科学、动力系统中的机制
- 模式与结构透镜：生物学、音乐理论、语言学、经济学、材料科学、化学、医学成像等中的模式

**要求**：
- 每个困难的候选池中**必须至少包含 1 个来自"非相邻领域"的候选**（如音乐理论、语言学、经济学、生物学等；物理、统计、数值方法这类与天文学近邻的领域不能占满候选池）。
- 每个候选只写一行：领域 | 概念/方法名称 | 一句话说明与抽象本质的结构相似性。
- 每个困难给 **3 个**候选（上限 3 个；确实凑不满可给 2 个，宁缺毋滥，不要编造）。
- **候选必须真实存在**：只写有成熟文献、公开实现或公认术语的方法/概念，**禁止发明术语、禁止编造文献或作者名**；不确定真实性的候选不要写。
- 输入中若出现「论文X」编号，表示用户论文集中的论文，你无法查看其内容：请基于该条目自带的文字分析，不要臆测该编号论文的具体内容。
- **整体输出务必精简**：候选保持一行一个，不做多余解释。

**只输出合法 JSON，格式：**
{{
  "sections": [
    {{
      "problem": "困难条目原文",
      "essence": "该困难的抽象本质",
      "candidates": [
        {{"field": "领域", "concept": "方法/概念名称", "similarity": "一句话结构相似性"}}
      ]
    }}
  ]
}}
"""

def build_connect_stage2_instruction(lang='zh'):
    lang_instruction = ('请使用中文输出全部内容。'
                        if lang == 'zh'
                        else 'Please output ALL content in English.')
    return f"""现在请作为**独立的评估者**，对上面的候选列表完成评分与排序（不要因为候选是"自己生成"的就偏向它）。

**{lang_instruction}**

**评分表（每项 1-5 分）**：
- isomorphism 结构同构度：与抽象本质的映射精确度（不是表面相似）
- maturity 解法成熟度：是否有成熟算法/理论/工具/公开实现
- convenience 迁移便利度：数据、代码、工具链能否直接搬进天文学工作流
- payoff 预期收益：针对该困难的实际改善程度

**硬性可行性检查**：对每个候选，判断其解法是否有可获取的实现/文献/数据；明显"听起来像但落不了地"的候选直接降分或剔除。**分数不得虚高**：maturity/convenience 拿不准就给低分（2 分及以下），低成熟候选必须如实反映。

**重要**：若上面的输入包含多个困难小节（每个 section 各有自己的 candidates），必须为**每个 section 分别输出一个 section**，且只针对该 section 自己的 candidates 评分与排序，problem 字段原样保留，不得混用其他 section 的候选。**若输入只有一个困难小节，则只输出一个 section，summary 字段可省略。**

**只输出合法 JSON，格式：**
{{
  "sections": [
    {{
      "problem": "原样保留阶段一中的 problem（不得改写、不得合并）",
      "essence": "抽象本质",
      "matches": [
        {{
          "field": "领域",
          "concept": "方法/概念名称",
          "solution": "该领域的解法要点",
          "why": "与天文问题的结构相似性",
          "scores": {{"isomorphism": 4, "maturity": 5, "convenience": 3, "payoff": 4}},
          "total": 16,
          "rationale": "为什么它优于邻近学科（如物理/统计）中的对应方法",
          "verify": "迁移后第一步如何验证（数据/实验设计）"
        }}
      ],
      "migration": "迁移到天文学的预期结果与价值"
    }}
  ],
  "summary": "整体判断：哪些迁移最值得尝试、综合价值与建议的研究路径"
}}

要求：
- matches 按 total 从高到低排序，每个困难**保留前 3 个**（宁缺毋滥）。
- **内容要详细**：solution（该领域的解法要点）、why（结构相似性）、rationale（为何优于邻近学科）、verify（迁移后第一步验证）每个字段写 2-3 句，把方法怎么用、为什么适合、怎么验证讲清楚，篇幅为之前的两到三倍；**不要用一句话敷衍**。
- 若某个困难确实没有可行对应，如实说明。
"""

def _connect_single_problem(problem, topic, context, lang, deepseek_key):
    """单个困难的完整流水线：阶段一(候选生成) → 阶段二(评分排序)。
    返回 (section_dict, candidates_list) 或 None（任一步失败）。"""
    try:
        # 阶段一：只针对这一个困难生成候选
        p1 = build_connect_stage1_prompt(topic, context, lang, [problem])
        m1 = [{"role": "system", "content": CONNECT_SYSTEM}, {"role": "user", "content": p1}]
        c1 = _call_deepseek(m1, deepseek_key, temperature=0.3, max_tokens=1000, timeout=90)
        s1 = _parse_json(c1)
        if not isinstance(s1, dict):
            return None
        secs = s1.get('sections') if isinstance(s1.get('sections'), list) else []
        if not secs:
            legacy = s1.get('candidates', [])
            if not isinstance(legacy, list) or not legacy:
                return None
            secs = [{'problem': problem, 'essence': s1.get('essence', ''), 'candidates': legacy}]
        sec = secs[0]
        cands = sec.get('candidates')
        if not isinstance(cands, list) or not cands:
            return None

        # 阶段二：独立评分（只针对本困难的候选）
        p2 = build_connect_stage2_instruction(lang)
        m2 = m1 + [{"role": "assistant", "content": c1}, {"role": "user", "content": p2}]
        c2 = _call_deepseek(m2, deepseek_key, temperature=0.3, max_tokens=2500, timeout=120)
        report = _parse_json(c2)
        if not isinstance(report, dict):
            report = _repair_json(m2, c2, deepseek_key, 1200)
        if not isinstance(report, dict):
            return None
        rsecs = report.get('sections')
        if isinstance(rsecs, list) and rsecs and isinstance(rsecs[0], dict):
            out_sec = rsecs[0]
        else:
            # 阶段二未按 sections 输出（旧格式）：用阶段一信息兜底
            out_sec = {'problem': sec.get('problem', problem), 'essence': sec.get('essence', ''),
                       'matches': report.get('matches', [])}
        if not out_sec.get('problem'):
            out_sec['problem'] = sec.get('problem', problem)
        if not out_sec.get('essence'):
            out_sec['essence'] = sec.get('essence', '')
        return (out_sec, cands)
    except requests.exceptions.RequestException:
        return None
    except Exception:
        return None


def _connect_summary(sections, lang, deepseek_key):
    """基于各小节生成整体 summary（小调用：输入短、输出短、速度快）。失败返回 None。"""
    try:
        lang_instruction = ('请使用中文撰写。' if lang == 'zh' else 'Please write in English.')
        digest = "\n".join(
            f"{i + 1}. 困难: {(sec.get('problem') or '')[:120]}" +
            " | 最佳迁移: " +
            "; ".join(f"{m.get('field', '')}·{m.get('concept', '')}(总分{m.get('total', '?')})"
                      for m in (sec.get('matches') if isinstance(sec.get('matches'), list) else [])[:2])
            for i, sec in enumerate(sections))
        prompt = f"""下面是若干「他山之石」分析小节（每个困难一个，已按可靠性评分）。请给出**整体判断**：哪些迁移最值得尝试、综合价值，以及建议的研究路径（可结合困难之间的共性）。

{lang_instruction}
{digest}

只输出合法 JSON：{{"summary": "一段话（100-200字）"}}"""
        content = _call_deepseek(
            [{"role": "system", "content": CONNECT_SYSTEM}, {"role": "user", "content": prompt}],
            deepseek_key, temperature=0.3, max_tokens=300, timeout=60)
        parsed = _parse_json(content)
        if isinstance(parsed, dict) and isinstance(parsed.get('summary'), str):
            return parsed['summary']
        return None
    except requests.exceptions.RequestException:
        return None


@app.route('/connect', methods=['POST'])
def connect():
    data = request.get_json(silent=True) or {}
    topic = data.get('topic', '')
    context = data.get('context', '')
    lang = data.get('lang', 'zh') or 'zh'
    if lang not in ('zh', 'en'):
        lang = 'zh'

    if not topic and not context:
        return jsonify({'error': '请提供要分析的主题或摘要文本'}), 400

    deepseek_key = request.headers.get('X-DeepSeek-Key', '').strip()
    if not deepseek_key:
        return jsonify({'error': '未提供 DeepSeek API Key，请在设置中填写'}), 400

    try:
        # 前端把「当前关键困难与待解问题」的每个项目符号拆成独立条目 → 每个条目单独一个小节分析
        problems = data.get('problems')
        if not isinstance(problems, list) or len(problems) < 2 or \
                not all(isinstance(p, str) and p.strip() for p in problems):
            problems = None
        # 限制并行分析的困难数，控制最坏延迟与成本（困难按重要性排序，保留前 5 条）
        if problems and len(problems) > 5:
            problems = problems[:5]

        if problems:
            # —— 并行流水线：每个困难独立跑 阶段一+阶段二（并发），最后一个小调用生成整体 summary ——
            # 单个调用输出短（每个 1-2 秒级），多个困难并发，墙钟时间约为串行的 1/2~1/3。
            with ThreadPoolExecutor(max_workers=4) as ex:
                results = list(ex.map(
                    lambda p: _connect_single_problem(p, topic, context, lang, deepseek_key),
                    problems))
            ok_results = [r for r in results if r]
            if not ok_results:
                return jsonify({'error': '候选生成失败，请重试'}), 500
            sections = []
            candidates = []
            for out_sec, cands in ok_results:
                sections.append(out_sec)
                candidates.extend(cands)
            report = {'sections': sections}
            summary = _connect_summary(sections, lang, deepseek_key)
            if summary:
                report['summary'] = summary
        else:
            # —— 单段兜底：整段上下文作为一个困难，沿用两阶段串行流程 ——
            stage1_prompt = build_connect_stage1_prompt(topic, context, lang, None)
            messages1 = [
                {"role": "system", "content": CONNECT_SYSTEM},
                {"role": "user", "content": stage1_prompt}
            ]
            content1 = _call_deepseek(messages1, deepseek_key, temperature=0.3, max_tokens=2500, timeout=120)
            stage1 = _parse_json(content1)
            if not isinstance(stage1, dict):
                return jsonify({'error': '候选生成失败，请重试'}), 500
            stage1_sections = stage1.get('sections') if isinstance(stage1.get('sections'), list) else []
            candidates = []
            for s in stage1_sections:
                for c in (s.get('candidates') if isinstance(s.get('candidates'), list) else []):
                    candidates.append(c)
            if not candidates:
                legacy_cands = stage1.get('candidates', [])
                if isinstance(legacy_cands, list) and legacy_cands:
                    candidates = legacy_cands
                    stage1_sections = [{'problem': context,
                                        'essence': stage1.get('essence', ''), 'candidates': legacy_cands}]
            if not candidates:
                return jsonify({'error': '候选生成失败，请重试'}), 500
            stage2_instruction = build_connect_stage2_instruction(lang)
            messages2 = messages1 + [
                {"role": "assistant", "content": content1},
                {"role": "user", "content": stage2_instruction}
            ]
            content2 = _call_deepseek(messages2, deepseek_key, temperature=0.3, max_tokens=4500, timeout=120)
            report = _parse_json(content2)
            if not isinstance(report, dict):
                report = _repair_json(messages2, content2, deepseek_key, 2500)
            if not isinstance(report, dict):
                return jsonify({'error': '评估结果解析失败，请重试'}), 500
            if not isinstance(report.get('sections'), list):
                report['sections'] = []

        # 附带候选池信息，前端展示搜索广度以增强可信度
        pool_fields = sorted({c.get('field', '') for c in candidates if c.get('field')})
        return jsonify({
            'connection_report': report,
            'pool_count': len(candidates),
            'pool_fields': pool_fields
        })
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': f'请求出错: {str(e)}'}), 500

# ========== Flask 路由 ==========

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    keyword = request.form.get('keyword', '').strip()
    lang = request.form.get('lang', 'zh').strip() or 'zh'
    if lang not in ('zh', 'en'):
        lang = 'zh'
    if not keyword:
        return jsonify({'error': '请输入关键词'}), 400

    ads_token = request.headers.get('X-ADS-Token', '').strip()
    deepseek_key = request.headers.get('X-DeepSeek-Key', '').strip()

    if not ads_token:
        return jsonify({'error': '未提供 ADS Token，请在设置中填写'}), 400
    if not deepseek_key:
        return jsonify({'error': '未提供 DeepSeek API Key，请在设置中填写'}), 400

    try:
        papers = fetch_papers(keyword, max_results=25, ads_token=ads_token)
        if not papers:
            return jsonify({'error': '未找到相关论文'}), 404

        summary_data = summarize_papers(papers, deepseek_key, lang, topic=keyword)
        if 'error' in summary_data:
            return jsonify({'error': summary_data['error']}), 500

        categories = summary_data.get('categories', [])
        if not isinstance(categories, list):
            categories = []

        # 缓存完整搜索结果（论文 + 分类），供 /graph 知识图谱直接复用
        set_result_cache(keyword, {'papers': papers, 'categories': categories})

        unresolved = []  # (cat, title) 待兜底查询的条目
        for cat in categories:
            if not isinstance(cat, dict):
                continue
            cat['papers_with_links'] = []
            papers_list = cat.get('papers', [])
            if not isinstance(papers_list, list):
                continue

            for item in papers_list:
                title = extract_title(item)
                if not title:
                    continue
                matched = None
                nt = norm_title(title)
                for p in papers:
                    if norm_title(p['title']) == nt:
                        matched = p
                        break
                # 词级相似度兜底：AI 转写的标题与原文略有出入时仍能匹配
                if matched is None:
                    for p in papers:
                        if title_similarity(p['title'], title) >= 0.7:
                            matched = p
                            break
                if matched:
                    cat['papers_with_links'].append(matched)
                else:
                    unresolved.append((cat, title))

        # 仍未匹配的标题：用 SciX 按标题兜底查询（并发执行、限制数量，避免拖慢响应）
        if unresolved:
            targets = unresolved[:4]
            with ThreadPoolExecutor(max_workers=4) as ex:
                lookups = list(ex.map(lambda t: lookup_paper_by_title(t, ads_token),
                                      [t for _, t in targets]))
            for (cat, _), p in zip(targets, lookups):
                if p and p.get('bibcode'):
                    cat['papers_with_links'].append(p)
                # 解析不出链接的条目直接不展示，保证抽屉里列出的论文都有链接

        return jsonify({
            'overview': summary_data.get('overview', ''),
            'categories': categories,
            'papers': papers
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': f'处理出错: {str(e)}'}), 500

def build_summarize_papers_prompt(papers, lang='zh'):
    """详情卡片提示词：每篇论文输出总结(≤600字)与扩展分析(≤600字)，最后输出综合比较。"""
    lang_instruction = ('请用中文输出全部内容。'
                        if lang == 'zh'
                        else 'Please write ALL content in English.')
    paper_texts = []
    for i, p in enumerate(papers, 1):
        abstract = transcribe_math(p.get('abstract', '（无摘要）'))
        paper_texts.append(f"论文{i}: {p.get('title', '无标题')} （{p.get('authors', '')}, {p.get('year', '')}）\n摘要:\n{abstract}")

    return f"""你是一位专业的天文学研究助理。请阅读下面 {len(papers)} 篇论文的摘要，完成三项任务。

**{lang_instruction}**
**任务一（总结）**：为每篇论文写一个**总结**，不超过 600 字，详细概括论文研究了什么、方法、得出什么结论。
**任务二（扩展分析）**：为每篇论文写一段**扩展分析**，不超过 600 字，基于 AI 的判断给出对后续研究工作的具体建议。
**任务三（综合比较）**：综合比较上述所有论文，写一段**综合比较**，指出它们的共同点、矛盾点等重要信息（不超过 400 字）。

**硬性要求**：
1. 总结与扩展分析只依据摘要内容撰写，不要添加摘要之外的常识性解释。
2. **总结与扩展分析的内容直接输出正文，不要带「论文X总结：」「论文X扩展分析：」之类的编号前缀。**
3. 「论文X」编号仅用于与上方列表对应，不得合并、不得遗漏。
4. 只输出合法 JSON，不要包含其他文字。

**只输出合法 JSON**，格式：
{{
  "papers": [
    {{"summary": "论文1的总结（≤600字）", "analysis": "论文1的扩展分析（≤600字）"}},
    {{"summary": "论文2的总结（≤600字）", "analysis": "论文2的扩展分析（≤600字）"}}
  ],
  "comparison": "综合比较（≤400字）"
}}

以下是各篇论文的摘要：
{chr(10).join(paper_texts)}
"""


def build_translate_prompt(data, lang='zh'):
    lang_instruction = ('请将下面的内容翻译成中文。'
                        if lang == 'zh'
                        else 'Please translate the following content into English.')
    # 翻译后「关键困难」小标题必须使用目标语言的准确写法（前端靠它定位该板块）
    difficulty_title = ('当前关键困难与待解问题' if lang == 'zh'
                        else 'Current Key Difficulties and Open Problems')
    parts = []
    if data.get('overview'):
        parts.append(f'[综述]\n{data["overview"]}')
    if data.get('categories'):
        cat_lines = [f"分类{i + 1}: {c.get('name', '')}" for i, c in enumerate(data['categories'])]
        parts.append('[分类名]\n' + '\n'.join(cat_lines))
    if data.get('detail'):
        parts.append(f'[详情]\n{data["detail"]}')

    return f"""你是一位专业的天文学翻译。{lang_instruction}

要求：
1. 文中的「论文X」编号标记（X为数字）必须原样保留，不得改动、增删或翻译。
2. 论文标题保持原文不变，不翻译（分类中的论文标题列表原样保留）。
3. 分类名称需要翻译。
4. 保持原有结构、段落与加粗标记（**）不变。
5. 若文中出现「当前关键困难与待解问题」或「Current Key Difficulties and Open Problems」小标题，翻译后必须严格使用「{difficulty_title}」这一准确标题，不得意译。

请只输出纯JSON，格式如下：
{{
  "overview": "翻译后的综述",
  "category_names": ["翻译后的分类名1", "翻译后的分类名2"],
  "detail": "翻译后的详情"
}}
如果某部分没有提供（字段缺失或为空），对应字段输出空字符串。
分类名数量必须与输入一致。

待翻译内容：
{chr(10).join(parts)}
"""

@app.route('/translate', methods=['POST'])
def translate_content():
    data = request.get_json(silent=True) or {}
    lang = data.get('lang', 'zh') or 'zh'
    if lang not in ('zh', 'en'):
        lang = 'zh'

    deepseek_key = request.headers.get('X-DeepSeek-Key', '').strip()
    if not deepseek_key:
        return jsonify({'error': '未提供 DeepSeek API Key，请在设置中填写'}), 400

    has_content = bool(data.get('overview')) or bool(data.get('categories')) or bool(data.get('detail'))
    if not has_content:
        return jsonify({'error': '没有可翻译的内容'}), 400

    prompt = build_translate_prompt(data, lang)
    messages = [
        {"role": "system", "content": "你是一位专业的天文学翻译，必须只输出合法的JSON格式，且严格遵守「论文X」编号不变的要求。"},
        {"role": "user", "content": prompt}
    ]
    try:
        content = _call_deepseek(messages, deepseek_key, temperature=0.3, max_tokens=3000, timeout=90)
        parsed = _parse_json(content)
        if not isinstance(parsed, dict):
            return jsonify({'error': '翻译结果解析失败'}), 500
        return jsonify({
            'overview': parsed.get('overview', ''),
            'category_names': parsed.get('category_names', []),
            'detail': parsed.get('detail', '')
        })
    except Exception as e:
        return jsonify({'error': f'请求出错: {str(e)}'}), 500

@app.route('/expand', methods=['POST'])
def expand_topic():
    data = request.get_json()
    topic = data.get('topic', '')
    papers = data.get('papers', [])
    lang = data.get('lang', 'zh') or 'zh'
    if lang not in ('zh', 'en'):
        lang = 'zh'

    if not topic or not papers:
        return jsonify({'error': '缺少参数'}), 400

    deepseek_key = request.headers.get('X-DeepSeek-Key', '').strip()
    if not deepseek_key:
        return jsonify({'error': '未提供 DeepSeek API Key，请在设置中填写'}), 400

    prompt = build_summarize_papers_prompt(papers, lang)

    messages = [
        {"role": "system", "content": "你是一位专业的天文学研究助理，必须只输出合法的JSON格式，总结与扩展分析各不超过600字，且不要带「论文X总结：」等前缀。"},
        {"role": "user", "content": prompt}
    ]
    try:
        content = _call_deepseek(messages, deepseek_key, temperature=0.3, max_tokens=6000, timeout=120)
        parsed = _parse_json(content)
        if not isinstance(parsed, dict) or not isinstance(parsed.get('papers'), list):
            # 解析失败（多为输出被截断）：让模型重写一次合法 JSON，避免用户直接看到错误
            parsed = _repair_json(messages, content, deepseek_key, 6000)
        if not isinstance(parsed, dict) or not isinstance(parsed.get('papers'), list):
            return jsonify({'error': '总结结果解析失败，请重试'}), 500
        return jsonify({'papers': parsed['papers'], 'comparison': parsed.get('comparison', '')})
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500

# ========== 知识图谱 ==========
@app.route('/graph/<keyword>')
def show_graph(keyword):
    keyword = keyword.strip()
    if not keyword:
        return "关键词不能为空", 400

    # 直接复用 /search 缓存的完整结果，不再重复请求 SciX（快、且不依赖请求头令牌）
    cached = result_cache.get(keyword)
    if cached is None:
        return "请先在主页面搜索该关键词（生成综述与分类后）再查看知识图谱", 400
    papers = cached.get('papers') or []
    categories = cached.get('categories') or []
    if not papers or not categories:
        return "缓存中没有可用的论文或分类，请重新搜索", 400

    G = nx.Graph()
    G.add_node(keyword, title=f"主题: {keyword}", color='#6A8CFF', size=30, shape='star')

    for cat in categories:
        cat_name = cat.get('name', '未分类')
        G.add_node(cat_name, title=f"分类: {cat_name}", color='#FFA500', size=20, shape='box')
        G.add_edge(keyword, cat_name)

        paper_titles = cat.get('papers', [])
        if not isinstance(paper_titles, list):
            continue

        for idx, item in enumerate(paper_titles):
            title = extract_title(item)
            if not title:
                continue
            matched = None
            nt = norm_title(title)
            for p in papers:
                if norm_title(p['title']) == nt:
                    matched = p
                    break
            if matched is None:
                for p in papers:
                    if title_similarity(p['title'], title) >= 0.7:
                        matched = p
                        break
            if matched:
                short_label = f"Paper {idx+1}"
                hover_text = f"{matched['title']}\n{matched['authors']}\n{matched['year']} · 引用 {matched['citations']} 次"
                size = 10 + min(matched['citations'] // 5, 10)
                G.add_node(short_label, title=hover_text, color='#D0D8E0', size=size, shape='dot')
                G.add_edge(cat_name, short_label)

    net = Network(height='750px', width='100%', bgcolor='#0B1319', font_color='#E8EDF2')
    net.from_nx(G)
    net.set_options("""
    var options = {
      "physics": {
        "enabled": true,
        "stabilization": {"iterations": 150},
        "barnesHut": {"gravitationalConstant": -3000, "centralGravity": 0.3}
      },
      "nodes": {
        "font": {"size": 14}
      }
    }
    """)
    graph_html = net.generate_html(notebook=False)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>知识图谱 - {keyword}</title>
        <style>
            body {{ margin: 0; background: #0B1319; font-family: 'Nunito Sans', 'Helvetica Neue', Arial, sans-serif; }}
            .header {{ padding: 20px 30px; background: rgba(18, 28, 40, 0.8); backdrop-filter: blur(8px); border-bottom: 1px solid rgba(255,255,255,0.06); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; }}
            .header a {{ color: #6A8CFF; text-decoration: none; font-weight: 600; font-size: 1rem; }}
            .header a:hover {{ color: #8AACFF; }}
            .header h2 {{ color: #E8EDF2; font-weight: 400; font-size: 1.4rem; margin: 0; }}
            .header h2 small {{ color: rgba(255,255,255,0.4); font-size: 1rem; font-weight: 400; }}
            .legend {{ display: flex; gap: 20px; color: rgba(255,255,255,0.6); font-size: 0.85rem; align-items: center; }}
            .legend-item {{ display: flex; align-items: center; gap: 6px; }}
            .legend-dot {{ display: inline-block; width: 14px; height: 14px; border-radius: 50%; }}
            .footer {{ text-align: center; padding: 15px; color: rgba(255,255,255,0.2); font-size: 0.8rem; border-top: 1px solid rgba(255,255,255,0.04); }}
            #graph-container {{ width: 100%; height: calc(100vh - 160px); }}
            #graph-container > div {{ width: 100%; height: 100%; }}
            @media (max-width: 640px) {{ .header {{ flex-direction: column; align-items: flex-start; gap: 8px; }} .header h2 {{ font-size: 1.2rem; }} .legend {{ flex-wrap: wrap; gap: 10px; }} }}
        </style>
    </head>
    <body>
        <div class="header">
            <a href="/">← 返回搜索</a>
            <h2>"{keyword}" 的研究结构 <small>· 节点可拖拽</small></h2>
            <div class="legend">
                <span class="legend-item"><span class="legend-dot" style="background:#6A8CFF;"></span> 主题</span>
                <span class="legend-item"><span class="legend-dot" style="background:#FFA500;"></span> 研究方向</span>
                <span class="legend-item"><span class="legend-dot" style="background:#D0D8E0;"></span> 论文</span>
            </div>
        </div>
        <div id="graph-container">
            {graph_html}
        </div>
        <div class="footer">节点大小表示引用数 · 悬停查看详细信息</div>
    </body>
    </html>
    """

if __name__ == '__main__':
    import os
    # 本地开发：python app.py（默认 debug 关闭）
    # 生产环境：waitress-serve --host 0.0.0.0 --port 5000 app:app
    #          （或 gunicorn -w 4 -b 0.0.0.0:5000 app:app）
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)
