"""Utility functions for formatting stock data and codes in TuShare plugin."""

from typing import Any, Dict, List, Optional, Union
import re


# 常见 A 股股票名称与代码静态快速映射（加速查询并作为离线兜底）
COMMON_A_STOCKS: Dict[str, str] = {
    "贵州茅台": "600519",
    "茅台": "600519",
    "宁德时代": "300750",
    "比亚迪": "002594",
    "平安银行": "000001",
    "中国平安": "601318",
    "五粮液": "000858",
    "招商银行": "600036",
    "中信证券": "600030",
    "东方财富": "300059",
    "中芯国际": "688981",
    "工业富联": "601138",
    "赛力斯": "601127",
    "长江电力": "600900",
    "美的集团": "000333",
    "海康威视": "002415",
    "立讯精密": "002475",
    "紫金矿业": "601899",
    "隆基绿能": "601012",
    "中兴通讯": "000063",
    "科大讯飞": "002230",
    "药明康德": "603259",
    "迈瑞医疗": "300760",
    "格力电器": "000651",
    "京东方A": "000725",
    "三花智控": "002050",
    "中际旭创": "300308",
    "天孚通信": "300394",
    "新易盛": "300502",
    "寒武纪": "688256",
    "中国石油": "601857",
    "中国石化": "600028",
    "工商银行": "601398",
    "建设银行": "601939",
    "农业银行": "601288",
    "中国银行": "601988",
    "邮储银行": "601658",
    "交通银行": "601328",
    "通威股份": "600438",
    "阳光电源": "300274",
    "顺丰控股": "002352",
    "恒瑞医药": "600276",
    "片仔癀": "600436",
    "伊利股份": "600887",
    "万科A": "000002",
    "保利发展": "600048",
    "海尔智家": "600690",
    "潍柴动力": "000338",
    "福耀玻璃": "600660",
    "中微公司": "688012",
    "北方华创": "002371",
}

# 常见指数代码与名称映射
INDEX_MAP: Dict[str, str] = {
    "sh000001": "000001.SH",
    "000001": "000001.SH",
    "sh": "000001.SH",
    "上证指数": "000001.SH",
    "大盘": "000001.SH",
    "sz399001": "399001.SZ",
    "399001": "399001.SZ",
    "sz": "399001.SZ",
    "深证成指": "399001.SZ",
    "sz399006": "399006.SZ",
    "399006": "399006.SZ",
    "cyb": "399006.SZ",
    "创业板指": "399006.SZ",
    "sh000688": "000688.SH",
    "000688": "000688.SH",
    "科创50": "000688.SH",
    "sh000300": "000300.SH",
    "000300": "000300.SH",
    "hs300": "000300.SH",
    "沪深300": "000300.SH",
    "sh000905": "000905.SH",
    "000905": "000905.SH",
    "中证500": "000905.SH",
    "sh000016": "000016.SH",
    "000016": "000016.SH",
    "上证50": "000016.SH",
    "bj899050": "899050.BJ",
    "899050": "899050.BJ",
    "北证50": "899050.BJ",
}

# 指数中文名称显示字典
INDEX_NAMES: Dict[str, str] = {
    "000001": "上证指数",
    "000001.SH": "上证指数",
    "399001": "深证成指",
    "399001.SZ": "深证成指",
    "399006": "创业板指",
    "399006.SZ": "创业板指",
    "000300": "沪深300",
    "000300.SH": "沪深300",
    "000688": "科创50",
    "000688.SH": "科创50",
    "000905": "中证500",
    "000905.SH": "中证500",
    "000016": "上证50",
    "000016.SH": "上证50",
    "899050": "北证50",
    "899050.BJ": "北证50",
}


def normalize_symbol(symbol: str) -> str:
    """标准化股票代码为 6 位数字格式。

    例如：
    - 'sh600519' -> '600519'
    - 'SZ000001' -> '000001'
    - '600519.SH' -> '600519'
    - '贵州茅台' -> '600519'
    """
    symbol = symbol.strip()
    if symbol in COMMON_A_STOCKS:
        return COMMON_A_STOCKS[symbol]

    # 去除 .SH / .SZ / .BJ 后缀
    symbol_clean = re.sub(r"\.(SH|SZ|BJ|sh|sz|bj)$", "", symbol)
    if symbol_clean in COMMON_A_STOCKS:
        return COMMON_A_STOCKS[symbol_clean]

    # 去除 sh/sz/bj 前缀
    m = re.match(r"^(?:sh|sz|bj|SH|SZ|BJ)?(\d{6})$", symbol_clean)
    if m:
        return m.group(1)

    # 提取字符串中的 6 位连续数字
    digits = re.findall(r"\b\d{6}\b", symbol)
    if digits:
        return digits[0]

    return symbol_clean


