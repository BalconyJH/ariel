import re
import time
import pickle
import binascii
from nonebot import logger
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from http.cookies import SimpleCookie
from datetime import datetime,timezone
from arielbot.ariel_sentry import sentry_http_get, sentry_http_post
from arielbot.plugins.Core.ariel_database import DataManager

class CookieManager:
    def __init__(self):
        self.cookie = None
        self.refresh_token = None
        self.headers  = {
        "user-agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0"
        }
        self.key = RSA.importKey('''\
-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDLgd2OAkcGVtoE3ThUREbio0Eg
Uc/prcajMKXvkCKFCWhJYJcLkcM2DKKcSeFpD/j6Boy538YXnR6VhcuUJOhH2x71
nzPjfdTcqMz7djHum0qSZA0AyCBDABUqCrfNgCiJ00Ra7GmRj+YCK1NJEuewlb40
JNrRuoEUXpabUzGB8QIDAQAB
-----END PUBLIC KEY-----''')
        

    async def get_cookie(self):
        async with DataManager() as m:
            result  = await m.select_cookie()
        if result is None:
            logger.info("未登录")
            return            
        self.refresh_token = result[1]
        self.cookie = pickle.loads(result[0])
        await self.__check_expire()
    
    async def __check_expire(self):
        if self.cookie is None:
            return
        cookie_expire = self.cookie["Expires"]
        now = int(time.time())
        if int(cookie_expire) - now > 3600:
            return
        await self.__refresh_cookie()
        
    async def __refresh_cookie(self):
        correspond_path = await self.__get_correspond_path()
        if correspond_path is None:
            return
        refresh_csrf =  await self.__get_refresh_csrf(correspond_path)
        if refresh_csrf is None:
            return
        new_data =  await self.__get_new_cookie(refresh_csrf)
        if new_data is None:
            return
        self.cookie = new_data[0]
        async with DataManager() as m:
            await m.update_cookie((pickle.dumps(self.cookie), new_data[1],self.refresh_token))
        self.refresh_token = new_data[1]
     
    async def __get_correspond_path(self):
        params = {"csrf":self.cookie["bili_jct"]}
        url = "https://passport.bilibili.com/x/passport-login/web/cookie/info"
        try:
            response = sentry_http_get(url,headers=self.headers,params=params,cookies=self.cookie)
            cipher = PKCS1_OAEP.new(self.key, SHA256)
            encrypted = cipher.encrypt(f'refresh_{response.json()["data"]["timestamp"]}'.encode())
            return binascii.b2a_hex(encrypted).decode()
        except Exception as e:
            logger.error(e)
            return None

    async def __get_refresh_csrf(self,correspond_path):
        url = f"https://www.bilibili.com/correspond/1/{correspond_path}"
        try:
            respoese = sentry_http_get(url,headers=self.headers,cookies=self.cookie)
            pattern = re.compile(r'<div\s+id\s*=\s*["\']1-name["\']\s*>(.*?)</div>',flags=re.DOTALL)
            match = pattern.search(respoese.text)
            return match.group(1).strip()
        except Exception as e:
            logger.error("get refresh_csrf error")
            logger.error(e)
            return None

    async def __get_new_cookie(self,refresh_csrf):
        url = "https://passport.bilibili.com/x/passport-login/web/cookie/refresh"
        data = {
            "csrf":self.cookie["bili_jct"],
            "refresh_csrf":refresh_csrf,
            "source":"main_web",
            "refresh_token":self.refresh_token
        }
        try:
            response = sentry_http_post(url,headers=self.headers,data=data,cookies=self.cookie)
            new_refresh_token  = response.json()["data"]["refresh_token"]
            new_cookies = response.headers.get_list("Set-Cookie")
            parsed_cookies = [await self.__parse_cookie_attributes(c) for c in  new_cookies]
            expires = parsed_cookies[0]["expires"]
            dt = datetime.strptime(expires, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
            new_cookie = {}
            timestamp = int(dt.timestamp())
            for i in parsed_cookies:
                new_cookie[i["name"]] = i["value"]
            new_cookie.update({"Expires":str (timestamp)})
            return (new_cookie,new_refresh_token)
        except Exception as e:
            logger.error("get new cookie error")
            logger.error(e)
            return None

    async def __parse_cookie_attributes(self,cookie_str: str) -> dict:
        cookie = SimpleCookie()
        cookie.load(cookie_str)
        parsed = {}
        for key, morsel in cookie.items():
            parsed.update({
                "name": key,
                "value": morsel.value,
                "expires": morsel.get("expires", None)
            })
        return parsed
