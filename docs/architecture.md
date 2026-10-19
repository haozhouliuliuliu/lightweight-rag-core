# 架构与数据流向（M1–M5）

## 1. 总体架构

```mermaid
flowchart LR
  D[PDF / DOCX / TXT<br/>data/docs] --> P[parser.py<br/>pypdf / python-docx]
  P --> PD[ParsedDocument<br/>TextBlock + source_file + page]
  PD --> C[chunker.py<br/>500 / 50]
  C --> CH[Chunks<br/>chunk_id / page / char range]
  CH --> E[DashScopeEmbedder<br/>text-embedding-v4 / 1024d]
  E --> V[(Chroma<br/>PersistentClient / cosine)]
  Q[用户问题] --> QE[问题 Embedding]
  QE --> R[Retriever<br/>Top-5]
  V --> R
  R --> X[回答上下文<br/>Top-10 + 同文档 sibling]
  X --> L[qwen-plus<br/>temperature=0]
  Q --> L
  L --> A[回答 + [n] 引用]
  A --> T[trace / 评测报告]

  subgraph LOCAL[本机 Python 进程 / 本地文件]
    D
    P
    PD
    C
    CH
    V
    R
    X
    A
  end

  subgraph CLOUD[阿里云百炼（外部服务）]
    E
    QE
    L
  end
```

## 2. 模块

| 模块 | 作用 |
| --- | --- |
| `parser.py` | PDF/DOCX/TXT 解析；`TextBlock`/`ParsedDocument`；结构化错误 |
| `chunker.py` | 500/50 切分；chunk_id/page/字符区间 |
| `catalog.py` | manifest 读取、标题/ID 映射、原子写入 |
| `documents.py` | 新增/删除文档，更新 manifest 和源文件 |
| `embeddings.py` | 百炼 `text-embedding-v4`，批处理、重试、维度校验 |
| `vector_store.py` | Chroma 持久化、upsert、query、按 doc 删除、brute-force 回退 |
| `indexer.py` | 全量/单文档重建，count 校验 |
| `retriever.py` | 问题向量 → Top-K；保留来源元数据 |
| `answer.py` | 上下文组装、qwen-plus、`[n]` 引用解析、拒答判断 |
| `evaluation.py` | 项目一 30 题判定规则与统计 |
| `scripts/*.py` | build_index / manage_docs / ask / evaluate / M2–M4 证据 |

## 3. 数据模型

### Chunk

| 字段 | 说明 |
| --- | --- |
| `text` | chunk 原文 |
| `source_file` | 相对项目根目录的源文件 |
| `chunk_id` | 文档内 1-based 序号 |
| `page` | 起始页；DOCX/TXT 为 `None` |
| `char_start` / `char_end` | 相对整篇文档的字符区间 |

### Chroma metadata

- `doc_id`、`doc_title`、`source_file`、`chunk_id`；
- `page`（无页码为 `-1`）、`char_start`、`char_end`、`format`；
- 稳定 ID：`{doc_id}:{chunk_id}`。

### AnswerResult / trace

- `answer`、`refused`、`citations`、`citation_error`；
- `retrieved`（Top-10 原始检索）；
- `context_chunks`（同文档扩展后的上下文）；
- `context`（实际模型输入中的资料部分）；
- 评测结果落盘 JSON + Markdown。

## 4. 检索与回答策略

1. 问题用 `text-embedding-v4` 向量化；
2. Chroma cosine 取 Top-10（回答用）；评测 Top-5 指标只看前 5 条；
3. 对 Top-10 命中的文档，补入同文档其余 chunk，解决 500 字切分拆散表格的问题；
4. 组装带 `[n]` 编号的上下文；
5. `qwen-plus` 生成回答，强制 `[n]` 引用；
6. 解析 `[n]`，映射到真实 `doc_title/source_file/chunk_id/page`；
7. 无答案/空上下文返回“资料不足”，不伪造来源。

## 5. 外部服务边界

> **chunk 文本、用户问题会发送到阿里云百炼。**

- Embedding：`https://dashscope.aliyuncs.com/compatible-mode/v1`；
- LLM：同一 base_url，模型 `qwen-plus`；
- 原始文档和 Chroma 索引保留在本机；
- 只使用 `data/docs` 的虚构资料；不得导入真实企业数据；
- key 只从 env/.env，`config.yaml`/`.env` 不进入 Git。

## 6. 文档生命周期

- **新增**：`DocumentManager.add` 先解析校验，再复制到 `data/docs/imported/`，更新 manifest；
- **索引**：`build_index` 按 manifest 重建/增量写入 Chroma；
- **删除**：删除 manifest、源文件、Chroma 中对应 `doc_id` 向量；
- **修改**：删除旧文档后重新加入同一 `doc_id`，或用 `--doc-id --no-recreate` 重建该文档；
- 稳定 ID + 重建前 delete 避免重复 chunk。

## 7. 评测

- 30 题与项目一原样一致；
- Top-5 检索只看前 5 条；
- 引用有效性只认回答中真实 `[n]` 映射；
- 无答案题只统计拒答，不混入检索分母；
- 报告保存在 `tests/results/`，失败题保留为回归用例。
