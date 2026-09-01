// 模拟 index.html 中的纯函数，验证 Bug1（段落重复）与 Bug2（详情标题格式）修复
'use strict';

// ---------- 从 index.html 复制的纯逻辑 ----------
// i18n 桩（测试默认用中文）
var lang = 'zh';
var I18N = {
    zh: {
        'detail.meta': '（{0}，引用数：{1}）',
        'detail.metaNoJournal': '（引用数：{0}）'
    },
    en: {
        'detail.meta': ' ({0}, citations: {1})',
        'detail.metaNoJournal': ' (citations: {0})'
    }
};
function t(key) {
    var entry = (I18N[lang] && I18N[lang][key]);
    if (entry === undefined) entry = key;
    var args = Array.prototype.slice.call(arguments, 1);
    for (var i = 0; i < args.length; i++) {
        entry = entry.split('{' + i + '}').join(args[i]);
    }
    return entry;
}

function deriveShortTitle(text) {
    var m = text.match(/^(.{2,120}?)[。．！？.!?]/);
    var t = m ? m[1] : '';
    t = t.replace(/[:：\-–—,，\s]+$/g, '').trim();
    if (t.length < 4) return '';
    return t;
}

function parseParagraph(trimmed) {
    var title = '';
    var content = trimmed;
    var titleMatch = trimmed.match(/^\*\*(.*?)\*\*/);
    if (titleMatch) {
        title = titleMatch[1].trim();
        content = trimmed.replace(/^\*\*.*?\*\*/, '').trim();
        content = content.replace(/^[:：\-–—\s]+/, '');
    } else {
        var t = deriveShortTitle(trimmed);
        if (t) {
            var rest = trimmed.slice(t.length).replace(/^[。．！？.!?，,：:；;\s]+/, '').trim();
            if (rest.length >= 10) {
                title = t;
                content = rest;
            }
        }
    }
    return { title: title, content: content };
}

function mergeParagraphs(rawParagraphs) {
    var merged = [];
    for (var i = 0; i < rawParagraphs.length; i++) {
        var para = rawParagraphs[i].trim();
        if (/^\*\*[^*]+\*\*$/.test(para)) {
            if (i + 1 < rawParagraphs.length) {
                merged.push(para + '\n' + rawParagraphs[i + 1].trim());
                i++;
                continue;
            }
            continue;
        }
        merged.push(para);
    }
    return merged;
}

function formatPaperHeader(num, papers) {
    var idx = parseInt(num) - 1;
    if (idx < 0 || idx >= papers.length) return null;
    var p = papers[idx];
    var firstAuthor = p.first_author || p.authors || 'Unknown';
    var authorShort = String(firstAuthor).replace(/\s*et\s+al\.?$/i, '').trim();
    authorShort = authorShort.split(',')[0].trim();
    var year = p.year || '????';
    var citations = p.citations || 0;
    var bibstem = p.bibstem || '';
    var cleanBibstem = String(bibstem).split(/[,，\s]+/)[0] || '';
    var journalPart = cleanBibstem ? t('detail.meta', cleanBibstem, citations) :
        t('detail.metaNoJournal', citations);
    var authorYear = authorShort + ' et al. ' + year;
    if (p.bibcode) {
        authorYear = '<a href="https://ui.adsabs.harvard.edu/abs/' + p.bibcode +
            '" target="_blank">' + authorYear + '</a>';
    }
    return authorYear + '<span class="detail-meta">' + journalPart + '</span>';
}

function titleSimilarity(a, b) {
    var ta = normTitle(a).split(' ').filter(function(w) { return w.length > 0; });
    var tb = normTitle(b).split(' ').filter(function(w) { return w.length > 0; });
    if (!ta.length || !tb.length) return 0;
    var set = {};
    var inter = 0;
    ta.forEach(function(w) { set[w] = true; });
    tb.forEach(function(w) { if (set[w]) inter++; });
    return inter / Math.min(ta.length, tb.length);
}

