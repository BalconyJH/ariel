from typing import Any

from arclet.cithun import Permission
from nonebot import get_driver
from nonebot.adapters import Bot, Event
from nonebot_plugin_permission import require_permission, system

ADMIN_PERMISSION = "ariel.admin"
GROUP_MANAGE_PERMISSION = "ariel.group.manage"

admin_permission = require_permission(ADMIN_PERMISSION, default_available=False)
group_manage_permission = require_permission(GROUP_MANAGE_PERMISSION, default_available=False)


def _is_config_superuser(event: Event) -> bool:
    try:
        user_id = event.get_user_id()
    except Exception:
        return False
    return user_id in get_driver().config.superusers


def _event_data(event: Event) -> Any:
    return getattr(event, "data", None)


async def _is_group_manager(bot: Bot, event: Event) -> bool:
    data = _event_data(event)
    if data is None or getattr(data, "message_scene", None) != "group":
        return False
    member = getattr(data, "group_member", None)
    if member is not None:
        return getattr(member, "role", None) in {"admin", "owner"}
    if not hasattr(bot, "get_group_member_info"):
        return False
    group_id = getattr(data, "peer_id", None)
    user_id = getattr(data, "sender_id", None)
    if group_id is None or user_id is None:
        return False
    member = await bot.get_group_member_info(
        group_id=group_id,
        user_id=user_id,
    )
    return getattr(member, "role", None) in {"admin", "owner"}


@system.attach(
    lambda resource_id: resource_id.startswith("ariel.")
    or resource_id.startswith("command.permission.")
)
async def _attach_ariel_permissions(
    user,
    resource_id: str,
    context,
    current_mask: Permission,
    permission_lookup,
) -> Permission:
    if context is None:
        return Permission(0)
    event = context["event"]
    bot = context["bot"]
    if _is_config_superuser(event):
        return Permission("vma")
    if resource_id.startswith("ariel.group.") and await _is_group_manager(bot, event):
        return Permission("v-a")
    return Permission(0)
