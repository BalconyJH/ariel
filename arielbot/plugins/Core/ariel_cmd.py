from nonebot import get_driver
from nonebot.adapters.milky import Bot as MilkyBot
from nonebot.adapters.milky import MessageEvent as MilkyMessageEvent
from nonebot.permission import SUPERUSER, Permission
from nonebot_plugin_alconna import Alconna, Args, CommandMeta, Match, on_alconna
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


def _is_superuser(session: Uninfo) -> bool:
    return session.user.id in get_driver().config.superusers


async def _send_message_reaction(bot: MilkyBot, event: MilkyMessageEvent, reaction: str) -> None:
    if event.data.message_scene != "group":
        return
    await bot._call(
        "send_group_message_reaction",
        {
            "group_id": event.data.peer_id,
            "message_seq": event.data.message_seq,
            "reaction": reaction,
            "reaction_type": "face",
            "is_add": True,
        },
    )


async def _ensure_admin_private(session: Uninfo, matcher) -> None:
    if _is_private_session(session):
        return
    await matcher.finish()


def _command_line(matcher) -> str:
    command = matcher.command()
    syntax = command.get_help().splitlines()[0].strip()
    if command.meta.description:
        return f"{syntax} - {command.meta.description}"
    return syntax


def _visible_help_matchers(session: Uninfo):
    matchers = [*GROUP_HELP_MATCHERS]
    if _is_superuser(session):
        matchers.extend(SUPERUSER_HELP_MATCHERS)
    return matchers


def _build_help_text(session: Uninfo, query: str | None = None) -> str:
    if query:
        target = query.strip()
        for matcher in _visible_help_matchers(session):
            command = matcher.command()
            if target == command.command or target == command.name:
                return command.get_help()
        return "没有找到可见的命令帮助"

    lines = ["Ariel Help", "", "Group Commands"]
    lines.extend(_command_line(matcher) for matcher in GROUP_HELP_MATCHERS)
    if _is_superuser(session):
        lines.extend(["", "Superuser Commands"])
        lines.extend(_command_line(matcher) for matcher in SUPERUSER_HELP_MATCHERS)
    lines.extend(["", "Use help <command> for command details."])
    return "\n".join(lines)


