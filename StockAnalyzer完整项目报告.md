# StockAnalyzer — 完整项目报告

**版本：** 0.5
**报告日期：** 2026-04-11
**技术栈：** Python · Streamlit · OpenAI GPT · yfinance
**部署：** Streamlit Community Cloud

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [文件架构](#3-文件架构)
4. [数据流](#4-数据流)
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
      ├──► fetch_price_data      → core/data.py（实时价格）
      │
      ├──► technical_analysis    → scoring/orchestrator.py（主分析流程）
      │         │
      │         ├── analyzers/（数据层，各维度独立）
      │         │     ├── technical.py          9个技术指标
      │         │     ├── fundamental.py        基本面数据
      │         │     ├── macro.py              宏观数据
      │         │     ├── event_driven.py       财报事件数据
      │         │     └── sentiment/
      │         │           ├── analyst.py      分析师评级
      │         │           ├── insider.py      内幕交易
      │         │           ├── options.py      期权链
      │         │           └── news.py         新闻文章
      │         │
      │         ├── scoring/（评分层，纯计算）
      │         │     ├── technical_scorer.py   三时间周期评分
      │         │     ├── fundamental_scorer.py 四象限评分
      │         │     ├── macro_scorer.py       宏观环境评分
      │         │     ├── event_scorer.py       可靠性系数
      │         │     ├── sentiment_scorer.py   聚合四子维度
      │         │     ├── sentiment/
      │         │     │     ├── analyst_scorer.py
      │         │     │     ├── insider_scorer.py
      │         │     │     ├── options_scorer.py
      │         │     │     └── news_scorer.py
      │         │     └── composite.py          最终决策
      │         │
      │         └── engine/llm.py（统一 LLM 入口，只在3处调用）
      │
      └── ui/（展示层）
            ├── views.py          完整页面视图
            ├── components.py     分数卡片、决策面板
            └── dropdowns.py      各维度折叠详情
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
├── app.py                          # Streamlit 入口（侧边栏 + 对话循环）
├── requirements.txt
│
├── core/
│   ├── config.py                   # 技术指标参数常量（RSI周期、MA长度等）
│   ├── data.py                     # yfinance 数据获取 + ticker解析
│   ├── utils.py                    # safe_get / safe_json_loads 工具函数
│   └── weights.py                  # ★ 所有权重集中配置（单一真相来源）
│
├── analyzers/                      # 数据层（只取数据，不评分）
│   ├── technical.py                # 9个技术指标计算
│   ├── fundamental.py              # 基本面数据获取
│   ├── macro.py                    # 宏观数据（VIX/国债/S&P500）
│   ├── event_driven.py             # 财报日历数据
│   └── sentiment/
│       ├── __init__.py
│       ├── analyst.py              # 分析师评级数据
│       ├── insider.py              # 内幕交易数据
│       ├── news.py                 # 新闻文章数据
│       └── options.py              # 期权链数据
│
├── scoring/                        # 评分层（只做计算，不取数据）
│   ├── orchestrator.py             # 主流程协调器
│   ├── technical_scorer.py         # 技术面评分（三时间周期）
│   ├── fundamental_scorer.py       # 基本面评分（四象限）
│   ├── macro_scorer.py             # 宏观评分 + 个股敏感性
│   ├── event_scorer.py             # 事件可靠性系数
│   ├── sentiment_scorer.py         # 情绪面聚合
│   ├── composite.py                # 综合评分 + 决策逻辑 + 风险矩阵
│   └── sentiment/
│       ├── __init__.py
│       ├── analyst_scorer.py       # 分析师评分引擎
│       ├── insider_scorer.py       # 内幕交易评分引擎
│       ├── news_scorer.py          # 新闻评分引擎
│       └── options_scorer.py       # 期权评分引擎
│
├── engine/
│   ├── ai.py                       # GPT tool 定义 + StockChatbot类
│   ├── llm.py                      # 统一 LLM 入口（换供应商只改这里）
│   └── comparison.py               # 多股对比（当前已禁用）
│
└── ui/
    ├── components.py               # 分数卡片 + 决策面板 + 事件横幅
    ├── dropdowns.py                # 各维度折叠详情展示
    └── views.py                    # 完整页面视图组合
```

---

## 4. 数据流

```
用户：「分析 NVDA」
         │
         ▼
1. Ticker解析         NVDA → yfinance验证
2. 实时价格           fetch_price_data() → $188.63
3. 历史OHLCV          1年日线数据（约252交易日）
         │
         ├── 4a. Technical    计算9个指标 → 3时间周期评分 → 综合技术分
         ├── 4b. Fundamental  取财务指标  → 四象限评分
         ├── 4c. Sentiment    ──┬── 新闻(GPT分析)
         │                     ├── 分析师(GPT分类机构权威度)
         │                     ├── 内幕交易(GPT检测10b5-1)
         │                     └── 期权(纯量化PCR/IV/Max Pain)
         ├── 4d. Macro        取VIX/10Y/3M/S&P500 → 环境评分 × 个股敏感性
         └── 4e. Event        取财报日历 → 可靠性系数（不改分数，只改可信度）
         │
         ▼
5. Composite          加权合并 → 0-100综合分 → 决策象限
         │
         ▼
6. GPT摘要            2-4句自然语言总结
         │
         ▼
7. UI渲染             4个分数卡 + 决策面板 + 5个折叠详情 + 风险矩阵
```

---

## 5. 维度详解

---

### 5.1 技术面（Technical）

**综合权重：43%**
**评分范围：0-100**
**数据来源：** yfinance 1年日线 OHLCV

技术面按三个时间周期独立评分，再加权合并：

| 时间周期 | 权重 | 含义 |
|---------|------|------|
| Short-term | 30% | 未来1-4周的价格动能 |
| Mid-term   | 35% | 未来1-3个月的趋势 |
| Long-term  | 35% | 未来半年以上的结构 |

#### Short-term（短期，max 80pts → 归一化0-100）

| 指标 | 参数 | 满分 | 逻辑 |
|------|------|------|------|
| RSI | 14日 | 25pts | <30超卖=25分，>70超买=5分，中性=12分 |
| Stochastic Oscillator | 14日 | 20pts | <20超卖=20分，>80超买=4分 |
| ROC（Rate of Change） | 10日 | 20pts | >5%强动能=20分，<-5%=0分 |
| Bollinger Bands | 20日±2σ | 15pts | 近下轨=15分（潜在反弹），近上轨=3分（潜在回调） |
| **BB Width（新增）** | 20日rolling | 附加信号 | width_ratio<0.75触发Squeeze警告⚡（爆发前兆），>1.25触发扩张警告 |
| Downtrend惩罚 | MA结构 | -0至-30pts | 价格跌破MA20+MA50+MA200=-30pts，跌破MA200=-20pts |

**BB Width 解释：** Bollinger Band宽度（上轨-下轨）与其20日均值之比。当波动率收缩至历史低位（<75%），市场正在积蓄能量，随后往往出现方向性突破——这是技术分析中著名的"Squeeze"信号。

#### Mid-term（中期，max 80pts → 归一化0-100）

| 指标 | 参数 | 满分 | 逻辑 |
|------|------|------|------|
| MACD | 12/26/9 EMA | 25pts | 多头交叉（histogram>0 且 MACD>signal）=25分，空头=0分 |
| MA20 | 20日均线 | 15pts | 价格在上=15分；在下但MA200上方=5分（临时回调） |
| MA50 | 50日均线 | 25pts | 价格在上=25分；在下但MA200上方=8分 |
| Volume（5日） | 5日均量/年均量 | 15pts | 缩量上涨=5分（弱势），放量上涨=15分，缩量=0分 |
| ATR | 14日 | 纯信息 | **已移出评分**，仅作参考展示。波动率≠方向信号，高Beta股会被系统性误判 |
| Downtrend惩罚 | MA结构 | -0至-30pts | 同Short-term |

#### Long-term（长期，max 90pts → 归一化0-100）

| 指标 | 参数 | 满分 | 逻辑 |
|------|------|------|------|
| MA200 | 200日均线 | 35pts | 价格在上=35分，在下=0分 |
| Golden/Death Cross | MA50 vs MA200 | 40pts | 新鲜金叉=40分，金叉已激活=28分，新鲜死叉=0分，死叉激活=5分 |
| MA Slope（新增，替代Volume） | MA50-MA200距离% | 15pts | MA50高于MA200超10%=15分（强势趋势），3-10%=10分，0-3%=5分，MA50在MA200下=0分 |
| Downtrend惩罚 | MA结构 | -0至-30pts | 同Short-term |

**MA Slope 替代 Volume 的原因：** 原长期评分使用5日成交量均值，与中期完全重复（双重计分）。MA50与MA200的距离百分比才是衡量长期趋势质量的有效指标——距离越大代表趋势越强、支撑越厚。

---

### 5.2 基本面（Fundamental）

**综合权重：27%**
**评分范围：0-100**
**数据来源：** yfinance `ticker.info`（TTM数据）

四象限各25分，合计100分：

#### 估值（Valuation，max 25pts）

| 指标 | 满分 | 逻辑 |
|------|------|------|
| Trailing P/E | 15pts | <15=15分（低估），15-25=12分，25-40=7分，>40=2分 |
| Forward P/E | 10pts | <15=10分（便宜），15-25=7分，25-40=3分，>40=0分，<0=0分（预期亏损） |

#### 盈利能力（Profitability，max 25pts）

| 指标 | 满分 | 逻辑 |
|------|------|------|
| Net Margin（净利润率） | 13pts | >20%=13分，10-20%=10分，0-10%=5分，<0=0分 |
| ROE（净资产收益率） | 12pts | >20%=12分，10-20%=8分，0-10%=3分，<0=0分 |

#### 成长性（Growth，max 25pts）

| 指标 | 满分 | 逻辑 |
|------|------|------|
| Revenue Growth（YoY） | 13pts | >20%=13分，10-20%=10分，0-10%=5分，<0=0分 |
| Earnings Growth | 12pts | >20%=12分；若收入负增长时盈利为正，最多给3分（一次性异常） |

#### 财务健康（Health，max 25pts）

| 指标 | 满分 | 逻辑 |
|------|------|------|
| Debt/Equity（负债股权比） | 13pts | <50=13分，50-100=9分，100-200=4分，>200=0分 |
| Current Ratio（流动比率） | 12pts | >2=12分，1.5-2=9分，1-1.5=5分，<1=0分（流动性风险） |

#### 叙事信号（Narrative，信息展示，不计分）

- **PEG Ratio**：P/E ÷ Earnings Growth。<1=成长被低估，1-2=合理，>2=相对成长偏贵
- **Beta**：相对市场波动性
- **52周位置**：当前价格在年度高低区间的百分比位置
- **分析师目标价 Upside%**：均值目标价相对当前价的上行空间

---

### 5.3 情绪面（Sentiment）

**综合权重：20%**
**评分范围：0-100**
**数据来源：** yfinance（原始数据）+ GPT（分析）

情绪面由四个子维度加权合并：

| 子维度 | 权重 | 数据来源 |
|--------|------|---------|
| 新闻（News） | 55% | yfinance 新闻 + GPT 8维分析 |
| 分析师（Analyst） | 22% | yfinance 评级记录 + GPT 机构分类 |
| 内幕交易（Insider） | 13% | yfinance 内幕交易记录 + GPT 10b5-1检测 |
| 期权（Options） | 10% | yfinance 期权链（纯量化） |

---

#### 5.3.1 新闻情绪（News Scorer）

**GPT对每篇文章进行8维度判断：**

| 维度 | 选项 | 权重乘数 |
|------|------|---------|
| Relevance（相关性） | direct/indirect/unrelated | 1.0 / 0.4 / 0.0 |
| Sentiment（情绪） | positive/neutral/negative | +1 / 0 / -1 |
| Intensity（强度） | strong/moderate/mild | 1.0 / 0.6 / 0.3 |
| Impact（影响力） | major/normal/minor | 2.0 / 1.0 / 0.5 |
| Scope（范围） | company/industry/macro | 1.5 / 1.0 / 0.6 |
| Credibility（可信度） | high/medium/low | 1.5 / 1.0 / 0.5 |
| Novelty（新颖度） | first/followup/repeat | 1.5 / 0.7 / 0.3 |
| Surprise（意外性） | unexpected/partial/expected | 1.5 / 1.0 / 0.5 |

**时间衰减：**
- 3日内：权重1.0
- 4-7日：0.8
- 8-14日：0.6
- 15-30日：0.4
- 30日+：0.2（重大事件最低0.5）

**跨文章共识调整：** 当≥4篇相关文章中同一方向占75%以上，整体×1.2（共识加成）；方向分散时×0.8（分歧惩罚）

**校准：** 原始分通过 `CALIBRATION_RAW=14.4` 归一化到0-100

---

#### 5.3.2 分析师评分（Analyst Scorer）

**评分组成（合计最高100分，含共识乘数后）：**

| 组成 | 满分 | 计算方式 |
|------|------|---------|
| 评级分布 | 30pts | Strong Buy×2 + Buy×1 - Sell×1 - Strong Sell×2，综合牛熊比 |
| 加权评级 | 20pts | 每条评级 × 机构权威（top=2.0/major=1.2/general=0.7）× 时间衰减 |
| 评级动量 | 20pts | 90天内升级 vs 降级数量差，新进驻（init）计0.5次 |
| 目标价 Upside | 20pts | 均值目标价相对当前价：>30%=20分，>20%=16分，>10%=10分 |
| 目标价分散度 | 10pts | 分散度<15%=10分，15-35%=6分，35-60%=3分，>60%=0分 |
| 共识乘数 | ×0.85~1.15 | 看多比例≥70%×1.15，分散时×0.85 |

**机构权威分类（GPT一次性批量分类）：**
- `top`（×2.0）：Goldman Sachs、Morgan Stanley、JPMorgan、Citi等
- `major`（×1.2）：Deutsche Bank、Barclays、UBS、Jefferies等
- `general`（×0.7）：较小或精品研究机构

**时间衰减（月）：** 1月内=1.0，3月内=0.8，6月内=0.6，12月内=0.3

**目标价分散度拆分（0.5新增）：**
- 方向共识（看多%）单独一行展示
- 目标价分散度单独一行展示，并注明"反映时间框架差异，非方向分歧"

---

#### 5.3.3 内幕交易（Insider Scorer）

**评分组成（0-100，含集群效应）：**

| 组成 | 满分 | 计算方式 |
|------|------|---------|
| 净买卖比率 | 30pts | (买入-卖出)/总额，10b5-1销售×0.3降权 |
| 买卖方人数 | 25pts | 纯买方占比（10b5-1卖方排除在外） |
| 最大单笔购买 | 20pts | USD金额分档：>1000万=20分，>500万=16分... |
| 最高级别买方 | 15pts | CEO=2.0×，CFO=1.8×，COO=1.6×... |
| **集群效应（新增）** | **+15pts** | 2名以上CEO/CFO/COO/President在7天内同时买入 |
| 基础分 | 10pts | 固定底线，避免无交易时归零 |

**10b5-1 计划性交易豁免（0.5核心修复）：**
当所有卖方交易中≥80%为10b5-1预登记计划时：
- 评分直接归中性（50分）
- 方向标记为 Neutral
- Risk Matrix从 HIGH 降为 LOW
- 显示：「📋 Scheduled trading plans — pre-registered wealth management, not a bearish signal」

**职位权重：**

| 职位 | 权重 |
|------|------|
| CEO | 2.0 |
| CFO | 1.8 |
| COO | 1.6 |
| President | 1.6 |
| Chairman | 1.5 |
| Director | 1.0 |
| VP | 0.9 |
| Officer | 0.8 |
| Other | 0.6 |

**时间衰减（月）：** 1月内=1.0，3月内=0.85，6月内=0.65，12月内=0.35

---

#### 5.3.4 期权情绪（Options Scorer）

**数据：** 选取30-90天到期的最近期权链，若不在此窗口则退而取最近到期。

**评分组成（0-60原始分 → 归一化0-100 → IV乘数）：**

| 组成 | 满分 | 计算方式 |
|------|------|---------|
| PCR Volume（看跌/看涨成交量比） | 35pts | <0.40极度看多=35分，>1.40极度看空=2分 |
| PCR OI（看跌/看涨持仓量比） | 25pts | <0.50=25分，>1.30=0分 |
| IV 置信度乘数 | ×0.70~1.00 | IV>60%时信号×0.70（高不确定），IV<35%时×1.00 |

**基准PCR：** 0.7（股票期权市场历史均值，非1.0）

**纯展示信号（不计入评分）：**
- **Max Pain（最大痛点）：** 让期权卖方损失最小的到期价格，对价格有引力效应
- **Call Wall / Put Wall：** 当前价格上方最大看涨OI的行权价（阻力）/ 下方最大看跌OI（支撑）

---

### 5.4 宏观面（Macro）

**综合权重：10%**
**评分范围：0-100（含个股敏感性调整）**
**数据来源：** yfinance（^VIX / ^TNX / ^IRX / ^GSPC）

宏观评分分两步：先得出环境分（Environment Score），再根据个股特性调整。

#### 步骤一：环境评分（max 100pts）

| 子维度 | 满分 | 数据 | 逻辑 |
|--------|------|------|------|
| VIX（恐慌指数） | 35pts | ^VIX | <15=35分，15-20=28分，20-25=20分，25-30=12分，30-35=5分，>35=0分 |
| 收益率曲线 + 利率趋势 | 35pts | ^TNX - ^IRX | 正常（>0.5pp）=35分，平坦=18分，倒挂=8分；30日内利率急升>0.4pp额外-8pts |
| 市场风险偏好 | 30pts | ^GSPC 30日涨跌 | +3%以上=30分，+1-3%=14分，-1-3%=8分，-3-7%=3分，<-7%=0分 |

**快速惩罚机制：**
- VIX 30日内上涨>40%：额外 -8pts（恐慌急剧上升）
- 10Y收益率30日内上升>0.4pp：额外 -8pts（利率急速收紧）
- 10Y收益率30日内下降>0.4pp：额外 +5pts（货币宽松信号）

#### 步骤二：个股敏感性调整

```
Adjusted Score = 50 + (Env Score - 50) × Sensitivity Multiplier
```

敏感性乘数 = Beta敏感性 × 0.55 + 行业敏感性 × 0.35 + 基础1.0 × 0.10

**Beta敏感性：**

| Beta范围 | 乘数 |
|---------|------|
| ≥2.50 | 1.40 |
| ≥2.00 | 1.25 |
| ≥1.50 | 1.10 |
| ≥1.00 | 1.00 |
| ≥0.60 | 0.85 |
| <0.60  | 0.70 |

**行业敏感性（rate × 利率主导权重 + vix × VIX主导权重）：**

| 行业 | Rate敏感 | VIX敏感 |
|------|---------|--------|
| Real Estate | 1.40 | 1.10 |
| Utilities | 1.30 | 0.75 |
| Technology | 1.15 | 1.30 |
| Consumer Cyclical | 1.05 | 1.20 |
| Healthcare | 0.80 | 0.70 |
| Consumer Defensive | 0.70 | 0.60 |

**逻辑：** 当环境分=50（中性）时，调整后分数不变。环境好时高Beta股受益更多；环境差时高Beta股受损更深。符合CAPM逻辑。

---

### 5.5 事件驱动（Event-Driven）

**设计：不是评分维度，是可靠性系数**
**不影响 Composite 分数，只影响信号可信度展示**
**数据来源：** yfinance `ticker.calendar` + `ticker.earnings_dates`

#### 时间窗口与可靠性系数

| 窗口 | 触发条件 | 可靠性 | 说明 |
|------|---------|--------|------|
| POST_EARNINGS_SHOCK | 财报后0-1天 | 50% | 市场仍在消化，信号噪音极大 |
| PRE_EARNINGS_IMMINENT | 财报前1-3天 | 65% | 价格被事件投机驱动 |
| PRE_EARNINGS_NEAR | 财报前4-7天 | 80% | 进入事件窗口 |
| PRE_EARNINGS_WATCH | 财报前8-14天 | 90% | 轻度感知，信号基本有效 |
| POST_EARNINGS_DIGEST | 财报后2-5天 | 85% | 市场调整中 |
| NORMAL | 其他时间 | 100% | 信号全效 |

**UI展示：**
- 可靠性<100%时，在分数卡下方显示彩色警告横幅
- `POST_EARNINGS_SHOCK` 和 `PRE_EARNINGS_IMMINENT` 显示红色警告
- NORMAL 窗口仅显示「📅 Earnings in Xd」提示

**财报数据展示：**
- 下次财报日期 + 到期天数
- EPS预期区间（低/高）
- 上次财报：实际EPS vs 预期EPS + surprise百分比（>+5%=beat，<-5%=miss）

---

## 6. 权重配置完整表

### 主维度权重

| 维度 | 当前权重 | 历史 | 3D Fallback |
|------|---------|------|-------------|
| Technical | 43% | 47% | 48% |
| Fundamental | 27% | 27% | 32% |
| Sentiment | 20% | 21% | 20% |
| Macro | 10% | 5%| 不参与 |

*3D Fallback：当 Macro 数据获取失败时自动切换*

### 开发者预设模式（不对用户开放）

| 模式 | Tech | Fund | Sent | Macro |
|------|------|------|------|-------|
| 当前（默认） | 43% | 27% | 20% | 10% |
| 长期投资模式 | 25% | 40% | 20% | 15% |
| 波段交易模式 | 40% | 25% | 25% | 10% |

### 决策象限阈值

| 维度 | 阈值 | 含义 |
|------|------|------|
| Technical | >50 | 技术面明确偏多 |
| Fundamental | >55 | 基本面实质性正面 |
| Sentiment | >60 | 情绪面有明确方向 |
| Macro | >50 | 宏观环境支持 |

### 情绪子维度权重

| 子维度 | 权重 |
|--------|------|
| 新闻 | 55% |
| 分析师 | 22% |
| 内幕交易 | 13% |
| 期权 | 10% |

### 技术面各周期权重

| 周期 | 权重 | 最大原始分 |
|------|------|-----------|
| Short-term | 30% | 80pts（+ downtrend penalty）|
| Mid-term | 35% | 80pts（+ downtrend penalty）|
| Long-term | 35% | 90pts（+ downtrend penalty）|

### 技术面各指标分值

**Short-term（总max 80pts）：**

| 指标 | 满分 |
|------|------|
| RSI（14日） | 25pts |
| Stochastic（14日） | 20pts |
| ROC（10日） | 20pts |
| Bollinger Bands | 15pts |

**Mid-term（总max 80pts）：**

| 指标 | 满分 |
|------|------|
| MACD（12/26/9） | 25pts |
| MA20 | 15pts |
| MA50 | 25pts |
| Volume Trend（5日） | 15pts |
| ATR | 仅展示 |

**Long-term（总max 90pts）：**

| 指标 | 满分 |
|------|------|
| MA200 | 35pts |
| Golden/Death Cross | 40pts |
| MA Slope（MA50 vs MA200距离%） | 15pts |

### 宏观子维度权重

| 子维度 | 满分 |
|--------|------|
| VIX | 35pts |
| 收益率曲线 + 利率趋势 | 35pts |
| 市场风险偏好（S&P500 30d） | 30pts |

### 宏观敏感性权重

| 来源 | 权重 |
|------|------|
| Beta敏感性 | 55% |
| 行业敏感性 | 35% |
| 固定基础 | 10% |

---

## 7. Composite 综合决策逻辑

### 评分计算

```
Composite = Technical × 43% + Fundamental × 27% + Sentiment × 20% + Macro × 10%
```

若任一维度数据缺失，其权重按比例重新分配给其他维度。

### 评分区间与标签

| 分数范围 | 标签 |
|---------|------|
| 75-100 | Strong Uptrend |
| 60-74 | Uptrend |
| 40-59 | Neutral |
| 25-39 | Downtrend |
| 0-24 | Strong Downtrend |

### 决策象限（Quadrant）

根据各维度是否超过阈值，输出人类可读的决策标签：

| 条件 | 象限 | 图标 |
|------|------|------|
| Tech高 + Fund高 + Sent高/无 + Macro高 + **short-term≥40** | **Strong Buy** | 🟢 |
| Tech高 + Fund高 + Sent高/无 + Macro高 + **short-term<40** | **Cautious Buy** | 🟢 |
| Tech高 + Fund高 + Sent低 + Macro高 | Cautious Buy | 🟢 |
| Tech高 + Fund高 + Macro低 | Macro Headwind | 🟡 |
| Tech高 + Fund低 | Trader Play | 🟡 |
| Tech低 + Fund高 + Sent高 | Value Opportunity | 🔵 |
| Tech低 + Fund高 + Sent低 | Value Watch | 🟠 |
| 其他 | Avoid | 🔴 |
| 仅有技术数据 | Technical Only | ⬜ |

**短期时机覆盖（0.5新增）：** 当所有维度满足Strong Buy但 `short_term < 40` 时，标题降为Cautious Buy，行动建议改为"等待回调后入场"。

---

## 8. 风险矩阵

风险矩阵由 `composite.py` 自动生成，基于现有分数数据派生，无需新数据源。

每个条目包含：类别、等级（HIGH/MEDIUM/LOW）、具体信号描述。

| 条目 | 数据来源 | 触发HIGH条件 |
|------|---------|-------------|
| Technical Momentum | 技术总分 | <35分 |
| Valuation | P/E、Forward P/E、P/S | P/E>50 或 Forward P/E>40 |
| Financial Health | D/E、Current Ratio、FCF | D/E>200 或 FCF<0 |
| Sentiment Divergence | Technical vs Sentiment分差 | 差值>35且技术>情绪 |
| Insider Activity | Insider评分 + 10b5-1比例 | 评分≤25 且 10b5-1<80% |
| Volatility | Beta值 | Beta>2.0 |
| Analyst Direction | 看多比例 | 看多<40% |
| Analyst Target Dispersion | 目标价分散度 | 分散度>60%（降为MEDIUM，注明时间框架差异）|
| Macro Environment | Macro评分 | <30分 |
| Event Risk | 财报窗口严重程度 | PRE/POST_IMMINENT |

---

## 9. 未来计划

### 近期待办（技术上可行，等待实现）

**逻辑改进类：**
- **Insider集群效应扩展：** 目前检测7天内集群，未来可加入"同月集群"和跨公司（同行业CEO群体买入）检测
- **Options Max Pain 纳入评分：** 当前仅作展示，价格距Max Pain超5%时有明显引力效应，可贡献0-10分
- **Analyst Revision Momentum：** 记录目标价上调/下调趋势，而非只看当前评级（需历史目标价序列）
- **LLM Confidence Score：** 当GPT自判新闻质量低/模糊时，自动降低该条新闻的维度权重
- **Debt/Equity行业感知阈值：** 金融/REIT行业天然高杠杆，当前统一阈值会误判

**数据维度类（需接入新数据源）：**

| 功能 | 候选数据源 | 说明 |
|------|-----------|------|
| 行业实时对标（NVDA vs AMD/TSMC） | 直接拉多股数据 | 相对估值比绝对估值更有意义 |
| 13F机构持仓变化 | SEC EDGAR API（免费） | 季度增减持，聪明钱追踪 |
| 期权大单流向（Unusual Activity） | Unusual Whales / Tradier | Sweep/Block检测，真正的机构信号 |
| Short Interest / 融券比率 | FINRA / iborrowdesk | 空头挤压风险量化 |
| 逐季QoQ财务分析 | yfinance quarterly_financials | 增速加速/减速拐点识别 |
| Macro四因子重构 | 现有数据重组 | Rates/Liquidity/Risk Appetite/AI Capex独立因子 |

### 中期规划

- **股票对比功能恢复：** 当前因Token消耗过高已禁用，待Token优化（批量GPT调用、缓存）后重新开放
- **权重自动化测试框架：** 对历史数据进行回测，量化验证各权重组合的预测准确率
- **Streamlit缓存优化：** 部分维度（分析师评级、宏观数据）变化频率低，可缓存减少API调用

### 长期愿景

- **多Agent架构：** 将各维度分析器改为独立Agent，支持并行执行，大幅缩短分析时间（目前单股约30-60秒）
- **Monte Carlo情景模拟：** 基于历史波动率生成未来价格路径分布
- **自定义用户画像：** 根据用户风险偏好（保守/平衡/激进）自动切换权重预设

---

*报告基于 0.5 版本，所有权重数据均从 `core/weights.py` 直接提取，所有评分逻辑均从对应 scorer 文件提取，确保与代码完全同步。*
