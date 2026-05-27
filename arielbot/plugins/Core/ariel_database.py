import aiosqlite
from os import environ, getcwd, makedirs, path
from typing import Optional

from arielbot.ariel_sentry import sentry_span

DEFAULT_DB_PATH = path.join(getcwd(), "data.sqlite")


class DataManager:
    def __init__(self):
        self.__conn: Optional[aiosqlite.Connection] = None
        self.__cursor:Optional[aiosqlite.Cursor] = None
        self.__sentry_span = None

    async def __aenter__(self):
        db_path = environ.get("ARIEL_DB_PATH", DEFAULT_DB_PATH)
        self.__sentry_span = sentry_span(
            "db.transaction",
            "sqlite transaction",
            **{
                "db.system": "sqlite",
                "db.name": path.basename(db_path),
            },
        )
        self.__sentry_span.__enter__()
        try:
            if db_dir := path.dirname(db_path):
                makedirs(db_dir, exist_ok=True)
            self.__conn = await aiosqlite.connect(db_path)
            await self.__conn.execute("PRAGMA foreign_keys = ON;")
            self.__cursor = await self.__conn.cursor()
            await self.__cursor.execute("BEGIN")
            await self.__ensure_schema()
            return self
        except Exception as exc:
            if self.__cursor is not None:
                await self.__cursor.close()
                self.__cursor = None
            if self.__conn is not None:
                await self.__conn.close()
                self.__conn = None
            self.__sentry_span.__exit__(type(exc), exc, exc.__traceback__)
            self.__sentry_span = None
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                await self.__conn.commit()
            else:
                await self.__conn.rollback()
            await self.__cursor.close()
            await self.__conn.close()
        finally:
            if self.__sentry_span is not None:
                self.__sentry_span.__exit__(exc_type, exc_val, exc_tb)
                self.__sentry_span = None
            self.__cursor = None
            self.__conn = None

    async def __ensure_schema(self):
        await self.__create_sub_target_table()
        await self.__create_sub_channel_table()
        await self.__create_bot_status_table()
        await self.__create_cookie_table()
        await self.__create_dynamic_table()
        await self.__deduplicate_rows()
        await self.__create_indexes()
    
    async def __create_sub_target_table(self):
        sql ="""
            CREATE TABLE IF NOT EXISTS subTarget (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                nickname TEXT NOT NULL,
                uid TEXT NOT NULL UNIQUE,
                live_status INTEGER NOT NULL DEFAULT 1 CHECK(live_status IN (0, 1)),
                last_live_end_time INTEGER
            );
            """
        
        await self.__cursor.execute(sql)
    
    async def __create_sub_channel_table(self):
        sql ="""
            CREATE TABLE IF NOT EXISTS subChannel (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                uid TEXT NOT NULL,
                groupId INTEGER NOT NULL,
                bot INTEGER NOT NULL,
                live_active INTEGER NOT NULL DEFAULT 1 CHECK(live_active IN (0, 1)),
                dyn_active INTEGER NOT NULL DEFAULT 1 CHECK(dyn_active IN (0, 1)),
                FOREIGN KEY (uid) 
                REFERENCES subTarget(uid) 
                ON DELETE CASCADE
            );
            """
        await self.__cursor.execute(sql)
        
    async def __create_bot_status_table(self):
        sql ="""
            CREATE TABLE IF NOT EXISTS botStatus (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                bot INTEGER NOT NULL,
                groupId INTEGER NOT NULL,
                push_active INTEGER NOT NULL DEFAULT 1 CHECK(push_active IN (0, 1)),
                bot_active INTEGER NOT NULL DEFAULT 1 CHECK(bot_active IN (0, 1))
            );
            """
        await self.__cursor.execute(sql)
            
    async def __create_cookie_table(self):
        sql ="""
            CREATE TABLE IF NOT EXISTS Cookie (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                cookie  BLOB NOT NULL,
                refresh_token  TEXT NOT NULL
            );
            """
        await self.__cursor.execute(sql)

    async def __create_dynamic_table(self):
        sql ="""
            CREATE TABLE IF NOT EXISTS Dynamic (
                dyn_id TEXT NOT NULL PRIMARY KEY,
                uname  TEXT NOT NULL,
                dyn_content  BLOB NOT NULL
            );
            """
        await self.__cursor.execute(sql)

    async def __deduplicate_rows(self):
        await self.__cursor.execute(
            """
            DELETE FROM subChannel
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM subChannel
                GROUP BY uid, groupId, bot
            );
            """
        )
        await self.__cursor.execute(
            """
            DELETE FROM botStatus
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM botStatus
                GROUP BY bot, groupId
            );
            """
        )

    async def __create_indexes(self):
        indexes = (
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_subChannel_unique ON subChannel(uid, groupId, bot);",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_botStatus_unique ON botStatus(bot, groupId);",
            "CREATE INDEX IF NOT EXISTS idx_subChannel_push ON subChannel(uid, live_active, dyn_active);",
            "CREATE INDEX IF NOT EXISTS idx_subChannel_group ON subChannel(bot, groupId);",
            "CREATE INDEX IF NOT EXISTS idx_botStatus_push ON botStatus(bot, groupId, push_active, bot_active);",
            "CREATE INDEX IF NOT EXISTS idx_subTarget_live ON subTarget(uid, live_status);",
        )
        for sql in indexes:
            await self.__cursor.execute(sql)


