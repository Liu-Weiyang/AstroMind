# 后端逻辑测试：语言参数贯穿 搜索/详情/翻译，及提示词语言指令
# 运行：python3 test_backend.py
import json
from unittest.mock import patch

import app as m

pass_count = 0
fail_count = 0

def check(name, cond, extra=''):
    global pass_count, fail_count
    if cond:
        pass_count += 1
        print('  ✅ ' + name)
    else:
        fail_count += 1
        print('  ❌ ' + name + ('  → ' + str(extra) if extra else ''))

PAPERS = [{
    'title': 'Test Paper', 'abstract': 'abs', 'authors': 'Cai, L.',
    'first_author': 'Cai, L.', 'year': '2026', 'citations': 8,
    'bibstem': 'RAA', 'bibcode': '2026RAA....'
}]

print('===== 提示词语言指令 =====')
p_zh = m.build_summary_prompt(PAPERS, 'zh')
p_en = m.build_summary_prompt(PAPERS, 'en')
check('综述提示词(zh)含「中文」', '中文' in p_zh)
check('综述提示词(en)含「English」', 'English' in p_en)
check('综述提示词保留「论文1」编号要求', '论文1' in p_en and '论文X' in p_en)
check('综述提示词(zh)含关键困难小标题', '当前关键困难与待解问题' in p_zh)
check('综述提示词(en)含英文关键困难小标题', 'Current Key Difficulties and Open Problems' in p_en)
check('综述提示词要求覆盖全部论文', '全部' in p_zh and '引用' in p_zh and '不得遗漏' in p_zh)
p_kw = m.build_summary_prompt(PAPERS, 'zh', 'early dark energy')
check('综述提示词(带关键词)要求译名开头', '译名' in p_kw and '括号' in p_kw and '本综述' in p_kw and 'little red dot' in p_kw)
check('综述提示词第一小节为总体介绍', '总体介绍' in p_kw and 'Overall Introduction' in m.build_summary_prompt(PAPERS, 'en', 'early dark energy'))

# 连接功能提示词已在下方「/connect 两阶段」段落中测试（阶段一/阶段二）

s_en = m.build_summarize_papers_prompt(PAPERS, 'en')
check('详情提示词(en)含「English」', 'English' in s_en)
check('详情提示词(en)含总结要求', 'summary' in s_en.lower())
s_zh = m.build_summarize_papers_prompt(PAPERS, 'zh')
check('详情提示词(zh)含总结要求', '总结' in s_zh)
check('详情提示词(zh)含扩展分析要求', '扩展分析' in s_zh)
check('详情提示词(zh)含综合比较要求', '综合比较' in s_zh)
check('详情提示词限制 600 字', '600' in s_zh)
check('详情提示词禁止编号前缀', '前缀' in s_zh and '论文X总结' in s_zh)
check('详情提示词输出 papers/comparison JSON', '"papers"' in s_zh and '"comparison"' in s_zh)
check('详情提示词含完整摘要', 'Test Paper' in s_zh and '摘要' in s_zh)

t_en = m.build_translate_prompt({'overview': '中文综述内容', 'categories': [{'name': '观测方法'}], 'detail': '中文详情'}, 'en')
check('翻译提示词(en)含「English」', 'English' in t_en)
check('翻译提示词包含原文', '中文综述内容' in t_en and '中文详情' in t_en)
check('翻译提示词要求保留论文X编号', '论文X' in t_en)
check('翻译提示词要求论文标题不翻译', '不翻译' in t_en)
check('翻译提示词(en)要求关键困难标题准确', 'Current Key Difficulties and Open Problems' in t_en)

print('===== /search 语言参数贯穿 =====')

def fake_scix_get(url, params=None, headers=None, timeout=None):
    class R:
        status_code = 200
        text = '{}'
        def json(self):
            return {'response': {'docs': [{
                'title': ['Test Paper'], 'abstract': ['abs'], 'author': ['Cai, L.'],
                'year': '2026', 'citation_count': 8, 'bibcode': '2026RAA....', 'bibstem': 'RAA'
            }]}}
    return R()

def fake_deepseek_post(url, headers=None, **kwargs):
    class R:
        status_code = 200
        def json(self):
            return {'choices': [{'message': {'content': json.dumps({
                'overview': 'English review text',
                'categories': [{'name': 'Observational Methods', 'papers': ['Test Paper']}]
            }, ensure_ascii=False)}}]}
    return R()

client = m.app.test_client()

