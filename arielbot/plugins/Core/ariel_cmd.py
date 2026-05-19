from nonebot.permission import SUPERUSER, Permission
from nonebot_plugin_alconna import Alconna, Args, Match, on_alconna
from nonebot_plugin_alconna.uniseg import MsgTarget, Target, UniMessage
from nonebot_plugin_uninfo import Uninfo

from arielbot.plugins.Core.ariel_push import DynPusher
from arielbot.plugins.Core.ariel_rule import bot_is_active
from arielbot.plugins.Core.ariel_tools import (
    AddSubTools,
    ChannelCtx,
    DelSubTools,
    LoginTools,
    SubListTools,
    UpdateBotStatusTools,
    UpdateSubTools,
)


async def _is_group_admin(session: Uninfo) -> bool:
    member = session.member
    if member is None or member.role is None:
        return False
    return member.role.id in {"ADMINISTRATOR", "OWNER"}


GROUP_AUTH = SUPERUSER | Permission(_is_group_admin)


def _ctx_from(session: Uninfo) -> ChannelCtx:
    return ChannelCtx(self_id=int(session.self_id), group_id=int(session.scene.id))


def _admin_ctx_from(session: Uninfo, group_id: str) -> ChannelCtx:
    return ChannelCtx(self_id=int(session.self_id), group_id=int(group_id))


def _extract_numeric(value: Match[str]) -> str | None:
    if not value.available:
        return None
    text = value.result.strip()
    return text if text.isdigit() else None


def _is_private_session(session: Uninfo) -> bool:
    return session.scene.is_private


async def _ensure_admin_private(session: Uninfo, matcher) -> None:
    if _is_private_session(session):
        return
    await matcher.finish()


login = on_alconna(Alconna("login"), aliases={"登录"}, permission=SUPERUSER)
add_sub = on_alconna(
    Alconna("sub", Args["uid?", str]),
    rule=bot_is_active,
    aliases={"订阅"},
    permission=GROUP_AUTH,
)
del_sub = on_alconna(
    Alconna("unsub", Args["uid?", str]),
    rule=bot_is_active,
    aliases={"删除"},
    permission=GROUP_AUTH,
)
live_active = on_alconna(
    Alconna("live_on", Args["uid?", str]),
    rule=bot_is_active,
    permission=GROUP_AUTH,
)
live_deactivate = on_alconna(
    Alconna("live_off", Args["uid?", str]),
    rule=bot_is_active,
    permission=GROUP_AUTH,
)
dyn_active = on_alconna(
    Alconna("dyn_on", Args["uid?", str]),
    rule=bot_is_active,
    permission=GROUP_AUTH,
)
dyn_deactivate = on_alconna(
    Alconna("dyn_off", Args["uid?", str]),
    rule=bot_is_active,
    permission=GROUP_AUTH,
)
bot_active = on_alconna(Alconna("bot_on"), permission=GROUP_AUTH)
bot_deactivate = on_alconna(Alconna("bot_off"), permission=GROUP_AUTH)
sub_list = on_alconna(Alconna("list"), rule=bot_is_active, aliases={"列表"})
bot_help = on_alconna(Alconna("help"))
s_dyn = on_alconna(Alconna("sd", Args["dyn_id?", str]))
get_img = on_alconna(Alconna("img", Args["dyn_id?", str]))
admin_sub_add = on_alconna(
    Alconna("admin_sub_add", Args["group_id?", str]["uid?", str]),
    permission=SUPERUSER,
)
admin_sub_del = on_alconna(
    Alconna("admin_sub_del", Args["group_id?", str]["uid?", str]),
    permission=SUPERUSER,
)
admin_live_on = on_alconna(
    Alconna("admin_live_on", Args["group_id?", str]["uid?", str]),
    permission=SUPERUSER,
)
admin_live_off = on_alconna(
    Alconna("admin_live_off", Args["group_id?", str]["uid?", str]),
    permission=SUPERUSER,
)
admin_dyn_on = on_alconna(
    Alconna("admin_dyn_on", Args["group_id?", str]["uid?", str]),
    permission=SUPERUSER,
)
admin_dyn_off = on_alconna(
    Alconna("admin_dyn_off", Args["group_id?", str]["uid?", str]),
    permission=SUPERUSER,
)
admin_sub_list = on_alconna(
    Alconna("admin_sub_list", Args["group_id?", str]),
    permission=SUPERUSER,
)


