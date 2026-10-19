# lightweight-rag-core

用 Python 自行组装完整 RAG 链路的轻量项目：

**解析 → 切分 → 真实 Embedding → Chroma → 检索 → qwen-plus → 可核对引用**

> 项目二不依赖 RAGFlow/Dify 等封装产品。项目一负责部署/验证成熟 RAG 产品；本项目负责证明自己能组装并验证 RAG 核心技术链路。
>
> 测试语料与 30 道题与项目一 **enterprise-rag-kb** 同源；题目原样复用，不修改题目/答案/判定规则。

## 1. 最终结果

| 指标 | 结果 | 要求 |
| --- | --- | --- |
| 有答案 25 题 Top-5 检索 | **23/25 = 92%** | ≥70% |
| 有答案 25 题引用有效性 | **25/25 = 100%** | ≥80% |
| 无答案 5 题正确拒答 | **5/5 = 100%** | ≥4/5 |
| 回答命中 | **25/25** | — |
| 编造 / 错误 | **0 / 0** | 0 |
| pytest | **37 passed** | ≥10 |

与项目一对照：项目一 Top-5 21/25（84%）、来源 22/25（88%）、无答案 5/5。项目二不追求超过项目一，重点是链路真实、引用可核对。

## 2. M1–M5 状态

| 里程碑 | 内容 | 状态 |
| --- | --- | --- |
| M1 | PDF/DOCX/TXT 解析、500/50 切分、元数据/错误、解析报告、3 chunk 抽查 | ✅ |
| M2 | 真实 `text-embedding-v4`、Chroma 持久化、新增/删除/重建索引 | ✅ |
| M3 | Top-K 检索、上下文组装、qwen-plus、`[n]` 引用、trace | ✅ |
| M4 | 新增/删除/修改/重索引、重启持久化、异常/超时/401、不伪造成功 | ✅ |
| M5 | 项目一 30 题、判定规则、评测报告、干净环境复现、文档/安全 | ✅ |

## 3. 目录

```text
lightweight-rag-core/
├── src/lightrag/
│   ├── parser.py          # PDF/DOCX/TXT，结构化错误
│   ├── chunker.py         # 500/50，chunk 元数据
│   ├── catalog.py         # manifest
│   ├── documents.py       # 新增/删除
│   ├── embeddings.py      # 百炼 embedding
│   ├── vector_store.py    # Chroma + brute-force 回退
│   ├── indexer.py         # 索引重建
│   ├── retriever.py       # 检索
│   ├── answer.py          # qwen-plus + 引用
│   ├── evaluation.py      # 30 题判定
│   └── refusal.py         # 拒答词表
├── tests/
│   ├── test_*.py          # 37 个测试
│   ├── questions.full.json
│   ├── fixtures/          # parse-report、chunks、测试文档
│   └── results/           # M1–M5 证据
├── data/docs/             # 22 份同源虚构文档 + manifest
├── scripts/
│   ├── build_index.py
│   ├── manage_docs.py
│   ├── ask.py
│   ├── evaluate.py
│   └── m2/m3/m4/m5 证据脚本
├── docs/
│   ├── architecture.md
│   ├── deployment.md
│   └── security.md
├── config.example.yaml
├── .env.example
├── requirements.txt
└── README.md
```

## 4. 快速开始

```powershell
# 虚拟环境（.venv 已 gitignore）
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check

# 测试
.\.venv\Scripts\python.exe -m pytest

# 配置：复制示例，只在本机 .env 填真实 key
copy config.example.yaml config.yaml
copy .env.example .env

# 建索引（真实调用 embedding）
.\.venv\Scripts\python.exe scripts\build_index.py

# 单题
.\.venv\Scripts\python.exe scripts\ask.py "X-100 的额定功率是多少？"

# 30 题
.\.venv\Scripts\python.exe scripts\evaluate.py
```

完整命令见 [docs/deployment.md](docs/deployment.md)。

## 5. 关键设计

- **解析**：PDF 按页；DOCX 段落/表格；TXT 段落；每个 block 带 `source_file`，PDF 带 page；
- **切分**：项目代码控制 500/50；chunk_id、page、字符区间；
- **Embedding**：百炼 `text-embedding-v4`，1024 维；批处理/重试/维度校验；
- **Chroma**：`PersistentClient`，cosine；稳定 ID `doc_id:chunk_id`；
- **检索**：Top-5 为评测口径；回答用 Top-10 + 同文档 sibling 扩展，弥补 500 字切分把表格拆开的问题；
- **回答**：`qwen-plus`，temperature=0；强制 `[n]` 引用；
- **引用**：`[n]` 映射到真实 `doc_title/source_file/chunk_id/page`；非法编号判失败，不自动补来源；
- **生命周期**：新增/删除/修改/重索引；删除按 `doc_id` 清理 Chroma；
- **异常**：缺 key/401/超时/空文档/不支持格式均明确失败，不伪装成功。

## 6. 证据

- M1：[m1-parse-spotcheck.md](tests/results/m1-parse-spotcheck.md)
- M2：[m2-smoke.md](tests/results/m2-smoke.md)、[m2-index-report.json](tests/results/m2-index-report.json)
- M3：[m3-answer-trace.md](tests/results/m3-answer-trace.md)
- M4：[m4-lifecycle.md](tests/results/m4-lifecycle.md)、[m4-restart.md](tests/results/m4-restart.md)、[m4-failures.md](tests/results/m4-failures.md)
- M5：[m5-final-summary.md](tests/results/m5-final-summary.md)、[m5-clean-install.md](tests/results/m5-clean-install.md)
- 30 题原始结果：[eval-20261019-150357.md](tests/results/eval-20261019-150357.md)

## 7. 安全与数据

- key 只从环境变量或本地 `.env`；
- `.env`、`config.yaml`、`data/chroma` 均 gitignore；
- chunk 文本和用户问题会发送到阿里云百炼；
- 只使用虚构资料，禁止真实企业数据；
- 详见 [docs/security.md](docs/security.md)。

## 8. 已知限制

1. **Top-5 仍漏 2 题**：M05（校准+包装混合）、V04（V2.0/V2.1 同时覆盖）；最终回答通过扩展上下文命中，但 Top-5 指标保留失败。
2. **表格切分**：500 字切分把 PDF 表格拆开，依赖 sibling 扩展；未做表格结构还原。
3. **未做 rerank/查询拆分**：当前 92% Top-5，后续可提升。
4. **Chroma HNSW**：本机无 AVX2，但当前版本正常；保留 `brute_force` 回退。
5. **无 Web UI**：CLI 是交付接口，符合“简单界面或 API”范围。
6. **非生产级**：单机、无权限/多租户/审计/限流。
7. **虚构数据**：文档全部虚构，不用于真实生产决策。

## 9. 与项目一关系

- 同一套 22 份虚构文档（SHA-256 一致）；
- 同一套 30 题（SHA-256 `6d90b732...` 一致）；
- 项目一使用 AnythingLLM；项目二使用 Python + Chroma + 百炼；
- 两套结果可横向对照，但项目二不修改题目以追求更高分。
