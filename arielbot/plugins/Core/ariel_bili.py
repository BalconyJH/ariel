import time
import urllib.parse
from hashlib import md5
from nonebot import logger
from functools import reduce
from typing import Optional,List,Union
from arielbot.ariel_sentry import sentry_http_get, sentry_http_post
from arielbot.plugins.Core.ariel_cookie import CookieManager
from dynamicadaptor.Message import RenderMessage
from dynamicadaptor.DynamicConversion import formate_message


class Login:
    def __init__(self):
        self.qrcode_key = None
        self.headers  = {
        "user-agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0"
        }

    async def check_scan_result(self) -> Optional[dict]:
        """获取登陆二维码扫描结果

        :return: {
                        "code": 0,
                        "message": "0",
                        "ttl": 1,
                        "data": {
                            "url": "https://passport.biligame.com/crossDomain?DedeUserID=&DedeUserID__ckMd5=*&Expires=*&SESSDATA=*&bili_jct=**&gourl=*",
                            "refresh_token": "***",
                            "timestamp": 1662363009601,
                            "code": 0,
                            "message": ""
                        }
                    }
        :rtype: Optional[dict]
        """

        url = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
        params = {
            "qrcode_key":self.qrcode_key
        }
        try:
            response = sentry_http_get(url,headers=self.headers,params=params)
            response.raise_for_status()
            return response.json()["data"]
        except Exception:
            logger.exception("Failed to poll Bilibili login QR code")
            return None

    async def get_qrcode_key(self):
        url = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
        try:
            response = sentry_http_get(url,headers=self.headers)
            response.raise_for_status()
            self.qrcode_key = response.json()["data"]["qrcode_key"]
            return response.json()["data"]["url"]
        except Exception:
            logger.exception("Failed to generate Bilibili login QR code")
            return None


class Dynamic(CookieManager):
    def __init__(self):
        super().__init__()

    async def get_dynamic_from_follow_list(self) -> Optional[List[RenderMessage]] :
        """获取关注列表的前20条动态

        :return: 格式化后的动态
        :rtype: Optional[List[RenderMessage]]
        """
        await self.get_cookie()
        if self.cookie is None:
            return None
        self.headers.update({
            "referer":"https://t.bilibili.com/?spm_id_from=333.1007.0.0",
            "origin":"https://t.bilibili.com"
        })
        url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/all"
        params = {
            "timezone_offset":"-480",
            "type":"all",
            "web_location":"333.1365",
            "platform":"web",
            "page":1,
            "features":"itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote,decorationCard,onlyfansAssetsV2,forwardListHidden,ugcDelete,onlyfansQaCard,commentsNewVersion",
            "x-bili-device-req-json":{"platform":"web","device":"pc"},
            "x-bili-web-req-json":{"spm_id":"333.1365"}
        }
        try:
            response = sentry_http_get(url,headers=self.headers,cookies=self.cookie,params=params)
            response.raise_for_status()
            data = response.json()
            if data["code"] != 0:
                logger.warning(f"Failed to fetch Bilibili dynamic feed: code={data['code']}")
                return None
            return  [ await formate_message("web",i) for i in  data["data"]["items"]]
        except Exception:
            logger.exception("Failed to fetch Bilibili dynamic feed")
            return None
            
    async def get_dynamic_from_id(self,dyn_id:str) -> Optional[RenderMessage]:
        """获取指定动态id的动态信息

        :param dyn_id: 动态id
        :type dyn_id: str
        :return: 格式化后的动态信息
        :rtype: Optional[RenderMessage]
        """
        
        await self.get_cookie()
        if self.cookie is None:
            return None
        sign = Sign()
        await sign.getWbiKeys()
        if sign.img_key is None or sign.sub_key is None:
            logger.warning(f"Failed to get Bilibili WBI keys for dynamic detail: dynamic_id={dyn_id}")
            return None
        self.headers.update({
            "referer":f"https://t.bilibili.com/{dyn_id}?spm_id_from=333.1365.list.card_time.click",
            "origin":"https://t.bilibili.com"
        })
        params = {
            "timezone_offset":"-480",
            "platform":"web",
            "gaia_source":"main_web",
            "id":dyn_id,
            "features":"itemOpusStyle,opusBigCover,onlyfansVote,endFooterHidden,decorationCard,onlyfansAssetsV2,ugcDelete,onlyfansQaCard,editable,opusPrivateVisible"
        }
        signed_params = await sign.encWbi(
            params=params,
            img_key=sign.img_key,
            sub_key=sign.sub_key
        )
        url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail"
        try:
            response = sentry_http_get(url,headers=self.headers,params=signed_params,cookies=self.cookie)
            response.raise_for_status()
            return await formate_message("web",response.json()["data"]["item"])
        except Exception:
            logger.exception(f"Failed to fetch Bilibili dynamic detail: dynamic_id={dyn_id}")
            return None
    
    async def get_short_link_location(self,short_link:str):
        try:
            response = sentry_http_get(short_link,headers=self.headers)
            return response.headers.get("Location",None)
        except Exception:
            logger.exception(f"Failed to resolve Bilibili short link: url={short_link}")
            return None



