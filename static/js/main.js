        // ===== 更新按钮 =====
        function handleUpdateClick() {
            if (isSearching) {
                if (currentController) {
                    currentController.abort();
                    currentController = null;
                }
                isSearching = false;
                updateBtn.innerHTML = iconHtml('refresh') + ' ' + t('update.btn');
                updateBtn.classList.remove('stop');
                sayStatus('status.stopping', [], '');
            } else {
                var kw = keywordInput.value.trim() || currentKeyword;
                if (!kw) {
                    alert(t('kw.emptyAlert'));
                    return;
                }
                performSearch(kw, true, true);
            }
        }

        // ===== 初始化 =====
        function init() {
            applyI18n();

            renderKeywords();
            document.getElementById('addKeywordBtn').addEventListener('click', addKeyword);
            updateBtn.addEventListener('click', handleUpdateClick);
            searchBtn.addEventListener('click', function() {
                performSearch(keywordInput.value, true, false);
            });
            keywordInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    performSearch(keywordInput.value, true, false);
                }
            });

            initSettings();

            document.getElementById('settingsToggle').addEventListener('click', function() {
                var panel = document.getElementById('settingsPanel');
                panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
            });
            // 点击面板外部区域自动关闭 API 设置（无需再点设置按钮）
            document.addEventListener('click', function(e) {
                var panel = document.getElementById('settingsPanel');
                var toggle = document.getElementById('settingsToggle');
                if (panel.style.display !== 'none' && !panel.contains(e.target) && !toggle.contains(e.target)) {
                    panel.style.display = 'none';
                }
            });
            document.getElementById('langBtn').addEventListener('click', toggleLang);

            // 引导
            initTutorial();

            // 页面加载时处理 URL 参数
            var params = new URLSearchParams(window.location.search);
            var q = params.get('q');
            if (q) {
                keywordInput.value = q;
                currentKeyword = q;
                var cachedData = getLocal('searchResult_v2_' + lang + '_' + q);
                if (cachedData) {
                    searchCache[q] = cachedData;
                    currentPapers = cachedData.papers || [];
                    contentLang = lang;
                    displayResults(cachedData);
                    var totalPapers = cachedData.papers ? cachedData.papers.length : 0;
                    sayStatus('status.doneCache', [totalPapers], 'success');
                } else {
                    sayStatus('status.noCache', [q], '');
                    resultsDiv.innerHTML = '';
                }
            }
        }

        // popstate
        window.addEventListener('popstate', function(event) {
            if (event.state && event.state.keyword) {
                var keyword = event.state.keyword;
                keywordInput.value = keyword;
                currentKeyword = keyword;
                var cachedData = getLocal('searchResult_v2_' + lang + '_' + keyword);
                if (cachedData) {
                    searchCache[keyword] = cachedData;
                    currentPapers = cachedData.papers || [];
                    contentLang = lang;
                    displayResults(cachedData);
                    var totalPapers = cachedData.papers ? cachedData.papers.length : 0;
                    sayStatus('status.doneCache', [totalPapers], 'success');
                } else {
                    sayStatus('status.noCache2', [], '');
                    resultsDiv.innerHTML = '';
                    currentPapers = [];
                }
                closeSidePanel();
            } else {
                resultsDiv.innerHTML = '';
                sayStatus('status.initial', [], '');
                keywordInput.value = '';
                currentPapers = [];
                currentKeyword = '';
                lastSearchData = null;
                contentLang = '';
                closeSidePanel();
            }
        });

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
        } else {
            init();
        }
    