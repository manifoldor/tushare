"""TuShare API wrapper providing robust A-share market data query methods."""

import datetime
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional
import pandas as pd
import requests

from .utils import (
    COMMON_A_STOCKS,
    INDEX_MAP,
    INDEX_NAMES,
    format_amount,
    format_change,
    format_price,
    format_volume,
    normalize_symbol,
    render_company_info_markdown,
    render_kline_markdown,
    render_stock_quote_markdown,
    render_trade_cal_markdown,
    to_ts_code,
)

logger = logging.getLogger(__name__)

# 全局补丁：为 requests 请求注入真实浏览器 User-Agent
_orig_session_request = requests.Session.request


def _patched_session_request(self, method, url, **kwargs):
    headers = kwargs.setdefault("headers", {})
    if "User-Agent" not in headers and "user-agent" not in headers:
        headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    return _orig_session_request(self, method, url, **kwargs)


requests.Session.request = _patched_session_request

# 缓存与配置
_TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")
_PRO_API = None
_STOCK_CATALOG_CACHE: Optional[List[Dict[str, str]]] = None
_STOCK_CATALOG_CACHE_TIME: float = 0
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
_CACHE_DIR.mkdir(exist_ok=True)


def _save_company_cache(ts_code: str, data: Dict[str, Any]):
    """保存上市公司资料到本地缓存。"""
    cache_file = _CACHE_DIR / "company_cache.json"
    cache = {}
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}
    if ts_code not in cache:
        cache[ts_code] = {}
    cache[ts_code].update(data)
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_company_cache(ts_code: str) -> Optional[Dict[str, Any]]:
    """从本地缓存或内置种子数据加载上市公司资料。"""
    cache_file = _CACHE_DIR / "company_cache.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
                if ts_code in cache:
                    return cache.get(ts_code)
        except Exception:
            pass

    # 尝试从内置 seed 数据读取
    seed_file = Path(__file__).resolve().parent / "data" / "seed_companies.json"
    if seed_file.exists():
        try:
            with open(seed_file, "r", encoding="utf-8") as f:
                seed_data = json.load(f)
                return seed_data.get(ts_code)
        except Exception:
            pass
    return None


def get_tushare_module():
    """获取 tushare 模块。"""
    try:
        import tushare as ts
        return ts
    except ImportError:
        raise ImportError(
            "未安装 tushare 依赖。请运行 '.venv/bin/pip install tushare' 或 'pip install tushare'。"
        )


def get_pro_api():
    """获取 TuShare Pro API 客户端实例（支持从环境变量或配置文件自动加载 Token）。"""
    global _PRO_API, _TUSHARE_TOKEN
    if _PRO_API is not None:
        return _PRO_API

    ts = get_tushare_module()

    token = os.environ.get("TUSHARE_TOKEN", "") or _TUSHARE_TOKEN
    # 尝试读取 ~/.tushare_token
    if not token:
        token_file = Path.home() / ".tushare_token"
        if token_file.exists():
            token = token_file.read_text().strip()

    if token:
        _TUSHARE_TOKEN = token
        ts.set_token(token)
        _PRO_API = ts.pro_api(token)
        return _PRO_API
    else:
        # 无 token 时使用默认 pro_api 尝试
        try:
            _PRO_API = ts.pro_api()
            return _PRO_API
        except Exception:
            return None


