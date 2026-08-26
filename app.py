from flask import Flask, render_template, request, jsonify
import ads
import requests
import time
import re
import json
import datetime
import networkx as nx
from pyvis.network import Network

app = Flask(__name__)

# ========== 缓存 ==========
category_cache = {}

# 缓存限制
MAX_CATEGORY_CACHE = 50
cache_keys = []  # 记录关键词插入顺序，用于LRU

def set_category_cache(key, value):
    global cache_keys
    if key in category_cache:
        # 如果已存在，更新值并移动到最后
        cache_keys.remove(key)
        cache_keys.append(key)
    else:
        if len(cache_keys) >= MAX_CATEGORY_CACHE:
            # 删除最旧的条目
            oldest = cache_keys.pop(0)
            del category_cache[oldest]
        cache_keys.append(key)
    category_cache[key] = value

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

# ========== 获取论文（使用 requests 直接调用 SciX API） ==========
def fetch_papers(query, max_results=25, ads_token=None):
    current_year = datetime.datetime.now().year
    start_year = current_year - 5
    user_query = query.strip()
    has_quotes = '"' in user_query
    has_logic = re.search(r'\b(OR|AND)\b', user_query, re.IGNORECASE) is not None
    if has_quotes or has_logic:
        abs_query = f'abs:({user_query})'
    else:
        abs_query = f'abs:"{user_query}"'
    full_query = f'{abs_query} AND year:{start_year}-{current_year} AND citation_count:[1 TO *]'
    print(f"执行查询: {full_query}")

    if not ads_token:
        raise ValueError("未提供 ADS Token")

    # 直接调用 SciX API（与 curl 测试保持一致）
    url = "https://scixplorer.org/v1/search/query"
    params = {
        'q': full_query,
        'fl': 'title,abstract,author,year,citation_count,bibcode,bibstem',
        'rows': max_results,
        'sort': 'date desc'
    }
    headers = {
        'Authorization': f'Bearer {ads_token}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
    except requests.exceptions.RequestException as e:
        raise Exception(f"请求 SciX API 失败: {str(e)}")

    if response.status_code != 200:
        raise Exception(f"SciX API 返回错误: {response.status_code}, {response.text}")

    if response.status_code == 401:
        raise Exception("ADS Token 无效或已过期，请检查设置")

    data = response.json()
    results = []
    for doc in data.get('response', {}).get('docs', []):
        title = doc.get('title', ['无标题'])[0] if doc.get('title') else '无标题'
        first_author = doc.get('author', [''])[0] if doc.get('author') else ''
        authors = doc.get('author', [])
        authors_str = ', '.join(authors[:3]) + (' ...' if len(authors) > 3 else '')
        results.append({
            'title': title,
            'abstract': doc.get('abstract', [''])[0] if doc.get('abstract') else '（无摘要）',
            'authors': authors_str,
            'first_author': first_author,
            'year': doc.get('year', ''),
            'citations': doc.get('citation_count', 0),
            'bibcode': doc.get('bibcode', ''),
            'bibstem': doc.get('bibstem', '')
        })
        # 适当延时避免过频
        time.sleep(0.2)
        if len(results) >= max_results:
            break

    return results

# ========== 生成主综述 ==========
def summarize_papers(papers, api_key):
    paper_texts = []
    for i, p in enumerate(papers, 1):
        abstract = p['abstract'][:500] + ("..." if len(p['abstract']) > 500 else "")
        authors_str = p['authors']
        paper_texts.append(f"论文{i}: {p['title']} （{authors_str}, {p['year']}）\n摘要: {abstract}")

    prompt = f"""你是一位专业的天文学研究助理。请根据以下{len(papers)}篇论文的摘要，完成两个任务。

**任务一：撰写一篇详细的研究介绍（不要使用“本综述”、“本文”等表述）**
请写一篇详细的介绍（约800-1200字），要求：
- 第一段（总述）：直接以该研究方向的名称（例如“哈勃张力”）开头，介绍其背景、重要性和核心问题。
- 然后按主题分小节，每个小节必须有一个 **小标题**（用 **加粗** 包裹，例如 **观测进展**、**理论模型**），小标题后换行开始该节内容。
- 每个小节下，**必须引用具体论文**，并说明：
  - **使用方法**：例如用了什么数据集、仪器、模型。
  - **关键结论**：尽量给出定量结果（如哈勃常数数值、红移范围、置信区间等）。
- 最后一段：总结当前共识、主要争议和未来方向。

**引用格式要求**：
- 在句子中引用论文时，请使用“论文X”的格式（X为论文编号，从1开始），例如“论文1”。不要直接写作者名字，统一用编号。

**任务二：将论文按主题分类**
将以下论文根据研究主题分组（如“观测方法”、“理论模型”、“数据分析”、“数值模拟”等），每组给出分类名称和对应的论文标题列表。

请以**纯JSON格式**返回结果，结构如下：
{{
  "overview": "这里是研究介绍的完整文本...",
  "categories": [
    {{"name": "分类名称", "papers": ["论文标题1", "论文标题2"]}}
  ]
}}

**重要**：只输出JSON，不要包含其他文字。

以下是论文摘要：
{chr(10).join(paper_texts)}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一位专业的天文学研究助理，必须只输出合法的JSON格式。每个小节必须有加粗小标题（用**包裹）。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 3000
    }
    response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload)
    if response.status_code == 200:
        content = response.json()['choices'][0]['message']['content']
        print("=== AI原始输出 ===")
        print(content)
        print("=== 输出结束 ===")
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError as e:
                return {"error": f"JSON解析失败: {str(e)}\n原始内容: {content}"}
        else:
            return {"error": "未找到JSON格式，原始内容: " + content}
    else:
        return {"error": f"API调用失败: {response.status_code}"}

# ========== Flask 路由 ==========

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    keyword = request.form.get('keyword', '').strip()
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

        summary_data = summarize_papers(papers, deepseek_key)
        if 'error' in summary_data:
            return jsonify({'error': summary_data['error']}), 500

        categories = summary_data.get('categories', [])
        if not isinstance(categories, list):
            categories = []

        set_category_cache(keyword, categories)

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
                for p in papers:
                    if p['title'].strip().lower() == title.lower():
                        matched = p
                        break
                if matched:
                    cat['papers_with_links'].append({
                        'title': matched['title'],
                        'bibcode': matched['bibcode'],
                        'authors': matched['authors'],
                        'first_author': matched['first_author'],
                        'year': matched['year'],
                        'abstract': matched['abstract'],
                        'citations': matched['citations'],
                        'bibstem': matched['bibstem']
                    })
                else:
                    cat['papers_with_links'].append({
                        'title': title,
                        'bibcode': None
                    })

        return jsonify({
            'overview': summary_data.get('overview', ''),
            'categories': categories,
            'papers': papers
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': f'处理出错: {str(e)}'}), 500

@app.route('/expand', methods=['POST'])
def expand_topic():
    data = request.get_json()
    topic = data.get('topic', '')
    papers = data.get('papers', [])

    if not topic or not papers:
        return jsonify({'error': '缺少参数'}), 400

    deepseek_key = request.headers.get('X-DeepSeek-Key', '').strip()
    if not deepseek_key:
        return jsonify({'error': '未提供 DeepSeek API Key，请在设置中填写'}), 400

    paper_texts = []
    for i, p in enumerate(papers, 1):
        abstract = p.get('abstract', '无摘要')[:500] + ("..." if len(p.get('abstract', '')) > 500 else "")
        paper_texts.append(f"论文{i}: {p.get('title', '无标题')} （{p.get('authors', '')}, {p.get('year', '')}）\n摘要: {abstract}")

    prompt = f"""你是一位专业的天文学研究助理。用户正在研究主题：**{topic}**，并希望针对该主题下引用的具体论文，获得一份更详细的介绍。

**重要：编号重置规则（必须严格遵守）**
本次分析仅涉及下方提供的 {len(papers)} 篇论文。**请统一使用“论文1”到“论文{len(papers)}”的新编号**。即使主综述中曾使用过“论文19”等旧编号，**在本详情中一律作废**，只使用新编号。绝对禁止提及任何超出 1 到 {len(papers)} 范围的编号。

请根据以下提供的论文摘要撰写详细介绍（约1500-2000字），要求：
- 每篇提供的论文，**必须且只能生成一个独立的小节**，绝对不要将同一篇论文拆分成多个小节。
- 每个小节使用 **论文X 的方法与结论** 作为小标题（X为论文编号，从1开始）。
- 详细说明该论文使用的研究方法、关键数据、主要结论以及可能的局限性。
- **如果只有一篇论文，则只详细介绍这一篇，不要生成“综合对比”部分**。
- 如果有多篇论文，则在介绍完所有论文后，增加一个“综合对比”小节，指出关联、分歧或互补性。
- 语言专业客观，引用具体数据（如红移值、哈勃常数、置信区间等）。
- **不要使用Markdown标题（如##），只使用纯文本和 **加粗** 标注小标题。**

**事实约束（必须严格遵守）**：
1. 严禁凭空编造数据、数值或结论。文中出现的任何具体物理量（如红移、哈勃常数、置信区间），**必须**能在上方提供的摘要中找到对应依据。
2. 若某个结论或数据是依据多篇摘要综合推断的，请在句末**明确标注对应的论文编号**（如“（综合论文1、论文3推断） ”）。
3. 如果摘要中未提供具体数值，只提供了定性描述（如“显著”、“较高”），请使用定性词汇，**切勿**自行估算或补充具体数字。

以下是提供的论文摘要：
{chr(10).join(paper_texts)}

请直接输出纯文本格式的详细介绍，不需要 JSON。
"""

    headers = {
        "Authorization": f"Bearer {deepseek_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一位专业的天文学研究助理，擅长深入分析论文内容。输出纯文本，使用**加粗**表示小标题，不要Markdown。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 3000
    }
    try:
        response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            return jsonify({'detailed_review': content})
        else:
            return jsonify({'error': f'AI调用失败: {response.status_code}'}), 500
    except Exception as e:
        return jsonify({'error': f'请求出错: {str(e)}'}), 500

# ========== 知识图谱 ==========
@app.route('/graph/<keyword>')
def show_graph(keyword):
    keyword = keyword.strip()
    if not keyword:
        return "关键词不能为空", 400

    ads_token = request.headers.get('X-ADS-Token', '').strip()
    if not ads_token:
        return "请在设置中填写 ADS Token 以生成知识图谱", 400

    papers = fetch_papers(keyword, max_results=25, ads_token=ads_token)
    if not papers:
        return "未找到相关论文，无法生成图谱", 404

    categories = category_cache.get(keyword)
    if categories is None:
        return "需要 DeepSeek API Key 来生成分类，请在主页面搜索后查看", 400

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
            for p in papers:
                if p['title'].strip().lower() == title.lower():
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
    app.run(host='0.0.0.0', port=5000, debug=True)