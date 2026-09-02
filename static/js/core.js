        // ===== 工具 =====
        function getLocal(key) {
            try {
                var val = localStorage.getItem(key);
                return val ? JSON.parse(val) : null;
            } catch (e) { return null; }
        }

        function setLocal(key, value) {
            try {
                localStorage.setItem(key, JSON.stringify(value));
            } catch (e) {}
        }

        function removeLocal(key) {
            localStorage.removeItem(key);
        }



        // ===== DOM 引用 =====
        var sidePanel = document.getElementById('sidePanel');
        var panelContent = document.getElementById('panelContent');
        var keywordInput = document.getElementById('keyword');
        var searchBtn = document.getElementById('searchBtn');
        var updateBtn = document.getElementById('updateBtn');
        var statusDiv = document.getElementById('status');
        var resultsDiv = document.getElementById('results');
        var panelTitle = document.getElementById('panelTitle');

        // ===== 国际化（中/英） =====
        var lang = getLocal('lang') || 'zh';

        // ===== 抽象风格 SVG 小图标（线条风格，颜色跟随文字，风格统一） =====
        // 用 svgLine/svgSolid 生成器复用公共属性，图标只写内部图形，输出与展开写法完全一致
        var ICONS = (function() {
            var ATTRS = 'viewBox="0 0 24 24" width="1em" height="1em" class="ico"';
            function line(inner) {
                return '<svg ' + ATTRS + ' fill="none" stroke="currentColor" stroke-width="1.8" ' +
                    'stroke-linecap="round" stroke-linejoin="round">' + inner + '</svg>';
            }
            function solid(inner) {
                return '<svg ' + ATTRS + ' fill="currentColor" stroke="none">' + inner + '</svg>';
            }
            return {
                search: line('<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>'),
                refresh: line('<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 3.5V8h-4.5"/>'),
                stop: solid('<rect x="6" y="6" width="12" height="12" rx="2.5"/>'),
                check: line('<path d="M4.5 12.5l5 5L19.5 6.5"/>'),
                warn: line('<path d="M12 3.5L2.8 20h18.4L12 3.5z"/><path d="M12 9.5v4.5"/><path d="M12 17.2h.01"/>'),
                error: line('<circle cx="12" cy="12" r="9"/><path d="M9.2 9.2l5.6 5.6M14.8 9.2l-5.6 5.6"/>'),
                empty: line('<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v13a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 18.5v-13z"/><path d="M4 13.5h5l1.8 2.5h2.4L15 13.5h5"/>'),
                detail: line('<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>'),
                connect: line('<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1.3.5 2.6 1.5 3.5.8.8 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>'),
                folder: line('<path d="M3 7a2 2 0 0 1 2-2h4l2 3h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>'),
                gear: line('<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>'),
                globe: line('<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.7 2.7 4 6 4 9s-1.3 6.3-4 9c-2.7-2.7-4-6-4-9s1.3-6.3 4-9z"/>'),
                clear: line('<path d="M4 7h16"/><path d="M9.5 7V5a1.5 1.5 0 0 1 1.5-1.5h2A1.5 1.5 0 0 1 14.5 5v2"/><path d="M6.5 7l1 13h9l1-13"/>'),
                star: line('<path d="M12 3.5l2.6 5.3 5.9.9-4.2 4.1 1 5.8-5.3-2.8-5.3 2.8 1-5.8-4.2-4.1 5.9-.9L12 3.5z"/>'),
                welcome: line('<path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3z"/><path d="M18.5 4.5l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z"/>'),
                plus: line('<path d="M12 5v14M5 12h14"/>'),
                close: line('<path d="M6 6l12 12M18 6L6 18"/>')
            };
        })();
        function iconHtml(name) {
            return ICONS[name] || '';
        }
        // 状态栏图标映射（按状态 key 配图标）
        var STATUS_ICONS = {
            'status.initial': 'star',
            'status.searching': 'search',
            'status.done': 'check',
            'status.doneCache': 'check',
            'status.doneLocal': 'check',
            'status.noKeyword': 'warn',
            'status.noKeys': 'warn',
            'status.badToken': 'warn',
            'status.badKey': 'warn',
            'status.noPapers': 'empty',
            'status.error': 'error',
            'status.cancelled': 'stop',
            'status.stopping': 'stop',
            'status.noCache': 'empty',
            'status.noCache2': 'empty',
            'status.translating': 'refresh'
        };
        function statusHtml(key, text) {
            return iconHtml(STATUS_ICONS[key] || '') + (text ? ' ' + text : '');
        }
        var I18N = {
            zh: {
                'lang.title': '切换语言',
                'alpha.title': 'A测版本',
                'brand.poweredBy': 'powered by',
                'search.placeholder': '输入关键词，如 hubble tension',
                'search.btn': '搜索',
                'update.btn': '更新',
                'stop.btn': '停止',
                'update.title': '强制更新当前关键词的综述',
                'preset.label': '常用搜索：',
                'addKeyword.placeholder': '输入关键词...',
                'kw.exists': '该关键词已存在。',
                'kw.emptyAlert': '请先输入或搜索一个关键词。',
                'settings.title': 'API 设置',
                'settings.save': '保存设置',
                'settings.saved': '已保存',
                'settings.clear': ICONS.clear + ' 清除搜索缓存（保留密钥）',
                'settings.clearConfirm': '确定要清除搜索与详情缓存吗？\n（ADS Token、DeepSeek API Key 和常用关键词会保留）',
                'settings.needOne': '请至少输入一项密钥',
                'settings.hintFromAds': '从 <a href="https://ui.adsabs.harvard.edu/user/settings/token" target="_blank">ADS</a> 获取',
                'settings.hintFromDs': '从 <a href="https://platform.deepseek.com/api_keys" target="_blank">DeepSeek</a> 获取',
                'settings.resetTutorial': '重置引导',
                'status.initial': '输入关键词或点击常用搜索开始探索',
                'status.searching': '正在搜索 "{0}"...',
                'status.done': '共搜索到最近5年的{0}篇相关论文，介绍已生成',
                'status.doneCache': '共搜索到最近5年的{0}篇相关论文，介绍已生成（来自缓存）',
                'status.doneLocal': '共搜索到最近5年的{0}篇相关论文，介绍已生成（来自本地缓存）',
                'status.noKeyword': '请输入关键词',
                'status.noKeys': '请先在 API 设置中填写 ADS Token 和 DeepSeek API Key',
                'status.badToken': 'ADS Token 无效，请检查 API 设置中的 Token',
                'status.badKey': 'DeepSeek API Key 无效，请检查 API 设置中的 Key',
                'status.noPapers': '未找到与 “{0}” 相关的论文，请尝试其他关键词',
                'net.retry': '与 DeepSeek 的连接中断，已自动重试仍失败。请检查网络后稍等片刻再试，或到 DeepSeek 官网确认服务状态。',
                'status.error': '{0}',
                'status.cancelled': '搜索已取消',
                'status.stopping': '正在停止...',
                'status.noCache': '暂无缓存，点击“更新”按钮生成 “{0}” 的介绍。',
                'status.noCache2': '暂无缓存，点击“更新”按钮生成介绍。',
                'status.translating': '正在将内容翻译为{0}...',
                'status.loadingText': '正在检索文献并生成介绍…',
                'status.emptyHint': '输入关键词或点击常用搜索，让 AI 为你生成研究介绍',
                'lang.zh': '中文',
                'lang.en': '英文',
                'connect.btn': '跨领域连接',
                'connect.generating': '生成中...',
                'connect.title': '跨领域连接',
                'connect.loading': '正在寻找跨领域连接...',
                'connect.empty': '没有可分析的困难条目。',
                'connect.essence': '抽象本质',
                'connect.solution': '解决方式：',
                'connect.why': '结构相似性：',
                'connect.migration': '迁移预期',
                'connect.summary': '总体结论',
                'connect.noSearch': '请先搜索一个关键词',
                'connect.noKey': '请先在 API 设置中填写 DeepSeek API Key',
                'connect.pool': '候选池：{0} 个候选 · 覆盖 {1}',
                'connect.score.isomorphism': '同构',
                'connect.score.maturity': '成熟',
                'connect.score.convenience': '便利',
                'connect.score.payoff': '收益',
                'connect.score.total': '总分',
                'connect.rationale': '入选理由（为何优于邻近学科）：',
                'connect.verify': '验证路径：',
                'detail.title': '详情',
                'detail.btn': '查看详情',
                'detail.loading': '正在生成详情，请稍候...',
                'detail.noRefs': '该段落未引用具体论文。',
                'detail.noMatch': '未找到匹配的论文。',
                'detail.netErr': '网络错误: {0}',
                'detail.meta': '（{0}，引用数：{1}）',
                'detail.metaNoJournal': '（引用数：{0}）',
                'detail.summary': '总结',
                'detail.analysis': '扩展分析',
                'detail.comparison': '综合比较',
                'category.count': '（{0}篇）',
                'category.empty': '暂无分类数据',
                'footer': '懒人不想走路，于是发明了轮子',
                'tutorial.title': '欢迎使用 <img class="title-icon" src="/static/galaxy-2-solid.svg" alt=""> <span class="astro">Astro</span><span class="mind">Mind</span>',
                'tutorial.sub': '几分钟带你快速上手',
                'tutorial.step1Title': '设置 API 密钥',
                'tutorial.step1a': '点击「' + ICONS.gear + ' API 设置」展开面板',
                'tutorial.step1b': '粘贴你的 <strong>ADS Token</strong> 和 <strong>DeepSeek API Key</strong>',
                'tutorial.step1c': '点击「保存设置」',
                'tutorial.step2Title': '搜索关键词',
                'tutorial.step2a': '在搜索框输入你感兴趣的天文学话题',
                'tutorial.step2b': '或点击「常用搜索」快捷标签',
                'tutorial.step2c': '等待 AI 生成研究介绍与论文分类',
                'tutorial.step3Title': '深入阅读',
                'tutorial.step3a': '点击「' + ICONS.detail + ' 查看详情」查看每篇论文的总结、扩展分析与综合比较',
                'tutorial.step3b': '点击「' + ICONS.connect + ' 跨领域连接」获取跨学科方法迁移建议',
                'tutorial.step3c': '点击「更新」可重新生成介绍',
                'tutorial.skip': '跳过',
                'tutorial.next': '下一步 →',
                'tutorial.finish': '完成',
                'tutorial.prev': '← 上一页',
            },
            en: {
                'lang.title': 'Switch language',
                'alpha.title': 'Alpha build',
                'brand.poweredBy': 'powered by',
                'search.placeholder': 'Enter a keyword, e.g. hubble tension',
                'search.btn': 'Search',
                'update.btn': 'Refresh',
                'stop.btn': 'Stop',
                'update.title': 'Force-refresh the review for the current keyword',
                'preset.label': 'Presets:',
                'addKeyword.placeholder': 'Type a keyword...',
                'kw.exists': 'This keyword already exists.',
                'kw.emptyAlert': 'Enter or search a keyword first.',
                'settings.title': 'API Settings',
                'settings.save': 'Save settings',
                'settings.saved': 'Saved',
                'settings.clear': ICONS.clear + ' Clear search cache (keep keys)',
                'settings.clearConfirm': 'Clear search & detail caches?\n(ADS Token, DeepSeek API Key and custom keywords are kept)',
                'settings.needOne': 'Enter at least one key',
                'settings.hintFromAds': 'get it from <a href="https://ui.adsabs.harvard.edu/user/settings/token" target="_blank">ADS</a>',
                'settings.hintFromDs': 'get it from <a href="https://platform.deepseek.com/api_keys" target="_blank">DeepSeek</a>',
                'settings.resetTutorial': 'Reset tutorial',
                'status.initial': 'Enter a keyword or tap a preset to start',
                'status.searching': 'Searching "{0}"...',
                'status.done': 'Found {0} related papers from the last 5 years; introduction generated',
                'status.doneCache': 'Found {0} related papers from the last 5 years; introduction generated (cached)',
                'status.doneLocal': 'Found {0} related papers from the last 5 years; introduction generated (local cache)',
                'status.noKeyword': 'Please enter a keyword',
                'status.noKeys': 'Add your ADS Token and DeepSeek API Key in API Settings first',
                'status.badToken': 'Invalid ADS Token — check it in API Settings',
                'status.badKey': 'Invalid DeepSeek API Key — check it in API Settings',
                'status.noPapers': 'No papers found for "{0}" — try another keyword',
                'net.retry': 'Connection to DeepSeek was interrupted and retries failed. Check your network and try again shortly.',
                'status.error': '{0}',
                'status.cancelled': 'Search cancelled',
                'status.stopping': 'Stopping...',
                'status.noCache': 'No cache yet — click "Refresh" to generate "{0}".',
                'status.noCache2': 'No cache yet — click "Refresh" to generate the introduction.',
                'status.translating': 'Translating content to {0}...',
                'status.loadingText': 'Searching the literature and generating the introduction…',
                'status.emptyHint': 'Enter a keyword or tap a preset to have AI generate a research introduction',
                'lang.zh': 'Chinese',
                'lang.en': 'English',
                'connect.btn': 'Cross-field connections',
                'connect.generating': 'Generating...',
                'connect.title': 'Cross-field Connections',
                'connect.loading': 'Finding cross-field connections...',
                'connect.empty': 'No specific difficulties to analyze.',
                'connect.essence': 'Abstract essence',
                'connect.solution': 'Solution: ',
                'connect.why': 'Structural similarity: ',
                'connect.migration': 'Expected outcome of migration',
                'connect.summary': 'Overall assessment',
                'connect.noSearch': 'Search a keyword first',
                'connect.noKey': 'Add your DeepSeek API Key in API Settings first',
                'connect.pool': 'Candidate pool: {0} candidates · covering {1}',
                'connect.score.isomorphism': 'Iso',
                'connect.score.maturity': 'Maturity',
                'connect.score.convenience': 'Ease',
                'connect.score.payoff': 'Payoff',
                'connect.score.total': 'Total',
                'connect.rationale': 'Why over adjacent fields: ',
                'connect.verify': 'Verification path: ',
                'detail.title': 'Details',
                'detail.btn': 'Details',
                'detail.loading': 'Generating details, please wait...',
                'detail.noRefs': 'This paragraph does not cite any paper.',
                'detail.noMatch': 'No matching papers found.',
                'detail.netErr': 'Network error: {0}',
                'detail.meta': ' ({0}, citations: {1})',
                'detail.metaNoJournal': ' (citations: {0})',
                'detail.summary': 'Summary',
                'detail.analysis': 'Extended analysis',
                'detail.comparison': 'Overall comparison',
                'category.count': ' ({0} papers)',
                'category.empty': 'No categories yet',
                'footer': 'Not wanting to walk, the lazy invented the wheel.',
                'tutorial.title': 'Welcome to <img class="title-icon" src="/static/galaxy-2-solid.svg" alt=""> <span class="astro">Astro</span><span class="mind">Mind</span>',
                'tutorial.sub': 'Get started in a few minutes',
                'tutorial.step1Title': 'Set up API keys',
                'tutorial.step1a': 'Click "' + ICONS.gear + ' API Settings" to open the panel',
                'tutorial.step1b': 'Paste your <strong>ADS Token</strong> and <strong>DeepSeek API Key</strong>',
                'tutorial.step1c': 'Click "Save settings"',
                'tutorial.step2Title': 'Search a keyword',
                'tutorial.step2a': 'Type an astronomy topic in the search box',
                'tutorial.step2b': 'Or tap a preset keyword below the search box',
                'tutorial.step2c': 'Wait for the AI to generate the introduction and paper categories',
                'tutorial.step3Title': 'Dive deeper',
                'tutorial.step3a': 'Click "' + ICONS.detail + ' Details" to see each paper summary, extended analysis and overall comparison',
                'tutorial.step3b': 'Click "' + ICONS.connect + ' Cross-field connections" for cross-discipline insights',
                'tutorial.step3c': 'Click "Refresh" to regenerate the introduction',
                'tutorial.skip': 'Skip',
                'tutorial.next': 'Next →',
                'tutorial.finish': 'Finish',
                'tutorial.prev': '← Previous',
            }
        };

        // 取当前语言文案；支持 {0} {1} 占位符替换
        function t(key) {
            var entry = (I18N[lang] && I18N[lang][key]);
            if (entry === undefined) entry = I18N.zh[key];
            if (entry === undefined) entry = key;
            var args = Array.prototype.slice.call(arguments, 1);
            for (var i = 0; i < args.length; i++) {
                entry = entry.split('{' + i + '}').join(args[i]);
            }
            return entry;
        }

        // 应用当前语言到所有带 data-i18n 标记的元素
        function applyI18n() {
            document.querySelectorAll('[data-i18n]').forEach(function(el) {
                el.textContent = t(el.getAttribute('data-i18n'));
            });
            document.querySelectorAll('[data-i18n-html]').forEach(function(el) {
                el.innerHTML = t(el.getAttribute('data-i18n-html'));
            });
            document.querySelectorAll('[data-i18n-placeholder]').forEach(function(el) {
                el.setAttribute('placeholder', t(el.getAttribute('data-i18n-placeholder')));
            });
            document.querySelectorAll('[data-i18n-title]').forEach(function(el) {
                el.setAttribute('title', t(el.getAttribute('data-i18n-title')));
            });
            var langBtnEl = document.getElementById('langBtn');
            if (langBtnEl) langBtnEl.innerHTML = iconHtml('globe') + '<span id="langLabel">' + (lang === 'zh' ? '中' : 'EN') + '</span>';
            var settingsToggleEl = document.getElementById('settingsToggle');
            if (settingsToggleEl) settingsToggleEl.innerHTML = iconHtml('gear');
            var addKwEl = document.getElementById('addKeywordBtn');
            if (addKwEl) addKwEl.innerHTML = iconHtml('plus');
            var closeBtnEl = document.querySelector('.panel-header .close-btn');
            if (closeBtnEl) closeBtnEl.innerHTML = iconHtml('close');
            if (!isSearching) {
                updateBtn.innerHTML = iconHtml('refresh') + ' ' + t('update.btn');
            } else {
                updateBtn.innerHTML = iconHtml('stop') + ' ' + t('stop.btn');
            }
            var searchBtnEl = document.getElementById('searchBtn');
            if (searchBtnEl) searchBtnEl.innerHTML = iconHtml('search') + ' ' + t('search.btn');
            // 状态栏（首次加载、尚无状态时）与 CSS 变量文案
            if (!lastStatus.key) {
                statusDiv.innerHTML = statusHtml('status.initial', t('status.initial'));
            }
            document.documentElement.style.setProperty('--loading-text', '"' + t('status.loadingText') + '"');
            document.documentElement.style.setProperty('--empty-hint', '"' + t('status.emptyHint') + '"');
            // 面板标题：连接模式下覆盖默认「详情」标题
            if (panelTitle) {
                if (panelType === 'connect') {
                    panelTitle.innerHTML = iconHtml('connect') + ' ' + t('connect.title');
                } else {
                    panelTitle.innerHTML = iconHtml('detail') + ' ' + t('detail.title');
                }
            }
        }
