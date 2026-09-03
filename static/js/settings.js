        // ===== API 设置管理 =====
        // 密钥行的线条风格小图标（局部定义，避免依赖其它模块）
        var KEY_SVG = {
            check: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 12.5l5 5L19.5 6.5"/></svg>',
            eye: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>',
            eyeOff: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17.9 17.9A10.2 10.2 0 0 1 12 19c-6.5 0-10-7-10-7a19.2 19.2 0 0 1 3.1-4.2"/><path d="M9.9 4.2A10.2 10.2 0 0 1 12 4c6.5 0 10 7 10 7a19.2 19.2 0 0 1-2.3 3.2"/><path d="M2 2l20 20"/></svg>'
        };

        function initSettings() {
            var adsInput = document.getElementById('adsToken');
            var dskInput = document.getElementById('deepseekKey');
            var saveBtn = document.getElementById('saveSettingsBtn');
            var clearBtn = document.getElementById('clearCacheBtn');

            // 输入框默认为空（已保存的 key 只在 localStorage，不回填到输入框）
            adsInput.value = '';
            dskInput.value = '';

            function toggleSaveBtn() {
                var ads = adsInput.value.trim();
                var dsk = dskInput.value.trim();
                saveBtn.disabled = !(ads || dsk);
            }

            // 根据 localStorage 是否已保存，刷新“已保存”标记（带对勾 SVG）
            function updateSavedState() {
                [
                    ['adsToken', 'adsSaved'],
                    ['deepseekKey', 'deepseekSaved']
                ].forEach(function(pair) {
                    var badge = document.getElementById(pair[1]);
                    if (!badge) return;
                    var saved = !!getLocal(pair[0]);
                    badge.style.display = saved ? '' : 'none';
                    badge.innerHTML = KEY_SVG.check + ' ' + t('settings.saved');
                });
            }

            // 为单个输入框绑定“显示/隐藏”切换按钮（type 在 password/text 之间切换）
            function bindKeyToggle(input, btnId) {
                var btn = document.getElementById(btnId);
                if (!btn) return;
                btn.innerHTML = KEY_SVG.eyeOff;   // 默认隐藏中，点按后显示明文
                btn.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();   // 阻断冒泡：此按钮只负责显隐切换，不得触发“点击外部关闭设置卡片”
                    var show = input.type === 'password';
                    var val = input.value;
                    var pos = input.selectionStart;
                    input.type = show ? 'text' : 'password';   // 显示=明文，隐藏=小黑点
                    btn.innerHTML = show ? KEY_SVG.eye : KEY_SVG.eyeOff;
                    btn.title = show ? '隐藏' : '显示';
                    if (input.value !== val) input.value = val;   // 个别浏览器切换 type 会清空，手动保留
                    input.focus();
                    try { input.setSelectionRange(pos, pos); } catch (err) {}
                });
            }

            bindKeyToggle(adsInput, 'adsToggleBtn');
            bindKeyToggle(dskInput, 'deepseekToggleBtn');
            updateSavedState();

            // 每次打开设置面板：输入框保持为空、刷新“已保存”标记（面板由 settingsToggle 控制开关）
            var settingsToggle = document.getElementById('settingsToggle');
            if (settingsToggle) {
                settingsToggle.addEventListener('click', function() {
                    adsInput.value = '';
                    dskInput.value = '';
                    toggleSaveBtn();
                    updateSavedState();
                });
            }

            adsInput.addEventListener('input', toggleSaveBtn);
            dskInput.addEventListener('input', toggleSaveBtn);

            saveBtn.addEventListener('click', function() {
                var adsToken = adsInput.value.trim();
                var deepseekKey = dskInput.value.trim();
                if (!adsToken && !deepseekKey) {
                    alert(t('settings.needOne'));
                    return;
                }
                // 仅保存非空项（避免覆盖为空的另一项）
                if (adsToken) setLocal('adsToken', adsToken);
                if (deepseekKey) setLocal('deepseekKey', deepseekKey);
                // 保存后清空输入框并刷新“已保存”标记
                adsInput.value = '';
                dskInput.value = '';
                toggleSaveBtn();
                updateSavedState();
                var originalText = saveBtn.textContent;
                saveBtn.textContent = t('settings.saved');
                setTimeout(function() {
                    saveBtn.textContent = originalText;
                }, 2000);
            });

            // 清除搜索/详情缓存（保留 API 密钥、自定义关键词与引导进度）
            clearBtn.addEventListener('click', function() {
                if (confirm(t('settings.clearConfirm'))) {
                    var keysToRemove = [];
                    for (var i = 0; i < localStorage.length; i++) {
                        var key = localStorage.key(i);
                        if (key && (key.indexOf('searchResult_') === 0 || key.indexOf('detail_') === 0)) {
                            keysToRemove.push(key);
                        }
                    }
                    keysToRemove.forEach(function(k) { removeLocal(k); });
                    searchCache = {};
                    detailCache = {};
                    location.reload();
                }
            });

            // 清除已保存的密钥：删除 localStorage 中的 token，并与“已保存”标记联动
            var clearKeysBtn = document.getElementById('clearKeysBtn');
            if (clearKeysBtn) {
                clearKeysBtn.addEventListener('click', function() {
                    if (!getLocal('adsToken') && !getLocal('deepseekKey')) return;
                    if (confirm('确定要清除已保存的 ADS Token 和 DeepSeek API Key 吗？')) {
                        removeLocal('adsToken');
                        removeLocal('deepseekKey');
                        adsInput.value = '';
                        dskInput.value = '';
                        toggleSaveBtn();
                        updateSavedState();   // 徽标随之消失
                    }
                });
            }

            // 重置引导：清除"已看过"标记，关闭设置卡片后重新弹出页面导引
            var resetTutorialBtn = document.getElementById('resetTutorialBtn');
            if (resetTutorialBtn) {
                resetTutorialBtn.addEventListener('click', function() {
                    removeLocal('hasSeenTutorial');
                    document.getElementById('settingsPanel').style.display = 'none';
                    initTutorial();
                });
            }

            toggleSaveBtn();
        }
