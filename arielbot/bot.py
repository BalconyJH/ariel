from pathlib import Path

import nonebot
from nonebot.adapters.milky import Adapter as MilkyAdapter


nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(MilkyAdapter)

nonebot.load_plugin("nonebot_plugin_sentry")
nonebot.load_plugin("arielbot.plugins.Core")

plugins_dir = Path.cwd() / "plugins"
if plugins_dir.exists():
    nonebot.load_plugins(str(plugins_dir))

app = nonebot.get_asgi()
config = driver.config
