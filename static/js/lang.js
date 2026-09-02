        function toggleLang() {
            var newLang = (lang === 'zh') ? 'en' : 'zh';
            if (isTranslating) return;   // 翻译进行中，忽略重复点击
            // 连接面板内容不随语言切换（内容为 AI 生成），切语言时先关闭
            if (panelType === 'connect' && sidePanel.classList.contains('open')) {
                closeSidePanel();
            }
            // 已有生成内容且语言与目标不一致 → 先查目标语言缓存，有则直接切换（省一次翻译调用）
            if (lastSearchData && contentLang !== newLang) {
                var cachedOtherLang = getLocal('searchResult_v2_' + newLang + '_' + currentKeyword);
                if (cachedOtherLang) {
                    // 目标语言版本已存在（之前生成或翻译过）：零成本切换
                    lang = newLang;
                    setLocal('lang', lang);
                    contentLang = newLang;
                    applyI18n();
                    searchCache[currentKeyword] = cachedOtherLang;
                    displayResults(cachedOtherLang);
                    var totalCached = cachedOtherLang.papers ? cachedOtherLang.papers.length : 0;
                    sayStatus('status.doneCache', [totalCached], 'success');
                    if (sidePanel.classList.contains('open') && currentDetailIndex !== null) {
                        var ck2 = 'detail_v8_' + lang + '_' + currentKeyword + '_' + currentDetailIndex;
                        var ctx2 = detailCtxCache[ck2];
                        if (ctx2) {
                            panelContent.innerHTML = formatPaperSummaries(ctx2.paperData, ctx2.papers, ctx2.comparison);
                            renderMath();
                        }
                    }
                    return;
                }
                translateCurrentContent(newLang);
                return;
            }
            // 无内容或内容语言已匹配：直接切换界面语言
            lang = newLang;
            setLocal('lang', lang);
            applyI18n();
            if (lastStatus.key) {
                setStatus(statusHtml(lastStatus.key, t.apply(null, [lastStatus.key].concat(lastStatus.args))), lastStatus.type);
            }
            if (lastSearchData) {
                displayResults(lastSearchData);
            }
            if (sidePanel.classList.contains('open') && currentDetailIndex !== null) {
                var ck = 'detail_v8_' + lang + '_' + currentKeyword + '_' + currentDetailIndex;
                var ctx = detailCtxCache[ck];
                if (ctx) {
                    panelContent.innerHTML = formatPaperSummaries(ctx.paperData, ctx.papers, ctx.comparison);
                    renderMath();
                }
            }
        }

        // 调用 AI 把当前已生成的内容（综述 + 分类名）翻译成目标语言；
        // 详情卡片（原文+逐字翻译）不在这里二次翻译，切换后由 reloadDetailInLang 按新语言重新请求
        function translateCurrentContent(newLang) {
            isTranslating = true;
            var targetName = t(newLang === 'zh' ? 'lang.zh' : 'lang.en');
            sayStatus('status.translating', [targetName], 'loading');

            var headers = {
                'Content-Type': 'application/json',
                'X-DeepSeek-Key': getLocal('deepseekKey') || ''
            };
            var payload = { lang: newLang, overview: lastSearchData.overview || '' };
            if (lastSearchData.categories) {
                payload.categories = lastSearchData.categories.map(function(c) {
                    return { name: c.name, papers: (c.papers || []) };
                });
            }

            fetch('/translate', {
                    method: 'POST',
                    headers: headers,
                    body: JSON.stringify(payload)
                })
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    if (data.error) {
                        sayStatus('status.error', [data.error], 'error');
                        return;
                    }
                    // 切换语言并应用
                    lang = newLang;
                    setLocal('lang', lang);
                    contentLang = newLang;
                    applyI18n();

                    // 重建搜索结果：分类名替换，papers 与链接信息保留
                    var updated = {
                        overview: data.overview || lastSearchData.overview,
                        categories: (lastSearchData.categories || []).map(function(c, i) {
                            var nc = JSON.parse(JSON.stringify(c));
                            if (data.category_names && data.category_names[i]) {
                                nc.name = data.category_names[i];
                            }
                            return nc;
                        }),
                        papers: lastSearchData.papers
                    };
                    searchCache[currentKeyword] = updated;
                    setLocal('searchResult_v2_' + lang + '_' + currentKeyword, updated);
                    displayResults(updated);

                    // 详情面板：按新语言重新请求逐字翻译（有缓存则直接展示）
                    if (sidePanel.classList.contains('open') && panelType === 'paper') {
                        reloadDetailInLang(newLang);
                    }

                    sayStatus('status.done', [updated.papers.length], 'success');
                })
                .catch(function(err) {
                    sayStatus('status.error', [err.message], 'error');
                })
                .finally(function() {
                    isTranslating = false;
                });
        }
