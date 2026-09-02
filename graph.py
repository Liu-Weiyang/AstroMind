# ========== 知识图谱：构建并返回独立 HTML 页 ==========
import networkx as nx
from pyvis.network import Network

from cache import result_cache
from utils import extract_title, norm_title, title_similarity


def render_graph_page(keyword):
    """基于 /search 缓存构建知识图谱页面。返回 (html_or_message, status_code)。"""
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

    page = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>知识图谱 - {keyword}</title>
        <style>
            body {{ margin: 0; background: #0B1319; font-family: 'Nunito Sans', 'Helvetica Neue', Arial, sans-serif; }}
            .header {{ padding: 20px 30px; background: rgba(18, 28, 40, 0.8); border-bottom: 1px solid rgba(255,255,255,0.06); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; }}
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
    return page, 200