@get_img.handle()
async def _(dyn_id: Match[str]):
    target_id = _extract_numeric(dyn_id)
    if target_id is None:
        await get_img.finish()
    message = await DynPusher.search_dyn_img_by_id(target_id)
    if message is None:
        await get_img.finish()
    await get_img.finish(message)


@s_dyn.handle()
async def _(dyn_id: Match[str]):
    target_id = _extract_numeric(dyn_id)
    if target_id is None:
        await s_dyn.finish()
    dyn_img = await DynPusher.search_dyn_by_id(target_id)
    if dyn_img is None:
        await s_dyn.finish()
    await s_dyn.finish(dyn_img)


@login.handle()
async def _(target: MsgTarget):
    await LoginTools().login_handle(target)
    await login.finish()


@add_sub.handle()
async def _(session: Uninfo, uid: Match[str]):
    target_uid = _extract_numeric(uid)
    if target_uid is None:
        await add_sub.finish("请携带正确的uid后重试")
    result = await AddSubTools(target_uid).add_sub_processor(_ctx_from(session))
    await add_sub.finish(result)


@del_sub.handle()
async def _(session: Uninfo, uid: Match[str]):
    target_uid = _extract_numeric(uid)
    if target_uid is None:
        await del_sub.finish("请携带正确的uid后重试")
    result = await DelSubTools(target_uid).del_sub_processor(_ctx_from(session))
    await del_sub.finish(result)


@live_active.handle()
async def _(session: Uninfo, uid: Match[str]):
    target_uid = _extract_numeric(uid)
    if target_uid is None:
        await live_active.finish("请携带正确的uid后重试")
    result = await UpdateSubTools(target_uid).update_sub_handler(_ctx_from(session), 1)
    await live_active.finish(result)


@live_deactivate.handle()
async def _(session: Uninfo, uid: Match[str]):
    target_uid = _extract_numeric(uid)
    if target_uid is None:
        await live_deactivate.finish("请携带正确的uid后重试")
    result = await UpdateSubTools(target_uid).update_sub_handler(_ctx_from(session), 0)
    await live_deactivate.finish(result)


@dyn_active.handle()
async def _(session: Uninfo, uid: Match[str]):
    target_uid = _extract_numeric(uid)
    if target_uid is None:
        await dyn_active.finish("请携带正确的uid后重试")
    result = await UpdateSubTools(target_uid).update_sub_handler(_ctx_from(session), dyn_active=1)
    await dyn_active.finish(result)


@dyn_deactivate.handle()
async def _(session: Uninfo, uid: Match[str]):
    target_uid = _extract_numeric(uid)
    if target_uid is None:
        await dyn_deactivate.finish("请携带正确的uid后重试")
    result = await UpdateSubTools(target_uid).update_sub_handler(_ctx_from(session), dyn_active=0)
    await dyn_deactivate.finish(result)


@bot_active.handle()
async def _(session: Uninfo):
    result = await UpdateBotStatusTools().update_bot_status_processor(_ctx_from(session), 1)
    await bot_active.finish(result)


@bot_deactivate.handle()
async def _(session: Uninfo):
    result = await UpdateBotStatusTools().update_bot_status_processor(_ctx_from(session), 0)
    if result is None:
        await bot_deactivate.finish()
    await bot_deactivate.finish(result)


@bot_help.handle()
async def _():
    await bot_help.finish(
        UniMessage.image(
            url="https://i0.hdslb.com/bfs/new_dyn/abef945ad1d209ad1d2360624180a15d490040351.png"
        )
    )


@sub_list.handle()
async def _(session: Uninfo):
    msg = await SubListTools().get_sub_list_data(_ctx_from(session))
    await sub_list.finish(msg)


@admin_sub_add.handle()
async def _(session: Uninfo, group_id: Match[str], uid: Match[str]):
    await _ensure_admin_private(session, admin_sub_add)
    target_group_id = _extract_numeric(group_id)
    if target_group_id is None:
        await admin_sub_add.finish("请携带正确的群号后重试")
    target_uid = _extract_numeric(uid)
    if target_uid is None:
        await admin_sub_add.finish("请携带正确的uid后重试")
    ctx = _admin_ctx_from(session, target_group_id)
    await UpdateBotStatusTools.ensure_bot_status(ctx)
    result = await AddSubTools(target_uid).add_sub_processor(ctx)
    await admin_sub_add.finish(result)