def _get_tencent_realtime_quote(symbol: str) -> Optional[Dict[str, Any]]:
    """通过腾讯财经实时行情通道获取极速 L1 实时盘口与估值（毫秒级响应，作为主备高可用通道）。"""
    norm_symbol = normalize_symbol(symbol)
    prefix = (
        "sh"
        if norm_symbol.startswith(("6", "9", "5", "688"))
        else ("bj" if norm_symbol.startswith(("8", "4", "92")) else "sz")
    )
    secid = f"{prefix}{norm_symbol}"
    url = f"http://qt.gtimg.cn/q={secid}"

    try:
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            text = resp.content.decode("gbk", errors="ignore").strip()
            m = re.search(r'="([^"]+)"', text)
            if m:
                parts = m.group(1).split("~")
                if len(parts) > 30 and parts[1]:
                    name = parts[1]
                    latest_price = float(parts[3]) if parts[3] else None
                    prev_close = float(parts[4]) if parts[4] else None
                    open_price = float(parts[5]) if parts[5] else None
                    volume = float(parts[6]) if parts[6] else None  # 手
                    change_amount = float(parts[31]) if parts[31] else None
                    change_percent = float(parts[32]) if parts[32] else None
                    high = float(parts[33]) if parts[33] else None
                    low = float(parts[34]) if parts[34] else None
                    amount = (
                        float(parts[37]) * 10000 if parts[37] else None
                    )  # 万元 -> 元
                    turnover_rate = float(parts[38]) if parts[38] else None
                    pe_ratio = float(parts[39]) if parts[39] else None
                    total_mv = (
                        float(parts[44]) * 100000000 if len(parts) > 44 and parts[44] else None
                    )
                    circ_mv = (
                        float(parts[45]) * 100000000 if len(parts) > 45 and parts[45] else None
                    )
                    pb_ratio = (
                        float(parts[46]) if len(parts) > 46 and parts[46] else None
                    )

                    bid_ask = {
                        "buy_1_price": float(parts[9]) if parts[9] else None,
                        "buy_1_volume": float(parts[10]) if parts[10] else None,
                        "buy_2_price": float(parts[11]) if parts[11] else None,
                        "buy_2_volume": float(parts[12]) if parts[12] else None,
                        "buy_3_price": float(parts[13]) if parts[13] else None,
                        "buy_3_volume": float(parts[14]) if parts[14] else None,
                        "buy_4_price": float(parts[15]) if parts[15] else None,
                        "buy_4_volume": float(parts[16]) if parts[16] else None,
                        "buy_5_price": float(parts[17]) if parts[17] else None,
                        "buy_5_volume": float(parts[18]) if parts[18] else None,
                        "sell_1_price": float(parts[19]) if parts[19] else None,
                        "sell_1_volume": float(parts[20]) if parts[20] else None,
                        "sell_2_price": float(parts[21]) if parts[21] else None,
                        "sell_2_volume": float(parts[22]) if parts[22] else None,
                        "sell_3_price": float(parts[23]) if parts[23] else None,
                        "sell_3_volume": float(parts[24]) if parts[24] else None,
                        "sell_4_price": float(parts[25]) if parts[25] else None,
                        "sell_4_volume": float(parts[26]) if parts[26] else None,
                        "sell_5_price": float(parts[27]) if parts[27] else None,
                        "sell_5_volume": float(parts[28]) if parts[28] else None,
                    }

                    raw_time = parts[30] if len(parts) > 30 else ""
                    update_time = (
                        f"{raw_time[:4]}-{raw_time[4:6]}-{raw_time[6:8]} {raw_time[8:10]}:{raw_time[10:12]}:{raw_time[12:14]}"
                        if len(raw_time) == 14
                        else datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )

                    return {
                        "symbol": norm_symbol,
                        "name": name,
                        "latest_price": latest_price,
                        "prev_close": prev_close,
                        "open": open_price,
                        "high": high,
                        "low": low,
                        "volume": volume,
                        "amount": amount,
                        "change_amount": change_amount,
                        "change_percent": change_percent,
                        "turnover_rate": turnover_rate,
                        "pe_ratio": pe_ratio,
                        "pb_ratio": pb_ratio,
                        "total_mv": total_mv,
                        "circ_mv": circ_mv,
                        "update_time": update_time,
                        "bid_ask": bid_ask,
                    }
    except Exception as e:
        logger.warning(f"腾讯备选通道获取失败 ({secid}): {e}")
    return None


