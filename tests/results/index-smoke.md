# M2 真实 Embedding / Chroma 冒烟

## Embedding

- 模型：`text-embedding-v4`
- 维度：`1024`
- 返回条数：2
- 每条维度：[1024, 1024]
- 结论：真实 API 调用成功。

## Chroma

- 客户端：`EphemeralClient`（仅冒烟，不写入正式 collection）
- 后端：`hnsw`
- 写入条数：3
- 查询 Top-2：alpha (0.994), beta (0.110)
- 结论：HNSW query 正常，AVX2 兼容性门禁通过。
