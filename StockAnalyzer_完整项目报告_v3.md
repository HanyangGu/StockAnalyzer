# StockAnalyzer — 完整项目报告

**版本：** v0.6（DataBundle 架构）
**报告日期：** 2026-04-11
**技术栈：** Python · Streamlit · OpenAI GPT · yfinance
**部署：** Streamlit Community Cloud

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [文件架构](#3-文件架构)
4. [数据流（v0.6 DataBundle）](#4-数据流)
5. [维度详解](#5-维度详解)
   - 5.1 技术面（Technical）
   - 5.2 基本面（Fundamental）
   - 5.3 情绪面（Sentiment）
   - 5.4 宏观面（Macro）
   - 5.5 事件驱动（Event-Driven）
6. [权重配置完整表](#6-权重配置完整表)
7. [Composite 综合决策逻辑](#7-composite-综合决策逻辑)
8. [风险矩阵](#8-风险矩阵)
9. [未来计划](#9-未来计划)

---

## 1. 项目概述

StockAnalyzer 是一个基于量化模型的股票分析工具，通过对话界面让用户输入任何股票，系统自动从多个维度进行评分，最终输出一个 0-100 的综合分数和投资决策建议。

**核心设计哲学：**
- 将"确定性量化指标"（价格、财务数据）与"模糊定性信号"（新闻情绪、分析师评级）通过 LLM 标准化对齐
- 数据层（analyzer）与评分层（scorer）严格分离，方便未来换数据源
- 所有权重集中在 `core/weights.py`，不分散在各模块
- **v0.6 新增：** 所有 yfinance 数据在分析开始时一次性拉取（DataBundle），彻底解决 rate limit 问题

**目前支持功能：**
- 单股完整分析（Technical + Fundamental + Sentiment + Macro + Event）
- 实时价格查询
- 历史回测模式（分析指定日期的股票状态）
- 数据来源：全部 yfinance，无需额外 API Key

---

## 2. 系统架构

```
用户对话输入
      │
      ▼
engine/ai.py（GPT tool router + StockChatbot）
      │
      ├──► fetch_price_data      → core/data.py（独立实时价格查询）
      │
      └──► technical_analysis    → scoring/orchestrator.py
                │
                ├── Step 1: resolve_ticker()
                │
                ├── Step 2: fetch_raw_bundle()  ← v0.6 核心改动
                │           一次性拉取所有数据
                │           ~4-8 个 HTTP 请求
                │
                ├── analyzers/（数据层，从 bundle 解析）
                │     ├── technical.py          9个技术指标（从 bundle.history）
                │     ├── fundamental.py        基本面（从 bundle.info）
                │     ├── macro.py              宏观数据（yf.download 批量）
                │     ├── event_driven.py       财报（从 bundle.calendar）
                │     └── sentiment/
                │           ├── analyst.py      评级（从 bundle.upgrades_downgrades）
                │           ├── insider.py      内幕交易（从 bundle.insider_transactions）
                │           ├── options.py      期权（从 bundle.option_chain）
                │           └── news.py         新闻（bundle.news + Search）
                │
                ├── scoring/（评分层，逻辑不变）
                │     ├── technical_scorer.py
                │     ├── fundamental_scorer.py
                │     ├── macro_scorer.py
                │     ├── event_scorer.py
                │     ├── sentiment_scorer.py
                │     ├── composite.py
                │     └── sentiment/
                │           ├── analyst_scorer.py
                │           ├── insider_scorer.py
                │           ├── options_scorer.py
                │           └── news_scorer.py
                │
                └── ui/（展示层）
                      ├── views.py
                      ├── components.py
                      └── dropdowns.py
```

**LLM 调用位置（仅3处）：**
1. `news_scorer.py` — 对每篇新闻进行8维度分析
2. `analyst_scorer.py` — 分类分析师机构权威等级（top/major/general）
3. `insider_scorer.py` — 10b5-1计划交易检测 + 信号质量判断

---

## 3. 文件架构

```
StockAnalyzer/
│
├── app.py                          # Streamlit 入口
├── requirements.txt
│
├── core/
│   ├── config.py                   # 技术指标参数常量
│   ├── data.py                     # ★ v0.6 新增 fetch_raw_bundle()
│   ├── utils.py                    # 工具函数
│   └── weights.py                  # 所有权重集中配置
│
├── analyzers/                      # 数据层（v0.6: 从 bundle 读取）
│   ├── technical.py                # 9个技术指标（从 bundle.history）
│   ├── fundamental.py              # 基本面（从 bundle.info）
│   ├── macro.py                    # 宏观数据（yf.download 批量下载）
│   ├── event_driven.py             # 财报（从 bundle.calendar/earnings_dates）
│   └── sentiment/
│       ├── analyst.py              # 评级（从 bundle.upgrades_downgrades）
│       ├── insider.py              # ★ v0.6 新增过滤逻辑
│       ├── news.py                 # 新闻（bundle.news + yf.Search）
│       └── options.py              # 期权（从 bundle.option_chain）
│
├── scoring/                        # 评分层（逻辑不变）
│   ├── orchestrator.py             # ★ v0.6 重构为 DataBundle 架构
│   ├── technical_scorer.py
│   ├── fundamental_scorer.py
│   ├── macro_scorer.py
│   ├── event_scorer.py
│   ├── sentiment_scorer.py
│   ├── composite.py
│   └── sentiment/
│       ├── analyst_scorer.py
│       ├── insider_scorer.py
│       ├── news_scorer.py
│       └── options_scorer.py
│
├── engine/
│   ├── ai.py                       # GPT tool 定义（compare 已禁用）
│   ├── llm.py                      # 统一 LLM 入口
│   └── comparison.py               # 多股对比（已禁用，待 token 优化）
│
└── ui/
    ├── components.py               # 分数卡片 + 决策面板
    ├── dropdowns.py                # 各维度折叠详情
    └── views.py                    # 完整页面视图
```

---

## 4. 数据流

### v0.6 DataBundle 架构（核心改动）

```
用户：「分析 NVDA」
         │
         ▼
Step 1: resolve_ticker()      NVDA → 验证 ticker 有效性

Step 2: fetch_raw_bundle()    ← 核心改动
         │
         ├── yf.Ticker("NVDA") 创建单一对象
         ├── .info                    → 价格 + 基本面 + 元数据
         ├── .history(1y)             → OHLCV 日线数据
         ├── .history(1d, 1m)         → 盘中数据（仅实时模式）
         ├── .upgrades_downgrades     → 分析师评级历史
         ├── .recommendations_summary → 评级分布
         ├── .analyst_price_targets   → 目标价
         ├── .insider_transactions    → 内幕交易记录
         ├── .options + .option_chain → 期权链
         ├── .news                    → 新闻
         ├── .calendar                → 下次财报
         └── .earnings_dates          → 历史财报

Macro（独立批量）:
         yf.download("^VIX ^TNX ^IRX ^GSPC")   ← 4个ticker 1次请求

Step 3-9: 所有 analyzer 从 bundle dict 读取
          零额外 HTTP 请求

Step 10: Composite → UI 渲染
```

**HTTP 请求对比：**

| 版本 | 请求数 | 说明 |
|------|--------|------|
| v0.1-v0.5 | 18-20次 | 每个 analyzer 独立调用 yfinance |
| **v0.6** | **~4-8次** | 一次 bundle + 批量 macro + news Search |

**唯一保留的独立请求：**
- `yf.Search()` — 新闻搜索，无法在 bundle 里预取（2次，ticker + company name）
- `yf.download()` — Macro 4个独立 ticker 批量下载（1次）

---

## 5. 维度详解

---

### 5.1 技术面（Technical）

**综合权重：43%**
**数据来源：** `bundle.history`（1年日线 OHLCV）

技术面按三个时间周期独立评分，再加权合并：

| 时间周期 | 权重 | 含义 |
|---------|------|------|
| Short-term | 30% | 未来1-4周的价格动能 |
| Mid-term   | 35% | 未来1-3个月的趋势 |
| Long-term  | 35% | 未来半年以上的结构 |

#### Short-term（max 80pts → 归一化0-100）

| 指标 | 参数 | 满分 | 逻辑 |
|------|------|------|------|
| RSI | 14日 | 25pts | <30超卖=25分，>70超买=5分 |
| Stochastic | 14日 | 20pts | <20超卖=20分，>80超买=4分 |
| ROC | 10日 | 20pts | >5%强动能=20分，<-5%=0分 |
| Bollinger Bands | 20日±2σ | 15pts | 近下轨=15分，近上轨=3分 |
| **BB Width Squeeze** | 20日rolling | 附加信号 | width_ratio<0.75触发⚡（爆发前兆），>1.25触发扩张警告 |
| Downtrend惩罚 | MA结构 | -0至-30pts | 价格跌破全部MA=-30pts |

**BB Width 计算：** `width_ratio = 当前band宽度 / 20日均值带宽`
- <0.75 = 收缩（Squeeze），市场蓄力，方向性突破临近 ⚡
- >1.25 = 扩张，波动率已经很高 ⚠️

#### Mid-term（max 80pts → 归一化0-100）

| 指标 | 参数 | 满分 | 说明 |
|------|------|------|------|
| MACD | 12/26/9 EMA | 25pts | 多头交叉=25分，空头=0分 |
| MA20 | 20日均线 | 15pts | 价格在上=15分 |
| MA50 | 50日均线 | 25pts | 价格在上=25分 |
| Volume | 5日/年均量 | 15pts | 缩量上涨=5分（弱势），放量=15分 |
| **ATR** | 14日 | **纯信息** | **已移出评分**，仅展示标注"(informational)" |
| Downtrend惩罚 | MA结构 | -0至-30pts | 同上 |

**ATR 移出说明：** 波动率不是方向信号，高Beta股（如NVDA Beta=2.33）会被系统性错误惩罚。ATR风险已由Risk Matrix的Volatility条目承担。

#### Long-term（max 90pts → 归一化0-100）

| 指标 | 参数 | 满分 | 说明 |
|------|------|------|------|
| MA200 | 200日均线 | 35pts | 价格在上=35分，在下=0分 |
| Golden/Death Cross | MA50 vs MA200 | 40pts | 新鲜金叉=40分，金叉已激活=28分 |
| **MA Slope** | MA50-MA200距离% | 15pts | **替代原Volume** |
| Downtrend惩罚 | MA结构 | -0至-30pts | 同上 |

**MA Slope 计算：** `gap_pct = (MA50 - MA200) / MA200 × 100`
- >10% = 强劲趋势（15分）
- 3-10% = 健康趋势（10分）
- 0-3% = 弱趋势（5分）
- <0% = MA50在MA200下方（0分）

**替代Volume原因：** 原长期评分用5日成交量均值，与中期完全重复（双重计分）。MA距离百分比才是衡量长期趋势质量的有效指标。

---

### 5.2 基本面（Fundamental）

**综合权重：27%**
**数据来源：** `bundle.info`（`ticker.info` dict）

四象限各25分，合计100分：

#### 估值（Valuation，max 25pts）

| 指标 | 满分 | 阈值 |
|------|------|------|
| Trailing P/E | 15pts | <15=15分，15-25=12分，25-40=7分，>40=2分 |
| Forward P/E | 10pts | <15=10分，15-25=7分，25-40=3分，>40=0分，<0=0分 |

#### 盈利能力（Profitability，max 25pts）

| 指标 | 满分 | 阈值 |
|------|------|------|
| Net Margin | 13pts | >20%=13分，10-20%=10分，0-10%=5分，<0=0分 |
| ROE | 12pts | >20%=12分，10-20%=8分，0-10%=3分，<0=0分 |

#### 成长性（Growth，max 25pts）

| 指标 | 满分 | 阈值 |
|------|------|------|
| Revenue Growth（YoY） | 13pts | >20%=13分，10-20%=10分，0-10%=5分，<0=0分 |
| Earnings Growth | 12pts | >20%=12分；收入负增长时盈利最多给3分 |

#### 财务健康（Health，max 25pts）

| 指标 | 满分 | 阈值 |
|------|------|------|
| Debt/Equity | 13pts | <50=13分，50-100=9分，100-200=4分，>200=0分 |
| Current Ratio | 12pts | >2=12分，1.5-2=9分，1-1.5=5分，<1=0分 |

#### 叙事信号（不计分，仅展示）

- **PEG Ratio**：P/E ÷ Earnings Growth（仅当两者为正时显示）
- **Beta**：相对市场波动性
- **52周位置**：当前价在年度区间的百分位
- **分析师目标价 Upside%**

---

### 5.3 情绪面（Sentiment）

**综合权重：20%**

情绪面由四个子维度加权合并：

| 子维度 | 权重 | 数据来源 |
|--------|------|---------|
| 新闻（News） | 55% | `bundle.news` + `yf.Search()` |
| 分析师（Analyst） | 22% | `bundle.upgrades_downgrades` + `bundle.recommendations_summary` + `bundle.analyst_price_targets` |
| 内幕交易（Insider） | 13% | `bundle.insider_transactions`（过滤后） |
| 期权（Options） | 10% | `bundle.option_chain`（选定到期日） |

---

#### 5.3.1 新闻情绪（News）

**数据策略：**
- `bundle.news` → 最多15篇通用新闻（从 bundle 读取，0额外请求）
- `yf.Search(ticker)` + `yf.Search(company_name)` → 最多10篇特定新闻（2次独立请求）
- 去重合并后最多20篇送 GPT 分析

**GPT 8维度分析（每篇文章）：**

| 维度 | 选项 | 权重乘数 |
|------|------|---------|
| Relevance | direct/indirect/unrelated | 1.0 / 0.4 / 0.0 |
| Sentiment | positive/neutral/negative | +1 / 0 / -1 |
| Intensity | strong/moderate/mild | 1.0 / 0.6 / 0.3 |
| Impact | major/normal/minor | 2.0 / 1.0 / 0.5 |
| Scope | company/industry/macro | 1.5 / 1.0 / 0.6 |
| Credibility | high/medium/low | 1.5 / 1.0 / 0.5 |
| Novelty | first/followup/repeat | 1.5 / 0.7 / 0.3 |
| Surprise | unexpected/partial/expected | 1.5 / 1.0 / 0.5 |

**时间衰减：** 3日内=1.0，7日内=0.8，14日内=0.6，30日内=0.4，30日+=0.2（重大事件最低0.5）

**跨文章共识：** ≥4篇相关文章同向占75%以上 → ×1.2；分散 → ×0.8

---

#### 5.3.2 分析师（Analyst）

**数据来源：** `bundle.upgrades_downgrades`（历史评级）/ `bundle.recommendations_summary`（分布）/ `bundle.analyst_price_targets`

**时间窗口：** 优先6个月内评级，不足3条时扩展到12个月

**评分组成（0-100，含共识乘数）：**

| 组成 | 满分 | 计算方式 |
|------|------|---------|
| 评级分布 | 30pts | Strong Buy×2 + Buy×1 - Sell×1 - Strong Sell×2 |
| 加权评级 | 20pts | 评级 × 机构权威（top=2.0 / major=1.2 / general=0.7）× 时间衰减 |
| 评级动量 | 20pts | 90天内升级 vs 降级数量差 |
| 目标价 Upside | 20pts | >30%=20分，>20%=16分，>10%=10分 |
| 目标价分散度 | 10pts | <15%=10分，>60%=0分 |
| 共识乘数 | ×0.85~1.15 | 看多≥70% × 1.15 |

**机构权威（GPT 分类）：**
- `top` (×2.0)：Goldman Sachs、Morgan Stanley、JPMorgan 等
- `major` (×1.2)：Deutsche Bank、Barclays、UBS 等
- `general` (×0.7)：其他研究机构

**时间衰减（月）：** 1月=1.0，3月=0.8，6月=0.6，12月=0.3

**Risk Matrix 拆分（v0.5 新增）：**
- `Analyst Direction`：方向共识（看多%）独立条目
- `Analyst Target Dispersion`：目标价分散度独立条目，注明"反映时间框架差异"

---

#### 5.3.3 内幕交易（Insider）

**数据来源：** `bundle.insider_transactions`
**时间窗口：** 优先6个月，不足3条时扩展到12个月

**v0.6 新增：交易过滤逻辑（发送给 GPT 前）**

| 职位类别 | 过滤条件 | 原因 |
|---------|---------|------|
| CEO / CFO / COO / President / Chairman / Director | **全部保留** | 高管交易无论金额大小都有信号价值 |
| VP / Officer / Other | 仅保留金额 **> $50,000** | 低级员工小额例行卖出是噪音 |
| 上限 | 最多 **20条** | 防止 GPT token 超限（CTSH 71条 → ~12条高信号） |

**双字段输出：**
- `transactions` — GPT 分析的高信号子集（scorer 用这个）
- `all_transactions` — 完整交易列表（UI 表格显示这个）

**评分组成（0-100）：**

| 组成 | 满分 | 计算方式 |
|------|------|---------|
| 净买卖比率 | 30pts | (买入-卖出)/总额，10b5-1 ×0.3降权 |
| 买卖方人数 | 25pts | 纯买方占比（10b5-1卖方排除） |
| 最大单笔购买 | 20pts | >$10M=20分，>$5M=16分，>$1M=12分... |
| 最高级别买方 | 15pts | CEO=2.0×，CFO=1.8×，COO=1.6×... |
| **集群效应** | **+15pts** | 2名以上高管7天内同时买入 |
| 基础分 | 10pts | 固定底线 |

**10b5-1 豁免（v0.5 核心修复）：** 当≥80%销售为计划性交易且无主动买入者时，直接返回 score=50（Neutral），Risk Matrix 从 HIGH 降为 LOW。

**职位权重：**
CEO=2.0 / CFO=1.8 / COO=1.6 / President=1.6 / Chairman=1.5 / Director=1.0 / VP=0.9 / Officer=0.8 / Other=0.6

---

#### 5.3.4 期权（Options）

**数据来源：** `bundle.option_chain`（在 bundle 阶段已选好到期日）

**到期日选择策略：** 优先选择距今20-90天的最近到期日，无则取最近可用

**评分组成（0-60原始分 → IV乘数后归一化0-100）：**

| 组成 | 满分 | 阈值 |
|------|------|------|
| PCR Volume（看跌/看涨成交量比） | 35pts | <0.40=35分，>1.40=2分 |
| PCR OI（看跌/看涨持仓量比） | 25pts | <0.50=25分，>1.30=0分 |
| IV 置信度乘数 | ×0.70~1.00 | IV>60% → ×0.70，IV<35% → ×1.00 |

**基准PCR：** 0.7（历史均值）

**纯展示信号（不计入评分）：**
- Max Pain：期权卖方损失最小价格，有价格引力效应
- Call Wall / Put Wall：最大OI行权价（阻力/支撑）

---

### 5.4 宏观面（Macro）

**综合权重：10%**
**数据来源：** `yf.download("^VIX ^TNX ^IRX ^GSPC")`（v0.6：4个ticker合为1次批量请求）

**v0.6 改动：** 原来4次独立 `yf.Ticker().history()` 调用改为 1次 `yf.download()` 批量下载，有自动 fallback。

#### 步骤一：环境评分（max 100pts）

| 子维度 | 满分 | 数据 | 逻辑 |
|--------|------|------|------|
| VIX（恐慌指数） | 35pts | ^VIX | <15=35分，15-20=28分，20-25=20分，25-30=12分，>35=0分 |
| 收益率曲线 + 利率趋势 | 35pts | ^TNX - ^IRX | 正常(>0.5pp)=35分，平坦=18分，倒挂=8分 |
| 市场风险偏好 | 30pts | ^GSPC 30日涨跌 | +3%以上=30分，-3-7%=3分，<-7%=0分 |

**快速惩罚：** VIX 30日上涨>40% → -8pts；10Y利率30日上升>0.4pp → -8pts；10Y下降>0.4pp → +5pts

#### 步骤二：个股敏感性

```
Adjusted Score = 50 + (Env Score - 50) × Sensitivity Multiplier
Sensitivity   = Beta敏感性 × 0.55 + 行业敏感性 × 0.35 + 基础1.0 × 0.10
```

| Beta范围 | Beta敏感性 |
|---------|-----------|
| ≥2.50 | 1.40 |
| ≥2.00 | 1.25 |
| ≥1.50 | 1.10 |
| ≥1.00 | 1.00 |
| ≥0.60 | 0.85 |
| <0.60  | 0.70 |

---

### 5.5 事件驱动（Event-Driven）

**设计：不是评分维度，是可靠性系数**
**数据来源：** `bundle.calendar`（下次财报）+ `bundle.earnings_dates`（历史财报）

| 时间窗口 | 可靠性 |
|---------|--------|
| 财报后0-1天 | 50% |
| 财报前1-3天 | 65% |
| 财报前4-7天 | 80% |
| 财报前8-14天 | 90% |
| 财报后2-5天 | 85% |
| 正常期 | 100% |

---

## 6. 权重配置完整表

### 主维度权重

| 维度 | 当前权重 | 历史 | 3D Fallback |
|------|---------|------|-------------|
| Technical | 43% | 47%（v0.1-v0.4） | 48% |
| Fundamental | 27% | 27% | 32% |
| Sentiment | 20% | 21% | 20% |
| Macro | 10% | 5%（v0.4）| 不参与 |

### 开发者预设（不对用户开放）

| 模式 | Tech | Fund | Sent | Macro |
|------|------|------|------|-------|
| 默认 | 43% | 27% | 20% | 10% |
| 长期投资 | 25% | 40% | 20% | 15% |
| 波段交易 | 40% | 25% | 25% | 10% |

### 决策象限阈值

| 维度 | 阈值 |
|------|------|
| Technical | >50 |
| Fundamental | >55 |
| Sentiment | >60 |
| Macro | >50 |

### 情绪子维度权重

| 子维度 | 权重 |
|--------|------|
| 新闻 | 55% |
| 分析师 | 22% |
| 内幕交易 | 13% |
| 期权 | 10% |

### 技术面各周期权重与指标分值

**周期权重：** Short 30% / Mid 35% / Long 35%

**Short-term（max 80pts）：** RSI 25 + Stoch 20 + ROC 20 + BB 15

**Mid-term（max 80pts）：** MACD 25 + MA20 15 + MA50 25 + Volume 15 + ATR（仅展示）

**Long-term（max 90pts）：** MA200 35 + Golden Cross 40 + MA Slope 15

### 宏观子维度权重

VIX 35pts + 收益率曲线/利率趋势 35pts + 市场风险偏好 30pts

### 宏观敏感性权重

Beta敏感性 55% + 行业敏感性 35% + 固定基础 10%

---

## 7. Composite 综合决策逻辑

```
Composite = Technical×43% + Fundamental×27% + Sentiment×20% + Macro×10%
```

### 决策象限

| 条件 | 象限 |
|------|------|
| Tech高 + Fund高 + Sent高/无 + Macro高 + short_term≥40 | **Strong Buy** |
| Tech高 + Fund高 + Sent高/无 + Macro高 + **short_term<40** | **Cautious Buy** |
| Tech高 + Fund高 + Sent低 + Macro高 | Cautious Buy |
| Tech高 + Fund高 + Macro低 | Macro Headwind |
| Tech高 + Fund低 | Trader Play |
| Tech低 + Fund高 + Sent高 | Value Opportunity |
| Tech低 + Fund高 + Sent低 | Value Watch |
| 其他 | Avoid |
| 仅技术数据 | Technical Only |

**短期时机覆盖（v0.5b）：** 当所有维度满足 Strong Buy 但 `short_term < 40` 时，标题降为 Cautious Buy，行动建议改为"等待回调后入场"。

---

## 8. 风险矩阵

自动生成，基于现有数据，无需新数据源。

| 条目 | 触发 HIGH 条件 |
|------|--------------|
| Technical Momentum | <35分 |
| Valuation | P/E>50 或 Forward P/E>40 |
| Financial Health | D/E>200 或 FCF<0 |
| Sentiment Divergence | Tech vs Sent 差值>35pts |
| **Insider Activity** | score≤25 且非10b5-1计划（v0.5修复） |
| Volatility | Beta>2.0 |
| **Analyst Direction** | 看多<40%（v0.5 从 Analyst Consensus 拆分） |
| **Analyst Target Dispersion** | 分散度>60%（降为MEDIUM，注明时间框架差异） |
| Macro Environment | <30分 |
| Event Risk | PRE/POST_IMMINENT |

---

## 9. 未来计划

### 近期待办

**已规划，技术可行：**

| 功能 | 状态 | 说明 |
|------|------|------|
| Backtesting 完善 | **下一步** | 批量回测、准确率统计、时间窗口验证 |
| 权重测试与修正 | 依赖 Backtesting | 基于历史数据数据驱动调整权重 |
| Insider 分批GPT | 待做 | 超过20条时分批发送，合并结果 |
| Options Max Pain 纳入评分 | 待做 | 价格距Max Pain>5%时贡献0-10分 |
| LLM Confidence Score | 待做 | GPT自判新闻质量低时自动降权 |
| Debt/Equity 行业感知 | 待做 | 金融/REIT行业使用不同D/E阈值 |

**需接入新数据源：**

| 功能 | 候选数据源 |
|------|-----------|
| 行业实时对标（NVDA vs AMD/TSMC） | 多股同时拉取 |
| 13F 机构持仓变化 | SEC EDGAR API（免费） |
| 期权大单流向 | Unusual Whales / Tradier |
| Short Interest | FINRA / iborrowdesk |
| 逐季 QoQ 财务分析 | yfinance quarterly_financials |
| Macro 四因子重构 | 现有数据重组 |

### 中期规划

- **股票对比恢复：** Token 优化（批量GPT + 缓存）后重新开放
- **Streamlit 缓存：** Macro/Fundamental 数据按变化频率分级缓存

### 长期愿景

- **多 Agent 并行：** 各维度分析器独立 Agent，大幅缩短分析时间
- **Monte Carlo 情景：** 基于历史波动率生成未来价格路径分布
- **用户权重画像：** 保守/平衡/激进自动切换权重预设

---

## 附录：版本历史

| 版本 | 主要改动 |
|------|---------|
| v0.1-v0.4 | 基础架构建立，4维度评分，初始权重 |
| v0.5 | Macro权重5%→10%；Insider 10b5-1修复；Analyst Direction/Dispersion拆分；Decision动态文字；Sector Benchmarks；数据时间戳 |
| v0.5b | BB Width Squeeze信号；ATR移出评分→MA Slope替代Volume；Insider集群效应；Cautious Buy覆盖；composite.py `short_term`参数；`_md_safe()` Markdown修复 |
| **v0.6** | **DataBundle 架构**：18-20次HTTP请求→~4-8次；Macro yf.download批量；Insider高信号过滤（高管优先+$50k阈值，上限20条）；`all_transactions`双字段；USD nan→N/A修复 |

---

*报告基于 v0.6 版本（final_upload 目录），所有权重数据均从 `core/weights.py` 直接提取，所有评分逻辑均从对应 scorer 文件提取，确保与代码完全同步。*
