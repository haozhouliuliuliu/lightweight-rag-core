# M4 新进程读取持久化 Chroma

- 运行时间：2026-10-19T15:09:48+08:00
- 新进程 PID：7372
- 持久化目录：`C:\RAG库\lightweight-rag-core\data\chroma`
- collection：`lightweight-rag-core`
- 读取 count：**55**
- 检索 Top-5 条数：5
- Top-5 来源：1. X-100 便携式扭矩校验仪产品说明书 (chunk_id=4)；2. X-100S 便携式扭矩校验仪产品说明书 (chunk_id=2)；3. X-100 整机物料清单 (chunk_id=1)；4. X-100 便携式扭矩校验仪产品说明书 (chunk_id=3)；5. X-100 便携式扭矩校验仪产品说明书 (chunk_id=1)

结论：**新进程**可以读取已持久化的 Chroma 索引，不依赖上一次进程内存。
