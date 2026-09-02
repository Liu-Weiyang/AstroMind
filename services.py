# ========== AI 业务编排（综述生成 / 跨领域连接流水线） ==========
import requests

from config import CONNECT_SYSTEM
from deepseek import _call_deepseek, _parse_json, _repair_json
from prompts import (build_connect_stage1_prompt, build_connect_stage2_instruction,
                     build_summary_prompt)


def summarize_papers(papers, api_key, lang='zh', topic=None):
    """生成主卡片内容：调用模型产出 {overview, categories} JSON。"""
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