def get_stock_quote(symbol: str) -> Dict[str, Any]:
    """查询指定 A 股个股的最新实时行情、价格变动与五档买卖盘口。

    参数:
        symbol: 股票代码（例如 '600519', '000001'）或简称（例如 '贵州茅台'）

    返回:
        字典包含结构化行情数据与预渲染的 Markdown 文本。
    """
    ts = get_tushare_module()
    norm_symbol = normalize_symbol(symbol)

    quote_data: Dict[str, Any] = {}
    tencent_data = _get_tencent_realtime_quote(norm_symbol)

    try:
        # 使用 TuShare 原生实时行情接口
        df = ts.get_realtime_quotes(norm_symbol)
        if df is not None and not df.empty:
            row = df.iloc[0]
            name = str(row.get("name", norm_symbol))
            latest_price = float(row["price"]) if row["price"] and float(row["price"]) > 0 else (
                tencent_data["latest_price"] if tencent_data else 0.0
            )
            prev_close = float(row["pre_close"]) if row["pre_close"] else (
                tencent_data["prev_close"] if tencent_data else 0.0
            )
            open_price = float(row["open"]) if row["open"] else (
                tencent_data["open"] if tencent_data else 0.0
            )
            high = float(row["high"]) if row["high"] else (
                tencent_data["high"] if tencent_data else 0.0
            )
            low = float(row["low"]) if row["low"] else (
                tencent_data["low"] if tencent_data else 0.0
            )

            # volume 字段在 tushare 经典接口中单位为“股”，转为“手”
            raw_vol = float(row["volume"]) if row["volume"] else 0.0
            volume = raw_vol / 100.0 if raw_vol > 0 else (
                tencent_data["volume"] if tencent_data else 0.0
            )
            amount = float(row["amount"]) if row["amount"] else (
                tencent_data["amount"] if tencent_data else 0.0
            )

            change_amount = round(latest_price - prev_close, 3) if prev_close else 0.0
            change_percent = (
                round((change_amount / prev_close) * 100, 2) if prev_close else 0.0
            )

            # 五档盘口（tushare 经典接口中的 b1_v/a1_v 单位为手）
            bid_ask = {
                "buy_1_price": float(row["b1_p"]) if row.get("b1_p") else None,
                "buy_1_volume": float(row["b1_v"]) if row.get("b1_v") else None,
                "buy_2_price": float(row["b2_p"]) if row.get("b2_p") else None,
                "buy_2_volume": float(row["b2_v"]) if row.get("b2_v") else None,
                "buy_3_price": float(row["b3_p"]) if row.get("b3_p") else None,
                "buy_3_volume": float(row["b3_v"]) if row.get("b3_v") else None,
                "buy_4_price": float(row["b4_p"]) if row.get("b4_p") else None,
                "buy_4_volume": float(row["b4_v"]) if row.get("b4_v") else None,
                "buy_5_price": float(row["b5_p"]) if row.get("b5_p") else None,
                "buy_5_volume": float(row["b5_v"]) if row.get("b5_v") else None,
                "sell_1_price": float(row["a1_p"]) if row.get("a1_p") else None,
                "sell_1_volume": float(row["a1_v"]) if row.get("a1_v") else None,
                "sell_2_price": float(row["a2_p"]) if row.get("a2_p") else None,
                "sell_2_volume": float(row["a2_v"]) if row.get("a2_v") else None,
                "sell_3_price": float(row["a3_p"]) if row.get("a3_p") else None,
                "sell_3_volume": float(row["a3_v"]) if row.get("a3_v") else None,
                "sell_4_price": float(row["a4_p"]) if row.get("a4_p") else None,
                "sell_4_volume": float(row["a4_v"]) if row.get("a4_v") else None,
                "sell_5_price": float(row["a5_p"]) if row.get("a5_p") else None,
                "sell_5_volume": float(row["a5_v"]) if row.get("a5_v") else None,
            }

            date_str = str(row.get("date", ""))
            time_str = str(row.get("time", ""))
            update_time = f"{date_str} {time_str}".strip() or datetime.datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            quote_data = {
                "symbol": norm_symbol,
                "name": name,
                "latest_price": latest_price,
                "prev_close": prev_close,
                "open": open_price,
                "high": high,
                "low": low,
                "volume": volume,
                "amount": amount,
                "change_amount": change_amount,
                "change_percent": change_percent,
                "turnover_rate": tencent_data.get("turnover_rate") if tencent_data else "-",
                "pe_ratio": tencent_data.get("pe_ratio") if tencent_data else "-",
                "pb_ratio": tencent_data.get("pb_ratio") if tencent_data else "-",
                "total_mv": tencent_data.get("total_mv") if tencent_data else None,
                "circ_mv": tencent_data.get("circ_mv") if tencent_data else None,
                "update_time": update_time,
                "bid_ask": bid_ask,
            }
    except Exception as e:
        logger.warning(f"TuShare 原生行情接口失败 ({norm_symbol}): {e}")

    # 若 TuShare 原生接口未取到有效数据，使用备选通道
    if not quote_data and tencent_data:
        quote_data = tencent_data

    if not quote_data:
        raise RuntimeError(f"未能获取到股票 {symbol} ({norm_symbol}) 的行情数据。")

    quote_data["markdown"] = render_stock_quote_markdown(quote_data)
    return quote_data