#bot status process
    async def select_bot_status(self,data:tuple) -> Optional[tuple]:
        """select bot status

        Args:
            data (set): (bot,groupId)

        Returns:
            Optional[set]: (push_active,bot_active)
        """
        sql = "SELECT push_active,bot_active FROM botStatus WHERE bot=? AND groupId=?"
        await self.__cursor.execute(sql,data)
        return await self.__cursor.fetchone()
    
    async def select_all_bot(self) -> Optional[list]:
        """select all bot

        :return: [bot]
        :rtype: Optional[list]
        """
        sql = "SELECT DISTINCT  bot FROM botStatus"
        await self.__cursor.execute(sql)
        return await self.__cursor.fetchall()
    
    async def insert_bot_status(self,data:tuple):
        """insert bot status

        Args:
            data (set): (bot,groupId,push_active,bot_active)
        """
        sql = """
            INSERT INTO botStatus (bot,groupId,push_active,bot_active)
            VALUES (?, ?,?,?)
            ON CONFLICT(bot, groupId) DO UPDATE SET
                push_active=excluded.push_active;
            """
        await self.__cursor.execute(sql,data)
        
    async def update_bot_push_status(self,data:tuple) -> None:
        """update bot push status

        Args:
            data (set): (push_active,bot,groupId)
        """
        sql = "UPDATE botStatus SET push_active = ?  WHERE bot=? AND groupId=?"
        await self.__cursor.execute(sql,data)
        
    async def update_bot_active_status(self,data:tuple):
        """update bot active status

        Args:
            data (set): (bot_active, bot)
        """
        sql = "UPDATE botStatus SET bot_active = ? WHERE bot=?"
        await self.__cursor.execute(sql,data)

    async def select_bot_status_by_bot(self, bot: int) -> list:
        sql = "SELECT groupId,push_active,bot_active FROM botStatus WHERE bot=? ORDER BY groupId ASC"
        await self.__cursor.execute(sql, (bot,))
        return await self.__cursor.fetchall()
        

# cookie process
    async def select_cookie(self):
        sql = "SELECT cookie, refresh_token FROM Cookie"
        await self.__cursor.execute(sql)
        return await self.__cursor.fetchone()  
    
    async def insert_cookie(self,data:tuple):
        sql = "INSERT INTO Cookie (cookie,refresh_token) VALUES (?, ?);"
        await self.__cursor.execute(sql,data)
    
    async def update_cookie(self,data:tuple):
        sql = "UPDATE Cookie SET cookie = ? , refresh_token=?  WHERE refresh_token=?"
        await self.__cursor.execute(sql,data)

    async def clean_cookie(self):
        sql = "DELETE FROM Cookie"
        await self.__cursor.execute(sql)

#dynamic process
    async def select_dyn_content(self,dyn_id: str):
        sql = "SELECT dyn_content FROM Dynamic WHERE dyn_id=?"
        await self.__cursor.execute(sql,(dyn_id,))
        return await self.__cursor.fetchone()
    
    async def insert_dyn_data(self,dyn_data:tuple):
        """insert dyn data

        Args:
            dyn_data (tuple): (dyn_id,uname,dyn_content)
        """
        sql = "INSERT OR IGNORE INTO Dynamic (dyn_id,uname,dyn_content) VALUES (?, ?,?);"
        await self.__cursor.execute(sql,dyn_data)

# subTarget process
    async def insert_sub_target(self,sub_data:tuple):
        """增加订阅记录

        :param sub_data: (uid,nickname,live_status)
        :type sub_data: tuple
        """
        sql = """
            INSERT INTO subTarget (uid,nickname,live_status)
            VALUES (?, ?,?)
            ON CONFLICT(uid) DO UPDATE SET
                nickname=excluded.nickname;
            """
        await self.__cursor.execute(sql,sub_data)
    
    async def select_sub_target(self,uid:str):
        sql = "SELECT nickname FROM subTarget WHERE uid=?"
        await self.__cursor.execute(sql,(uid,))
        return await self.__cursor.fetchone()
    
    async def update_sub_target(self,data:tuple):
        """修改订阅名单

        :param data: (nickname,live_status,uid)
        :type data: tuple
        """
        sql = "UPDATE subTarget SET  nickname=?, live_status=?  WHERE uid=?"
        await self.__cursor.execute(sql,data)

    async def update_sub_target_live_end(self, data: tuple):
        """Update subscription target status with the last detected live end time.

        :param data: (nickname, live_status, last_live_end_time, uid)
        :type data: tuple
        """
        sql = "UPDATE subTarget SET nickname=?, live_status=?, last_live_end_time=? WHERE uid=?"
        await self.__cursor.execute(sql, data)

