# M4 异常与失败处理证据

| 场景 | 结果 | 证据 |
| --- | --- | --- |
| 不支持格式 | PASS | unsupported format: .csv |
| 空文档 | PASS | cannot import empty.txt: empty_document: file is empty (0 bytes) |
| Embedding 鉴权失败 | PASS | embedding request failed (AuthenticationError): Error code: 401 - {'error': {'message': 'Incorrect API key provided. For details, see: https://help.aliyun.com/z |
| LLM 鉴权失败 | PASS | LLM request failed (AuthenticationError): Error code: 401 - {'error': {'message': 'Incorrect API key provided. For details, see: https://help.aliyun.com/zh/mode |

## 自动化测试覆盖

- `tests/test_documents.py`：不支持格式、空文档、重复 id。
- `tests/test_embeddings.py::test_dimension_mismatch_raises`：Embedding 维度异常。
- `tests/test_answer.py::test_llm_failure_is_not_fake_answer`：LLM 超时抛出错误，不返回假回答。
- `tests/test_answer.py::test_no_retrieval_is_refusal_without_llm_call`：空检索直接拒答。
- `tests/test_lifecycle.py`：新增、删除、重新索引、重复索引。
- `tests/test_vector_store.py`：删除后 count=0、brute-force 回退路径。

## 结论

- 不支持的格式和空文档被拒绝；
- Embedding/LLM 鉴权失败均抛错，没有生成假向量或假回答；
- 自动化测试覆盖超时、维度、删除和重索引路径。