def to_ts_code(symbol: str, is_index: bool = False) -> str:
    """将代码转换为 TuShare Pro 标准格式（如 600519.SH, 000001.SZ, 000001.SH）。"""
    symbol = symbol.strip()

    if is_index:
        if symbol in INDEX_MAP:
            return INDEX_MAP[symbol]
        norm = normalize_symbol(symbol)
        if norm.startswith(("000", "sh", "SH")):
            return f"{norm}.SH"
        elif norm.startswith(("399", "sz", "SZ")):
            return f"{norm}.SZ"
        elif norm.startswith(("899", "bj", "BJ")):
            return f"{norm}.BJ"
        return f"{norm}.SH"

    # 若是股票
    if symbol in COMMON_A_STOCKS:
        norm = COMMON_A_STOCKS[symbol]
    else:
        norm = normalize_symbol(symbol)

    # 若已包含后缀
    if re.search(r"\.(SH|SZ|BJ)$", norm, re.IGNORECASE):
        return norm.upper()

    if norm == "000001":
        return "000001.SZ"

    # 个股规则
    if norm.startswith(("6", "9", "5", "688")):
        return f"{norm}.SH"
    elif norm.startswith(("00", "30")):
        return f"{norm}.SZ"
    elif norm.startswith(("8", "4", "92")):
        return f"{norm}.BJ"

    return f"{norm}.SH"


def format_amount(val: Optional[Union[int, float]]) -> str:
    """格式化金额（自动转换为 元/万元/亿元）。"""
    if val is None or val == "":
        return "-"
    try:
        f = float(val)
        if abs(f) >= 1e8:
            return f"{f / 1e8:.2f} 亿元"
        elif abs(f) >= 1e4:
            return f"{f / 1e4:.2f} 万元"
        else:
            return f"{f:.2f} 元"
    except (ValueError, TypeError):
        return str(val)


def format_volume(val: Optional[Union[int, float]]) -> str:
    """格式化成交量（单位：手）。"""
    if val is None or val == "":
        return "-"
    try:
        f = float(val)
        if abs(f) >= 1e8:
            return f"{f / 1e8:.2f} 亿手"
        elif abs(f) >= 1e4:
            return f"{f / 1e4:.2f} 万手"
        else:
            return f"{f:.0f} 手"
    except (ValueError, TypeError):
        return str(val)


def format_price(val: Optional[Union[int, float]], precision: int = 2) -> str:
    """格式化价格。"""
    if val is None or val == "":
        return "-"
    try:
        f = float(val)
        return f"{f:.{precision}f}"
    except (ValueError, TypeError):
        return str(val)


def format_change(
    change_pct: Optional[Union[int, float]],
    change_amt: Optional[Union[int, float]] = None,
) -> str:
    """根据中国 A 股市场习惯格式化涨跌指示：
    - 🔴 红色上涨 (+)
    - 🟢 绿色下跌 (-)
    - ⚪ 平盘 (0.00%)
    """
    if change_pct is None or change_pct == "":
        return "-"
    try:
        pct = float(change_pct)
        amt_str = ""
        if change_amt is not None and change_amt != "":
            amt = float(change_amt)
            amt_str = f" ({'+' if amt > 0 else ''}{amt:.2f})"

        if pct > 0:
            return f"🔴 +{pct:.2f}%{amt_str}"
        elif pct < 0:
            return f"🟢 {pct:.2f}%{amt_str}"
        else:
            return f"⚪ 0.00%{amt_str}"
    except (ValueError, TypeError):
        return str(change_pct)


