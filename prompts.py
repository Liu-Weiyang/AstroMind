# ========== 提示词构建（纯文本生成，不发起调用） ==========
from utils import transcribe_math


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
    """主卡片（概念介绍）提示词：以关键词译名开头 → 总体介绍 → 3-4 个主题分区 → 关键困难。"""
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
    """主卡片/详情内容翻译提示词（综述 + 分类名 + 详情）。"""
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


def build_connect_stage1_prompt(topic, context, lang='zh', problems=None):
    """跨领域连接 · 阶段一：提炼本质 + 多视角候选生成。"""
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
    """跨领域连接 · 阶段二：独立评分排序（保留前 3 个，内容详细）。"""
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
