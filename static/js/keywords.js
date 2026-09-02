        // ===== 关键词管理 =====
        var STORAGE_KEY = 'customKeywords';
        var defaultKeywords = ['Dark Energy', 'Dark Matter', 'Hubble Tension', 'Early Dark Energy', 'Halo Galaxy Connection',
            'Reionisation'
        ];

        function getKeywords() {
            var stored = getLocal(STORAGE_KEY);
            if (stored && Array.isArray(stored) && stored.length > 0) {
                return stored;
            }
            setLocal(STORAGE_KEY, defaultKeywords);
            return defaultKeywords;
        }

        function saveKeywords(keywords) {
            setLocal(STORAGE_KEY, keywords);
        }

        function renderKeywords() {
            var container = document.getElementById('keywordList');
            if (!container) return;
            var keywords = getKeywords();
            container.innerHTML = '';
            keywords.forEach(function(kw) {
                var span = document.createElement('span');
                span.className = 'preset-keyword';
                span.dataset.keyword = kw;
                span.textContent = kw;

                var delBtn = document.createElement('button');
                delBtn.className = 'delete-btn';
                delBtn.innerHTML = iconHtml('close');
                delBtn.setAttribute('aria-label', '删除');
                delBtn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    deleteKeyword(kw);
                });
                span.appendChild(delBtn);

                span.addEventListener('click', function(e) {
                    if (e.target.classList.contains('delete-btn')) return;
                    performSearch(kw, true, false);
                });
                container.appendChild(span);
            });
        }

        function deleteKeyword(keyword) {
            var keywords = getKeywords();
            var newList = keywords.filter(function(k) { return k !== keyword; });
            saveKeywords(newList);
            renderKeywords();
        }

        function addKeyword() {
            var addBtn = document.getElementById('addKeywordBtn');
            if (!addBtn || addBtn.style.display === 'none') return;

            addBtn.style.display = 'none';
            var input = document.createElement('input');
            input.type = 'text';
            input.className = 'add-keyword-input';
            input.placeholder = t('addKeyword.placeholder');
            input.autofocus = true;
            addBtn.parentNode.insertBefore(input, addBtn);
            input.focus();

            var isFinished = false;

            function finish() {
                if (isFinished) return;
                isFinished = true;
                var val = input.value.trim();
                if (input.parentNode) input.remove();
                addBtn.style.display = '';
                if (val) {
                    var keywords = getKeywords();
                    var exists = keywords.some(function(k) { return k.toLowerCase() === val.toLowerCase(); });
                    if (exists) {
                        alert(t('kw.exists'));
                        return;
                    }
                    keywords.push(val);
                    saveKeywords(keywords);
                    renderKeywords();
                }
            }

            input.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    finish();
                }
            });
            input.addEventListener('blur', function() {
                setTimeout(finish, 150);
            });
        }