function formatDetailReview(text, papers) {
    var content = text;
    content = content.replace(/\*\*论文\s*(\d+)[^\n]*?\*\*/g, function(match, num) {
        var header = formatPaperHeader(num, papers);
        return header === null ? match : '<strong class="detail-title">' + header + '</strong>';
    });
    content = content.replace(/^(\s*)\*\*((?!论文\s*\d)[^*\n])*论文\s*(\d+)((?!论文\s*\d)[^*\n])*\*\*\s*$/gm, function(match, ws, pre, num) {
        var header = formatPaperHeader(num, papers);
        return header === null ? match : '<strong class="detail-title">' + header + '</strong>';
    });
    content = content.replace(/^(\s*)\*\*([^*\n]*)\*\*\s*$/gm, function(match, ws, inner) {
        var ym = inner.match(/\b(19|20)\d{2}\b/);
        if (!ym) return match;
        var year = ym[0];
        for (var i = 0; i < papers.length; i++) {
            var p = papers[i];
            if (String(p.year || '') !== year) continue;
            var fa = String(p.first_author || p.authors || '');
            var surname = fa.replace(/\s*et\s+al\.?$/i, '').trim().split(',')[0].trim();
            if (!surname || inner.indexOf(surname) === -1) continue;
            var header = formatPaperHeader(i + 1, papers);
            if (header !== null) return '<strong class="detail-title">' + header + '</strong>';
        }
        return match;
    });
    content = content.replace(/^(\s*)论文\s*(\d+)[^\n]{0,30}?(方法与结论|方法|结论)[^\n]{0,12}$/gm, function(match, ws, num) {
        var header = formatPaperHeader(num, papers);
        return header === null ? match : '<strong class="detail-title">' + header + '</strong>';
    });
    content = content.replace(/论文(\d+)/g, function(match, num) {
        var idx = parseInt(num) - 1;
        if (idx >= 0 && idx < papers.length) {
            var p = papers[idx];
            var firstAuthor = p.first_author || p.authors || 'Unknown';
            var authorShort = String(firstAuthor).replace(/\s*et\s+al\.?$/i, '').trim();
            authorShort = authorShort.split(',')[0].trim();
            return authorShort + ' et al. ' + (p.year || '????');
        }
        return match;
    });
    content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    content = content.replace(/\n/g, '<br>');
    return content;
}

function normTitle(t) {
    return String(t || '').toLowerCase()
        .replace(/[^a-z0-9\u4e00-\u9fa5\s-]/g, ' ')
        .replace(/[\s-]+/g, ' ')
        .trim();
}

// ---------- 测试数据 ----------
var papers = [
    { title: 'A', first_author: 'Smith et al.', authors: 'Smith, J., Doe, A.', year: '2022', citations: 120, bibstem: 'MNRAS', bibcode: '2022MNRAS...' },
    { title: 'B', first_author: 'Wang et al.', authors: 'Wang, L.', year: '2023', citations: 45, bibstem: 'ApJ', bibcode: '2023ApJ....' },
    { title: 'C', first_author: 'Li et al.', authors: 'Li, X.', year: '2021', citations: 8, bibstem: 'PRD', bibcode: '2021PhRvD..' }
];

var pass = 0, fail = 0;
function check(name, cond, extra) {
    if (cond) { pass++; console.log('  ✅ ' + name); }
    else { fail++; console.log('  ❌ ' + name + (extra ? '  → ' + extra : '')); }
}

console.log('===== Bug1: 综述卡片段落解析 =====');

// 场景1：纯小标题段落 + 下一段（AI 把标题单独一行）
var raw1 = ['**观测进展**', '论文1使用HST数据测量H0=73.0±1.0 km/s/Mpc，与Planck结果存在显著差异。'];
var merged1 = mergeParagraphs(raw1);
check('纯标题段落与下一段合并', merged1.length === 1 && merged1[0].indexOf('**观测进展**') === 0);
var p1 = parseParagraph(merged1[0]);
check('合并后标题提取为「观测进展」', p1.title === '观测进展', JSON.stringify(p1));
check('合并后正文以「论文1」开头', p1.content.indexOf('论文1') === 0, p1.content);

