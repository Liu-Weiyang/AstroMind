        // ===== 详情面板 =====
        // 切换右侧卡片类型（详情 ↔ 跨领域连接）：面板已打开时**原地替换**标题与内容，
        // 面板宽度保持不变 → 左侧主框架位置不动、无闪烁；正反两个方向动画完全一致。
        // targetType 预先设为目标面板类型，使 openFn 内部的类型分支不再命中（避免递归切换）。
        function switchToPanel(openFn, targetType) {
            if (!sidePanel.classList.contains('open')) { openFn(); return; }
            panelType = targetType;
            openFn();
            panelContent.classList.remove('swap-in');   // 触发一次内容淡入，提示已切换
            void panelContent.offsetWidth;
            panelContent.classList.add('swap-in');
        }

        function openSidePanel(topic, papers, paragraphIndex, btnElement) {
            // 若右侧当前打开的是跨领域连接面板：原地切换为详情卡片（不收回，主框架不动）
            if (panelType === 'connect' && sidePanel.classList.contains('open')) {
                switchToPanel(function() { openSidePanel(topic, papers, paragraphIndex, btnElement); }, 'paper');
                return;
            }
            panelType = 'paper';
            currentConnectIdx = null;   // 切到详情时，连接面板不再对应任何段落（生成完成后不强行切回）
            if (currentDetailIndex === paragraphIndex && sidePanel.classList.contains('open')) {
                closeSidePanel();
                return;
            }

            // 面板标题切回「详情」（跨领域连接面板会把标题改成「跨领域连接」）
            panelTitle.innerHTML = iconHtml('detail') + ' ' + t('detail.title');

            document.querySelectorAll('.expand-btn').forEach(function(btn) {
                btn.classList.remove('active');
            });
            document.querySelectorAll('.connect-btn').forEach(function(btn) {
                btn.classList.remove('active');
            });
            if (btnElement) {
                btnElement.classList.add('active');
            } else {
                var btn = document.querySelector('.expand-btn[data-paragraph-index="' + paragraphIndex + '"]');
                if (btn) btn.classList.add('active');
            }

            sidePanel.classList.add('open');
            currentDetailIndex = paragraphIndex;

            var onTransitionEnd = function(e) {
                if (e.propertyName === 'width') {
                    window.scrollTo({
                        left: document.documentElement.scrollWidth,
                        behavior: 'smooth'
                    });
                    sidePanel.removeEventListener('transitionend', onTransitionEnd);
                }
            };
            sidePanel.addEventListener('transitionend', onTransitionEnd);
            setTimeout(function() {
                if (sidePanel.classList.contains('open')) {
                    window.scrollTo({
                        left: document.documentElement.scrollWidth,
                        behavior: 'smooth'
                    });
                    sidePanel.removeEventListener('transitionend', onTransitionEnd);
                }
            }, 500);

            // v6 缓存键：详情卡片 = 每篇论文的原文摘要 + 逐字翻译，按语言区分
            currentDetailPapers = papers;
            currentDetailTopic = topic;
            var cacheKey = 'detail_v8_' + lang + '_' + currentKeyword + '_' + paragraphIndex;
            var cachedData = getLocal(cacheKey);
            if (cachedData) {
                panelContent.innerHTML = cachedData;
                detailCache[cacheKey] = cachedData;
                renderMath();
                return;
            }
            if (detailCache[cacheKey]) {
                panelContent.innerHTML = detailCache[cacheKey];
                renderMath();
                return;
            }

            fetchPaperDetail(cacheKey, topic, papers, paragraphIndex);
        }

        function closeSidePanel() {
            sidePanel.classList.remove('open');
            currentDetailIndex = null;
            currentConnectIdx = null;
            panelType = 'paper';
            document.querySelectorAll('.expand-btn').forEach(function(btn) {
                btn.classList.remove('active');
            });
            document.querySelectorAll('.connect-btn').forEach(function(btn) {
                btn.classList.remove('active');
            });
        }

        function renderMath() {
            if (window.renderMathInElement) {
                try {
                    window.renderMathInElement(panelContent, {
                        delimiters: [{ left: '$', right: '$', display: false }]
                    });
                } catch (e) {}
            }
        }

        // ===== 详情正文排版：把小标题严格统一为「作者 et al. 年份（期刊，引用数：N）」 =====
        function formatPaperHeader(num, papers) {
            var idx = parseInt(num) - 1;
            if (idx < 0 || idx >= papers.length) return null;
            var p = papers[idx];
            var firstAuthor = p.first_author || p.authors || 'Unknown';
            var authorShort = String(firstAuthor).replace(/\s*et\s+al\.?$/i, '').trim();
            // 只保留姓氏（去掉逗号后的名字缩写），例如 "Liu, X." -> "Liu"
            authorShort = authorShort.split(',')[0].trim();
            var year = p.year || '????';
            var citations = p.citations || 0;
            var bibstem = p.bibstem || '';
            var cleanBibstem = String(bibstem).split(/[,，\s]+/)[0] || '';
            var journalPart = cleanBibstem ? t('detail.meta', cleanBibstem, citations) :
                t('detail.metaNoJournal', citations);
            var authorYear = authorShort + ' et al. ' + year;
            // 作者+年份保留 ADS 链接（无下划线），点击跳转论文页面
            if (p.bibcode) {
                authorYear = '<a href="https://ui.adsabs.harvard.edu/abs/' + p.bibcode +
                    '" target="_blank">' + authorYear + '</a>';
            }
            return authorYear + '<span class="detail-meta">' + journalPart + '</span>';
        }

        // ===== 详情卡片：每篇论文 = 小标题 + 总结 + 扩展分析，最后是综合比较 =====
        function formatPaperSummaries(paperData, papers, comparison) {
            var html = '';
            papers.forEach(function(p, i) {
                var header = formatPaperHeader(i + 1, papers);
                if (header === null) {
                    header = '<strong class="detail-title">' + escapeHtml(p.title || ('Paper ' + (i + 1))) + '</strong>';
                }
                html += '<div class="detail-paper">';
                html += '<div class="detail-title">' + header + '</div>';
                var d = (paperData && paperData[i]) ? paperData[i] : {};
                if (d.summary) {
                    html += '<div class="detail-label">' + t('detail.summary') + '</div>';
                    html += '<div class="detail-abstract">' + escapeHtml(mathify(d.summary)).replace(/\n/g, '<br>') + '</div>';
                }
                if (d.analysis) {
                    html += '<div class="detail-label">' + t('detail.analysis') + '</div>';
                    html += '<div class="detail-abstract">' + escapeHtml(mathify(d.analysis)).replace(/\n/g, '<br>') + '</div>';
                }
                html += '</div>';
            });
            if (comparison) {
                var safeComparison = escapeHtml(mathify(comparison));
                safeComparison = replacePaperRefs(safeComparison, papers);
                html += '<div class="detail-comparison">';
                html += '<div class="detail-title">' + t('detail.comparison') + '</div>';
                html += '<div class="detail-abstract">' + safeComparison.replace(/\n/g, '<br>') + '</div>';
                html += '</div>';
            }
            return html;
        }

        // 请求 /expand 获取每篇论文的总结/扩展分析与综合比较，渲染并缓存
        function fetchPaperDetail(cacheKey, topic, papers, paragraphIndex) {
            panelContent.innerHTML = '<div class="loading-text">' + iconHtml('refresh') + ' ' + t('detail.loading') + '</div>';

            var paperData = papers.map(function(p) {
                return {
                    title: p.title || '无标题',
                    abstract: p.abstract || '无摘要',
                    authors: p.authors || '',
                    year: p.year || '',
                    bibstem: p.bibstem || ''
                };
            });
            var headers = {
                'Content-Type': 'application/json',
                'X-DeepSeek-Key': getLocal('deepseekKey') || ''
            };

            fetch('/expand', {
                    method: 'POST',
                    headers: headers,
                    body: JSON.stringify({ topic: topic, papers: paperData, lang: lang })
                })
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    // 面板守卫：只有当前仍显示该段落的详情时才写入内容，
                    // 避免生成期间切到连接面板后，被迟到的 /expand 响应覆盖成错误提示
                    var isCurrent = panelType === 'paper' && currentDetailIndex === paragraphIndex && sidePanel.classList.contains('open');
                    if (data.error) {
                        if (isCurrent) {
                            panelContent.innerHTML = '<div style="color:#FF6B6B;">' + iconHtml('error') + ' ' + data.error + '</div>';
                        }
                    } else {
                        var paperData = data.papers || [];
                        var comparison = data.comparison || '';
                        detailCtxCache[cacheKey] = { paperData: paperData, comparison: comparison, papers: papers, lang: lang };
                        var content = formatPaperSummaries(paperData, papers, comparison);
                        if (isCurrent) {
                            panelContent.innerHTML = content;
                            detailCache[cacheKey] = content;
                            setLocal(cacheKey, content);
                            renderMath();
                        }
                    }
                })
                .catch(function(err) {
                    if (panelType === 'paper' && currentDetailIndex === paragraphIndex && sidePanel.classList.contains('open')) {
                        panelContent.innerHTML = '<div style="color:#FF6B6B;">' + iconHtml('error') + ' ' + t('detail.netErr', err.message) + '</div>';
                    }
                });
        }

        // 语言切换后：详情卡片按新语言重新请求总结（有缓存则直接展示）
        function reloadDetailInLang(newLang) {
            if (currentDetailIndex === null || !currentDetailPapers.length) return;
            var cacheKey = 'detail_v8_' + newLang + '_' + currentKeyword + '_' + currentDetailIndex;
            var cachedData = getLocal(cacheKey);
            if (cachedData) {
                panelContent.innerHTML = cachedData;
                detailCache[cacheKey] = cachedData;
                renderMath();
                return;
            }
            var ctx = detailCtxCache[cacheKey];
            if (ctx) {
                panelContent.innerHTML = formatPaperSummaries(ctx.paperData, ctx.papers, ctx.comparison);
                renderMath();
                return;
            }
            fetchPaperDetail(cacheKey, currentDetailTopic || t('detail.title'), currentDetailPapers, currentDetailIndex);
        }