def render_stock_quote_markdown(data: Dict[str, Any]) -> str:
    """将个股实时行情及五档买卖盘渲染为美观的 Markdown。"""
    name = data.get("name", "未知")
    symbol = data.get("symbol", "")
    price = format_price(data.get("latest_price"))
    change_pct = data.get("change_percent")
    change_amt = data.get("change_amount")
    change_str = format_change(change_pct, change_amt)

    open_price = format_price(data.get("open"))
    prev_close = format_price(data.get("prev_close"))
    high = format_price(data.get("high"))
    low = format_price(data.get("low"))
    volume = format_volume(data.get("volume"))
    amount = format_amount(data.get("amount"))
    turnover_rate = (
        f"{data.get('turnover_rate', '-'):.2f}%"
        if isinstance(data.get("turnover_rate"), (int, float))
        else str(data.get("turnover_rate", "-"))
    )
    pe = (
        f"{data.get('pe_ratio', '-'):.2f}"
        if isinstance(data.get("pe_ratio"), (int, float))
        else str(data.get("pe_ratio", "-"))
    )
    pb = (
        f"{data.get('pb_ratio', '-'):.2f}"
        if isinstance(data.get("pb_ratio"), (int, float))
        else str(data.get("pb_ratio", "-"))
    )
    update_time = data.get("update_time", "实时快照")

    lines = [
        f"### 📈 {name} ({symbol}) 实时行情",
        "",
        f"**最新价格**：**{price} 元** | **涨跌幅度**：**{change_str}**",
        "",
        f"- **今开**：`{open_price}` | **昨收**：`{prev_close}`",
        f"- **最高**：`{high}` | **最低**：`{low}`",
        f"- **成交量**：`{volume}` | **成交额**：`{amount}`",
        f"- **换手率**：`{turnover_rate}` | **市盈率(动)**：`{pe}` | **市净率**：`{pb}`",
        f"- **数据更新时间**：`{update_time}`",
    ]

    bid_ask = data.get("bid_ask")
    if bid_ask and isinstance(bid_ask, dict):
        lines.extend([
            "",
            "#### 📊 五档盘口",
            "| 档位 | 卖价(元) | 卖量(手) | 档位 | 买价(元) | 买量(手) |",
            "|:---|:---|:---|:---|:---|:---|",
        ])
        for i in range(5, 0, -1):
            sell_p = format_price(bid_ask.get(f"sell_{i}_price"))
            sell_v = format_volume(bid_ask.get(f"sell_{i}_volume"))
            buy_p = format_price(bid_ask.get(f"buy_{i}_price"))
            buy_v = format_volume(bid_ask.get(f"buy_{i}_volume"))
            lines.append(f"| 卖{i} | {sell_p} | {sell_v} | 买{i} | {buy_p} | {buy_v} |")

    lines.extend([
        "",
        "> 💡 *提示：红色为上涨，绿色为下跌。数据源自 TuShare 金融大数据接口，仅供参考，不作为投资决策依据。*",
    ])

    return "\n".join(lines)


def render_kline_markdown(
    symbol: str, name: str, period: str, records: List[Dict[str, Any]]
) -> str:
    """渲染历史 K 线数据摘要及表格。"""
    if not records:
        return f"未查询到股票 {name} ({symbol}) 的 {period} K线数据。"

    period_cn = {"daily": "日", "weekly": "周", "monthly": "月"}.get(period, period)

    lines = [
        f"### 📊 {name} ({symbol}) 历史 {period_cn}K 线走势 (最近 {len(records)} 条)",
        "",
        "| 日期 | 开盘价 | 收盘价 | 最高价 | 最低价 | 涨跌幅 | 成交量(手) | 成交额 | 换手率 |",
        "|:---|:---|:---|:---|:---|:---|:---|:---|:---|",
    ]

    # 取最近 15 条
    display_records = records[:15] if len(records) > 15 else records

    for r in display_records:
        date = r.get("trade_date", r.get("date", "-"))
        if len(str(date)) == 8:
            date = f"{str(date)[:4]}-{str(date)[4:6]}-{str(date)[6:]}"
        open_p = format_price(r.get("open"))
        close_p = format_price(r.get("close"))
        high_p = format_price(r.get("high"))
        low_p = format_price(r.get("low"))
        pct = format_change(r.get("pct_chg", r.get("change_pct")))
        vol = format_volume(r.get("vol", r.get("volume")))
        amt = format_amount(r.get("amount"))
        turnover = r.get("turnover_rate", r.get("turnover", "-"))
        turnover_str = f"{turnover:.2f}%" if isinstance(turnover, (int, float)) else str(turnover)
        lines.append(
            f"| {date} | {open_p} | {close_p} | {high_p} | {low_p} | {pct} | {vol} | {amt} | {turnover_str} |"
        )

    lines.extend([
        "",
        f"*共返回 {len(records)} 条数据，上方表格展示最近 {len(display_records)} 个周期数据。*",
        "> 💡 *数据源：TuShare Pro 行情接口。*",
    ])
    return "\n".join(lines)


