import pickle
import time
from dataclasses import dataclass
from io import BytesIO

import qrcode
import qrcode.image.pure
from nonebot import logger
from nonebot_plugin_alconna.uniseg import Target, UniMessage
from urllib.parse import parse_qs, urlsplit

from arielbot.plugins.Core.ariel_bili import Login, UserInfo
from arielbot.plugins.Core.ariel_database import DataManager


@dataclass(frozen=True)
class ChannelCtx:
    self_id: int
    group_id: int


class LoginTools:

    async def login_handle(self, target: Target):
        login = Login()
        scan_url = await login.get_qrcode_key()
        if scan_url is None:
            await UniMessage.text("获取扫码链接失败").send(target=target)
            return
        qrcode_buffer = BytesIO()
        qr = qrcode.QRCode()
        qr.add_data(scan_url)
        img = qr.make_image(image_factory=qrcode.image.pure.PyPNGImage)
        img.save(qrcode_buffer)
        await UniMessage.image(raw=qrcode_buffer.getvalue()).send(target=target)
        while True:
            scan_result = await login.check_scan_result()
            if scan_result is None or scan_result["code"] == 86038:
                await UniMessage.text("登陆失败").send(target=target)
                break
            if scan_result["code"] == 0:
                cookies = await self.__parse_cookie(scan_result)
                if cookies is None:
                    await UniMessage.text("cookie 解析失败").send(target=target)
                    break
                async with DataManager() as d:
                    await d.clean_cookie()
                    await d.insert_cookie((pickle.dumps(cookies), scan_result["refresh_token"]))
                break
            time.sleep(3)

    async def __parse_cookie(self, data):
        try:
            query_str = urlsplit(data["url"]).query
            params = parse_qs(query_str)
            cookies = {k: v[0] for k, v in params.items()}
            cookies.pop("gourl")
            return cookies
        except Exception:
            logger.exception("Failed to parse Bilibili login cookie")
            return None


class PublicSubTools:
    def __init__(self, uid):
        self.uid = uid

    async def check_uid_info(self):
        uinfo = UserInfo()
        data = await uinfo.get_user_info_by_uid(self.uid)
        return data

    async def check_uid_in_group(self, bot: int, group_id: int):
        async with DataManager() as m:
            return await m.select_sub_channel((self.uid, group_id, bot))

    async def check_uid_has_sub(self):
        async with DataManager() as m:
            return await m.select_sub_target(self.uid)

    async def follow_user(self, uid, act):
        uinfo = UserInfo()
        return await uinfo.change_follow_status(uid, act)


class AddSubTools(PublicSubTools):
    def __init__(self, uid):
        super().__init__(uid)

    async def add_sub_processor(self, ctx: ChannelCtx):
        check_sub_result = await self.check_uid_has_sub()
        if check_sub_result:
            check_uid_in_group_result = await self.check_uid_in_group(ctx.self_id, ctx.group_id)
            if check_uid_in_group_result:
                if check_uid_in_group_result[0] == 0 or check_uid_in_group_result[1] == 0:
                    async with DataManager() as m:
                        await m.update_sub_channel((1, 1, self.uid, ctx.group_id, ctx.self_id))
                    return f"成功添加订阅 --> {check_sub_result[0]}({self.uid})"
                else:
                    return f"本群已订阅过 --> {check_sub_result[0]}({self.uid})"
            else:
                async with DataManager() as m:
                    await m.insert_sub_channel((self.uid, ctx.group_id, ctx.self_id))
                return f"成功添加订阅 --> {check_sub_result[0]}({self.uid})"
        else:
            uid_info = await self.check_uid_info()
            if isinstance(uid_info, str):
                return uid_info
            if not uid_info["following"]:
                follow_result = await self.follow_user(self.uid, 1)
                if not follow_result:
                    return "添加订阅失败"
            async with DataManager() as m:
                await m.insert_sub_target((self.uid, uid_info["card"]["name"], 0))
                await m.insert_sub_channel((self.uid, ctx.group_id, ctx.self_id))
            return f"成功添加订阅 --> {uid_info['card']['name']}({self.uid})"


class DelSubTools(PublicSubTools):
    def __init__(self, uid):
        super().__init__(uid)

    async def del_sub_processor(self, ctx: ChannelCtx):
        check_uid_in_group_result = await self.check_uid_in_group(ctx.self_id, ctx.group_id)
        if not check_uid_in_group_result:
            return f"本群没有订阅 --> {self.uid}"
        else:
            async with DataManager() as m:
                await m.delete_sub_channel((self.uid, ctx.group_id, ctx.self_id))
                uid_info = await m.select_sub_target(self.uid)
            return f"成功删除订阅 --> {uid_info[0]}({self.uid})"


class UpdateSubTools(PublicSubTools):
    def __init__(self, uid):
        super().__init__(uid)

    async def update_sub_handler(self, ctx: ChannelCtx, live_active: int = None, dyn_active: int = None):
        check_uid_in_group_result = await self.check_uid_in_group(ctx.self_id, ctx.group_id)
        if not check_uid_in_group_result:
            return f"本群没有订阅 --> {self.uid}"
        old_live_active = check_uid_in_group_result[0]
        old_dyn_active = check_uid_in_group_result[1]
        async with DataManager() as m:
            if live_active is None:
                await m.update_sub_channel((old_live_active, dyn_active, self.uid, ctx.group_id, ctx.self_id))
                return "开启动态推送成功" if dyn_active == 1 else "关闭动态推送成功"
            else:
                await m.update_sub_channel((live_active, old_dyn_active, self.uid, ctx.group_id, ctx.self_id))
                return "开启直播推送成功" if live_active == 1 else "关闭直播推送成功"


