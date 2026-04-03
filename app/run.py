"""
该文件是 `python -m app.run` 形式的兼容包装入口。

说明：
- 真正逻辑位于 `src.app.run`；
- 保留这个包装层，是为了兼容历史命令和测试脚本；
- 推荐优先使用仓库根目录下的 `run.py` 作为主入口。
"""

from src.app.run import main

if __name__ == "__main__":
    raise SystemExit(main())