@admin_sub_del.handle()
async def _(session: Uninfo, group_id: Match[str], uid: Match[str]):
    await _ensure_admin_private(session, admin_sub_del)
    target_group_id = _extract_numeric(group_id)
    if target_group_id is None:
        await admin_sub_del.finish("请携带正确的群号后重试")
    target_uid = _extract_numeric(uid)
    if target_uid is None:
        await admin_sub_del.finish("请携带正确的uid后重试")
    result = await DelSubTools(target_uid).del_sub_processor(_admin_ctx_from(session, target_group_id))
    await admin_sub_del.finish(result)


@admin_live_on.handle()
async def _(session: Uninfo, group_id: Match[str], uid: Match[str]):
    await _ensure_admin_private(session, admin_live_on)
    target_group_id = _extract_numeric(group_id)
    if target_group_id is None:
        await admin_live_on.finish("请携带正确的群号后重试")
    target_uid = _extract_numeric(uid)
    if target_uid is None:
        await admin_live_on.finish("请携带正确的uid后重试")
    ctx = _admin_ctx_from(session, target_group_id)
    await UpdateBotStatusTools.ensure_bot_status(ctx)
    result = await UpdateSubTools(target_uid).update_sub_handler(ctx, 1)
    await admin_live_on.finish(result)


@admin_live_off.handle()
async def _(session: Uninfo, group_id: Match[str], uid: Match[str]):
    await _ensure_admin_private(session, admin_live_off)
    target_group_id = _extract_numeric(group_id)
    if target_group_id is None:
        await admin_live_off.finish("请携带正确的群号后重试")
    target_uid = _extract_numeric(uid)
    if target_uid is None:
        await admin_live_off.finish("请携带正确的uid后重试")
    ctx = _admin_ctx_from(session, target_group_id)
    await UpdateBotStatusTools.ensure_bot_status(ctx)
    result = await UpdateSubTools(target_uid).update_sub_handler(ctx, 0)
    await admin_live_off.finish(result)


@admin_dyn_on.handle()
async def _(session: Uninfo, group_id: Match[str], uid: Match[str]):
    await _ensure_admin_private(session, admin_dyn_on)
    target_group_id = _extract_numeric(group_id)
    if target_group_id is None:
        await admin_dyn_on.finish("请携带正确的群号后重试")
    target_uid = _extract_numeric(uid)
    if target_uid is None:
        await admin_dyn_on.finish("请携带正确的uid后重试")
    ctx = _admin_ctx_from(session, target_group_id)
    await UpdateBotStatusTools.ensure_bot_status(ctx)
    result = await UpdateSubTools(target_uid).update_sub_handler(ctx, dyn_active=1)
    await admin_dyn_on.finish(result)


@admin_dyn_off.handle()
async def _(session: Uninfo, group_id: Match[str], uid: Match[str]):
    await _ensure_admin_private(session, admin_dyn_off)
    target_group_id = _extract_numeric(group_id)
    if target_group_id is None:
        await admin_dyn_off.finish("请携带正确的群号后重试")
    target_uid = _extract_numeric(uid)
    if target_uid is None:
        await admin_dyn_off.finish("请携带正确的uid后重试")
    ctx = _admin_ctx_from(session, target_group_id)
    await UpdateBotStatusTools.ensure_bot_status(ctx)
    result = await UpdateSubTools(target_uid).update_sub_handler(ctx, dyn_active=0)
    await admin_dyn_off.finish(result)


@admin_sub_list.handle()
async def _(session: Uninfo, group_id: Match[str]):
    await _ensure_admin_private(session, admin_sub_list)
    if not group_id.available:
        await admin_sub_list.finish("请携带正确的群号后重试")
    target_group_id = group_id.result.strip()
    tools = SubListTools()
    if target_group_id == "all":
        msg = await tools.get_admin_sub_list_all(int(session.self_id))
        await admin_sub_list.finish(msg)
    if not target_group_id.isdigit():
        await admin_sub_list.finish("请携带正确的群号后重试")
    msg = await tools.get_sub_list_data(_admin_ctx_from(session, target_group_id))
    await admin_sub_list.finish(msg)
