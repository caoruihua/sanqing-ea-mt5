"""
该文件是放在仓库根目录下的主入口脚本，方便直接从项目根目录启动交易程序。

使用方式：
    uv run python run.py --config config/runtime.ini --once

说明：
- 这里只做入口转发；
- 真正的运行逻辑位于 `src.app.run`；
- 这样做是为了让入口不要埋得太深，便于日常使用。
"""

from src.app.run import main

if __name__ == "__main__":
    raise SystemExit(main())
