# 部署与环境说明（M1 骨架）

> 本项目当前只完成 M1（解析 + 切分），不调用 Embedding / LLM，也不创建 Chroma 索引。

## 1. 环境要求

| 项目 | 要求 | 本机实测 |
| --- | --- | --- |
| 操作系统 | Windows 10/11 x64 | Windows 10 Pro 22H2，Build 19045 |
| Python | ≥ 3.10（建议 3.12） | **3.12.14** |
| 虚拟环境 | venv，禁止全局 pip | `.venv`（已 gitignore） |
| 依赖 | `requirements.txt` | 已安装，`pip check` 通过 |

## 2. 创建虚拟环境

```powershell
cd C:\RAG库\lightweight-rag-core
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

验证：

```powershell
.\.venv\Scripts\python.exe -c "import sys, pypdf, docx, chromadb, openai, pytest, yaml; print(sys.version); print(chromadb.__version__)"
```

## 3. 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

M1 实测：**14 passed**。

## 4. 生成解析/切分证据

```powershell
.\.venv\Scripts\python.exe scripts\build_m1_reports.py
.\.venv\Scripts\python.exe scripts\m1_spotcheck.py
```

输出：

- `tests/fixtures/parse-report.json`：每份文档格式、block 数、chunk 数、错误；
- `tests/fixtures/chunks.jsonl`：每个 chunk 的文本与元数据；
- `tests/results/m1-parse-spotcheck.md`：3 个 chunk 人工抽查。

## 5. 配置与密钥

- 复制 `config.example.yaml` 为本地 `config.yaml`（后续 M2 使用），不要提交真实配置；
- API key 只从环境变量或 `.env` 读取，`.env` 已 gitignore；
- `config.example.yaml` 不含真实 key；
- M2 起调用百炼前，必须确认虚构数据声明和外部数据流向。

## 6. 后续步骤（占位）

- M2：Embedding + Chroma 持久化；
- M3：Top-K 检索；
- M4：`qwen-plus` 回答与引用；
- M5：30 题对照评测。

以上步骤的环境细节在后续里程碑补充。
