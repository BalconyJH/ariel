from nonebot import get_driver, require
from nonebot.adapters import Bot

require("nonebot_plugin_apscheduler")
require("nonebot_plugin_alconna")
require("nonebot_plugin_uninfo")

from nonebot_plugin_apscheduler import scheduler

from arielbot.plugins.Core import ariel_cmd  # noqa: F401  register matchers
from arielbot.plugins.Core.ariel_push import DynPusher, LivePusher
from arielbot.plugins.Core.ariel_tools import UpdateBotStatusTools

driver = get_driver()


@driver.on_bot_connect
async def _(bot: Bot):
    await UpdateBotStatusTools.update_bot_active_processor((1, bot.self_id))


@driver.on_bot_disconnect
async def _(bot: Bot):
    await UpdateBotStatusTools.update_bot_active_processor((0, bot.self_id))


@driver.on_shutdown
async def _():
    await UpdateBotStatusTools.shutdown_all_bot()


@scheduler.scheduled_job(
    "cron",
    second="*/8",
    id="dyn_pusher",
    name="push_dynamic",
    max_instances=1,
)
async def push_dynamic():
    pusher = DynPusher()
    await pusher.push_dynamic()


@scheduler.scheduled_job(
    "cron",
    second="*/10",
    id="live_pusher",
    name="push_live",
    max_instances=1,
)
async def push_live():
    pusher = LivePusher()
    await pusher.push_live()
