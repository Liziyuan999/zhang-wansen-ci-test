# -*- coding: utf-8 -*-
"""pytest 公共配置。

仓库里有四个"脚本式"验证件：test_admin.py / test_smoke.py / smoke_org.py / sse_live_check.py。
它们的共同特征是模块级直接执行、依赖真实数据库与外部 LLM 服务、结尾调用 sys.exit()，
其中 test_admin.py 在 import 阶段就会跑完整流程。
pytest 收集阶段会 import 这些模块，一旦执行就会抛 SystemExit，导致
INTERNALERROR: SystemExit(1) 甚至整个测试会话崩溃。

因此在这里把它们排除出 pytest 的收集范围，让 `pytest tests/` 只跑真正的单元测试
（tests/test_unit_core.py），这条命令也是 Docker 构建时测试门禁的执行入口。

这些脚本依然可以手动运行，用法不变：

    python tests/test_smoke.py     # 端到端冒烟（需数据库 + LLM Key）
    python tests/test_admin.py     # 管理员后台验证
    python tests/smoke_org.py      # 多组织隔离验证
    python tests/sse_live_check.py # SSE 流式实时检查

被排除的只是"自动收集"，不是"删除能力"。
"""
import sys
from pathlib import Path

# 保证 pytest 以 server/ 为根导入 app 包
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 脚本式用例：模块级即执行 + sys.exit()，不能交给 pytest 收集
collect_ignore = [
    "test_admin.py",
    "test_smoke.py",
    "smoke_org.py",
    "sse_live_check.py",
]

# 兜底：任何以 smoke / live 命名的脚本都不参与自动收集
collect_ignore_glob = [
    "smoke_*.py",
    "*_live_*.py",
]


def pytest_report_header(config):
    """在测试输出头部打印一行说明，方便排查门禁到底跑了什么。"""
    return "KnowSeek 测试门禁：仅收集 tests/test_unit_core.py，脚本式验证件已通过 conftest 排除"
