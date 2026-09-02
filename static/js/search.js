        // ===== 搜索（核心） =====
        function performSearch(keyword, pushHistory, forceUpdate) {
            if (pushHistory === undefined) pushHistory = true;
            if (forceUpdate === undefined) forceUpdate = false;
            keyword = keyword.trim();
            if (!keyword) {
                sayStatus('status.noKeyword', [], 'error');
                return;
            }

            closeSidePanel();

            if (currentController) {
                currentController.abort();
                currentController = null;
                isSearching = false;
                updateBtn.innerHTML = iconHtml('refresh') + ' ' + t('update.btn');
                updateBtn.classList.remove('stop');
            }

            if (forceUpdate) {
                removeLocal('searchResult_v2_' + lang + '_' + keyword);
                var keysToRemove = [];
                for (var i = 0; i < localStorage.length; i++) {
                    var key = localStorage.key(i);
                    if (key && key.startsWith('detail_') && key.indexOf(keyword) !== -1) {
                        keysToRemove.push(key);
                    }
                }
                keysToRemove.forEach(function(k) { removeLocal(k); });
                delete searchCache[keyword];
                for (var k in detailCache) {
                    if (k.startsWith('detail_') && k.indexOf(keyword) !== -1) {
                        delete detailCache[k];
                    }
                }
            }

            if (!forceUpdate && searchCache[keyword]) {
                var data = searchCache[keyword];
                keywordInput.value = keyword;
                currentKeyword = keyword;
                contentLang = lang;
                displayResults(data);
                var totalPapers = (data.categories || []).reduce(function(acc, c) {
                    return acc + (c.papers_with_links ? c.papers_with_links.length : 0);
                }, 0);
                sayStatus('status.doneCache', [totalPapers], 'success');
                if (pushHistory) {
                    var newUrl = '?q=' + encodeURIComponent(keyword);
                    history.pushState({ keyword: keyword }, '', newUrl);
                }
                return;
            }

            if (!forceUpdate) {
                var cachedData = getLocal('searchResult_v2_' + lang + '_' + keyword);
                if (cachedData) {
                    searchCache[keyword] = cachedData;
                    keywordInput.value = keyword;
                    currentKeyword = keyword;
                    contentLang = lang;
                    displayResults(cachedData);
                    var totalPapers = (cachedData.categories || []).reduce(function(acc, c) {
                        return acc + (c.papers_with_links ? c.papers_with_links.length : 0);
                    }, 0);
                    sayStatus('status.doneLocal', [totalPapers], 'success');
                    if (pushHistory) {
                        var newUrl = '?q=' + encodeURIComponent(keyword);
                        history.pushState({ keyword: keyword }, '', newUrl);
                    }
                    return;
                }
            }

            // 检查 API 密钥是否已设置
            var adsToken = getLocal('adsToken');
            var deepseekKey = getLocal('deepseekKey');
            if (!adsToken || !deepseekKey) {
                sayStatus('status.noKeys', [], 'error');
                return;
            }

            keywordInput.value = keyword;
            searchBtn.disabled = true;
            isSearching = true;
            updateBtn.innerHTML = iconHtml('stop') + ' ' + t('stop.btn');
            updateBtn.classList.add('stop');
            updateBtn.disabled = false;

            sayStatus('status.searching', [keyword], 'loading');
            resultsDiv.innerHTML = '';
            resultsDiv.classList.add('is-loading');

            currentController = new AbortController();
            var signal = currentController.signal;

            var headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-ADS-Token': adsToken || '',
                'X-DeepSeek-Key': deepseekKey || ''
            };

            fetch('/search', {
                    method: 'POST',
                    headers: headers,
                    body: new URLSearchParams({ keyword: keyword, lang: lang }),
                    signal: signal
                })
                .then(function(response) {
                    if (!response.ok) {
                        return response.json().then(function(err) {
                            throw new Error(err.error || '请求失败');
                        });
                    }
                    return response.json();
                })
                .then(function(data) {
                    searchCache[keyword] = data;
                    setLocal('searchResult_v2_' + lang + '_' + keyword, data);
                    currentKeyword = keyword;
                    contentLang = lang;
                    currentPapers = data.papers || [];
                    displayResults(data);
                    var totalPapers = data.papers ? data.papers.length : 0;
                    sayStatus('status.done', [totalPapers], 'success');
                    if (pushHistory) {
                        var newUrl = '?q=' + encodeURIComponent(keyword);
                        history.pushState({ keyword: keyword }, '', newUrl);
                    }
                })
                .catch(function(err) {
                    if (err.name === 'AbortError') {
                        sayStatus('status.cancelled', [], '');
                    } else {
                        // 根据错误信息给出友好提示
                        var msg = err.message || '未知错误';
                        if (msg.includes('ADS Token') || msg.includes('未提供 ADS Token')) {
                            sayStatus('status.badToken', [], 'error');
                        } else if (msg.includes('DeepSeek') || msg.includes('未提供 DeepSeek')) {
                            sayStatus('status.badKey', [], 'error');
                        } else if (msg.includes('未找到相关论文')) {
                            sayStatus('status.noPapers', [keyword], 'error');
                        } else if (msg.indexOf('RemoteDisconnected') !== -1 || msg.indexOf('Connection aborted') !== -1 || msg.indexOf('连接中断') !== -1) {
                            sayStatus('status.error', [t('net.retry')], 'error');
                        } else {
                            sayStatus('status.error', [msg], 'error');
                        }
                    }
                })
                .finally(function() {
                    searchBtn.disabled = false;
                    isSearching = false;
                    updateBtn.innerHTML = iconHtml('refresh') + ' ' + t('update.btn');
                    updateBtn.classList.remove('stop');
                    currentController = null;
                    resultsDiv.classList.remove('is-loading');
                });
        }

        // ===== 状态信息辅助函数 =====
        function setStatus(text, type) {
            statusDiv.innerHTML = text;
            statusDiv.className = 'status';
            if (type) {
                statusDiv.classList.add(type);
            }
        }

        // 记录状态来源（key+args），语言切换后可按当前语言重译（带 SVG 图标）
        function sayStatus(key, args, type) {
            lastStatus = { key: key, args: args || [], type: type || '' };
            setStatus(statusHtml(key, t.apply(null, [key].concat(args || []))), type || '');
        }
