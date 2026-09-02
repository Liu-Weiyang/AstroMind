        // ===== 跨领域连接面板（他山之石，可以攻玉） =====
        function escapeHtml(text) {
            var div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // 数学记号美化：把 H_0、σ_8、f_EDE、s^-1、10^5 等带上下标的记号包进 $...$（LaTeX 模式），
        // 数学记号美化（LaTeX 模式）：
        // 1) 上下标加花括号：f_esc → $f_{esc}$、H_0 → $H_{0}$、10^5 → $10^{5}$、s^-1 → $s^{-1}$
        // 2) 关系符号与数值：≥0.2 → $≥0.2$、≈1.4 → $≈1.4$、z~11-6 → $z~11-6$、~0.5 → $~0.5$
        // 注意：$ 不会被 escapeHtml 转义，先 mathify 再 escape 的顺序是安全的。
        function mathify(text) {
            var s = String(text || '');
            // 0) 统一负号：U+2212(−)、长破折号 → ASCII 连字符，保证区间可被识别（如 z 11−6 → z 11-6）
            s = s.replace(/[−–—]/g, '-');
            // 1) 上下标加花括号：f_esc → $f_{esc}$、H_0 → $H_{0}$、10^5 → $10^{5}$、s^-1 → $s^{-1}$
            s = s.replace(/(^|[^$\w])((?:\d+|\w|[\u0370-\u03ff])[\w\u0370-\u03ff]*[_^])\{?([\w\u0370-\u03ff-]{1,12})\}?/g, '$1$$$2{$3}$$');
            // 2) 关系符号与数值：≥0.2、z>=10、R<0.5Rvir、z~11-6、≈1.4 等
            s = s.replace(/(^|[^A-Za-z0-9_\u0370-\u03ff])([a-zA-Z\u0370-\u03ff]?\s*(?:>=|<=|!=|≥|≤|≈|≳|≲|∼|~|～|<|>)\s*[\d.]+(?:[-~]\s*[\d.]+)?[\w\u0370-\u03ff]*)/g, '$1$$$2$$');
            // 3) 单字母变量 + 空格 + 数值/区间（如 z 0.1、z 11-6 → $z 0.1$、$z 11-6$）
            s = s.replace(/(^|[^$\w])([a-zA-Z\u0370-\u03ff])\s+(\d+(?:[-~]\d+)?(?:\.\d+)?)/g, '$1$$$2 $3$$');
            return s;
        }

        // 渲染连接报告（后端返回的 JSON：{sections:[{problem, essence, matches:[{field,concept,solution,why,scores,total,rationale,verify}], migration}], summary}）
        // 先转义再替换「论文X」为作者链接（Liu et al. 2024），保证安全且引用可点击
        function formatConnectText(text) {
            if (!text) return '';
            return escapeHtml(mathify(text)).replace(/论文(\d+)/g, function(match, num) {
                var idx = parseInt(num) - 1;
                if (idx >= 0 && idx < currentPapers.length) {
                    var p = currentPapers[idx];
                    var firstAuthor = p.first_author || p.authors || 'Unknown';
                    var authorShort = String(firstAuthor).replace(/\s*et\s+al\.?$/i, '').trim();
                    authorShort = authorShort.split(',')[0].trim();
                    var year = p.year || '????';
                    if (p.bibcode) {
                        return '<a href="https://ui.adsabs.harvard.edu/abs/' + p.bibcode +
                            '" target="_blank">' + authorShort + ' et al. ' + year + '</a>';
                    }
                    return authorShort + ' et al. ' + (p.year || '????');
                }
                return match;
            });
        }

        function scoreChip(label, value, isTotal) {
            if (value === undefined || value === null) return '';
            return '<span class="score-chip' + (isTotal ? ' total' : '') + '">' + escapeHtml(label) +
                ' <b>' + value + '</b></span>';
        }

        function formatConnectReport(data, pool) {
            if (!data || typeof data !== 'object') {
                return '<div style="color:#FF6B6B;">' + t('status.error', '解析失败') + '</div>';
            }
            var html = '';
            // 候选池信息：展示搜索广度，增强可信度
            if (pool && pool.count > 0) {
                var fields = (pool.fields || []).join(' / ');
                html += '<div class="connect-pool">' + iconHtml('search') + ' ' +
                    t('connect.pool', pool.count, fields) + '</div>';
            }
            var sections = data.sections || [];
            if (!sections.length) {
                html += '<div style="color:rgba(255,255,255,0.55);">' + t('connect.empty') + '</div>';
            }
            sections.forEach(function(sec, i) {
                html += '<div class="detail-title">' + (i + 1) + '. ' + formatConnectText(sec.problem || '') + '</div>';
                if (sec.essence) {
                    html += '<div class="connect-label">' + t('connect.essence') + '</div>';
                    html += '<div class="connect-body">' + formatConnectText(sec.essence) + '</div>';
                }
                (sec.matches || []).forEach(function(m) {
                    html += '<div class="connect-sub">' + formatConnectText(m.field || '') +
                        (m.concept ? ' · ' + formatConnectText(m.concept) : '') + '</div>';

                    // 计分区块紧跟在该跨领域项目的下一行
                    if (m.scores) {
                        var s = m.scores;
                        html += '<div class="connect-scores">';
                        html += scoreChip(t('connect.score.isomorphism'), s.isomorphism);
                        html += scoreChip(t('connect.score.maturity'), s.maturity);
                        html += scoreChip(t('connect.score.convenience'), s.convenience);
                        html += scoreChip(t('connect.score.payoff'), s.payoff);
                        if (m.total) html += scoreChip(t('connect.score.total'), m.total, true);
                        html += '</div>';
                    }
                    if (m.solution) {
                        html += '<div class="connect-body"><span class="connect-inline">' + t('connect.solution') +
                            '</span>' + formatConnectText(m.solution) + '</div>';
                    }
                    if (m.why) {
                        html += '<div class="connect-body"><span class="connect-inline">' + t('connect.why') +
                            '</span>' + formatConnectText(m.why) + '</div>';
                    }
                    if (m.rationale) {
                        html += '<div class="connect-rationale"><span class="connect-inline">' + t('connect.rationale') +
                            '</span>' + formatConnectText(m.rationale) + '</div>';
                    }
                    if (m.verify) {
                        html += '<div class="connect-verify"><span class="connect-inline">' + t('connect.verify') +
                            '</span>' + formatConnectText(m.verify) + '</div>';
                    }
                });
                if (sec.migration) {
                    html += '<div class="connect-migration"><span class="connect-inline">' + t('connect.migration') +
                        '</span>' + formatConnectText(sec.migration) + '</div>';
                }
            });
            if (data.summary) {
                html += '<div class="detail-title">' + t('connect.summary') + '</div>';
                html += '<div class="connect-body">' + formatConnectText(data.summary) + '</div>';
            }
            return html;
        }

        // 打开跨领域连接面板（先显示加载态）；idx 为对应段落索引
        function openConnectLoading(idx) {
            // 若右侧当前打开的是论文详情卡片：原地切换为连接面板（不收回，主框架不动）
            if (panelType === 'paper' && sidePanel.classList.contains('open')) {
                switchToPanel(function() { openConnectLoading(idx); }, 'connect');
                return;
            }
            panelType = 'connect';
            currentDetailIndex = null;   // 连接面板不持有详情索引（避免语言切换时误重渲染详情）
            currentConnectIdx = idx;
            document.querySelectorAll('.expand-btn').forEach(function(b) { b.classList.remove('active'); });
            panelTitle.innerHTML = iconHtml('connect') + ' ' + t('connect.title');
            panelContent.innerHTML = '<div class="loading-text">' + iconHtml('refresh') + ' ' + t('connect.loading') + '</div>';
            sidePanel.classList.add('open');
            window.scrollTo({ left: document.documentElement.scrollWidth, behavior: 'smooth' });
        }

        // 展示连接报告（pool: {count, fields} 候选池信息）；idx 为对应段落索引
        function openConnectPanel(report, title, pool, idx) {
            // 若右侧当前打开的是论文详情卡片：原地切换为连接面板（不收回，主框架不动）
            if (panelType === 'paper' && sidePanel.classList.contains('open')) {
                switchToPanel(function() { openConnectPanel(report, title, pool, idx); }, 'connect');
                return;
            }
            panelType = 'connect';
            currentDetailIndex = null;   // 连接面板不持有详情索引（避免语言切换时误重渲染详情）
            if (idx !== undefined) currentConnectIdx = idx;
            document.querySelectorAll('.expand-btn').forEach(function(b) { b.classList.remove('active'); });
            panelTitle.innerHTML = iconHtml('connect') + ' ' + (title || t('connect.title'));
            panelContent.innerHTML = formatConnectReport(report, pool);
            sidePanel.classList.add('open');
            setTimeout(function() {
                window.scrollTo({ left: document.documentElement.scrollWidth, behavior: 'smooth' });
            }, 400);
            renderMath();
        }