with patch.object(m.requests, 'get', side_effect=fake_scix_get), \
     patch.object(m.requests, 'post', side_effect=fake_deepseek_post) as mock_post:
    resp = client.post('/search', data={'keyword': 'hubble tension', 'lang': 'en'},
                       headers={'X-ADS-Token': 'tok', 'X-DeepSeek-Key': 'key'})
    body = resp.get_json()
    check('/search 返回 200', resp.status_code == 200, resp.status_code)
    check('/search 返回英文综述', body.get('overview') == 'English review text', body)
    check('/search 分类名为英文', body['categories'][0]['name'] == 'Observational Methods', body)
    # 检查 DeepSeek 收到的提示词确实要求英文
    call_args = mock_post.call_args
    prompt_sent = call_args.kwargs['json']['messages'][1]['content']
    check('DeepSeek 收到的提示词含「English」', 'English' in prompt_sent)
    # 分类论文标题匹配成功（相似度/规范化）
    check('分类论文匹配到 bibcode', body['categories'][0]['papers_with_links'][0]['bibcode'] == '2026RAA....',
          body['categories'][0].get('papers_with_links'))

print('===== /translate 翻译接口 =====')

def fake_translate_post(url, headers=None, **kwargs):
    class R:
        status_code = 200
        def json(self):
            return {'choices': [{'message': {'content': json.dumps({
                'overview': 'Translated English overview',
                'category_names': ['Observational Methods'],
                'detail': 'Translated English detail'
            }, ensure_ascii=False)}}]}
    return R()

with patch.object(m.requests, 'post', side_effect=fake_translate_post) as mock_post:
    resp = client.post('/translate', json={
        'lang': 'en',
        'overview': '中文综述',
        'categories': [{'name': '观测方法', 'papers': ['Test Paper']}],
        'detail': '中文详情'
    }, headers={'X-DeepSeek-Key': 'key'})
    body = resp.get_json()
    check('/translate 返回 200', resp.status_code == 200, resp.status_code)
    check('/translate 返回翻译后综述', body.get('overview') == 'Translated English overview', body)
    check('/translate 返回分类名列表', body.get('category_names') == ['Observational Methods'], body)
    check('/translate 返回翻译后详情', body.get('detail') == 'Translated English detail', body)
    prompt_sent = mock_post.call_args.kwargs['json']['messages'][1]['content']
    check('翻译提示词包含目标语言与原文', 'English' in prompt_sent and '中文综述' in prompt_sent)

with patch.object(m.requests, 'post', side_effect=fake_translate_post):
    resp = client.post('/translate', json={'lang': 'en', 'overview': 'x'},
                       headers={'X-DeepSeek-Key': 'key'})
    check('/translate 无分类/详情也能翻译综述', resp.status_code == 200)

resp = client.post('/translate', json={'lang': 'en', 'overview': 'x'})
check('/translate 缺 DeepSeek Key 返回 400', resp.status_code == 400)

print('===== /expand 语言参数 =====')

def fake_expand_post(url, headers=None, **kwargs):
    class R:
        status_code = 200
        def json(self):
            return {'choices': [{'message': {'content': json.dumps({
                'papers': [{'summary': 'A short summary.', 'analysis': 'Future work suggestion.'}],
                'comparison': 'Common points and contradictions.'
            }, ensure_ascii=False)}}]}
    return R()

with patch.object(m.requests, 'post', side_effect=fake_expand_post) as mock_post:
    resp = client.post('/expand', json={'topic': 't', 'papers': [{'title': 'x', 'abstract': 'a'}], 'lang': 'en'},
                       headers={'X-DeepSeek-Key': 'key'})
    body = resp.get_json()
    check('/expand 返回 200', resp.status_code == 200, resp.status_code)
    check('/expand 返回总结+扩展分析', body.get('papers', [{}])[0].get('summary') == 'A short summary.'
          and body['papers'][0].get('analysis') == 'Future work suggestion.', body)
    check('/expand 返回综合比较', body.get('comparison') == 'Common points and contradictions.', body)
    prompt_sent = mock_post.call_args.kwargs['json']['messages'][1]['content']
    check('/expand 提示词含「English」', 'English' in prompt_sent)

print('===== /connect 跨领域连接（两阶段） =====')

# 阶段一提示词
c1_zh = m.build_connect_stage1_prompt('Hubble Tension', '困难列表：观测上 H0 差异 5.2σ；理论上 EDE 破坏高 l 谱拟合。', 'zh')
c1_en = m.build_connect_stage1_prompt('Hubble Tension', 'difficulties list', 'en')
check('阶段一提示词含「他山之石」', '他山之石' in c1_zh)
check('阶段一提示词含多透镜要求', '数学结构透镜' in c1_zh and '数据处理透镜' in c1_zh and '系统动力学透镜' in c1_zh and '模式与结构透镜' in c1_zh)
check('阶段一要求非相邻领域候选', '非相邻领域' in c1_zh)
check('阶段一 JSON 含 essence/candidates', '"essence"' in c1_zh and '"candidates"' in c1_zh and '"similarity"' in c1_zh)
check('阶段一(en)含「English」', 'English' in c1_en)

# 阶段二指令
c2 = m.build_connect_stage2_instruction('zh')
check('阶段二含评分表维度', all(k in c2 for k in ('isomorphism', 'maturity', 'convenience', 'payoff')))
check('阶段二含评分输出字段', '"scores"' in c2 and '"total"' in c2 and '"rationale"' in c2 and '"verify"' in c2)
check('阶段二强调独立评估', '独立' in c2)

