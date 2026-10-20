# lightweight-rag-core

用 Python 自行组装完整 RAG 链路：

**解析 → 切分 → 真实 Embedding → Chroma → 检索 → qwen-plus → 可核对引用**

> 不依赖 RAGFlow / Dify 等封装产品，重点是把「文档怎么进来、片段怎么检索、回答怎么引用」的每一步写清楚、可测试、可复现。

## 业务场景

企业要做知识库问答时，常见的两个选择是：

1. 直接采购成熟 RAG 产品，快速上线；
2. 自己组装链路，按企业文档格式和权限要求做定制。

这个项目对应第 2 条：用 22 份虚构企业文档，把解析、切分、向量化、检索、回答、引用和拒答串成一条可运行、可评测的链路。它适合用来评估“自建 RAG 需要控制哪些环节”，也可以作为企业知识库 PoC 的代码骨架。

评测语料与 30 道题和 [enterprise-rag-kb](https://github.com/haozhouliuliuliu/enterprise-rag-kb) 同源，题目与判定规则不改，便于对照“成熟产品”和“自建链路”的差异。

## 最终结果

| 指标 | 结果 | 门槛 |
|---|---:|---:|
| 有答案 25 题 Top-5 检索 | **23/25 = 92%** | ≥70% |
| 有答案 25 题引用有效性 | **25/25 = 100%** | ≥80% |
| 无答案 5 题正确拒答 | **5/5 = 100%** | ≥4/5 |
| 回答命中 | **25/25** | — |
| 编造 / 错误 | **0 / 0** | 0 |
| pytest | **37 passed** | ≥10 |

结果只代表当前虚构语料、题集、embedding 和模型配置，不代表生产环境准确率。

## 技术方案

| 环节 | 实现 |
|---|---|
| 解析 | PDF 按页；DOCX 段落/表格；TXT 段落；每个 block 带 `source_file`，PDF 带 page |
| 切分 | 代码控制 500/50；保留 `chunk_id`、page、字符区间 |
| Embedding | 百炼 `text-embedding-v4`，1024 维；批处理、重试、维度校验 |
| 向量库 | Chroma `PersistentClient`，cosine；稳定 ID `doc_id:chunk_id` |
| 检索 | Top-5 为评测口径；回答用 Top-10 + 同文档 sibling 扩展 |
| 回答 | `qwen-plus`，temperature=0；强制 `[n]` 引用 |
| 引用 | `[n]` 映射到真实 `doc_title/source_file/chunk_id/page`；非法编号判失败 |
| 生命周期 | 新增/删除/修改/重建索引；删除按 `doc_id` 清理 Chroma |
| 失败处理 | 缺 key/401/超时/空文档/不支持格式明确失败，不伪造成功 |

## 架构

```mermaid
flowchart LR
  D[PDF / DOCX / TXT] --> P[parser.py]
  P --> C[chunker.py<br/>500 / 50]
  C --> E[text-embedding-v4<br/>1024d]
  E --> V[(Chroma<br/>PersistentClient)]
  Q[问题] --> QE[问题 Embedding]
  QE --> R[Retriever<br/>Top-5]
  V --> R
  R --> X[Top-10 + sibling]
  X --> L[qwen-plus]
  Q --> L
  L --> A[回答 + [n] 引用]
  A --> T[trace / 评测报告]
```

## 目录

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
│   └── results/           # 验证记录
├── data/docs/             # 22 份虚构文档 + manifest
├── scripts/               # 建索引 / 文档管理 / 问答 / 评测 / 证据脚本
├── docs/                  # 架构 / 部署 / 安全
├── config.example.yaml
└── .env.example
```

## 快速开始

```powershell
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

# 30 题评测
.\.venv\Scripts\python.exe scripts\evaluate.py
```

完整命令见 [docs/deployment.md](docs/deployment.md)。

## 可复用产出

- 一套从解析到引用的最小 RAG 代码骨架；
- 22 份虚构文档 + 30 题固定评测集 + 判定脚本；
- 文档新增/删除/重建索引与重启持久化验证；
- 缺 key、401、超时、空文档等失败路径的明确处理；
- 引用编号与真实来源映射，便于审计回答依据。

## 已知限制

- 单机、单进程验证，不含企业级权限、多租户、高可用；
- 表格被 500 字切分后可能丢结构，需要 sibling 扩展兜底；
- 相似型号/版本对比仍可能漏检；
- 评测集规模有限，不能代表所有企业语料；
- 外部模型调用会发送问题与检索文本，只应使用获授权的数据。

## 安全

API key 只从环境变量或本机 `.env` 读取；`.env`、`config.yaml`、`data/chroma` 均已忽略。仓库不包含真实密钥。详见 [docs/security.md](docs/security.md)。

## 许可

[MIT](LICENSE)
