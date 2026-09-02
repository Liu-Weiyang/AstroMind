# ========== 全局配置与常量 ==========
import os

# ---- SciX / ADS API ----
SCIx_URL = "https://scixplorer.org/v1/search/query"
FIELDS = 'title,abstract,author,year,citation_count,bibcode,bibstem'

# ---- DeepSeek API ----
# 可用环境变量覆盖（无需改代码）：DEEPSEEK_URL 指向其它 OpenAI 兼容网关、DEEPSEEK_MODEL 切换模型
DEEPSEEK_URL = os.environ.get('DEEPSEEK_URL', "https://api.deepseek.com/v1/chat/completions")
# 官方 api.deepseek.com 的通用模型是 deepseek-chat（快且省）；deepseek-reasoner 是慢速推理模型，不要用。
# 注意：deepseek-v4-flash 不是官方 API 的模型名（会返回 401/400），仅当 DEEPSEEK_URL 指向支持它的网关时才用。
DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL', "deepseek-chat")

# ---- 搜索结果缓存（供 /graph 复用） ----
MAX_RESULT_CACHE = 50

# ---- 跨领域连接 ----
CONNECT_SYSTEM = "你是一位跨学科方法迁移专家，核心理念是「他山之石，可以攻玉」。必须只输出合法的JSON格式。"