// 场景2：中文段落无加粗小标题（旧代码会把整段当作标题 → 上下重复）
var chinesePara = '哈勃张力是当前宇宙学中最受关注的问题之一。论文1利用Pantheon+数据重新测量了哈勃常数，论文2则从理论角度提出了早期暗能量的解释方案。';
var p2 = parseParagraph(chinesePara);
check('中文无标题段落：标题只取第一句', p2.title.length < p2.content.length && p2.title.indexOf('哈勃张力') === 0, JSON.stringify(p2));
check('中文无标题段落：标题不等于整段（不重复）', p2.title !== chinesePara && p2.title.length < chinesePara.length * 0.5);
check('中文无标题段落：正文不再包含标题片段', p2.content.indexOf('哈勃张力') === -1, p2.content);

// 场景3：标准格式段落（**小标题** 与正文同行）
var p3 = parseParagraph('**理论模型**：论文2提出了早期暗能量模型，该模型可以在红移z>3000时提供额外能量密度。');
check('标准段落：标题「理论模型」', p3.title === '理论模型');
check('标准段落：正文去掉冒号', p3.content.indexOf('论文2') === 0, p3.content);

// 场景4：英文段落无小标题
var p4 = parseParagraph('The hubble tension refers to the discrepancy between the local and early universe measurements of the expansion rate. Paper 1 addresses this with new SNe data.');
check('英文段落：有标题且不重复', p4.title.length > 0 && p4.title !== p4.content && p4.content.indexOf('Paper 1') === 0, JSON.stringify(p4));

// 场景5：单句短段落（无标题时不应生成近似全文的标题）
var p5 = parseParagraph('这是仅有的一句话总结，用于验证短段落场景是否会出现整段重复的问题。');
check('单句短段落：无标题（避免重复）', p5.title === '', JSON.stringify(p5));

// 场景6：无标题时标题为空的段落（正文原样保留）
var p6 = parseParagraph('论文1与论文2的结果在统计上一致，均支持当前宇宙学模型。');
check('无标题段落：正文保留完整', p6.title === '' && p6.content.indexOf('论文1') === 0);

// 场景7：整段重复去重（同一段落出现两次）
var raw2 = ['**观测进展**\n论文1的观测结果。', '**观测进展**\n论文1的观测结果。', '**理论模型**\n论文2的理论。'];
var merged2 = mergeParagraphs(raw2);
var seen = new Set();
var filtered = merged2.filter(function(para) {
    var fp = para.trim().substring(0, 100);
    if (seen.has(fp)) return false;
    seen.add(fp);
    return true;
});
check('重复段落按指纹去重', filtered.length === 2);

// 场景8：结尾孤立的纯标题段落（无正文）应被丢弃
var raw3 = ['**观测进展**\n论文1的观测结果。', '**理论模型**'];
var merged3 = mergeParagraphs(raw3);
check('结尾孤立标题被丢弃', merged3.length === 1 && merged3[0].indexOf('**观测进展**') === 0, JSON.stringify(merged3));

// 场景9：多段连续纯标题 + 正文
var raw4 = ['**观测进展**', '论文1的观测结果。', '**理论模型**', '论文2的理论结果。'];
var merged4 = mergeParagraphs(raw4);
check('多段标题-正文对合并正确', merged4.length === 2 && merged4[1].indexOf('**理论模型**') === 0, JSON.stringify(merged4));

console.log('');
console.log('===== Bug2: 详情小标题统一为作者格式 =====');

// 场景A：标准格式
var detailA = '**论文1 的方法与结论**\n论文1使用HST观测了1000颗造父变星。\n\n**论文2 的方法与结论**\n论文2分析了CMB数据。\n\n**综合对比**\n论文1与论文2的结果互补（综合论文1、论文3推断）。';
var outA = formatDetailReview(detailA, papers);
check('A1: 论文1标题转为带链接的作者格式', outA.indexOf('<a href="https://ui.adsabs.harvard.edu/abs/2022MNRAS..." target="_blank">Smith et al. 2022</a><span class="detail-meta">（MNRAS，引用数：120）</span>') !== -1, outA);
check('A2: 论文2标题转为带链接的作者格式', outA.indexOf('<a href="https://ui.adsabs.harvard.edu/abs/2023ApJ...." target="_blank">Wang et al. 2023</a><span class="detail-meta">（ApJ，引用数：45）</span>') !== -1);
check('A3: 标题带 detail-title 类', (outA.match(/detail-title/g) || []).length === 2);
check('A4: 综合对比标题保留（不加作者格式）', outA.indexOf('<strong>综合对比</strong>') !== -1);
check('A5: 句中的（综合论文1、论文3推断）不会被当作小标题（detail-title 仍为 2 个）', (outA.match(/detail-title/g) || []).length === 2 && outA.indexOf('综合') !== -1, outA);

