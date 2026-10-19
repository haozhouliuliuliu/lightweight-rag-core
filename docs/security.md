# 安全与配置说明

## 1. 密钥

- API key **只**从环境变量或本地 `.env` 读取；
- `.env`、`config.yaml` 已在 `.gitignore` 中；
- `config.example.yaml`、`.env.example` 只含占位值；
- 代码和日志不打印 key；错误信息只显示状态码/原因；
- 仓库提交前执行 key 扫描。

## 2. 外部服务与数据流向

| 数据 | 目的地 | 说明 |
| --- | --- | --- |
| chunk 文本 | 阿里云百炼 `text-embedding-v4` | 生成 1024 维向量 |
| 用户问题 | 阿里云百炼 `text-embedding-v4` | 生成查询向量 |
| 问题 + Top-K chunk | 阿里云百炼 `qwen-plus` | 生成回答 |
| 原始文档、Chroma 索引 | 本机 | `data/docs`、`data/chroma` |

> 文本会离开本机。仓库只使用虚构资料；不得导入真实企业资料、客户数据、个人信息或未授权内部文档。

## 3. 本地数据

- `data/docs`：虚构源文档，22 份，SHA-256 与enterprise-rag-kb manifest 一致；
- `data/chroma`：本地 Chroma 持久化目录，已 gitignore；
- `data/chroma` 可删除后重建，不包含密钥；
- 生命周期测试使用 `tests/fixtures` 的临时文本，测试结束后从知识库删除。

## 4. 失败与边界

- 缺 key/401：CLI 非零退出，不生成假索引或假回答；
- Embedding 维度不是 1024：中止；
- LLM 超时/失败：不返回“成功”回答；
- 删除文档：同步删除 manifest、源文件和 Chroma `doc_id` 向量；
- 重新索引：稳定 chunk ID + 删除旧向量，避免重复；
- Chroma HNSW 在无 AVX2 机器上若崩溃：可配置 `query_backend: brute_force`，仍使用 Chroma 存储；不得静默切换。

## 5. 已知限制

- 只有 CLI 接口，没有用户权限系统；
- 没有多租户隔离；
- 没有生产级审计、限流或加密存储；
- 以上均不属于本项目第一版范围。
