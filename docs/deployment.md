# 部署与运行指南

## 1. 环境要求

| 项目 | 要求 | 本机实测 |
| --- | --- | --- |
| 操作系统 | Windows 10/11 x64 | Windows 10 Pro 22H2 |
| Python | ≥3.10，建议 3.12 | **3.12.14** |
| 虚拟环境 | venv，禁止全局 pip | `.venv` / 项目外干净 venv |
| Chroma | 嵌入式 `PersistentClient` | **1.5.9** |
| Embedding | 百炼 `text-embedding-v4` | 1024 维 |
| LLM | 百炼 `qwen-plus` | temperature=0 |

## 2. 安装（干净环境可复现）

```powershell
cd C:\RAG库\lightweight-rag-core
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest
```

实测：`pytest` **37 passed**；项目外干净 venv 同样 37 passed，见
`tests/results/m5-clean-install.md`。

## 3. 配置

```powershell
copy config.example.yaml config.yaml
copy .env.example .env
# 只在本机 .env 填入真实 DASHSCOPE_API_KEY；不要提交
```

- `config.yaml`、`.env` 已被 gitignore；
- `config.example.yaml` 不含真实 key；
- key 只从环境变量或 `.env` 读取；
- 主要配置：
  - `chunking.size/overlap`：500/50；
  - `embedding.dimensions`：1024；
  - `retrieval.top_k`：5（评测口径）；
  - `retrieval.answer_top_k`：10（回答上下文）；
  - `vector_store.persist_dir`：`data/chroma`。

## 4. 建索引

```powershell
.\.venv\Scripts\python.exe scripts\build_index.py
```

输出：

- `data/chroma/`：本地持久化索引（gitignored）；
- `tests/results/m2-index-report.json`：22 docs / 55 chunks / 1024 维 / count=55。

小规模冒烟：

```powershell
.\.venv\Scripts\python.exe scripts\build_index.py --limit 3
```

## 5. 单题问答

```powershell
.\.venv\Scripts\python.exe scripts\ask.py "X-100 的额定功率是多少？"
.\.venv\Scripts\python.exe scripts\ask.py "X-100S 的防护等级是什么？" --json
```

`--json` 输出检索结果、上下文、回答、citations 和 citation_error，便于追溯。

## 6. 30 题评测

```powershell
.\.venv\Scripts\python.exe scripts\evaluate.py
```

输出：

- `tests/results/eval-<timestamp>.json/.md`
- 指标：Top-5 检索、引用有效性、无答案拒答、编造/错误。

### 当前结果（2026-10-19）

| 指标 | 结果 |
| --- | --- |
| Top-5 检索 | 23/25（92%） |
| 引用有效性 | 25/25（100%） |
| 无答案拒答 | 5/5（100%） |
| 回答命中 | 25/25 |
| pytest | 37 passed |

## 7. 文档管理

```powershell
# 新增（解析校验后复制到 data/docs/imported，并更新 manifest）
.\.venv\Scripts\python.exe scripts\manage_docs.py add .\some.docx --title "新文档"

# 新增并立即重建该文档向量
.\.venv\Scripts\python.exe scripts\manage_docs.py add .\some.docx --reindex

# 列出
.\.venv\Scripts\python.exe scripts\manage_docs.py list

# 删除（必须确认；删除 manifest、源文件和 Chroma doc_id 向量）
.\.venv\Scripts\python.exe scripts\manage_docs.py remove DOC-ID --yes

# 全量/单文档重索引
.\.venv\Scripts\python.exe scripts\manage_docs.py reindex
.\.venv\Scripts\python.exe scripts\manage_docs.py reindex --doc-id DOC-ID
```

## 8. Chroma 兼容性

本机 i7-3770 无 AVX2；当前 Chroma 1.5.9 HNSW smoke/查询正常。若换机或升级后
`query` 以 `0xC000001D` 崩溃：

1. 不更换向量库；
2. 在本地 `config.yaml` 设置 `retrieval.query_backend: brute_force`；
3. 使用 Chroma 持久化向量 + NumPy cosine 排序；
4. 记录后端与原因。

## 9. 故障排查

| 现象 | 检查 |
| --- | --- |
| `missing API key` | `.env` 是否有 `DASHSCOPE_API_KEY` |
| 401 | key 是否有效；不要打印/提交 key |
| Chroma count 0 | 先运行 `build_index.py` |
| 回答全“资料不足” | 检查 count、Top-K、prompt、context |
| HNSW 崩溃 | 切 `query_backend: brute_force` |
| 引用编号无效 | 检查回答 `[n]` 是否超出上下文编号 |

## 10. 依赖与外部服务

- 依赖：`pypdf`、`python-docx`、`chromadb`、`openai`、`pytest`、`PyYAML`、`numpy`、`python-dotenv`；
- 外部服务：百炼 embedding / LLM；chunk 文本和问题会离开本机；
- 只用虚构资料；
- 许可证/第三方库遵循各自开源许可证。
