# ========== AstroMind 入口 ==========
# 运行：python3 app.py（本地开发）
# 生产：waitress-serve --host 0.0.0.0 --port 5000 app:app
# 模块划分：
#   config.py   全局常量     utils.py   文本工具（标题匹配/数学转写）
#   cache.py    结果缓存     scix.py    SciX 论文检索
#   deepseek.py DeepSeek 客户端  prompts.py  提示词构建
#   services.py AI 业务编排   graph.py   知识图谱
#   routes.py   Flask 蓝图（所有路由）
import os

import requests  # noqa: F401  —— 测试用 patch 目标（patch.object(app.requests,...)）
from flask import Flask, jsonify

from routes import bp

# —— 测试兼容导出（test_backend.py 通过 import app 访问这些名字） ——
from prompts import (build_connect_stage1_prompt,  # noqa: F401
                     build_connect_stage2_instruction,
                     build_summarize_papers_prompt,
                     build_summary_prompt,
                     build_translate_prompt)

app = Flask(__name__)
app.register_blueprint(bp)


@app.errorhandler(Exception)
def handle_unhandled(e):
    """兜底：任何未捕获异常都返回 JSON 而非 HTML 页面，
    避免前端 res.json() 遇到 HTML 时报 "Unexpected token '<'"。"""
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    import traceback
    traceback.print_exc()
    return jsonify({'error': f'服务器内部错误: {type(e).__name__}'}), 500


if __name__ == '__main__':
    # 本地开发：python app.py（默认 debug 关闭）
    # 生产环境：waitress-serve --host 0.0.0.0 --port 5000 app:app
    #          （或 gunicorn -w 4 -b 0.0.0.0:5000 app:app）
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)
