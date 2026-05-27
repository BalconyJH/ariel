import pickle
import skia
import asyncio
import time
from nonebot import logger
from io import BytesIO
from dynrender_skia.Core import DynRender
from nonebot_plugin_alconna.uniseg import Target, UniMessage
from arielbot.ariel_sentry import sentry_span
from arielbot.plugins.Core.ariel_database import DataManager
from arielbot.plugins.Core.ariel_bili import Dynamic,Live
from arielbot.plugins.Core.ariel_live_state import should_suppress_live_push


class PublicPusher:
    async def assign_tasks(self,task):
        with sentry_span("ariel.push.assign", "assign push tasks", target_count=len(task["target"])):
            await asyncio.gather(*[self.process_task(i,task["message"]) for i in task["target"]])
    
    async def process_task(self,push_target,message):
        target = Target(str(push_target[0]), self_id=str(push_target[1]))
        with sentry_span(
            "ariel.push.send",
            "send push message",
            target_id=str(push_target[0]),
            self_id=str(push_target[1]),
        ):
            await message.send(target=target)


class DynPusher(PublicPusher):
    
    async def push_dynamic(self):
        with sentry_span("ariel.push.dynamic", "push dynamic") as span:
            follow_dynamic_list = await Dynamic().get_dynamic_from_follow_list()
            if follow_dynamic_list is None:
                span.set_data("fetch.result", "empty")
                return
            span.set_data("dynamic.count", len(follow_dynamic_list))
            task_list = []
            async with DataManager() as m:
                for dynamic in follow_dynamic_list:
                    result = await m.select_dyn_content(dynamic.message_id)
                    if result:
                        continue
                    logger.info(
                        f"Detected new dynamic: uid={dynamic.header.mid}, "
                        f"dynamic_id={dynamic.message_id}, uname={dynamic.header.name}"
                    )
                    all_push_group = await m.select_dynamic_push(dynamic.header.mid)
                    await m.insert_dyn_data((dynamic.message_id,dynamic.header.name,pickle.dumps(dynamic)))
                    if not all_push_group:
                        logger.debug(
                            f"Skip dynamic push without subscribers: "
                            f"uid={dynamic.header.mid}, dynamic_id={dynamic.message_id}"
                        )
                        continue
                    span.set_data("dynamic.push_target_count", len(all_push_group))
                    with sentry_span(
                        "ariel.render.dynamic",
                        "render dynamic image",
                        dynamic_id=dynamic.message_id,
                        uid=dynamic.header.mid,
                    ):
                        img = await DynRender(font_family="Noto Sans CJK SC").run(dynamic)
                        img = skia.Image.fromarray(img, colorType=skia.ColorType.kRGBA_8888_ColorType)
                        img_buffer = BytesIO()
                        img.save(img_buffer)
                    message = UniMessage.text(
                        f"{dynamic.header.name}发布了新动态:\n\n"
                        f"传送门→https://t.bilibili.com/{dynamic.message_id}"
                    ) + UniMessage.image(raw=img_buffer.getvalue())
                    task_list.append({"target":all_push_group,"message":message})
            span.set_data("push.task_count", len(task_list))
            if task_list:
                await asyncio.gather(*[self.assign_tasks(i) for i in task_list])
    
    @staticmethod
    async def search_dyn_by_id(message_id):
        async with DataManager() as m:
            dynamic = await m.select_dyn_content(message_id)
        if not dynamic:
            obj = Dynamic()
            dynamic = await obj.get_dynamic_from_id(message_id)
            if dynamic is None:
                return
            else:
                async with DataManager() as m:
                    await m.insert_dyn_data((message_id,dynamic.header.name,pickle.dumps(dynamic)))
        else:
            dynamic = pickle.loads(dynamic[0])
        with sentry_span("ariel.render.dynamic", "render dynamic image", dynamic_id=message_id):
            img = await DynRender(font_family="Noto Sans CJK SC").run(dynamic)
            img = skia.Image.fromarray(img, colorType=skia.ColorType.kRGBA_8888_ColorType)
            img_buffer = BytesIO()
            img.save(img_buffer)
        return UniMessage.image(raw=img_buffer.getvalue())

    @staticmethod
    async def search_dyn_img_by_id(message_id):
        async with DataManager() as m:
            dynamic = await m.select_dyn_content(message_id)
        if not dynamic:
            obj = Dynamic()
            dynamic = await obj.get_dynamic_from_id(message_id)
            if dynamic is None:
                return
            else:
                async with DataManager() as m:
                    await m.insert_dyn_data((message_id,dynamic.header.name,pickle.dumps(dynamic)))
        else:
            dynamic = pickle.loads(dynamic[0])
        if dynamic.major.type == "MAJOR_TYPE_OPUS":
            message = UniMessage()
            for pic in dynamic.major.opus.pics:
                message += UniMessage.image(url=pic.url)
            return message
        else:
            return "此动态没有图片"
        
        

                
                
        
class LivePusher(PublicPusher):
    
    async def push_live(self):
        with sentry_span("ariel.push.live", "push live") as span:
            async with DataManager() as m:
                all_check_uid_list = await m.select_live_check_uid()
            if not all_check_uid_list:
                span.set_data("live.check_uid_count", 0)
                return
            span.set_data("live.check_uid_count", len(all_check_uid_list))
            all_live_statuses = {f"{i[0]}":(i[1], i[2]) for i in all_check_uid_list}
            all_check_uid_list = [i[0] for i in all_check_uid_list]
            check_result= await Live().get_room_info_by_uids(all_check_uid_list)
            if check_result  is None:
                span.set_data("live.fetch_result", "empty")
                return
            span.set_data("live.room_count", len(check_result))
            detected_at = int(time.time())
            tasks = []
            for k,v in check_result.items():
                if v["live_status"] !=1:
                    v["live_status"]=0

                live_status, last_live_end_time = all_live_statuses[k]
                if live_status == v["live_status"]:
                    continue
                if live_status == 1:
                    async with DataManager() as m:
                        await m.update_sub_target_live_end((v["uname"],0,detected_at,v["uid"]))
                    logger.info(f"Detected live end: uid={v['uid']}, uname={v['uname']}")
                    continue
                suppress_live_push = should_suppress_live_push(last_live_end_time, detected_at)
                async with DataManager() as m:
                    await m.update_sub_target((v["uname"],1,v["uid"]))
                    if not suppress_live_push:
                        all_push_target = await m.select_live_push(v["uid"])
                if suppress_live_push:
                    elapsed = detected_at - last_live_end_time if last_live_end_time is not None else None
                    logger.info(
                        f"Suppress live restart push: uid={v['uid']}, "
                        f"uname={v['uname']}, elapsed={elapsed}"
                    )
                    continue
                if not all_push_target:
                    logger.debug(f"Skip live push without subscribers: uid={v['uid']}, uname={v['uname']}")
                    continue
                logger.info(
                    f"Detected live start: uid={v['uid']}, uname={v['uname']}, "
                    f"target_count={len(all_push_target)}"
                )
                message = UniMessage.text(
                    f"【{v['uname']}】开播啦!!!\n\n"
                    f"标题：{v['title']}\n\n"
                    f"传送门：https://live.bilibili.com/{v['room_id']}"
                ) + UniMessage.image(url=v["cover_from_user"])
                tasks.append({"target":all_push_target,"message":message})
            span.set_data("push.task_count", len(tasks))
            if tasks:
                await asyncio.gather(*[self.assign_tasks(i) for i in tasks])
    
    
            
            
                
            
        
        
        
        
        

    
    