def get_index_quote(symbol: str = "000001") -> Dict[str, Any]:
    """获取 A 股大盘及重要指数行情。

    参数:
        symbol: 指数代码或简称，如 '000001'(上证指数), '399001'(深成指), '399006'(创业板指), 'all'(全市场主要指数)
    """
    ts = get_tushare_module()
    symbol_str = symbol.strip().lower()

    if symbol_str in ("all", "overview", "大盘", "指数", "市场", "000001"):
        codes = ["sh", "sz", "cyb", "hs300"]
    else:
        norm = normalize_symbol(symbol)
        if norm in ("000001", "sh000001"):
            codes = ["sh"]
        elif norm in ("399001", "sz399001"):
            codes = ["sz"]
        elif norm in ("399006", "sz399006"):
            codes = ["cyb"]
        elif norm in ("000300", "sh000300"):
            codes = ["hs300"]
        else:
            codes = [norm]

    try:
        df = ts.get_realtime_quotes(codes)
    except Exception as e:
        logger.warning(f"获取指数行情失败 ({codes}): {e}")
        df = None

    records = []
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            code = str(row.get("code", ""))
            name = str(row.get("name", INDEX_NAMES.get(code, code)))
            price = float(row["price"]) if row["price"] else 0.0
            prev_close = float(row["pre_close"]) if row["pre_close"] else 0.0
            change_amount = round(price - prev_close, 2)
            change_pct = round((change_amount / prev_close) * 100, 2) if prev_close else 0.0
            vol = float(row["volume"]) if row["volume"] else 0.0  # 指数成交量通常为手
            amt = float(row["amount"]) if row["amount"] else 0.0  # 指数成交额为元

            records.append({
                "code": code,
                "name": name,
                "price": price,
                "prev_close": prev_close,
                "change_amount": change_amount,
                "change_percent": change_pct,
                "volume": vol,
                "amount": amt,
                "time": f"{row.get('date', '')} {row.get('time', '')}".strip(),
            })

    # 生成 Markdown 表格
    lines = [
        "### 🇨🇳 A 股核心大盘指数行情",
        "",
        "| 指数名称 | 指数代码 | 最新点位 | 涨跌幅 | 涨跌点 | 成交量(手) | 成交额 | 更新时间 |",
        "|:---|:---|:---|:---|:---|:---|:---|:---|",
    ]

    for r in records:
        chg_str = format_change(r["change_percent"])
        amt_str = f"{'+' if r['change_amount'] > 0 else ''}{r['change_amount']:.2f}"
        lines.append(
            f"| **{r['name']}** | `{r['code']}` | **{r['price']:.2f}** | {chg_str} | {amt_str} | {format_volume(r['volume'])} | {format_amount(r['amount'])} | {r['time']} |"
        )

    lines.extend([
        "",
        "> 💡 *提示：红色代表上涨，绿色代表下跌。数据源自 TuShare 行情系统。*",
    ])

    return {
        "symbol": symbol,
        "count": len(records),
        "records": records,
        "markdown": "\n".join(lines),
    }


