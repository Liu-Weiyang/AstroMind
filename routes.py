# ========== Web 路由（Flask Blueprint） ==========
from concurrent.futures import ThreadPoolExecutor

import requests
from flask import Blueprint, jsonify, render_template, request

from cache import set_result_cache
from config import CONNECT_SYSTEM
from deepseek import _call_deepseek, _parse_json, _repair_json
from graph import render_graph_page
from prompts import (build_connect_stage1_prompt, build_connect_stage2_instruction,
                     build_summarize_papers_prompt, build_translate_prompt)
from scix import fetch_papers, lookup_paper_by_title
from services import _connect_single_problem, _connect_summary, summarize_papers
from utils import extract_title, norm_title, title_similarity

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/search', methods=['POST'])
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


@bp.route('/translate', methods=['POST'])
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


@bp.route('/expand', methods=['POST'])
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


@bp.route('/connect', methods=['POST'])
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


@bp.route('/graph/<keyword>')
def show_graph(keyword):
    body, status = render_graph_page(keyword)
    return body, status
