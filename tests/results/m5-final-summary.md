# 项目二最终验收汇总（M1–M5）

## 1. 最终指标

| 指标 | 结果 | 门槛 | 判定 |
| --- | --- | --- | --- |
| 有答案 25 题 Top-5 检索命中 | **23/25 = 92%** | ≥70% | ✅ |
| 有答案 25 题引用有效性 | **25/25 = 100%** | ≥80% | ✅ |
| 无答案 5 题正确拒答 | **5/5 = 100%** | ≥4/5 | ✅ |
| 回答命中（关键词+引用） | **25/25 = 100%** | 参考 | ✅ |
| 编造 / 错误 | **0 / 0** | 0 | ✅ |
| 自动化测试 | **37 passed** | ≥10 | ✅ |

与项目一最终值对照（仅对照，不作为竞争目标）：

| 指标 | 项目一 | 项目二 |
| --- | ---: | ---: |
| Top-5 检索 | 21/25（84%） | **23/25（92%）** |
| 回答来源 | 22/25（88%） | **25/25（100%）** |
| 无答案 | 5/5 | **5/5** |

## 2. 链路与关键配置

```text
PDF/DOCX/TXT
  -> parser.py（source_file/page/结构化错误）
  -> chunker.py（500/50，chunk_id/page/字符区间）
  -> DashScopeEmbedder（text-embedding-v4，1024 维）
  -> Chroma PersistentClient（cosine）
  -> Retriever（Top-5 指标；回答用 Top-10 + 同文档 sibling chunk 扩展）
  -> qwen-plus（temperature=0，强制 [n] 引用）
  -> eval.py（30 题，项目一判定规则）
```

- `data/docs`：22 份同源文档，SHA-256 与项目一一致；
- Chroma：`data/chroma`，55 chunks，collection count=55；
- 回答上下文扩展：Top-10 命中文档的其余 chunk 一并加入上下文，解决 500 字切分把表格拆开的问题；**Top-5 指标仍只取前 5 条**；
- 模型：`text-embedding-v4` / `qwen-plus`，base_url 为百炼 OpenAI 兼容接口。

## 3. M2 证据

- `tests/results/m2-smoke.md`：真实 2 条 embedding（1024 维）+ Chroma HNSW Top-2 query；
- `tests/results/m2-index-report.json`：22 docs、55 chunks、1024 维、collection count=55、HNSW；
- `scripts/build_index.py`：可重复重建索引。

## 4. M3 证据

- `tests/results/m3-answer-trace.md` / `.json`：
  - Top-5 检索结果；
  - system prompt 与检索上下文；
  - qwen-plus 原始回答；
  - `[n]` → `doc_title/source_file/chunk_id/page` 引用映射；
  - `citation_error` 与 `refused` 字段。

## 5. M4 证据

- `tests/results/m4-lifecycle.md`：
  - 新增 M4-ADD：55→56，Top-5 可检索；
  - 删除：56→55，旧内容不再命中；
  - 修改后重新索引：旧 token 不再命中，新 token 命中；
  - 连续两次全量重建：55→55，ID 唯一 55/55；
  - 重新创建 PersistentClient：count=55，仍可检索 X-100；
  - `tests/results/m4-restart.md`：**新进程**读取持久化 Chroma，count=55，Top-5 可检索。
- `tests/results/m4-failures.md`：
  - 不支持格式、空文档被拒绝；
  - Embedding 401、LLM 401 均抛错，不返回假结果；
  - 单元测试覆盖超时、维度异常、空检索、删除、重索引。
- `scripts/manage_docs.py`：add/remove/list/reindex 可复现。

## 6. M5 证据

- `tests/questions.full.json`：与项目一 SHA-256 完全一致：
  `6d90b7326168b7ef267a6eb64a299f63b6b0a740dbad4dc8e87a5d66fb75489e`
- 最终原始结果：`tests/results/eval-20261019-150357.json/.md`
- `tests/results/m5-clean-install.md`：项目外干净 venv 安装 + 37 tests passed
- 测试集分类：10 直接 + 5 多资料 + 5 易混淆 + 5 版本 + 5 无答案。

## 7. 未命中题与已知限制

### 7.1 Top-5 检索未命中 2 题

| 题号 | 现象 | 原因 | 回答结果 |
| --- | --- | --- | --- |
| M05 | Top-5 未包含《X-100 系列扭矩校准记录模板》 | 校准周期问题与包装问题混合，向量排序被包装/说明书占据 | 扩展上下文后最终回答命中 25/25 |
| V04 | Top-5 未同时覆盖 V2.0 与 V2.1 | 两个版本 chunk 排序接近，Top-5 只覆盖 V2.1 | 扩展上下文后最终回答命中 |

这两题说明：**Top-5 检索指标与最终回答质量不能混为一谈**。项目二保留了这两个失败案例，没有改题。

### 7.2 其他限制

1. **Chunk 500/50 的表格切分**：PDF 表格常被切开，回答依赖同文档 sibling chunk 扩展；这是当前检索准确率的主要来源。
2. **Chroma HNSW**：本机 i7-3770 无 AVX2，但 Chroma 1.5.9 HNSW smoke/查询正常；已保留 `brute_force` 后端作为兼容回退。
3. **Top-5 指标 92%**：未做 rerank/查询拆分；M05、V04 仍是回归用例。
4. **回答上下文扩展**：比严格 Top-5 使用更多 chunk；评测的检索指标仍按前 5 条计算，引用可回溯到扩展 chunk。
5. **无 Web UI**：交付接口是 CLI（`ask.py`/`manage_docs.py`/`evaluate.py`），符合“简单界面或 API 不要求复杂 UI”。
6. **真实数据**：全部文档为虚构资料，不得替换为真实企业资料。
7. **密钥**：仅 `.env`/环境变量；`.env`、`config.yaml`、`data/chroma` 均不进入 Git。

## 8. 复现命令

```powershell
cd C:\RAG库\lightweight-rag-core
.\.venv\Scripts\python.exe -m pytest

# 重建索引（会调用百炼 embedding）
.\.venv\Scripts\python.exe scripts\build_index.py

# 单题
.\.venv\Scripts\python.exe scripts\ask.py "X-100 的额定功率是多少？"

# 30 题评测
.\.venv\Scripts\python.exe scripts\evaluate.py
```

## 9. 结论

项目二 M2–M5 已完成，链路真实运行并具备：

- 真实百炼 embedding + Chroma 持久化；
- Top-5 检索 92%、引用有效性 100%、无答案拒答 100%；
- 新增/删除/修改/重新索引/重复索引/重启持久化证据；
- 异常与外部服务失败不伪造成功；
- 37 个自动化测试；
- 干净 venv 可复现；
- 30 题原样复用，未修改题目或判定规则。
