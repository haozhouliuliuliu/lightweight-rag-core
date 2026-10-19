# 测试说明

## 1. 测试集来源

`questions.full.json` 与项目一 **enterprise-rag-kb** 的 30 题测试集原样一致：

- 来源提交：`4a2adb3b2b871fe52ddb4024c806e197725cda1a`
- SHA-256：`6d90b7326168b7ef267a6eb64a299f63b6b0a740dbad4dc8e87a5d66fb75489e`
- 结构：10 直接 + 5 多资料 + 5 易混淆 + 5 版本冲突 + 5 无答案
- 禁止为了让结果更好而改题、改标准答案或改判定规则。

## 2. 题目 schema

```json
{
  "id": "F01",
  "question": "问题",
  "type": "分类",
  "mode": "query",
  "expected": "预期答案说明",
  "judge": {
    "must_include_all": ["必须出现的词"],
    "must_include_any": ["任一出现即可的词"],
    "must_refuse": true,
    "expected_sources": ["来源标题"],
    "expected_sources_all": ["必须同时引用的来源标题"]
  }
}
```

### 判定规则

- `must_refuse: true`：无答案题；回答必须出现拒答标记（如“资料不足”“未提及”“未出现”“没有相关记录”）。
- 可回答题：先检查 `must_include_all/any`，再检查回答中的 `[n]` 引用映射到真实 chunk；`expected_sources` 至少匹配一个来源，`expected_sources_all` 必须全部匹配。
- 引用编号必须是本轮上下文中真实存在的编号；非法编号 `[n]` 直接判未命中。
- `retrieval_hit` 只取 **前 5 条检索结果** 的 `doc_title`，与回答使用的扩展上下文分开统计。
- 无答案题不得计入检索命中率分母；有答案题 25 道为分母。

## 3. 指标口径

| 指标 | 计算 |
| --- | --- |
| Top-5 检索命中 | 有答案 25 题中，前 5 条检索包含 expected source |
| 引用有效性 | 有答案 25 题中，回答含真实 `[n]` 且映射到实际 chunk |
| 无答案拒答 | 5 道无答案题中，回答明确说明资料不足 |
| 回答命中 | 关键词 + 引用来源均满足 judge |

## 4. 产物

- `tests/fixtures/parse-report.json`：22 份文档解析/切分统计；
- `tests/fixtures/chunks.jsonl`：55 个 chunk 的文本与元数据；
- `tests/results/m1-parse-spotcheck.md`：3 chunk 人工抽查；
- `tests/results/m2-smoke.md`：真实 embedding + Chroma smoke；
- `tests/results/m2-index-report.json`：索引统计；
- `tests/results/m3-answer-trace.md`：单题全链路 trace；
- `tests/results/m4-lifecycle.md`：新增/删除/修改/重索引；
- `tests/results/m4-restart.md`：新进程读取持久化 Chroma；
- `tests/results/m4-failures.md`：格式、空文档、401 失败；
- `tests/results/eval-*.json/.md`：30 题评测原始结果；
- `tests/results/m5-final-summary.md`：最终指标、失败案例与限制；
- `tests/results/m5-clean-install.md`：项目外干净 venv 复现。

## 5. 运行

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\evaluate.py
```
