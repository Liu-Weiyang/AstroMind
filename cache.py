# ========== 搜索结果缓存（供 /graph 知识图谱直接复用） ==========
# 缓存完整搜索结果（论文列表 + 分类），避免图谱每次都要重新请求 SciX（慢）且依赖分类缓存（易失）。
from config import MAX_RESULT_CACHE

result_cache = {}
_cache_keys = []  # 记录关键词插入顺序，用于LRU


def set_result_cache(key, value):
    global _cache_keys
    if key in result_cache:
        _cache_keys.remove(key)
        _cache_keys.append(key)
    else:
        if len(_cache_keys) >= MAX_RESULT_CACHE:
            del result_cache[_cache_keys.pop(0)]
        _cache_keys.append(key)
    result_cache[key] = value