def get_stock_history(
    symbol: str,
    period: str = "daily",
    start_date: str = "",
    end_date: str = "",
    limit: int = 30,
) -> Dict[str, Any]:
    """查询指定 A 股个股的历史 K 线行情数据（支持 daily / weekly / monthly）。

    参数:
        symbol: 股票代码（例如 '600519' 或 '600519.SH'）
        period: K线周期，可选：'daily'（日K线，默认）、'weekly'（周K线）、'monthly'（月K线）
        start_date: 开始日期，格式 'YYYYMMDD'（如 '20240101'）
        end_date: 结束日期，格式 'YYYYMMDD'（如 '20241014'）
        limit: 最大返回交易日数（默认 30 条）
    """
    pro = get_pro_api()
    norm_symbol = normalize_symbol(symbol)
    ts_code = to_ts_code(symbol, is_index=False)
    name = COMMON_A_STOCKS.get(norm_symbol, norm_symbol)

    today = datetime.date.today()
    if not end_date:
        end_date = today.strftime("%Y%m%d")
    else:
        end_date = end_date.replace("-", "").replace("/", "")

    if not start_date:
        # 默认取最近 180 天以满足周线和月线聚合要求
        start_dt = today - datetime.timedelta(days=180 if period != "daily" else 90)
        start_date = start_dt.strftime("%Y%m%d")
    else:
        start_date = start_date.replace("-", "").replace("/", "")

    records = []

    # 优先使用 TuShare Pro
    if pro is not None:
        try:
            if period == "daily":
                df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            elif period == "weekly":
                try:
                    df = pro.weekly(ts_code=ts_code, start_date=start_date, end_date=end_date)
                except Exception:
                    # 若 weekly 接口频次超限，从 daily 数据重采样
                    df_daily = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                    df = _resample_kline(df_daily, "W-FRI")
            elif period == "monthly":
                try:
                    df = pro.monthly(ts_code=ts_code, start_date=start_date, end_date=end_date)
                except Exception:
                    df_daily = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                    df = _resample_kline(df_daily, "ME")
            else:
                df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)

            if df is not None and not df.empty:
                # 转换金额与成交量单位
                # TuShare pro.daily: vol 为手，amount 为千元
                for _, r in df.head(limit).iterrows():
                    amt_yuan = float(r["amount"]) * 1000 if "amount" in r and r["amount"] else None
                    records.append({
                        "trade_date": str(r.get("trade_date", "")),
                        "open": float(r["open"]) if r.get("open") else None,
                        "close": float(r["close"]) if r.get("close") else None,
                        "high": float(r["high"]) if r.get("high") else None,
                        "low": float(r["low"]) if r.get("low") else None,
                        "pct_chg": float(r["pct_chg"]) if r.get("pct_chg") else None,
                        "vol": float(r["vol"]) if r.get("vol") else None,
                        "amount": amt_yuan,
                        "turnover_rate": float(r["turnover_rate"]) if r.get("turnover_rate") else "-",
                    })
        except Exception as e:
            logger.warning(f"TuShare Pro 获取历史K线失败 ({ts_code}): {e}")

    # 若 TuShare Pro 未取到数据（无 Token 或接口受限），启动 Web 备选通道
    if not records:
        records = _get_web_kline_fallback(norm_symbol, period=period, limit=limit)

    markdown = render_kline_markdown(norm_symbol, name, period, records)
    return {
        "symbol": norm_symbol,
        "ts_code": ts_code,
        "name": name,
        "period": period,
        "count": len(records),
        "records": records,
        "markdown": markdown,
    }


def _resample_kline(df_daily: pd.DataFrame, rule: str) -> pd.DataFrame:
    """将日 K 线数据通过 Pandas 重采样为周线或月线。"""
    if df_daily is None or df_daily.empty:
        return df_daily
    df = df_daily.copy()
    df["date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values("date")
    resampled = df.resample(rule, on="date").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "vol": "sum",
        "amount": "sum",
    }).dropna().reset_index()
    resampled["trade_date"] = resampled["date"].dt.strftime("%Y%m%d")
    # 计算涨跌幅
    resampled["pct_chg"] = (
        (resampled["close"] - resampled["close"].shift(1))
        / resampled["close"].shift(1)
        * 100
    ).fillna(0.0)
    # 按日期倒序排列
    return resampled.sort_values("trade_date", ascending=False)


