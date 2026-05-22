from pathlib import Path

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter


nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

nonebot.load_plugin("arielbot.plugins.Core")

plugins_dir = Path.cwd() / "plugins"
if plugins_dir.exists():
    nonebot.load_plugins(str(plugins_dir))

app = nonebot.get_asgi()
config = driver.config