class Live(CookieManager):
    def __init__(self):
        super().__init__()
    
    async def get_live_users_from_follow_list(self):
        await self.get_cookie()
        if self.cookie is None:
            return None
        self.headers.update({
            "referer":"https://t.bilibili.com/?spm_id_from=333.1007.0.0",
            "origin":"https://t.bilibili.com"
        })
        params = {
            "up_list_more":1,
            "web_location":333.1365
        }
        url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/portal"
        try:
            response = sentry_http_get(url,headers=self.headers,cookies=self.cookie,params=params)
            response.raise_for_status()
            return response.json()["data"]["live_users"]
        except Exception:
            logger.exception("Failed to fetch Bilibili live users from follow list")
            return None

    async def get_room_info_by_uids(self,uids:List[Union[int, str]]):
        url = "https://api.live.bilibili.com/room/v1/Room/get_status_info_by_uids"
        data = {
            "uids":uids
        }
        try:
            response = sentry_http_post(url,headers=self.headers,json=data)
            response.raise_for_status()
            result = response.json()["data"]
            return result if isinstance(result, dict) else None
        except Exception:
            logger.exception(f"Failed to fetch Bilibili room info: uid_count={len(uids)}")
            return None

class UserInfo(CookieManager):
    def __init__(self):
        super().__init__()
    
    async def get_user_info_by_uid(self,uid):
        """通过uid获取信息

        Args:
            uid (int): 用户uid
        """
        
        await self.get_cookie()
        if self.cookie is None:
            return "未登录"
        url = "https://api.bilibili.com/x/web-interface/card"
        params = {
            "mid":uid,
            "photo":"true",
            "web_location":"0.0"
        }
        self.headers.update({
            "host":"api.bilibili.com",
            "origin":"https://t.bilibili.com",
            "referer":"https://t.bilibili.com/"
        })
        try:
            response = sentry_http_get(url,headers=self.headers,cookies=self.cookie,params=params)
            response.raise_for_status()
            if response.json()["code"] !=0:
                return "未找到相关UP信息"
            else:
                return response.json()["data"]
        except Exception as e:
            return str(e)

    async def change_follow_status(self, uid, act):
        await self.get_cookie()
        if self.cookie is None:
            return None
        url = 'https://api.bilibili.com/x/relation/modify?statistics={"appId":100,"platform":5}&x-bili-device-req-json={"platform":"web","device":"pc","spmid":"0.0"}'
        data = {
            "fid":f"{uid}",
            "act":f"{act}",
            "re_src":"11",
            "gaia_source":"web_main",
            "spmid":"0.0",
            "extend_content":'{"entity":"user","entity_id":477332594}',
            "is_from_frontend_component":"true",
            "csrf":self.cookie["bili_jct"]
        }
        try:
            response = sentry_http_post(url,headers=self.headers,cookies=self.cookie,data=data)
            response.raise_for_status()
            if response.json()["code"]==0:
                return True
            return None
        except Exception:
            logger.exception(f"Failed to change Bilibili follow status: uid={uid}, action={act}")
            return None
    

class Sign:
    def __init__(self):
        self.mixinKeyEncTab = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]
        self.headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'Referer': 'https://www.bilibili.com/'
    }
        self.img_key = None
        self.sub_key = None
        
    async def getWbiKeys(self) -> None:
        try:
            resp = sentry_http_get('https://api.bilibili.com/x/web-interface/nav', headers=self.headers)
            resp.raise_for_status()
            json_content = resp.json()
            img_url: str = json_content['data']['wbi_img']['img_url']
            sub_url: str = json_content['data']['wbi_img']['sub_url']
            self.img_key = img_url.rsplit('/', 1)[1].split('.')[0]
            self.sub_key = sub_url.rsplit('/', 1)[1].split('.')[0]
        except Exception:
            logger.exception("Failed to fetch Bilibili WBI keys")
        
    async def __getMixinKey(self, orig: str):
        '对 imgKey 和 subKey 进行字符顺序打乱编码'
        return reduce(lambda s, i: s + orig[i], self.mixinKeyEncTab, '')[:32]
    
    async def encWbi(self,params: dict, img_key: str, sub_key: str):
        '为请求参数进行 wbi 签名'
        mixin_key = await self.__getMixinKey(img_key + sub_key)
        curr_time = round(time.time())
        params['wts'] = curr_time                                   # 添加 wts 字段
        params = dict(sorted(params.items()))                       # 按照 key 重排参数
        # 过滤 value 中的 "!'()*" 字符
        params = {
            k : ''.join(filter(lambda chr: chr not in "!'()*", str(v)))
            for k, v 
            in params.items()
        }
        query = urllib.parse.urlencode(params)                      # 序列化参数
        wbi_sign = md5((query + mixin_key).encode()).hexdigest()    # 计算 w_rid
        params['w_rid'] = wbi_sign
        return params
