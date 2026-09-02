        // ===== 缓存 =====
        var searchCache = {};
        var currentPapers = [];
        var currentParagraphs = [];   // 解析后的综述段落（供展示与详情共用）
        var detailCache = {};
        var detailCtxCache = {};      // 详情原始文本缓存（用于语言切换后重渲染）
        var currentDetailIndex = null;
        var currentDetailPapers = [];   // 当前打开详情的论文列表（语言切换后重新请求翻译用）
        var currentDetailTopic = '';    // 当前打开详情的段落主题
        var currentKeyword = '';
        var lastSearchData = null;    // 最近一次渲染的搜索结果（语言切换时重渲染用）
        var lastStatus = { key: '', args: [], type: '' };
        var contentLang = '';         // 当前内容的语言（'zh'/'en'），用于判断切换时是否需要翻译
        var isTranslating = false;    // 翻译进行中标记
        var panelType = 'paper';      // 右侧面板类型：'paper'（论文详情）或 'connect'（跨领域连接）
        var connectCache = {};        // 已生成的跨领域连接报告缓存：{段落索引: {report, pool, keyword}}，新搜索/更新后清空
        var connectBusyIdx = null;    // 正在生成连接报告的段落索引（null=当前无生成中），用于生成期间自由切换面板
        var currentConnectIdx = null; // 当前连接面板对应的段落索引

        // ===== 搜索控制 =====
        var isSearching = false;
        var currentController = null;
