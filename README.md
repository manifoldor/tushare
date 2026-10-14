# tushare — China A-share market data plugin for Grok Bot

`tushare` is an Agent Plugins 1.0 / MCP plugin that lets Grok Bot query China A-share stock quotes and 5-level order book, daily/weekly/monthly K-line history, intraday ticks, major indices (SSE, SZSE, ChiNext, CSI 300, STAR 50), stock search by name or code, company profiles, and the trading calendar.

- **Author:** yishan · **Publisher:** manifoldor · **Homepage:** https://sibox.org · **License:** MIT

## Install

```bash
git clone https://github.com/manifoldor/tushare.git && cd tushare
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

The plugin manifest is `.cursor-plugin/plugin.json`; the MCP server is declared in `mcp.json` and started with `python3 run_server.py`.

## Tools

`get_stock_quote`, `get_stock_history`, `get_stock_intraday`, `get_index_quote`, `search_stock`, `get_stock_info`, `get_trade_calendar` (see the table below).

## Tushare token

A [Tushare Pro](https://tushare.pro) token is **recommended but not strictly required**. Set it via the `TUSHARE_TOKEN` environment variable (e.g. in the `env` block of your MCP config) or put it in `~/.tushare_token`. Without a token, Tushare Pro endpoints are unavailable and the plugin falls back to public web quote endpoints (Sina / Tencent) and a bundled seed list, so coverage and reliability are reduced. **Never commit your token to the repository.**

## Data source & attribution

Data comes from [Tushare Pro](https://tushare.pro) via the open-source `tushare` Python package, plus public web quote endpoints as fallback. This plugin is an independent project and is **not affiliated with or endorsed by the Tushare project**.

## Disclaimer

All data is provided for reference only and may be delayed or inaccurate. It is **not investment advice**.

## 中文简介

`tushare` 插件基于 Tushare Pro（https://tushare.pro）查询 A 股行情、盘口、K 线、分时、指数、公司资料和交易日历。建议配置环境变量 `TUSHARE_TOKEN`（或 `~/.tushare_token`），不配也能用部分公开备选接口，但数据不全。本插件为独立项目，与 Tushare 官方无关；数据仅供参考，不构成投资建议。请勿把 Token 提交到仓库。

---

# TuShare A 股行情与金融数据 Grokbot 插件 (tushare)

[![Standard: Agent Plugins 1.0](https://img.shields.io/badge/standard-Agent%20Plugins%201.0-blue.svg)](https://agent-plugins.org)
[![MCP: Supported](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-green.svg)](https://modelcontextprotocol.io)
[![Data: TuShare](https://img.shields.io/badge/Data%20Source-TuShare%20Pro-orange.svg)](https://tushare.pro/)

一款专为 **Grokbot**（及遵循 Agent Plugins 1.0 标准与 Model Context Protocol (MCP) 协议的智能体平台）打造的 **A 股股票价格查询、行情分析与上市公司综合金融数据插件**，插件名称为 `tushare`。

插件深度整合 [TuShare](https://tushare.pro/) 经典与 TuShare Pro 接口，为 Grokbot 赋予实时股价与五档买卖盘口跟踪、历史多周期 K 线走势分析、日内分笔交易、大盘核心指数监控、上市公司高管与主营业务画像、以及市场交易日历查询等能力。

---

## 🌟 核心特性

1. **完全遵循 Grokbot & Agent Plugins 1.0 规范**：
   - 包含完整的插件元数据清单 `plugin.json`。
   - 包含 MCP 服务配置 `mcp.json` 与 `mcp_config.json`。
   - 包含规范的智能体技能定义 `skills/tushare-stock/SKILL.md`，内含针对中国 A 股交易市场规范（如“红涨绿跌”、交易时段、停复牌等）的引导提示词。
2. **多维度 A 股行情与公司数据覆盖**：
   - ⚡ **实时股价与五档买卖盘口**：查询买一至买五、卖一至卖五挂单量及价格、成交量、成交额、换手率。
   - 📈 **历史多周期 K 线**：支持日线（daily）、周线（weekly）、月线（monthly），自动重采样聚合与限频容错。
   - ⏱️ **日内分笔成交数据**：盘中逐笔买卖明细与交易性质。
   - 🇨🇳 **核心大盘指数**：上证指数、深证成指、创业板指、沪深300、科创50等行情。
   - 🔍 **模糊检索与实时看盘**：支持股票简称（如“茅台”、“宁德”、“比亚迪”）与 6 位数字代码互相检索，并联动实时行情。
   - 🏢 **上市公司资料与高管画像**：董事长、总经理、董秘、注册资本、主营业务、公司简介、总市值与估值指标。
   - 📅 **交易日历查询**：查询 A 股开市与节假日休市安排。
3. **高可用双通道与本土化规则**：
   - 涨跌指示严格遵循中国 A 股规则：🔴 **红色代表上涨 (+)**，🟢 **绿色代表下跌 (-)**。
   - 自动格式化大额成交量（手、万手、亿手）与成交金额（元、万元、亿元）。
   - 内置智能缓存与多通道备选保障机制，针对 TuShare 接口频次限制做了自动化容灾保护。

---

## 📁 目录结构

```text
tushare/
├── .cursor-plugin/plugin.json  # 插件清单（市场使用）
├── plugin.json                 # 兼容元数据清单
├── LICENSE
├── assets/logo.png             # 插件 Logo
├── mcp.json                    # Model Context Protocol 服务注册配置
├── mcp_config.json             # 兼容配置
├── requirements.txt            # Python 依赖清单
├── run_server.py               # 带有虚拟环境自适应检测的 MCP 启动入口
├── skills/                     # 智能体技能定义目录
│   └── tushare-stock/
│       └── SKILL.md            # A股查询决策树、Prompt 引导与业务规范
├── tushare_mcp/                # 核心 Python 插件模块
│   ├── __init__.py
│   ├── server.py               # FastMCP 服务实现（注册 7 大 Tool 函数）
│   ├── client.py               # TuShare 接口封装、本地缓存与容错备选逻辑
│   └── utils.py                # 标准化代码、涨跌指示器、Markdown 表格渲染
├── tests/                      # 单元与集成测试
│   └── test_plugin.py
└── README.md                   # 插件使用与开发文档
```

---

## 🛠️ 可用 MCP 工具一览

| 工具名称 (Tool) | 功能描述 | 核心入参 |
| :--- | :--- | :--- |
| `get_stock_quote` | 查询个股实时股价、五档买卖盘口及涨跌幅 | `symbol`: 股票代码（如 `600519`）或股票简称（如 `贵州茅台`） |
| `get_stock_history` | 获取个股历史 K 线走势记录 | `symbol`, `period`('daily'/'weekly'/'monthly'), `start_date`, `end_date`, `limit` |
| `get_stock_intraday` | 查询今日个股分笔分时成交数据 | `symbol`: 6 位股票代码 |
| `get_index_quote` | 查询大盘及重要指数行情 | `symbol`: 指数代码（如 `000001` 上证指数，`399001` 深成指，`all` 全市场核心指数） |
| `search_stock` | 模糊搜索股票代码与基本行情 | `keyword`: 公司简称或拼音简写，`limit`: 最大数量 |
| `get_stock_info` | 查询个股公司资料、高管人员、主营业务、行业及市值估值 | `symbol`: 股票代码或简称 |
| `get_trade_calendar` | 查询 A 股交易日历与休市安排 | `start_date`, `end_date` (格式 'YYYYMMDD') |

---

## 🚀 安装与配置指南

### 1. 运行环境准备
本插件基于 Python 3.10+ 开发，在插件根目录下创建虚拟环境并安装依赖：

```bash
# 1. 创建虚拟环境
python3 -m venv .venv