// 场景A6：第一作者带缩写（"Liu, X."）→ 只保留姓氏，精确匹配用户要求的格式
var papersLiu = [
    { title: 'D', first_author: 'Liu, X.', authors: 'Liu, X., Chen, Y.', year: '2024', citations: 12, bibstem: 'MNRAS', bibcode: '2024MNRAS...' }
];
var outA6 = formatDetailReview('**论文1 的方法与结论**\n论文1的内容。', papersLiu);
check('A6: 精确格式「Liu et al. 2024（MNRAS，引用数：12）」带链接', outA6.indexOf('<a href="https://ui.adsabs.harvard.edu/abs/2024MNRAS..." target="_blank">Liu et al. 2024</a><span class="detail-meta">（MNRAS，引用数：12）</span>') !== -1, outA6);
check('A6b: 不带缩写「Liu, X.」', outA6.indexOf('Liu, X. et al.') === -1, outA6);
check('A6c: 小标题链接无下划线样式由 CSS 控制（a 标签无内联下划线）', outA6.indexOf('<a ') !== -1 && outA6.indexOf('text-decoration') === -1, outA6);

// 场景B：AI 用了非标准格式（**论文1：方法与结论** / **1. 论文2 ...**）
var detailB = '**论文1：方法与结论**\n内容A。\n\n**1. 论文2 的方法与结论**\n内容B。';
var outB = formatDetailReview(detailB, papers);
check('B1: **论文1：方法与结论** 被转换', outB.indexOf('Smith et al. 2022') !== -1, outB);
check('B2: **1. 论文2 ...**（兜底第二遍）被转换', outB.indexOf('Wang et al. 2023') !== -1, outB);
check('B3: 两种格式共2个 detail-title', (outB.match(/detail-title/g) || []).length === 2, outB);

// 场景C：AI 漏了编号范围外的引用（不崩溃、保留原样）
var detailC = '**论文5 的方法与结论**\n内容。';
var outC = formatDetailReview(detailC, papers);
check('C1: 编号超出范围时保留原文', outC.indexOf('**论文5 的方法与结论**') !== -1 || outC.indexOf('<strong>论文5 的方法与结论</strong>') !== -1, outC);

// 场景D：编号带空格
var detailD = '**论文 2 的方法与结论**\n内容。';
var outD = formatDetailReview(detailD, papers);
check('D1: **论文 2 ...**（带空格）被转换', outD.indexOf('Wang et al. 2023') !== -1, outD);

// 场景E：整段只有标题（无正文）
var detailE = '**论文3 的方法与结论**';
var outE = formatDetailReview(detailE, papers);
check('E1: 只有标题也正常转换', outE.indexOf('Li et al. 2021') !== -1, outE);

// 场景F：AI 把作者名直接写进小标题（**Cai et al. 2026 的方法与结论**）
var papersF = [
    { title: 'F', first_author: 'Cai, L.', authors: 'Cai, L., Zhang, W.', year: '2026', citations: 8, bibstem: 'RAA', bibcode: '2026RAA....' }
];
var detailF = '**Cai et al. 2026 的方法与结论**\n论文1的内容。';
var outF = formatDetailReview(detailF, papersF);
check('F1: 作者名标题按「姓氏+年份」匹配并转换（带链接）', outF.indexOf('<a href="https://ui.adsabs.harvard.edu/abs/2026RAA...." target="_blank">Cai et al. 2026</a><span class="detail-meta">（RAA，引用数：8）</span>') !== -1, outF);
check('F2: 不再残留「的方法与结论」', outF.indexOf('的方法与结论') === -1, outF);

