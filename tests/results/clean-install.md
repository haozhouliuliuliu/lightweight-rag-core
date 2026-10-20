# M5 干净环境复现记录

- 日期：2026-10-19
- 目标：在项目目录之外新建 venv，按 README 安装依赖并运行测试，验证不是依赖当前 `.venv` 的偶然状态。

## 环境

| 项目 | 值 |
| --- | --- |
| Python | 3.12.14 |
| 干净 venv | `C:\RAG库\venvs\lightweight-rag-core-clean` |
| 安装命令 | `.venv\Scripts\python.exe -m pip install -r requirements.txt`（等价 venv 命令） |
| 依赖检查 | `pip check` → **No broken requirements found** |
| 测试 | `pytest -q` → **37 passed** |

## 关键输出

```text
InstallExit=0
No broken requirements found.
.....................................                                    [100%]
37 passed in 3.92s
CleanPytestExit=0
3.12.14
C:\RAG库\venvs\lightweight-rag-core-clean
```

## 结论

- 从空 venv 安装 `requirements.txt` 成功；
- 不依赖仓库内 `.venv` 的缓存；
- 37 个测试全部通过；
- 真实 API 测试未在干净环境重复调用，避免重复费用；真实调用证据见 M2/M3/M4 报告。