# 2. 激活虚拟环境并安装依赖
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. TuShare Token 配置 (可选但推荐)
如需使用 TuShare Pro 高级历史 K 线与深度上市公司数据库：
* 注册 [TuShare Pro](https://tushare.pro/) 并获取专属 Token。
* 设置系统环境变量：
  ```bash
  export TUSHARE_TOKEN="your_tushare_token_here"
  ```
* 或保存在 `~/.tushare_token` 文件中。插件在未配置 Token 时会自动使用原生实时通道与公共数据接口。

### 3. 在 Grokbot / Grok Build 中使用

#### 方式 A：通过本地插件目录加载
在运行 Grokbot 时，指定插件所在目录或将其软链接至插件目录：

```bash
# 复制或链接至 Grokbot 插件目录
mkdir -p ~/.grok/plugins
ln -s /path/to/tushare ~/.grok/plugins/tushare
```

#### 方式 B：配置 `mcp.json`
在 Grokbot 或客户端的 MCP 配置中注册服务：

```json
{
  "mcpServers": {
    "tushare": {
      "command": "python3",
      "args": ["/path/to/tushare/run_server.py"],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "TUSHARE_TOKEN": "your_tushare_token_here"
      }
    }
  }
}
```

---

## 💡 使用示例与提示词 (Prompts)

您可以直接向 Grokbot 提问：

1. **查询实时股价与盘口**：
   > “帮我查一下贵州茅台现在的实时价格和五档买卖盘口”  
   > “查看 000001 平安银行当前涨跌幅是多少”

2. **分析历史走势与 K 线**：
   > “查看宁德时代（300750）最近一个月的日K线走势与涨跌幅”  
   > “调取比亚迪近半年的周K线走势”

3. **关注宏观大盘走势**：
   > “今天 A 股大盘行情怎么样？上证指数和创业板指当前点位是多少？”

4. **上市公司资料与高管画像**：
   > “查询中芯国际（688981）的董事长是谁？主营业务有哪些？”  
   > “查一下贵州茅台的公司基本信息、注册资本和员工人数”

5. **交易日历与休市安排**：
   > “今天 A 股开市交易吗？下周哪天休市？”

---

## 🧪 运行测试

运行内置单元与集成测试以验证各接口功能：

```bash
.venv/bin/python3 -m unittest tests/test_plugin.py
```

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。数据来源于 TuShare 金融大数据平台及公开网络财经接口，仅供技术研究与个人参考，不构成任何投资建议。本插件为独立项目，与 TuShare 官方无关。
