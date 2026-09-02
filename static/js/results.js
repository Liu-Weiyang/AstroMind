        function replacePaperRefs(text, papers) {
            return text.replace(/论文(\d+)/g, function(match, num) {
                var idx = parseInt(num) - 1;
                if (idx >= 0 && idx < papers.length) {
                    var p = papers[idx];
                    var firstAuthor = p.first_author || p.authors || 'Unknown';
                    var authorShort = String(firstAuthor).replace(/\s*et\s+al\.?$/i, '').trim();
                    // 只保留姓氏，与详情小标题格式保持一致
                    authorShort = authorShort.split(',')[0].trim();
                    var year = p.year || '????';
                    if (p.bibcode) {
                        var url = 'https://ui.adsabs.harvard.edu/abs/' + p.bibcode;
                        return '<a href="' + url + '" target="_blank">' + authorShort + ' et al. ' + year + '</a>';
                    } else {
                        return authorShort + ' et al. ' + (p.year || '????');
                    }
                }
                return match;
            });
        }

        // ===== 显示结果 =====
        // 规范化标题用于模糊匹配：忽略大小写、标点、连字符与空白差异
        function normTitle(t) {
            return String(t || '').toLowerCase()
                .replace(/[^a-z0-9\u4e00-\u9fa5\s-]/g, ' ')  // 标点/符号 → 空格
                .replace(/[\s-]+/g, ' ')                     // 空白与连字符统一为单空格
                .trim();
        }

        // 标题词级相似度：共同词数 / 较短标题的词数，范围 0~1
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

        function displayResults(data) {
            connectCache = {};   // 搜索结果或内容更新后，旧的跨领域连接报告作废（点击「更新」后再点连接按钮才会重新生成）
            lastSearchData = data;   // 记录最近一次渲染的数据（语言切换时重渲染用）
            currentPapers = data.papers || [];

            var overviewText = data.overview || '';
            var rawParagraphs = overviewText.split(/\n\s*\n/).filter(function(p) { return p.trim().length > 0; });
            // 纯小标题段落与其后正文合并
            currentParagraphs = mergeParagraphs(rawParagraphs);
            // 去重：使用前100个字符作为指纹（去除首尾空白）
            var seen = new Set();
            currentParagraphs = currentParagraphs.filter(function(para) {
                var fingerprint = para.trim().substring(0, 100);
                if (seen.has(fingerprint)) return false;
                seen.add(fingerprint);
                return true;
            });

            var html = '<div class="overview-section">';
            currentParagraphs.forEach(function(para, idx) {
                var parsed = parseParagraph(para.trim());
                var title = parsed.title;
                var content = parsed.content;
                var hasRefs = /论文\d+/.test(content);
                // 「关键困难」板块：检测中英文标题，用于挂载跨领域连接按钮
                var isDifficulty = /当前关键困难与待解问题|Current Key Difficulties/.test(para);
                // 「关键困难」板块：把项目符号（- 或 •）逐条转换为数字编号（1.、2.、...）
                if (isDifficulty) {
                    var lines = content.split('\n');
                    var newLines = [];
                    var bulletIndex = 1;
                    for (var i = 0; i < lines.length; i++) {
                        var trimmed = lines[i].trim();
                        if (/^[-•]\s+/.test(trimmed)) {
                            newLines.push(bulletIndex + '. ' + trimmed.replace(/^[-•]\s+/, ''));
                            bulletIndex++;
                        } else if (trimmed) {
                            newLines.push(lines[i]);
                        }
                    }
                    content = newLines.join('\n');
                }
                // 使用修改后的 content 生成带链接与数学渲染的正文
                var contentWithLinks = replacePaperRefs(mathify(content), currentPapers);
                // 非困难板块：项目符号（- 或 •）转为独立行展示；首条 bullet 在段落开头也要补上 • 标记
                if (!isDifficulty) {
                    contentWithLinks = contentWithLinks
                        .replace(/^\s*[-•]\s+/, '<br>• ')
                        .replace(/\n\s*[-•]\s*/g, '\n<br>• ');
                }
                // 困难板块：编号条目按行换行展示；其它板块按原有逻辑合并空白
                var contentHtml = isDifficulty
                    ? contentWithLinks.replace(/\n/g, '<br>')
                    : contentWithLinks.replace(/\n/g, ' ');
                var finalContent = contentHtml.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

                html += '<div class="overview-card" data-paragraph-index="' + idx + '">';
                if (title) {
                    html += '<div class="title">' + title + '</div>';
                }
                html += '<div class="content">' + finalContent + '</div>';
                html += '<div class="actions">';
                if (hasRefs) {
                    html += '<button class="expand-btn" data-paragraph-index="' + idx + '">' + iconHtml('detail') + ' ' + t('detail.btn') + '</button>';
                }
                if (isDifficulty) {
                    html += '<button class="connect-btn" data-paragraph-index="' + idx + '" title="' + t('connect.title') + '">' + iconHtml('connect') + ' ' + t('connect.btn') + '</button>';
                }
                html += '</div></div>';
            });
            html += '</div>';

            if (data.categories && data.categories.length > 0) {
                data.categories.forEach(function(cat, idx) {
                    // 兜底：papers_with_links 为空时回退到 AI 返回的论文标题列表再匹配一次，避免抽屉空白
                    var catEntries = (cat.papers_with_links && cat.papers_with_links.length)
                        ? cat.papers_with_links
                        : (Array.isArray(cat.papers) ? cat.papers : []);
                    html += '<div class="category-card">';
                    html += '<div class="category-header" data-target="cat-' + idx + '">';
                    html += '<span>' + iconHtml('folder') + ' ' + cat.name + t('category.count', catEntries.length) + '</span>';
                    html += '<span class="arrow">▼</span>';
                    html += '</div>';
                    html += '<div class="category-body" id="cat-' + idx + '">';
                    catEntries.forEach(function(p) {
                        var isStr = (typeof p === 'string');
                        var ptitle = isStr ? p : (p.title || '');
                        var pBibcode = isStr ? null : p.bibcode;
                        var index = -1;
                        if (pBibcode) {
                            for (var i = 0; i < currentPapers.length; i++) {
                                if (currentPapers[i].bibcode === pBibcode) {
                                    index = i;
                                    break;
                                }
                            }
                        }
                        if (index === -1) {
                            // 标题模糊匹配：忽略大小写、标点与空白差异
                            var norm = normTitle(ptitle);
                            index = currentPapers.findIndex(function(paper) {
                                return normTitle(paper.title) === norm;
                            });
                        }
                        if (index === -1) {
                            // 词级相似度兜底：AI 转写标题略有出入时仍能匹配
                            index = currentPapers.findIndex(function(paper) {
                                return titleSimilarity(paper.title, ptitle) >= 0.7;
                            });
                        }
                        var matchedPaper = (index !== -1) ? currentPapers[index] : null;
                        // 分类数据缺 bibcode 时，用匹配到的论文信息补上
                        var realBibcode = pBibcode || (matchedPaper ? matchedPaper.bibcode : null);
                        var realAuthors = (isStr ? '' : p.authors) || (matchedPaper ? matchedPaper.authors : '');
                        var realYear = (isStr ? '' : p.year) || (matchedPaper ? matchedPaper.year : '');
                        // 解析不出链接的条目直接不展示，保证抽屉里列出的论文都有链接
                        if (!realBibcode) return;

                        var url = 'https://ui.adsabs.harvard.edu/abs/' + realBibcode;
                        html += '<a class="paper-link" href="' + url + '" target="_blank">';
                        html += ptitle;
                        html += '<span class="meta">' + (realAuthors || '') + ' · ' + (realYear || '') +
                            '</span>';
                            html += '</a>';
                        });
                    html += '</div></div>';
                });
            } else {
                html += '<p style="color:rgba(255,255,255,0.30);text-align:center;padding:1rem 0;">' + t('category.empty') + '</p>';
            }

            resultsDiv.innerHTML = html;

            // 有内容时取消垂直居中（贴顶），避免抽屉收回后主卡片底部与网页下沿出现空隙
            var hasContent = !!(data.overview || (data.categories && data.categories.length));
            document.body.classList.toggle('content-empty', !hasContent);

            document.querySelectorAll('.category-header').forEach(function(header) {
                header.addEventListener('click', function(e) {
                    var targetId = this.dataset.target;
                    var body = document.getElementById(targetId);
                    var arrow = this.querySelector('.arrow');
                    if (body) {
                        body.classList.toggle('open');
                        arrow.classList.toggle('open');
                    }
                });
            });

            document.querySelectorAll('.expand-btn').forEach(function(btn) {
                btn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    var idx = parseInt(this.dataset.paragraphIndex);
                    if (idx >= currentParagraphs.length) return;
                    var paraText = currentParagraphs[idx];
                    var refs = paraText.match(/论文(\d+)/g);
                    if (!refs) {
                        alert(t('detail.noRefs'));
                        return;
                    }
                    var indices = refs.map(function(ref) { return parseInt(ref.replace('论文', '')) - 1; });
                    var selected = indices.map(function(i) { return currentPapers[i]; }).filter(function(p) {
                        return p;
                    });
                    if (selected.length === 0) {
                        alert(t('detail.noMatch'));
                        return;
                    }
                    var parsed = parseParagraph(paraText.trim());
                    var title = parsed.title || t('detail.title');
                    openSidePanel(title, selected, idx, this);
                });
            });

            // 跨领域连接按钮：打开右侧面板展示「他山之石」分析
            // 把「当前关键困难与待解问题」段落拆成独立条目（- / • / 1. 开头），逐条独立分析
            function extractDifficultyBullets(context) {
                var items = [];
                String(context || '').split(/\n/).forEach(function(line) {
                    var l = line.trim();
                    if (!l) return;
                    if (/^[*\-•]\s+/.test(l)) {
                        items.push(l.replace(/^[*\-•]\s+/, '').trim());
                    } else if (/^\d+[.、)）]\s*/.test(l)) {
                        items.push(l.replace(/^\d+[.、)）]\s*/, '').trim());
                    }
                });
                return items;
            }
            document.querySelectorAll('.connect-btn').forEach(function(btn) {
                btn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    var idx = parseInt(this.dataset.paragraphIndex);
                    if (idx >= currentParagraphs.length) return;
                    var btnEl = this;
                    // 与「查看详情」一致的交互：按钮亮起（其余高亮清除）
                    document.querySelectorAll('.connect-btn').forEach(function(b) { b.classList.remove('active'); });
                    document.querySelectorAll('.expand-btn').forEach(function(b) { b.classList.remove('active'); });
                    btnEl.classList.add('active');

                    // 该段落已有连接报告 → 只做打开/关闭切换，不重新生成（重新生成需先点「更新」）
                    var cached = connectCache[idx];
                    if (cached && cached.keyword === currentKeyword) {
                        if (panelType === 'connect' && currentConnectIdx === idx && sidePanel.classList.contains('open')) {
                            closeSidePanel();
                        } else {
                            openConnectPanel(cached.report, t('connect.title'), cached.pool, idx);
                        }
                        return;
                    }
                    var context = currentParagraphs[idx];
                    var keyword = currentKeyword || keywordInput.value.trim();
                    if (!keyword) {
                        alert(t('connect.noSearch'));
                        return;
                    }
                    if (!getLocal('deepseekKey')) {
                        alert(t('connect.noKey'));
                        return;
                    }
                    // 生成中：只重新打开加载面板（不重复请求），生成完成后会自动更新内容
                    openConnectLoading(idx);
                    if (connectBusyIdx === idx) return;

                    // 逐条独立分析：拆出所有 bullet 条目（≥2 条时按条分析，否则整段兜底）
                    var problems = extractDifficultyBullets(context);
                    if (problems.length < 2) problems = null;
                    connectBusyIdx = idx;

                    var headers = {
                        'Content-Type': 'application/json',
                        'X-DeepSeek-Key': getLocal('deepseekKey') || ''
                    };
                    fetch('/connect', {
                            method: 'POST',
                            headers: headers,
                            body: JSON.stringify({ topic: keyword, context: context, problems: problems, lang: lang })
                        })
                        .then(function(res) { return res.json(); })
                        .then(function(data) {
                            if (data.error) {
                                if (panelType === 'connect' && currentConnectIdx === idx) {
                                    panelContent.innerHTML = '<div style="color:#FF6B6B;">' + t('status.error', data.error) + '</div>';
                                }
                            } else {
                                connectCache[idx] = {
                                    report: data.connection_report,
                                    pool: { count: data.pool_count, fields: data.pool_fields },
                                    keyword: currentKeyword
                                };
                                // 仅当用户当前正看着该段落的连接面板时才更新内容；已切到详情则只缓存，不打断
                                if (panelType === 'connect' && currentConnectIdx === idx && sidePanel.classList.contains('open')) {
                                    openConnectPanel(data.connection_report, t('connect.title'), {
                                        count: data.pool_count,
                                        fields: data.pool_fields
                                    }, idx);
                                }
                            }
                        })
                        .catch(function(err) {
                            if (panelType === 'connect' && currentConnectIdx === idx) {
                                panelContent.innerHTML = '<div style="color:#FF6B6B;">' + t('status.error', err.message) + '</div>';
                            }
                        })
                        .finally(function() {
                            if (connectBusyIdx === idx) connectBusyIdx = null;
                        });
                });
            });

            if (window.renderMathInElement) {
                try {
                    window.renderMathInElement(resultsDiv, {
                        delimiters: [{ left: '$', right: '$', display: false }]
                    });
                } catch (e) {}
            }
        }