// 场景G：作者名标题但年份对不上 / 姓氏不匹配 → 保留原文（不误伤）
var detailG = '**Cai et al. 2026 的方法与结论**\n内容。';
var outG = formatDetailReview(detailG, papers); // papers 里没有 Cai/2026
check('G1: 匹配不到论文时保留原文（不误转）', outG.indexOf('的方法与结论') !== -1, outG);

// 场景H：AI 忘记加粗的纯文本小标题行「论文1 的方法与结论」
var detailH = '论文1 的方法与结论\n论文1的内容。\n\n**综合对比**\n两者互补。';
var outH = formatDetailReview(detailH, papers);
check('H1: 纯文本小标题行被转换（带链接）', outH.indexOf('<a href="https://ui.adsabs.harvard.edu/abs/2022MNRAS..." target="_blank">Smith et al. 2022</a><span class="detail-meta">（MNRAS，引用数：120）</span>') !== -1, outH);
check('H2: 综合对比标题（无年份）不受影响', outH.indexOf('<strong>综合对比</strong>') !== -1, outH);

console.log('');
console.log('===== Bug B: 分类抽屉标题模糊匹配 =====');

// 模拟 displayResults 里的匹配链：bibcode → 规范化相等 → 词级相似度
function resolvePaperIndex(catEntry, currentPapers) {
    var index = -1;
    if (catEntry.bibcode) {
        for (var i = 0; i < currentPapers.length; i++) {
            if (currentPapers[i].bibcode === catEntry.bibcode) { index = i; break; }
        }
    }
    if (index === -1) {
        var norm = normTitle(catEntry.title);
        index = currentPapers.findIndex(function(paper) { return normTitle(paper.title) === norm; });
    }
    if (index === -1) {
        index = currentPapers.findIndex(function(paper) {
            return titleSimilarity(paper.title, catEntry.title) >= 0.7;
        });
    }
    return index;
}

var listPapers = [
    { title: 'Single Field Slow-Roll Inflation With Step Uplift to ns=1', bibcode: '2026RAA....1234A', authors: 'Cai, L.', year: '2026' },
    { title: 'The Pantheon+ Analysis: Cosmological Constraints', bibcode: '2022ApJ....1111B', authors: 'Brout, D.', year: '2022' },
    { title: 'Addressing the H0 tension through matter with pressure and no early dark energy', bibcode: '2025PhRvD..1111C', authors: 'Zhang, W.', year: '2025' }
];
// AI 分类里给出的标题（大小写/标点/多余空格/个别词与原文不同）
var catTitle1 = 'Single field slow-roll inflation with step uplift to ns=1';
var catTitle2 = 'The pantheon+ analysis: Cosmological constraints.';
var catTitle3 = 'Addressing the H0 tension through matter with pressure and no early dark energy'; // 与原文一致
var catTitle4 = 'Addressing the H0 tension via matter with pressure and no early dark energy';    // via 与 through 不同
check('B1: 大小写+等号差异能匹配（ns=1）', resolvePaperIndex({ title: catTitle1 }, listPapers) === 0);
check('B2: 标点/大小写差异能匹配', resolvePaperIndex({ title: catTitle2 }, listPapers) === 1);
check('B3: 完全不同的标题不误配', resolvePaperIndex({ title: 'Some other paper title' }, listPapers) === -1);
check('B4: 规范化后 ns=1 与 ns = 1 等价', normTitle('ns=1') === normTitle('ns = 1'));
check('B5: 规范化后 slow-roll 与 slow roll 等价', normTitle('slow-roll') === normTitle('slow roll'));
check('B6: 与原文一致的标题直接匹配', resolvePaperIndex({ title: catTitle3 }, listPapers) === 2);
check('B7: 词级差异（through→via）仍能相似度匹配', resolvePaperIndex({ title: catTitle4 }, listPapers) === 2);

console.log('');
console.log('===== 抽屉渲染：无「论文X：」前缀、无链接条目不展示 =====');

