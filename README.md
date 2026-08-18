# JobFit — 求职搜索 + 学习规划助手

JobFit 是一个**以求职为主线的 AI 助手**：按你选择的国家/地区，从当地主流求职网站搜索岗位；用学习规划 agent 生成学习路径和每周计划；还可以把你自己整理的资料（追踪表、JD、邮件、简历）变成可问答的知识库。底层 RAG 只是支撑问答的引擎，不是产品本身。

> 本项目脱胎于作者真实使用的求职系统，代码与数据已完全脱敏；所有数据默认保存在本地。

## 功能

- **按地区搜索岗位**：选择国家/地区（`--region`），按该地区启用的求职网站搜索。新加坡（SG）是参考实现，默认启用 JobStreet / MyCareersFuture / InternSG / GradConnection。
- **学习路径与计划 agent**：输入求职目标、当前技能、目标岗位、每周学习小时数，生成"学习路径 + 周计划 + 里程碑 + 快速见效项"。
- **公司背景调研**：生成简历或评估岗位前，可先搜索目标公司背景（`scripts/company_research.py`，结果缓存 7 天）。
- **本地资料库问答**：把个人资料索引后，可以用自然语言提问，答案带引用来源。

## 快速开始

```bash
git clone <your-repo-url>
cd jobfit
pip install -r requirements.txt
cp .env.example .env     # 填入 DeepSeek / Embedding API key

# 1) 看某地区启用了哪些求职网站
python cli.py sources --region SG

# 2) 搜索岗位（默认新加坡源）
python cli.py search --keyword "AI engineer"

# 3) 生成学习路径和周计划
python cli.py study --goal "2027 年 5 月前拿到新加坡 AI 应用岗 offer" \
  --skills "Python, Flask, RAG, LangGraph" \
  --roles "AI 应用 / 后端" --hours 15 --deadline "2027-01"

# 4) 对本地资料库提问（需先构建索引，见 docs/ARCHITECTURE.md）
python cli.py ask --question "哪些岗位月底截止？"
```

## 模型配置（BYO API Key）

项目本身**不包含任何密钥**，每个使用者填入自己的 API Key（`.env` 或环境变量）。

- **对话/规划模型**：走 OpenAI 兼容协议。改 `DEEPSEEK_BASE_URL` 和 `DEEPSEEK_MODEL` 即可切换模型，例如：
  - DeepSeek：`https://api.deepseek.com` + `deepseek-chat`
  - OpenAI：`https://api.openai.com/v1` + `gpt-4o-mini`
  - Kimi / 通义千问 / 智谱：各家的 OpenAI 兼容端点
  - 本地模型：Ollama 的兼容端口（`http://localhost:11434/v1` + 本地模型名）
- **Embedding 模型**：同样 OpenAI 兼容。改 `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL` / `EMBEDDING_API_KEY`，默认 `BAAI/bge-m3`（经 SiliconFlow）。
- **暂不支持**：Anthropic Claude、Google Gemini 的原生 API（非 OpenAI 兼容协议），需要扩展 provider 适配层。

## 添加你的国家/地区

求职网站适配器接口约定在 `scripts/sources_config.py`：每个站点实现一个 `fetch_<site>(keyword) -> list[dict]`，返回字段 `title / url / company / salary / deadline`，然后在对应地区的 `sources` 里注册并置 `enabled: True`。SG 的四个源就是参考实现，照抄即可。

## 目录结构

```text
jobfit/
├── cli.py                    # 命令行入口
├── scripts/
│   ├── daily_monitor.py      # 岗位抓取（SG 参考实现）
│   ├── sources_config.py     # 国家/地区 × 求职网站注册表
│   └── company_research.py   # 公司背景调研（缓存 7 天）
├── agent/
│   ├── llm.py                # LLM 封装（OpenAI 兼容）
│   └── study_planner.py      # 学习路径 / 周计划 agent
└── rag/                      # 检索问答引擎（config / retriever / pipeline）
```

## Roadmap

- [ ] 更多地区适配器：中国（猎聘/应届生）、美国（Indeed/LinkedIn）等
- [ ] Web 仪表盘：岗位看板、学习计划打卡、简历微调
- [ ] 定时任务：每日自动搜索并推送新岗位
- [ ] 简历定制：按 JD 微调简历（作者原版功能，将逐步抽离个人数据后开源）

## 免责声明

个人项目，无 SLA。抓取求职网站时请遵守各网站的服务条款与 robots 规则，控制请求频率；数据仅保存在本地，请勿上传含个人隐私的资料到公开仓库。