login = on_alconna(
    Alconna("login", meta=CommandMeta(description="scan bilibili login qrcode")),
    aliases={"登录"},
    permission=SUPERUSER,
)
add_sub = on_alconna(
    Alconna(
        "sub",
        Args["uid?", str],
        meta=CommandMeta(description="add a bilibili user subscription for this group"),
    ),
    rule=bot_is_active,
    aliases={"订阅"},
    permission=GROUP_AUTH,
)
del_sub = on_alconna(
    Alconna(
        "unsub",
        Args["uid?", str],
        meta=CommandMeta(description="disable a bilibili user subscription for this group"),
    ),
    rule=bot_is_active,
    aliases={"删除"},
    permission=GROUP_AUTH,
)
live_active = on_alconna(
    Alconna(
        "live_on",
        Args["uid?", str],
        meta=CommandMeta(description="enable live push for this group subscription"),
    ),
    rule=bot_is_active,
    permission=GROUP_AUTH,
)
live_deactivate = on_alconna(
    Alconna(
        "live_off",
        Args["uid?", str],
        meta=CommandMeta(description="disable live push for this group subscription"),
    ),
    rule=bot_is_active,
    permission=GROUP_AUTH,
)
dyn_active = on_alconna(
    Alconna(
        "dyn_on",
        Args["uid?", str],
        meta=CommandMeta(description="enable dynamic push for this group subscription"),
    ),
    rule=bot_is_active,
    permission=GROUP_AUTH,
)
dyn_deactivate = on_alconna(
    Alconna(
        "dyn_off",
        Args["uid?", str],
        meta=CommandMeta(description="disable dynamic push for this group subscription"),
    ),
    rule=bot_is_active,
    permission=GROUP_AUTH,
)
bot_active = on_alconna(
    Alconna("bot_on", meta=CommandMeta(description="enable bot push for this group")),
    permission=GROUP_AUTH,
)
bot_deactivate = on_alconna(
    Alconna("bot_off", meta=CommandMeta(description="disable bot push for this group")),
    permission=GROUP_AUTH,
)
sub_list = on_alconna(
    Alconna("list", meta=CommandMeta(description="show this group subscription list")),
    rule=bot_is_active,
    aliases={"列表"},
)
bot_help = on_alconna(
    Alconna(
        "help",
        Args["command?", str],
        meta=CommandMeta(description="show visible command help"),
    )
)
s_dyn = on_alconna(
    Alconna(
        "sd",
        Args["dyn_id?", str],
        meta=CommandMeta(description="search rendered dynamic by id"),
    )
)
get_img = on_alconna(
    Alconna(
        "img",
        Args["dyn_id?", str],
        meta=CommandMeta(description="search dynamic images by id"),
    )
)
admin_sub_add = on_alconna(
    Alconna(
        "admin_sub_add",
        Args["group_id?", str]["uid?", str],
        meta=CommandMeta(description="add a subscription for a target group"),
    ),
    permission=SUPERUSER,
)
admin_sub_del = on_alconna(
    Alconna(
        "admin_sub_del",
        Args["group_id?", str]["uid?", str],
        meta=CommandMeta(description="disable a subscription for a target group"),
    ),
    permission=SUPERUSER,
)
admin_live_on = on_alconna(
    Alconna(
        "admin_live_on",
        Args["group_id?", str]["uid?", str],
        meta=CommandMeta(description="enable live push for a target group subscription"),
    ),
    permission=SUPERUSER,
)
admin_live_off = on_alconna(
    Alconna(
        "admin_live_off",
        Args["group_id?", str]["uid?", str],
        meta=CommandMeta(description="disable live push for a target group subscription"),
    ),
    permission=SUPERUSER,
)
admin_dyn_on = on_alconna(
    Alconna(
        "admin_dyn_on",
        Args["group_id?", str]["uid?", str],
        meta=CommandMeta(description="enable dynamic push for a target group subscription"),
    ),
    permission=SUPERUSER,
)
admin_dyn_off = on_alconna(
    Alconna(
        "admin_dyn_off",
        Args["group_id?", str]["uid?", str],
        meta=CommandMeta(description="disable dynamic push for a target group subscription"),
    ),
    permission=SUPERUSER,
)
admin_sub_list = on_alconna(
    Alconna(
        "admin_sub_list",
        Args["group_id?", str],
        meta=CommandMeta(description="show target group subscriptions or all subscriptions"),
    ),
    permission=SUPERUSER,
)
admin_group_list = on_alconna(
    Alconna(
        "admin_group_list",
        meta=CommandMeta(description="show groups joined by current bot"),
    ),
    permission=SUPERUSER,
)


GROUP_HELP_MATCHERS = (
    add_sub,
    del_sub,
    live_active,
    live_deactivate,
    dyn_active,
    dyn_deactivate,
    bot_active,
    bot_deactivate,
    sub_list,
    s_dyn,
    get_img,
    bot_help,
)

SUPERUSER_HELP_MATCHERS = (
    login,
    admin_sub_add,
    admin_sub_del,
    admin_live_on,
    admin_live_off,
    admin_dyn_on,
    admin_dyn_off,
    admin_sub_list,
    admin_group_list,
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
async def _(bot: MilkyBot, event: MilkyMessageEvent, session: Uninfo, uid: Match[str]):
    target_uid = _extract_numeric(uid)
    if target_uid is None:
        await _send_message_reaction(bot, event, "187")
        await add_sub.finish()
    ctx = _ctx_from(session)
    await UpdateBotStatusTools.ensure_bot_status(ctx)
    await AddSubTools(target_uid).add_sub_processor(ctx)
    await _send_message_reaction(bot, event, "144")
    await add_sub.finish()


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
async def _(session: Uninfo, command: Match[str]):
    query = command.result if command.available else None
    await bot_help.finish(UniMessage.text(_build_help_text(session, query)))


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


@admin_group_list.handle()
async def _(session: Uninfo, bot: MilkyBot):
    await _ensure_admin_private(session, admin_group_list)
    groups = await bot.get_group_list(no_cache=True)
    if not groups:
        await admin_group_list.finish("Current bot has not joined any groups")
    lines = ["Joined Groups"]
    for group in sorted(groups, key=lambda item: item.group_id):
        lines.append(
            f"{group.group_id} {group.group_name} "
            f"({group.member_count}/{group.max_member_count})"
        )
    await admin_group_list.finish("\n".join(lines))