// 模拟 displayResults 的分类渲染（新逻辑）
function renderDrawer(catEntries, currentPapers) {
    var html = '';
    catEntries.forEach(function(p) {
        var idx = resolvePaperIndex(p, currentPapers);
        var matchedPaper = (idx !== -1) ? currentPapers[idx] : null;
        var realBibcode = p.bibcode || (matchedPaper ? matchedPaper.bibcode : null);
        if (!realBibcode) return;   // 无链接条目不展示
        html += '<a class="paper-link" href="https://ui.adsabs.harvard.edu/abs/' + realBibcode + '">';
        html += p.title;            // 不再有「论文X：」前缀
        html += '</a>';
    });
    return html;
}

var drawer = renderDrawer([
    { title: 'Single field slow-roll inflation with step uplift to ns=1' },  // 无 bibcode，靠相似度补链
    { title: 'Some totally unrelated garbage title' }                        // 无法解析 → 不展示
], listPapers);
check('D1: 无 bibcode 的条目也能补出链接', drawer.indexOf('https://ui.adsabs.harvard.edu/abs/2026RAA....1234A') !== -1, drawer);
check('D2: 不再出现「论文X：」前缀', drawer.indexOf('论文') === -1, drawer);
check('D3: 解析不出链接的条目被跳过（不出现无链接字样）', drawer.indexOf('无链接') === -1 && drawer.indexOf('Some totally') === -1, drawer);

console.log('');
console.log('===== 中英文切换：详情小标题元信息 =====');

// 英文模式
lang = 'en';
var outEn = formatDetailReview('**论文1 的方法与结论**\n论文1的内容。', papers);
check('E1: 英文小标题格式 (MNRAS, citations: 120)', outEn.indexOf('<a href="https://ui.adsabs.harvard.edu/abs/2022MNRAS..." target="_blank">Smith et al. 2022</a><span class="detail-meta"> (MNRAS, citations: 120)</span>') !== -1, outEn);
// 切回中文
lang = 'zh';
var outZh = formatDetailReview('**论文1 的方法与结论**\n论文1的内容。', papers);
check('E2: 中文小标题格式（引用数：120）', outZh.indexOf('<span class="detail-meta">（MNRAS，引用数：120）</span>') !== -1, outZh);
check('E3: t() 占位符替换 {0} {1}', t('detail.meta', 'RAA', 8) === '（RAA，引用数：8）');

console.log('');
console.log('===== 跨领域连接报告渲染 =====');