def render_company_info_markdown(data: Dict[str, Any]) -> str:
    """渲染上市公司资料、高管与主营业务。"""
    name = data.get("name", "未知")
    symbol = data.get("symbol", "")
    ts_code = data.get("ts_code", "")
    com_name = data.get("com_name", name)
    chairman = data.get("chairman", "-")
    manager = data.get("manager", "-")
    secretary = data.get("secretary", "-")
    reg_capital = data.get("reg_capital")
    reg_capital_str = (
        f"{reg_capital:,.2f} 万元" if isinstance(reg_capital, (int, float)) else str(reg_capital or "-")
    )
    setup_date = str(data.get("setup_date", "-"))
    if len(setup_date) == 8:
        setup_date = f"{setup_date[:4]}-{setup_date[4:6]}-{setup_date[6:]}"

    list_date = str(data.get("list_date", "-"))
    if len(list_date) == 8:
        list_date = f"{list_date[:4]}-{list_date[4:6]}-{list_date[6:]}"

    area = data.get("area", "-")
    province = data.get("province", area)
    city = data.get("city", "-")
    industry = data.get("industry", "-")
    website = data.get("website", "-")
    employees = data.get("employees", "-")
    total_mv = format_amount(data.get("total_mv"))
    circ_mv = format_amount(data.get("circ_mv"))
    pe = f"{data.get('pe_ratio', '-'):.2f}" if isinstance(data.get("pe_ratio"), (int, float)) else str(data.get("pe_ratio", "-"))
    pb = f"{data.get('pb_ratio', '-'):.2f}" if isinstance(data.get("pb_ratio"), (int, float)) else str(data.get("pb_ratio", "-"))
    main_business = data.get("main_business", "暂无主营业务信息")
    introduction = data.get("introduction", "")

    lines = [
        f"### 🏢 {com_name} ({symbol}) 公司基本资料",
        "",
        f"- **股票代码**：`{symbol}` (TuShare: `{ts_code}`)",
        f"- **所属行业**：`{industry}` | **所在地区**：`{province} - {city}`",
        f"- **上市日期**：`{list_date}` | **成立日期**：`{setup_date}`",
        f"- **法定代表/董事长**：`{chairman}` | **总经理**：`{manager}` | **董秘**：`{secretary}`",
        f"- **注册资本**：`{reg_capital_str}` | **员工人数**：`{employees}`",
        f"- **总市值**：`{total_mv}` | **流通市值**：`{circ_mv}`",
        f"- **动态市盈率(PE)**：`{pe}` | **市净率(PB)**：`{pb}`",
        f"- **官方网站**：{website}",
        "",
        "#### 🎯 主营业务",
        f"> {main_business}",
    ]

    if introduction:
        lines.extend([
            "",
            "#### 📖 公司简介",
            f"{introduction[:400]}{'...' if len(introduction) > 400 else ''}",
        ])

    lines.extend([
        "",
        "> 💡 *数据源自 TuShare Pro 上市公司数据库。*",
    ])
    return "\n".join(lines)


def render_trade_cal_markdown(records: List[Dict[str, Any]]) -> str:
    """渲染交易日历。"""
    if not records:
        return "未查询到交易日历数据。"

    lines = [
        "### 📅 A 股交易日历与休市安排",
        "",
        "| 日期 | 是否开市 | 星期 | 说明 |",
        "|:---|:---|:---|:---|",
    ]

    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    import datetime

    for r in records:
        date_str = str(r.get("cal_date", ""))
        is_open = r.get("is_open", 0)
        formatted_date = (
            f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}" if len(date_str) == 8 else date_str
        )
        try:
            dt = datetime.datetime.strptime(date_str, "%Y%m%d")
            w = weekdays[dt.weekday()]
        except Exception:
            w = "-"

        status = "🟢 开市交易" if is_open in (1, "1") else "🔴 休市"
        note = "正常交易日" if is_open in (1, "1") else ("周末休市" if w in ("周六", "周日") else "法定节假日休市")
        lines.append(f"| {formatted_date} | {status} | {w} | {note} |")

    return "\n".join(lines)