def _get_web_kline_fallback(
    symbol: str, period: str = "daily", limit: int = 30
) -> List[Dict[str, Any]]:
    """备选通道：从新浪行情 API 获取历史 K 线。"""
    norm = normalize_symbol(symbol)
    prefix = "sh" if norm.startswith(("6", "9", "5", "688")) else "sz"
    secid = f"{prefix}{norm}"

    scale_map = {"daily": 240, "weekly": 1200, "monthly": 7200}
    scale = scale_map.get(period, 240)
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={secid}&scale={scale}&ma=no&datalen={limit}"

    records = []
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                # 倒序取最新
                for item in reversed(data):
                    records.append({
                        "trade_date": item.get("day", "").replace("-", "")[:8],
                        "open": float(item["open"]) if item.get("open") else None,
                        "close": float(item["close"]) if item.get("close") else None,
                        "high": float(item["high"]) if item.get("high") else None,
                        "low": float(item["low"]) if item.get("low") else None,
                        "pct_chg": 0.0,
                        "vol": float(item["volume"]) / 100.0 if item.get("volume") else None,
                        "amount": None,
                        "turnover_rate": "-",
                    })
    except Exception as e:
        logger.warning(f"Web K线备选接口失败 ({secid}): {e}")
    return records


def get_stock_intraday(symbol: str) -> Dict[str, Any]:
    """获取指定 A 股个股今日分时分笔成交数据。

    参数:
        symbol: 股票代码（例如 '600519'）
    """
    ts = get_tushare_module()
    norm = normalize_symbol(symbol)
    name = COMMON_A_STOCKS.get(norm, norm)

    records = []
    try:
        df = ts.get_today_ticks(norm)
        if df is not None and not df.empty:
            # 倒序取最新 20 笔分笔成交
            for _, r in df.tail(20).iloc[::-1].iterrows():
                records.append({
                    "time": str(r.get("time", "")),
                    "price": float(r["price"]) if r.get("price") else None,
                    "vol": float(r["vol"]) if r.get("vol") else None,
                    "type": str(r.get("type", "-")),
                })
    except Exception as e:
        logger.warning(f"TuShare get_today_ticks 失败 ({norm}): {e}")

    lines = [
        f"### ⏱️ {name} ({norm}) 今日盘中分笔成交数据",
        "",
        "| 成交时间 | 成交价(元) | 成交量(手) | 买卖性质 |",
        "|:---|:---|:---|:---|",
    ]

    if records:
        for r in records:
            t_str = r["time"]
            formatted_time = (
                f"{t_str[:2]}:{t_str[2:4]}:{t_str[4:6]}" if len(t_str) == 6 else t_str
            )
            p_str = format_price(r["price"])
            v_str = format_volume(r["vol"])
            type_label = (
                "🔴 买盘"
                if r["type"] in ("买盘", "B", "1")
                else ("🟢 卖盘" if r["type"] in ("卖盘", "S", "-1") else "⚪ 中性盘")
            )
            lines.append(f"| {formatted_time} | {p_str} | {v_str} | {type_label} |")
    else:
        lines.append("| 暂无分笔成交数据 | - | - | - |")

    lines.extend([
        "",
        "> 💡 *数据源自 TuShare 实时分笔接口。*",
    ])

    return {
        "symbol": norm,
        "name": name,
        "count": len(records),
        "records": records,
        "markdown": "\n".join(lines),
    }


