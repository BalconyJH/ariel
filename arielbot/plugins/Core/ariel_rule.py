from nonebot_plugin_uninfo import Uninfo

from arielbot.plugins.Core.ariel_database import DataManager


async def bot_is_active(session: Uninfo) -> bool:
    if session.scene.id is None:
        return False
    self_id = int(session.self_id)
    group_id = int(session.scene.id)
    async with DataManager() as m:
        result = await m.select_bot_status((self_id, group_id))
        if not result:
            await m.insert_bot_status((self_id, group_id, 1, 1))
            return True
        return bool(result[0] and result[1])