// escapeHtml 桩（真实实现依赖 DOM，测试里用简单转义替代）
function escapeHtml(text) {
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// 复刻 index.html 的 formatConnectReport（JSON → HTML，含评分/理由/验证路径/候选池）
function scoreChip(label, value, isTotal) {
    if (value === undefined || value === null) return '';
    return '<span class="score-chip' + (isTotal ? ' total' : '') + '">' + escapeHtml(label) +
        ' <b>' + value + '</b></span>';
}

function formatConnectReport(data, pool) {
    if (!data || typeof data !== 'object') {
        return '<div style="color:#FF6B6B;">解析失败</div>';
    }
    var html = '';
    if (pool && pool.count > 0) {
        var fields = (pool.fields || []).join(' / ');
        html += '<div class="connect-pool">候选池：' + pool.count + ' 个候选 · 覆盖 ' + fields + '</div>';
    }
    var sections = data.sections || [];
    if (!sections.length) {
        html += '<div style="color:rgba(255,255,255,0.55);">没有可分析的困难条目。</div>';
    }
    sections.forEach(function(sec, i) {
        html += '<div class="detail-title">' + (i + 1) + '. ' + escapeHtml(sec.problem || '') + '</div>';
        if (sec.essence) {
            html += '<div class="connect-label">抽象本质</div>';
            html += '<div class="connect-body">' + escapeHtml(sec.essence) + '</div>';
        }
        (sec.matches || []).forEach(function(m) {
            html += '<div class="connect-sub">' + escapeHtml(m.field || '') +
                (m.concept ? ' · ' + escapeHtml(m.concept) : '') + '</div>';
            if (m.solution) {
                html += '<div class="connect-body"><span class="connect-inline">解决方式：</span>' + escapeHtml(m.solution) + '</div>';
            }
            if (m.why) {
                html += '<div class="connect-body"><span class="connect-inline">结构相似性：</span>' + escapeHtml(m.why) + '</div>';
            }
            if (m.scores) {
                var s = m.scores;
                html += '<div class="connect-scores">';
                html += scoreChip('同构', s.isomorphism);
                html += scoreChip('成熟', s.maturity);
                html += scoreChip('便利', s.convenience);
                html += scoreChip('收益', s.payoff);
                if (m.total) html += scoreChip('总分', m.total, true);
                html += '</div>';
            }
            if (m.rationale) {
                html += '<div class="connect-rationale"><span class="connect-inline">入选理由（为何优于邻近学科）：</span>' + escapeHtml(m.rationale) + '</div>';
            }
            if (m.verify) {
                html += '<div class="connect-verify"><span class="connect-inline">验证路径：</span>' + escapeHtml(m.verify) + '</div>';
            }
        });
        if (sec.migration) {
            html += '<div class="connect-migration"><span class="connect-inline">迁移预期</span>' + escapeHtml(sec.migration) + '</div>';
        }
    });
    if (data.summary) {
        html += '<div class="detail-title">总体结论</div>';
        html += '<div class="connect-body">' + escapeHtml(data.summary) + '</div>';
    }
    return html;
}

var report = {
    sections: [{
        problem: 'H0 测量与 CMB 拟合差异 5.2σ',
        essence: '两个独立测量系统的系统偏差估计问题',
        matches: [{
            field: '计量经济学', concept: '工具变量法', solution: 'IV 回归', why: '同为消除内生性偏差',
            scores: { isomorphism: 4, maturity: 5, convenience: 3, payoff: 4 },
            total: 16,
            rationale: '比物理学中的对应方法更成熟',
            verify: '用合成数据先做偏差消除实验'
        }],
        migration: '可显著降低系统误差来源'
    }],
    summary: '工具变量法最值得尝试'
};
var connHtml = formatConnectReport(report, { count: 3, fields: ['计量经济学', '音乐理论', '控制论'] });
check('C1: 每个困难生成一个 detail-title 小标题', (connHtml.match(/detail-title/g) || []).length === 2, connHtml);
check('C2: 抽象本质有标签', connHtml.indexOf('抽象本质') !== -1 && connHtml.indexOf('系统偏差估计问题') !== -1, connHtml);
check('C3: 跨领域匹配含领域与方法', connHtml.indexOf('计量经济学') !== -1 && connHtml.indexOf('工具变量法') !== -1, connHtml);
check('C4: 迁移预期有专属样式', connHtml.indexOf('connect-migration') !== -1 && connHtml.indexOf('可显著降低系统误差来源') !== -1, connHtml);
check('C5: 总体结论渲染', connHtml.indexOf('总体结论') !== -1 && connHtml.indexOf('工具变量法最值得尝试') !== -1, connHtml);
check('C6: 评分条渲染（四维 + 总分）', (connHtml.match(/score-chip/g) || []).length === 5
      && connHtml.indexOf('总分') !== -1 && connHtml.indexOf('<b>16</b>') !== -1, connHtml);
check('C7: 入选理由与验证路径渲染', connHtml.indexOf('入选理由') !== -1 && connHtml.indexOf('合成数据') !== -1, connHtml);
check('C8: 候选池展示搜索广度', connHtml.indexOf('connect-pool') !== -1 && connHtml.indexOf('3 个候选') !== -1, connHtml);
check('C9: HTML 转义生效（<script> 不注入）', formatConnectReport({ sections: [{ problem: '<script>alert(1)</script>' }] }).indexOf('&lt;script&gt;') !== -1);
check('C10: 空 sections 显示占位提示', formatConnectReport({ sections: [] }).indexOf('没有可分析的困难条目') !== -1);

console.log('');
console.log('结果: ' + pass + ' 通过, ' + fail + ' 失败');
process.exit(fail ? 1 : 0);
