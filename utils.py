# ========== 文本工具：标题匹配 / 数学符号转写 ==========
import re
import unicodedata


def extract_title(item):
    if isinstance(item, str):
        return item.strip()
    elif isinstance(item, list):
        if item:
            return extract_title(item[0])
        else:
            return None
    elif isinstance(item, dict):
        return item.get('title', '').strip()
    else:
        return None


def norm_title(t):
    """规范化标题用于模糊匹配：转小写、标点与连字符统一为空格、压缩空白。
    例如 "Single Field Slow-Roll Inflation With Step Uplift to ns=1"
    与 "Single field slow-roll inflation with step uplift to ns=1" 视为相同。"""
    s = re.sub(r'[^\w\s-]', ' ', str(t or '').lower())
    s = re.sub(r'[\s-]+', ' ', s)
    return s.strip()


def title_similarity(a, b):
    """标题词级相似度：共同词数 / 较短标题的词数，范围 0~1。"""
    ta = [w for w in norm_title(a).split(' ') if w]
    tb = [w for w in norm_title(b).split(' ') if w]
    if not ta or not tb:
        return 0.0
    sa, sb = set(ta), set(tb)
    inter = len(sa & sb)
    return inter / min(len(sa), len(sb))


# ========== 数学符号转写 ==========
# 把 Unicode 上下标/数学符号转写成 DeepSeek 易识读的 ASCII 形式，避免模型漏读
# （如 H₀→H_0、Ωₘ→Ω_m、σ₈→σ_8、10⁵→10^5、s⁻¹→s^-1、≈→~、×→x、−→-）。
_SUB2ASCII = str.maketrans('₀₁₂₃₄₅₆₇₈₉₊₋ₐₑₘₙₚₛₜₓᵢⱼₖₗᵣᵤᵥ', '0123456789+-aemnpstxijklruv')
_SUP2ASCII = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻', '0123456789+-')
_SYMBOL_MAP = {
    # 数学运算符/易错符号
    '×': 'x', '−': '-', '–': '-', '—': '-', '‐': '-',
    '≈': '~', '≃': '~', '∼': '~', '≲': '<=', '≳': '>=',
    '±': '+/-', '∓': '-/+', '≤': '<=', '≥': '>=', '≠': '!=', '≡': '==',
    '⟨': '<', '⟩': '>', 'ℓ': 'l',
    '½': '1/2', '¼': '1/4', '¾': '3/4', '…': '...',
    '‘': "'", '’': "'", '“': '"', '”': '"',
    # 上下标中的特殊字符（不参与连续串替换）
    '⁽': '(', '⁾': ')', 'ⁿ': '^n', 'ⁱ': '^i', 'ˣ': '^x',
}


def transcribe_math(text):
    """把文本中的 Unicode 数学符号转写为 ASCII 可读形式；再做 NFKC 收尾（全角、µ→μ 等）。"""
    if not text:
        return text
    s = str(text)
    # 上下标连续串一次转写（如 ⁻¹ → ^-1、ₘ → _m），避免逐个替换拼出 ^-^1 这类错误
    s = re.sub(r'[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+',
               lambda m: '^' + m.group(0).translate(_SUP2ASCII), s)
    s = re.sub(r'[₀₁₂₃₄₅₆₇₈₉₊₋ₐₑₘₙₚₛₜₓᵢⱼₖₗᵣᵤᵥ]+',
               lambda m: '_' + m.group(0).translate(_SUB2ASCII), s)
    for ch, rep in _SYMBOL_MAP.items():
        s = s.replace(ch, rep)
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()