def search_stock(keyword: str, limit: int = 10) -> Dict[str, Any]:
    """根据公司名称或股票代码模糊检索 A 股股票信息。

    参数:
        keyword: 检索词（如 '茅台', '比亚迪', '芯片', '600519'）
        limit: 最大返回结果数量（默认 10）
    """
    ts = get_tushare_module()
    kw = keyword.strip()

    catalog = _load_stock_catalog()
    matches = []

    # 1. 精确匹配
    for item in catalog:
        if kw == item["symbol"] or kw == item["name"]:
            matches.append(item)
            break

    # 2. 模糊匹配
    for item in catalog:
        if len(matches) >= limit:
            break
        if item in matches:
            continue
        if kw.lower() in item["symbol"].lower() or kw in item["name"]:
            matches.append(item)

    # 3. 若匹配结果少于限制，批量获取实时最新价格丰富表格
    results = []
    matched_symbols = [m["symbol"] for m in matches[:limit]]

    quotes_map = {}
    if matched_symbols:
        try:
            df_quotes = ts.get_realtime_quotes(matched_symbols)
            if df_quotes is not None and not df_quotes.empty:
                for _, q in df_quotes.iterrows():
                    quotes_map[str(q.get("code", ""))] = q
        except Exception as e:
            logger.warning(f"批量查询搜索股票行情失败: {e}")

    for m in matches[:limit]:
        sym = m["symbol"]
        q = quotes_map.get(sym)
        price = float(q["price"]) if q is not None and q.get("price") else None
        prev_close = float(q["pre_close"]) if q is not None and q.get("pre_close") else None
        change_pct = (
            round(((price - prev_close) / prev_close) * 100, 2)
            if (price and prev_close and prev_close > 0)
            else None
        )

        results.append({
            "symbol": sym,
            "ts_code": m.get("ts_code", to_ts_code(sym)),
            "name": m.get("name", ""),
            "industry": m.get("industry", "-"),
            "area": m.get("area", "-"),
            "price": price,
            "change_percent": change_pct,
        })

    # 生成 Markdown 搜索结果表格
    lines = [
        f"### 🔍 股票搜索结果：`{keyword}` (共找到 {len(results)} 条记录)",
        "",
        "| 股票代码 | 股票名称 | 最新股价 | 涨跌幅 | 所属行业 | 所在省市 |",
        "|:---|:---|:---|:---|:---|:---|",
    ]

    for r in results:
        price_str = f"{r['price']:.2f} 元" if r["price"] else "-"
        chg_str = format_change(r["change_percent"])
        lines.append(
            f"| `{r['symbol']}` | **{r['name']}** | {price_str} | {chg_str} | {r['industry']} | {r['area']} |"
        )

    lines.extend([
        "",
        "> 💡 *提示：点击股票代码可进一步调用 `get_stock_quote` 获取盘口详情。*",
    ])

    return {
        "keyword": keyword,
        "count": len(results),
        "results": results,
        "markdown": "\n".join(lines),
    }


def get_stock_info(symbol: str) -> Dict[str, Any]:
    """查询指定 A 股个股的公司资料、高管人员、主营业务、行业及市值估值信息。

    参数:
        symbol: 股票代码（例如 '600519' 或 '600519.SH'）
    """
    pro = get_pro_api()
    norm = normalize_symbol(symbol)
    ts_code = to_ts_code(symbol, is_index=False)
    name = COMMON_A_STOCKS.get(norm, norm)

    info_data: Dict[str, Any] = {
        "symbol": norm,
        "ts_code": ts_code,
        "name": name,
    }

    # 1. 尝试获取实时行情以补充市值与 PE/PB
    tencent_data = _get_tencent_realtime_quote(norm)
    if tencent_data:
        info_data.update({
            "name": tencent_data.get("name", name),
            "latest_price": tencent_data.get("latest_price"),
            "turnover_rate": tencent_data.get("turnover_rate"),
            "pe_ratio": tencent_data.get("pe_ratio"),
            "pb_ratio": tencent_data.get("pb_ratio"),
            "total_mv": tencent_data.get("total_mv"),
            "circ_mv": tencent_data.get("circ_mv"),
        })

    # 2. 查询 TuShare Pro 公司资料
    company_cached = _load_company_cache(ts_code)
    if company_cached:
        info_data.update(company_cached)

    if pro is not None:
        try:
            df_comp = pro.stock_company(ts_code=ts_code)
            if df_comp is not None and not df_comp.empty:
                c = df_comp.iloc[0].to_dict()
                comp_fields = {
                    "com_name": c.get("com_name"),
                    "chairman": c.get("chairman"),
                    "manager": c.get("manager"),
                    "secretary": c.get("secretary"),
                    "reg_capital": c.get("reg_capital"),
                    "setup_date": c.get("setup_date"),
                    "province": c.get("province"),
                    "city": c.get("city"),
                    "website": c.get("website"),
                    "employees": c.get("employees"),
                    "main_business": c.get("main_business"),
                    "introduction": c.get("introduction"),
                }
                info_data.update(comp_fields)
                _save_company_cache(ts_code, comp_fields)
        except Exception as e:
            logger.warning(f"TuShare Pro stock_company 失败 ({ts_code}): {e}")

        try:
            df_basic = pro.stock_basic(ts_code=ts_code)
            if df_basic is not None and not df_basic.empty:
                b = df_basic.iloc[0].to_dict()
                basic_fields = {
                    "name": b.get("name", info_data.get("name")),
                    "industry": b.get("industry", info_data.get("industry", "-")),
                    "area": b.get("area", info_data.get("area", "-")),
                    "list_date": b.get("list_date"),
                }
                info_data.update(basic_fields)
                _save_company_cache(ts_code, basic_fields)
        except Exception as e:
            logger.warning(f"TuShare Pro stock_basic 失败 ({ts_code}): {e}")

    info_data["markdown"] = render_company_info_markdown(info_data)
    return info_data


