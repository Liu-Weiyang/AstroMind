        // ===== API 设置管理 =====
        function initSettings() {
            var adsInput = document.getElementById('adsToken');
            var dskInput = document.getElementById('deepseekKey');
            var saveBtn = document.getElementById('saveSettingsBtn');
            var clearBtn = document.getElementById('clearCacheBtn');

            adsInput.value = '';
            dskInput.value = '';

            function toggleSaveBtn() {
                var ads = adsInput.value.trim();
                var dsk = dskInput.value.trim();
                saveBtn.disabled = !(ads || dsk);
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
                setLocal('adsToken', adsToken);
                setLocal('deepseekKey', deepseekKey);
                saveBtn.disabled = true;
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
