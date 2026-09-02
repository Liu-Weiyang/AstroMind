# AstroMind

**AstroMind** 是一个智能天文文献综述生成工具。它通过 SciX（NASA ADS）API 检索近5年高引用论文，利用 DeepSeek 大语言模型自动生成结构化的研究介绍、论文分类及深度分析，并支持「跨领域连接」功能，从其他学科挖掘可迁移的方法论。

## ✨ 主要功能

- 🔍 **文献检索**：根据关键词从 SciX 获取论文（标题、摘要、作者、引用数等）。
- 📝 **智能综述**：由 DeepSeek 生成包含「总体介绍」和多个主题分区的综述，并自动将论文归类。
- 📂 **分类抽屉**：按主题分组展示论文，每篇论文可点击跳转到 ADS 原文。
- 📄 **论文详情**：为每篇论文生成总结（≤600字）和扩展分析（≤600字），并提供综合比较。
- 🔗 **跨领域连接**：针对综述中的“关键困难”条目，自动从数学、数据处理、系统动力学、模式结构等视角推荐其他领域的成熟解法，并给出可行性评分和迁移路径。
- 🌐 **知识图谱**（尚未启用）：以可视化图谱展示主题 → 研究方向 → 论文的层级关系，节点大小反映引用数。
- 🌍 **中英双语**：界面和生成内容可一键切换语言（支持缓存）。
- 💾 **缓存机制**：搜索结果、详情、跨领域报告均缓存至本地（localStorage），减少重复请求。

## 🛠 技术栈

- **后端**：Flask (Python)
- **API**：SciX (NASA ADS) + DeepSeek (LLM)
- **前端**：原生 HTML/CSS/JavaScript（无第三方框架）
- **可视化**：NetworkX + Pyvis（知识图谱）

## 📁 项目结构
```
.
├── app.py                  # 入口：创建 Flask app、注册蓝图、错误兜底（保留测试兼容导出）
├── config.py               # 全局常量（API 地址、模型、缓存上限）
├── cache.py                # 搜索结果 LRU 缓存（供 /graph 复用）
├── utils.py                # 文本工具：标题匹配 + 数学符号转写
├── scix.py                 # SciX / ADS 论文检索
├── deepseek.py             # DeepSeek 客户端（调用 / JSON 解析 / 修复）
├── prompts.py              # 全部提示词构建
├── services.py             # AI 业务编排（综述生成 / 跨领域连接流水线）
├── graph.py                # 知识图谱页面构建
├── routes.py               # Flask 蓝图：全部路由
├── templates/
│   └── index.html          # 前端页面（单页应用，样式与脚本均已外置）
├── static/
│   ├── css/
│   │   └── index.css       # 全站样式
│   ├── js/                 # 前端脚本（按功能模块拆分，按序加载）
│   │   ├── core.js         # DOM 引用、存储、图标、i18n、数学渲染
│   │   ├── state.js        # 共享状态
│   │   ├── parse.js        # 段落/标题解析
│   │   ├── keywords.js     # 常用搜索词管理
│   │   ├── settings.js     # API 设置面板
│   │   ├── tutorial.js     # 引导系统
│   │   ├── lang.js         # 中英切换 / 翻译
│   │   ├── detail.js       # 右侧详情面板
│   │   ├── connect.js      # 跨领域连接面板
│   │   ├── results.js      # 主卡片渲染
│   │   ├── search.js       # 搜索流程
│   │   └── main.js         # 初始化 / 入口（最后加载）
│   └── *.svg               # 图标与 logo（galaxy、ADS、DeepSeek 等）
├── test_backend.py         # 后端测试（python3 test_backend.py）
├── test_parsing.js         # 前端解析测试（node test_parsing.js）
├── requirements.txt        # Python 依赖
└── README.md
```

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd astromind
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
# 或 venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 获取 API 密钥

- **ADS Token**：登录 [NASA ADS](https://ui.adsabs.harvard.edu/)，进入 Settings → API Token 生成。
- **DeepSeek API Key**：在 [DeepSeek Platform](https://platform.deepseek.com/api_keys) 注册并获取。

### 5. 启动服务

```bash
python app.py
```

默认运行在 `http://0.0.0.0:5000`。访问该地址即可使用。

> 生产环境建议使用 `waitress` 或 `gunicorn`（`app:app` 指向入口模块 `app.py` 中的 Flask 实例）：
> ```bash
> pip install waitress
> waitress-serve --host 0.0.0.0 --port 5000 app:app
> # 或 gunicorn -w 4 -b 0.0.0.0:5000 app:app
> ```

### 6. 使用

- 在页面右上角「API 设置」中填入你的 ADS Token 和 DeepSeek API Key，保存。
- 输入天文学关键词（如 `hubble tension`）或点击预设标签，点击「搜索」。
- 浏览生成的综述、分类抽屉；点击「查看详情」深入阅读每篇论文；点击「跨领域连接」获取方法论迁移建议。
- 点击「更新」可强制重新生成（清空缓存）。

## ⚙️ 环境变量（可选）

可通过环境变量覆盖默认配置：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DEEPSEEK_URL` | DeepSeek API 端点 | `https://api.deepseek.com/v1/chat/completions` |
| `DEEPSEEK_MODEL` | 使用的模型名称 | `deepseek-chat` |
| `PORT` | Flask 监听端口 | `5000` |
| `FLASK_DEBUG` | 是否开启调试模式（`1` 开启） | `0` |

例如：

```bash
export DEEPSEEK_MODEL=deepseek-chat   # 官方 API 通用模型（默认）
python app.py
```

> 模型名说明：官方 API 的通用模型为 `deepseek-chat`；`deepseek-reasoner` 为慢速推理模型，不建议用于本工具；`deepseek-v4-flash` 等其它模型名仅在 `DEEPSEEK_URL` 指向支持它们的网关时才会生效。

## 📝 依赖说明

- `Flask`：Web 框架
- `requests`：调用 SciX 和 DeepSeek API
- `networkx` + `pyvis`：生成知识图谱交互页面 (尚未启用)
- `waitress`：生产环境 WSGI 服务器

（Python 标准库 `re`, `json`, `os`, `datetime`, `unicodedata`, `concurrent.futures` 无需额外安装）

## 🤝 贡献

欢迎提交 Issue 和 Pull Request。

## 📄 许可

MIT License