def get_trade_calendar(start_date: str = "", end_date: str = "") -> Dict[str, Any]:
    """查询 A 股交易日历与休市安排。

    参数:
        start_date: 开始日期（格式 'YYYYMMDD'），默认今天
        end_date: 结束日期（格式 'YYYYMMDD'），默认 14 天后
    """
    pro = get_pro_api()
    today = datetime.date.today()

    if not start_date:
        start_date = today.strftime("%Y%m%d")
    else:
        start_date = start_date.replace("-", "").replace("/", "")

    if not end_date:
        end_date = (today + datetime.timedelta(days=14)).strftime("%Y%m%d")
    else:
        end_date = end_date.replace("-", "").replace("/", "")

    records = []
    if pro is not None:
        try:
            df = pro.trade_cal(exchange="SSE", start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                for _, r in df.iterrows():
                    records.append({
                        "cal_date": str(r.get("cal_date", "")),
                        "is_open": int(r.get("is_open", 0)),
                    })
        except Exception as e:
            logger.warning(f"TuShare Pro trade_cal 失败: {e}")

    # 若未从 Pro 接口获取到（如频次超限），通过常规工作日规则生成日历
    if not records:
        curr = datetime.datetime.strptime(start_date, "%Y%m%d").date()
        end_dt = datetime.datetime.strptime(end_date, "%Y%m%d").date()
        while curr <= end_dt:
            is_open = 1 if curr.weekday() < 5 else 0
            records.append({
                "cal_date": curr.strftime("%Y%m%d"),
                "is_open": is_open,
            })
            curr += datetime.timedelta(days=1)

    markdown = render_trade_cal_markdown(records)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "count": len(records),
        "records": records,
        "markdown": markdown,
    }


def _load_stock_catalog() -> List[Dict[str, str]]:
    """加载股票目录（包含本地持久化缓存与常用股票列表）。"""
    global _STOCK_CATALOG_CACHE, _STOCK_CATALOG_CACHE_TIME

    if _STOCK_CATALOG_CACHE and (time.time() - _STOCK_CATALOG_CACHE_TIME < 86400):
        return _STOCK_CATALOG_CACHE

    cache_file = _CACHE_DIR / "stock_catalog.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                _STOCK_CATALOG_CACHE = json.load(f)
                _STOCK_CATALOG_CACHE_TIME = time.time()
                return _STOCK_CATALOG_CACHE
        except Exception as e:
            logger.warning(f"读取本地股票目录缓存失败: {e}")

    # 尝试从 TuShare Pro 加载全部 A 股股票清单
    pro = get_pro_api()
    if pro is not None:
        try:
            df = pro.stock_basic(
                exchange="",
                list_status="L",
                fields="ts_code,symbol,name,area,industry,market,list_date",
            )
            if df is not None and not df.empty:
                catalog = []
                for _, r in df.iterrows():
                    catalog.append({
                        "symbol": str(r.get("symbol", "")),
                        "ts_code": str(r.get("ts_code", "")),
                        "name": str(r.get("name", "")),
                        "area": str(r.get("area", "")),
                        "industry": str(r.get("industry", "")),
                        "market": str(r.get("market", "")),
                    })
                _STOCK_CATALOG_CACHE = catalog
                _STOCK_CATALOG_CACHE_TIME = time.time()
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(catalog, f, ensure_ascii=False)
                except Exception:
                    pass
                return catalog
        except Exception as e:
            logger.warning(f"TuShare Pro 加载 stock_basic 失败: {e}")

    # 使用内置常用股票字典构建基础目录
    base_catalog = []
    for name, sym in COMMON_A_STOCKS.items():
        base_catalog.append({
            "symbol": sym,
            "ts_code": to_ts_code(sym),
            "name": name,
            "area": "中国",
            "industry": "A股核心标的",
            "market": "主板/创业板/科创板",
        })

    _STOCK_CATALOG_CACHE = base_catalog
    _STOCK_CATALOG_CACHE_TIME = time.time()
    return base_catalog