def fake_connect_post(url, headers=None, **kwargs):
    msgs = kwargs['json']['messages']
    if len(msgs) == 2:
        # 阶段一：返回候选池
        content = json.dumps({
            'essence': '参数估计的系统偏差问题',
            'candidates': [
                {'field': '计量经济学', 'concept': '工具变量法', 'similarity': '同为消除内生性偏差'},
                {'field': '音乐理论', 'concept': '节拍同步', 'similarity': '多周期锁定'},
                {'field': '控制论', 'concept': '鲁棒控制', 'similarity': '扰动抑制'}
            ]
        }, ensure_ascii=False)
    else:
        # 阶段二：返回评分报告
        content = json.dumps({
            'sections': [{
                'problem': 'H0 差异 5.2σ',
                'essence': '参数估计的系统偏差问题',
                'matches': [{
                    'field': '计量经济学', 'concept': '工具变量法', 'solution': 'IV 回归', 'why': '同为消除内生性偏差',
                    'scores': {'isomorphism': 4, 'maturity': 5, 'convenience': 3, 'payoff': 4},
                    'total': 16,
                    'rationale': '比物理学中的对应方法更成熟',
                    'verify': '用合成数据先做偏差消除实验'
                }],
                'migration': '可降低系统误差'
            }],
            'summary': '工具变量法最值得尝试'
        }, ensure_ascii=False)
    class R:
        status_code = 200
        def json(self):
            return {'choices': [{'message': {'content': content}}]}
    return R()

with patch.object(m.requests, 'post', side_effect=fake_connect_post) as mock_post:
    resp = client.post('/connect', json={'topic': 'hubble', 'context': '困难列表：H0 差异 5.2σ。', 'lang': 'zh'},
                       headers={'X-DeepSeek-Key': 'key'})
    body = resp.get_json()
    check('/connect 返回 200', resp.status_code == 200, resp.status_code)
    check('/connect 两阶段共 2 次调用', mock_post.call_count == 2, mock_post.call_count)
    check('/connect 返回结构化 sections', isinstance(body.get('connection_report', {}).get('sections'), list)
          and len(body['connection_report']['sections']) == 1, body)
    check('/connect 保留评分字段', body['connection_report']['sections'][0]['matches'][0]['scores']['maturity'] == 5
          and body['connection_report']['sections'][0]['matches'][0]['total'] == 16, body)
    check('/connect 保留理由与验证路径', body['connection_report']['sections'][0]['matches'][0]['rationale']
          and body['connection_report']['sections'][0]['matches'][0]['verify'], body)
    check('/connect 返回候选池信息', body.get('pool_count') == 3 and '音乐理论' in body.get('pool_fields', []), body)
    # 第二次调用的消息结构：system + 阶段一 user（缓存前缀）+ assistant + 阶段二 user
    call2_msgs = mock_post.call_args_list[1].kwargs['json']['messages']
    check('阶段二复用阶段一前缀并追加对话', len(call2_msgs) == 4 and call2_msgs[2]['role'] == 'assistant'
          and call2_msgs[3]['role'] == 'user', len(call2_msgs))
    check('阶段二消息前缀与阶段一一致（命中缓存）', call2_msgs[0] == call2_msgs[0]
          and call2_msgs[1]['content'] == mock_post.call_args_list[0].kwargs['json']['messages'][1]['content'])

resp = client.post('/connect', json={'topic': 'x'})
check('/connect 缺 DeepSeek Key 返回 400', resp.status_code == 400)

def fake_connect_bad_stage2(url, headers=None, **kwargs):
    msgs = kwargs['json']['messages']
    content = json.dumps({'essence': 'x', 'candidates': [{'field': 'A', 'concept': 'B', 'similarity': 'C'}]},
                         ensure_ascii=False) if len(msgs) == 2 else '抱歉，我无法回答'
    class R:
        status_code = 200
        def json(self):
            return {'choices': [{'message': {'content': content}}]}
    return R()

with patch.object(m.requests, 'post', side_effect=fake_connect_bad_stage2):
    resp = client.post('/connect', json={'topic': 'x', 'context': '困难', 'lang': 'zh'},
                       headers={'X-DeepSeek-Key': 'key'})
    check('/connect 阶段二非 JSON 时返回 500', resp.status_code == 500)

def fake_connect_bad_stage1(url, headers=None, **kwargs):
    class R:
        status_code = 200
        def json(self):
            return {'choices': [{'message': {'content': '抱歉，我无法回答'}}]}
    return R()

with patch.object(m.requests, 'post', side_effect=fake_connect_bad_stage1):
    resp = client.post('/connect', json={'topic': 'x', 'context': '困难', 'lang': 'zh'},
                       headers={'X-DeepSeek-Key': 'key'})
    check('/connect 阶段一失败时返回 500', resp.status_code == 500)

print('')
print(f'结果: {pass_count} 通过, {fail_count} 失败')
raise SystemExit(1 if fail_count else 0)