# subChannel process

    async def insert_sub_channel(self,data:tuple):
        """增加订阅群组及机器人记录

        :param data: (uid,groupId,bot)
        :type data: tuple
        """
        sql = """
            INSERT INTO subChannel (uid,groupId,bot)
            VALUES (?, ?,?)
            ON CONFLICT(uid, groupId, bot) DO UPDATE SET
                live_active=1,
                dyn_active=1;
            """
        await self.__cursor.execute(sql,data)
    
    async def update_sub_channel(self,data:tuple):
        """修改订阅群组记录

        :param data: (live_active,dyn_active,uid,groupId,bot)
        :type data: tuple
        """
        sql = "UPDATE subChannel SET  live_active=?, dyn_active=?  WHERE uid=? AND groupId=? AND bot=?"
        await self.__cursor.execute(sql,data)

    async def delete_sub_channel(self, data: tuple):
        """删除订阅群组记录

        :param data: (uid, groupId, bot)
        :type data: tuple
        """
        sql = "DELETE FROM subChannel WHERE uid=? AND groupId=? AND bot=?"
        await self.__cursor.execute(sql, data)
        
    async def select_sub_channel(self,data:tuple) -> Optional[tuple]:
        """select sub channel data

        Args:
            data (tuple): (uid, groupId, bot)

        Returns:
            Optional[set]: 
        """
        sql = "SELECT  live_active, dyn_active FROM subChannel  WHERE uid=? AND groupId=? AND bot=?"
        await self.__cursor.execute(sql,data)
        return await self.__cursor.fetchone()
    
# find dyn push list
    async def select_dynamic_push(self,uid:str) -> Optional[list]:
        """select dynamic push group and bot

        Args:
            uid (str): uid

        Returns:
            Optional[list]: [(groupId,bot)]
        """
        sql = """
            SELECT DISTINCT t2.groupId, t2.bot
            FROM 
                subTarget t1
                INNER JOIN subChannel t2 ON t1.uid = t2.uid
                INNER JOIN botStatus t3 ON t2.groupId = t3.groupId AND t2.bot = t3.bot
            WHERE 
                t1.uid = ? 
                AND t3.push_active = 1
                AND t2.dyn_active = 1
                AND t3.bot_active = 1;
            """
        
        await self.__cursor.execute(sql,(int(uid),))
        return await self.__cursor.fetchall()

#find live check uid
    async def select_live_check_uid(self) -> Optional[list]:
            """Select subscribed targets that need live status checks.

            Returns:
                Optional[list]: [(uid, live_status, last_live_end_time)]
            """
            sql = """
                SELECT DISTINCT t1.uid,t1.live_status,t1.last_live_end_time
                FROM 
                    subTarget t1
                    INNER JOIN subChannel t2 ON t1.uid = t2.uid
                    INNER JOIN botStatus t3 ON t2.groupId = t3.groupId AND t2.bot = t3.bot
                WHERE 
                    t3.push_active = 1
                    AND t2.live_active = 1
                    AND t3.bot_active = 1;
                """
            
            await self.__cursor.execute(sql)
            return await self.__cursor.fetchall()
#find live push list
    async def select_live_push(self,uid:str) -> Optional[list]:
            """select live push group and bot

            Args:
                uid (str): uid

            Returns:
                Optional[list]: [(groupId,bot)]
            """
            sql = """
                SELECT DISTINCT t2.groupId, t2.bot
                FROM 
                    subTarget t1
                    INNER JOIN subChannel t2 ON t1.uid = t2.uid
                    INNER JOIN botStatus t3 ON t2.groupId = t3.groupId AND t2.bot = t3.bot
                WHERE 
                    t1.uid = ? 
                    AND t3.push_active = 1
                    AND t2.live_active = 1
                    AND t3.bot_active = 1;
                """
            
            await self.__cursor.execute(sql,(uid,))
            return await self.__cursor.fetchall()

# get sub list
    async def select_sub_list(self,data:tuple) -> Optional[list]:
        """select sub list data

        Args:
            data (tuple): (bot, groupId)

        Returns:
            Optional[set]: (nickname,live_active,dyn_active)
        """

        sql = """
            SELECT DISTINCT t1.uid, t1.nickname,t2.live_active,t2.dyn_active
            FROM
                subTarget t1
                INNER JOIN subChannel t2 ON t1.uid = t2.uid
            WHERE
                t2.bot=?
                AND t2.groupId=?        
        """
        await self.__cursor.execute(sql,data)
        return await self.__cursor.fetchall()

    async def select_sub_list_by_bot(self, bot: int) -> Optional[list]:
        sql = """
            SELECT DISTINCT t2.groupId, t1.uid, t1.nickname, t2.live_active, t2.dyn_active
            FROM
                subTarget t1
                INNER JOIN subChannel t2 ON t1.uid = t2.uid
            WHERE
                t2.bot=?
            ORDER BY
                t2.groupId ASC,
                t1.uid ASC
            """
        await self.__cursor.execute(sql, (bot,))
        return await self.__cursor.fetchall()
        
        
