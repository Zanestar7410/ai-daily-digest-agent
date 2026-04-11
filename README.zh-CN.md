# AI Daily Digest Agent

[English](./README.md)

一个面向 AI 资讯、事件提取与研究报告生成的本地情报工作台。

## 项目概览

本项目为一个 AI 日报生成的小型情报系统，具备以下能力：

- 受控来源发现
- 结构化事件提取
- 历史检索
- 实体与主题跟踪
- 研究报告持久化
- 本地接口与展示面板

## 核心能力

- 从可信来源发现近期 AI 更新
- 自动筛选高价值条目并支持回补
- 生成中文摘要与结构化事件元数据
- 将条目、事件、日报运行记录、研究报告持久化到 SQLite
- 支持历史内容、事件、实体、主题与研究报告检索
- 支持基于持久化事件的研究模式，并可选实时增强
- 支持 LaTeX / PDF 日报与主题报告输出

## 快速开始

创建虚拟环境并安装基础依赖：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e .[dev]
```

如果需要 OpenAI API 路径：

```powershell
.venv\Scripts\python -m pip install -e .[dev,api]
```

## 常用命令

渲染已有 digest：

```powershell
.\scripts\run_digest.ps1 --input input\latest_digest.json
```

通过 OpenAI API 生成 digest：

```powershell
.venv\Scripts\python -m ai_news_digest --mode api --input input\latest_digest.json
```

生成主题报告：

```powershell
.venv\Scripts\python -m ai_news_digest --mode api --write-topic-reports
```

检索历史内容：

```powershell
.venv\Scripts\python -m ai_news_digest --history-query "agent" --source "OpenAI News" --entity "Responses API" --date-from 2026-04-01 --date-to 2026-04-10
```

检索事件：

```powershell
.venv\Scripts\python -m ai_news_digest --event-query "agent" --event-type product-release --entity "OpenAI" --sort-by confidence --limit 10
```

查看实体时间线：

```powershell
.venv\Scripts\python -m ai_news_digest --entity-timeline "OpenAI" --limit 10
```

运行研究模式：

```powershell
.venv\Scripts\python -m ai_news_digest --research-query "最近两周 OpenAI agent 相关变化" --limit 8
```

输出研究报告到 Markdown，并启用实时增强：

```powershell
.venv\Scripts\python -m ai_news_digest --research-query "最近两周 OpenAI agent 相关变化" --research-live --research-output output\research.md --limit 8
```

回填旧事件记录：

```powershell
.venv\Scripts\python -m ai_news_digest --backfill-events --state-dir state
```

启动本地接口与展示面板：

```powershell
.venv\Scripts\python -m ai_news_digest --serve-api --api-host 127.0.0.1 --api-port 8000
```

打开：

```text
http://127.0.0.1:8000/
```

## 本地接口

- `GET /health`
- `GET /events`
- `GET /events/detail?event_id=<id>`
- `GET /entities`
- `GET /topics`
- `GET /research/reports`
- `GET /research/report?report_id=<id>`
- `GET /research/run?query=<query>`

## 仓库结构

- `config/search_sources.json`：来源配置
- `input/`：digest JSON 示例
- `scripts/`：Windows 入口脚本与定时任务脚本
- `src/ai_news_digest/`：核心实现
- `templates/`：LaTeX 模板
- `tests/`：自动化测试
- `docs/IMPLEMENTATION_NOTES.md`：实现记录与已知限制

## 验证

```powershell
.venv\Scripts\python -m pytest -q
.\scripts\run_digest.ps1 --input input\latest_digest.example.json --dry-run
```

## 实现亮点

- 基于受控来源的 AI 情报发现与整理
- 结构化事件提取与持久化
- 历史检索、实体跟踪、主题聚合
- 研究模式与研究报告生成
- 本地接口与展示面板

## 说明

- 老的 SQLite 状态库在事件查询前可能需要先执行 `--backfill-events`
- 实时 OpenAI 路径需要配置 `OPENAI_API_KEY`

## License

[MIT](./LICENSE)
