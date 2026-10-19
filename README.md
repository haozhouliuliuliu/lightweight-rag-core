# lightweight-rag-core

用 Python 自行组装完整 RAG 链路的轻量实验项目：**解析 → 切分 → Embedding → 向量库 → 检索 → LLM → 引用**。

> **当前阶段：M1（解析与切分）已完成。** 本仓库只实现并验证 M1；Embedding、Chroma 入库、检索与 LLM 回答在后续里程碑实现。
>
> **与项目一的关系**：复用 [enterprise-rag-kb](https://github.com/haozhouliuliuliu/enterprise-rag-kb) 的同一套 22 份虚构企业文档和同一套 30 道测试题，作为两条技术路线的对照基准。项目一使用 AnythingLLM；本项目不依赖 RAGFlow/Dify 等封装产品。

## 1. 目标

- 文档解析：PDF、DOCX、TXT；
- 切分：项目代码显式控制 chunk size / overlap；
- 后续：百炼 Embedding、Chroma 本地持久化、Top-K 检索、`qwen-plus` 生成、chunk 级引用；
- 测试语料与测试问题与项目一同源，便于横向对照。

## 2. 当前 M1 结果

| 项目 | 结果 |
| --- | --- |
| 同源文档 | 22 份（12 DOCX + 10 PDF），与项目一 SHA-256 一致 |
| 解析成功 | 22/22 |
| 解析 blocks | 230 |
| 切分 chunk | 55（size 500 / overlap 50） |
| pytest | 14 passed |
| 人工抽查 | 3 个 chunk 文本与源文档字符区间完全一致 |

证据：

- `tests/fixtures/parse-report.json`
- `tests/fixtures/chunks.jsonl`
- `tests/results/m1-parse-spotcheck.md`

## 3. 目录结构

```text
lightweight-rag-core/
├── src/lightrag/
│   ├── __init__.py
│   ├── parser.py          # PDF/DOCX/TXT 解析、结构化错误
│   └── chunker.py         # 500/50 切分、chunk 元数据
├── tests/
│   ├── test_parser.py
│   ├── test_chunker.py
│   ├── fixtures/          # parse-report.json、chunks.jsonl
│   └── results/           # M1 人工抽查
├── data/docs/             # 22 份同源虚构文档（含 manifest）
├── scripts/
│   ├── build_m1_reports.py
│   └── m1_spotcheck.py
├── docs/
│   ├── architecture.md
│   └── deployment.md
├── config.example.yaml
├── .env.example
├── requirements.txt
├── pytest.ini
└── README.md
```

## 4. 快速开始

```powershell
# 1. 创建 venv（.venv 已被 gitignore）
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. 运行测试
.\.venv\Scripts\python.exe -m pytest

# 3. 重新生成 M1 证据
.\.venv\Scripts\python.exe scripts\build_m1_reports.py
.\.venv\Scripts\python.exe scripts\m1_spotcheck.py
```

完整环境说明见 [docs/deployment.md](docs/deployment.md)，架构见 [docs/architecture.md](docs/architecture.md)。

## 5. 配置与密钥

- `config.example.yaml` 只含占位配置，不含真实 key；
- API key 只从环境变量或 `.env` 读取；`.env` 已 gitignore；
- 本项目 M1 **不调用**任何外部 API；后续 embedding/LLM 会调用百炼，届时必须明确数据流向。

## 6. M1 范围与非目标

**M1 已完成**

- PDF/DOCX/TXT 解析；
- PDF 页码、source_file、block 元数据；
- 空文档、损坏 PDF/DOCX、不支持格式、文件缺失的结构化错误；
- 500/50 切分、短文档单 chunk、chunk_id/字符区间；
- 全量报告、chunk JSONL、3 个 chunk 人工抽查、pytest。

**M1 不做**

- Embedding / 百炼调用；
- Chroma 入库与检索；
- LLM 回答、引用渲染；
- Web UI / API 服务。

## 7. 虚构数据声明

`data/docs/` 下全部文档为**虚构演示资料**，公司名、型号、参数均为虚构。禁止替换为真实企业资料。文档来源与项目一提交见 `data/docs/README.md`。
