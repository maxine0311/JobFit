# 开发指南（给人，也给 AI 助手）

这个仓库刻意保持小而清晰：核心代码 6 个文件 + CLI + 配置注册表，没有个人数据。任何开发任务都可以交给 Codex / Copilot / Claude 等 AI 助手完成，前提是给它下面的上下文。

## 给 AI 助手的标准上下文（每次新任务先贴这段）

```text
你正在维护 D:\...\jobfit 这个开源项目（求职搜索 + 学习规划助手）。
先读 README.md、docs/DEVELOPMENT.md、scripts/sources_config.py、cli.py，
再动手。硬性约定：
1. 不得引入任何个人数据、API key、绝对路径；新增代码必须可公开。
2. 求职网站适配器必须遵守接口：fetch_<site>(keyword) ->
   list[dict]{title, url, company, salary{minimum,maximum}, deadline}。
3. 新增适配器要在 scripts/sources_config.py 注册并默认 enabled=false，
   由使用者自行开启；抓取要控制频率、处理失败，遵守网站条款。
4. LLM 调用统一走 agent/llm.py（OpenAI 兼容），不要新起一套客户端。
5. 改动后运行 py_compile 或最小冒烟测试，并更新 README 对应章节。
```

## 任务清单（按优先级，可直接当作任务描述）

### 1. 添加一个求职网站适配器（示例：中国猎聘）
```text
为 sources_config.py 里 CN 地区的 liepin 实现适配器：
新建 scripts/adapters/liepin.py，实现 fetch_liepin(keyword) 按接口返回岗位列表；
抓取时用带 User-Agent 的 requests，解析失败返回空列表而不是抛异常；
在 sources_config.py 中把 liepin 的 enabled 改为 True（或保留 False 由用户开启）；
写 1-2 个最小单测（可 mock 请求），并在 README 的地区列表里说明。
```

### 2. Provider 适配层（支持 Claude / Gemini）
```text
给 agent/llm.py 增加 provider 抽象：配置 LLM_PROVIDER=openai_compatible|anthropic|gemini，
新增 AnthropicClient 和 GeminiClient，实现同样的 chat(system,user) -> {text,tokens,cost} 接口；
cost 估算用各自的 token 计费表，读 rag/config.py 的新配置项；
更新 .env.example 与 README 的"模型配置"一节。
```

### 3. Web 仪表盘
```text
基于 Streamlit 做一个轻量仪表盘：岗位看板（读 data/new_jobs_history.jsonl）、
学习计划打卡（读写 data/study_plan.json）、公司背景调研入口；
复用现有 rag/pipeline.py 和 agent/study_planner.py，不重复造轮子；
页面文案中英皆可，保持奶油原木风；数据全部本地存储。
```

### 4. 定时任务与推送
```text
给 cli.py 增加 schedule 子命令：用系统计划任务（schtasks / crontab）说明文档，
或提供 --daemon 常驻模式；每日抓取后生成当日报告并可选推送到
Telegram / 邮件（新增 scripts/notify.py，配置放 .env，默认关闭）。
```

## 目录约定

- `scripts/adapters/`：新增的地区/网站适配器放这里，统一导入
- `agent/`：LLM 相关（llm.py、study_planner.py）
- `rag/`：检索问答引擎（不要放业务逻辑）
- 数据默认在 `data/`、索引在 `storage/`，两者都在 .gitignore

## 验收标准

- `python -m py_compile` 全绿
- 新增功能有最小冒烟测试或手工验证步骤
- README / DEVELOPMENT.md 同步更新
- 仓库无个人数据、无密钥