class UpdateBotStatusTools:
    @staticmethod
    async def ensure_bot_status(ctx: ChannelCtx):
        async with DataManager() as m:
            result = await m.select_bot_status((ctx.self_id, ctx.group_id))
            if result:
                return
            await m.insert_bot_status((ctx.self_id, ctx.group_id, 1, 1))

    async def update_bot_status_processor(self, ctx: ChannelCtx, status_new):
        async with DataManager() as m:
            result = await m.select_bot_status((ctx.self_id, ctx.group_id))
            if not result:
                await m.insert_bot_status((ctx.self_id, ctx.group_id, status_new, 1))
                return f"bot已开启 --> {ctx.self_id}/{ctx.group_id}" if status_new == 1 else f"bot已关闭 --> {ctx.self_id}/{ctx.group_id}"
            if status_new == result[0]:
                return None if status_new == 0 else f"bot已经为开启状态 --> {ctx.self_id}/{ctx.group_id}"
            else:
                await m.update_bot_push_status((status_new, ctx.self_id, ctx.group_id))
                return f"bot关闭成功 --> {ctx.self_id}/{ctx.group_id}" if status_new == 0 else f"bot开启成功 --> {ctx.self_id}/{ctx.group_id}"

    @staticmethod
    async def update_bot_active_processor(bot_active_status):
        async with DataManager() as m:
            await m.update_bot_active_status(bot_active_status)

    @staticmethod
    async def shutdown_all_bot():
        async with DataManager() as m:
            result = await m.select_all_bot()
            if not result:
                return
            for i in result:
                logger.info(f"Mark bot offline during shutdown: bot_id={i[0]}")
                await m.update_bot_active_status((0, i[0]))


class SubListTools:
    @staticmethod
    def __subscription_line(uid: str, nickname: str, live_active: int, dyn_active: int) -> str:
        live_text = "开" if live_active == 1 else "关"
        dyn_text = "开" if dyn_active == 1 else "关"
        return f"{uid} / {nickname} / live:{live_text} / dyn:{dyn_text}"

    @staticmethod
    def __status_text(status: tuple | None) -> str:
        if status is None:
            return "push:未初始化 / bot:未初始化"
        push_text = "开" if status[0] == 1 else "关"
        bot_text = "在线" if status[1] == 1 else "离线"
        return f"push:{push_text} / bot:{bot_text}"

    async def get_sub_list_data(self, ctx: ChannelCtx) -> UniMessage:
        async with DataManager() as m:
            all_data = await m.select_sub_list((ctx.self_id, ctx.group_id))
        if not all_data:
            return UniMessage.text("本群订阅列表为空")
        lines = ["本群订阅列表"]
        for uid, nickname, live_active, dyn_active in all_data:
            lines.append(self.__subscription_line(uid, nickname, live_active, dyn_active))
        return UniMessage.text("\n".join(lines))

    async def get_admin_sub_list_data(self, ctx: ChannelCtx) -> UniMessage:
        async with DataManager() as m:
            status = await m.select_bot_status((ctx.self_id, ctx.group_id))
            all_data = await m.select_sub_list((ctx.self_id, ctx.group_id))
        lines = [
            f"Bot {ctx.self_id} / Group {ctx.group_id}",
            self.__status_text(status),
        ]
        if not all_data:
            lines.append("当前群订阅列表为空")
            return UniMessage.text("\n".join(lines))
        for uid, nickname, live_active, dyn_active in all_data:
            lines.append(self.__subscription_line(uid, nickname, live_active, dyn_active))
        return UniMessage.text("\n".join(lines))

    async def get_admin_sub_list_all(self, self_id: int) -> UniMessage:
        async with DataManager() as m:
            all_data = await m.select_sub_list_by_bot(self_id)
            all_status = await m.select_bot_status_by_bot(self_id)
        status_by_group = {group_id: (push_active, bot_active) for group_id, push_active, bot_active in all_status}
        data_by_group: dict[int, list[tuple]] = {}
        for item in all_data:
            data_by_group.setdefault(item[0], []).append(item)
        group_ids = sorted(set(status_by_group) | set(data_by_group))
        if not group_ids:
            return UniMessage.text("当前 bot 没有任何订阅")
        lines: list[str] = []
        for group_id in group_ids:
            lines.append(f"群 {group_id}")
            lines.append(self.__status_text(status_by_group.get(group_id)))
            group_items = data_by_group.get(group_id, [])
            if not group_items:
                lines.append("当前群订阅列表为空")
                lines.append("")
                continue
            for _, uid, nickname, live_active, dyn_active in group_items:
                lines.append(self.__subscription_line(uid, nickname, live_active, dyn_active))
            lines.append("")
        return UniMessage.text("\n".join(lines[:-1]))
