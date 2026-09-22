#!/usr/bin/env python3
from aiofiles.os import path as aiopath, makedirs
from aiofiles import open as aiopen
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError
from dotenv import dotenv_values

from ... import DATABASE_URL, user_data, rss_dict, LOGGER, bot_id, config_dict, aria2_options, qbit_options, bot_loop


class DbManger:
    def __init__(self):
        self.__err = False
        self.__db = None
        self.__conn = None
        self.__connect()

    def __connect(self):
        try:
            self.__conn = AsyncIOMotorClient(DATABASE_URL)
            self.__db = self.__conn.kpsmlx # New Section for not conflicting with mltb section !!
        except PyMongoError as e:
            LOGGER.error(f"Error in DB connection: {e}")
            self.__err = True

    async def db_load(self):
        if self.__err:
            return
        await self.__db.settings.config.update_one({'_id': bot_id}, {'$set': config_dict}, upsert=True)
        if await self.__db.settings.aria2c.find_one({'_id': bot_id}) is None:
            await self.__db.settings.aria2c.update_one({'_id': bot_id}, {'$set': aria2_options}, upsert=True)
        if await self.__db.settings.qbittorrent.find_one({'_id': bot_id}) is None:
            await self.__db.settings.qbittorrent.update_one({'_id': bot_id}, {'$set': qbit_options}, upsert=True)
        if await self.__db.users[bot_id].find_one():
            rows = self.__db.users[bot_id].find({})
            async for row in rows:
                uid = row['_id']
                del row['_id']
                thumb_path = f'Thumbnails/{uid}.jpg'
                rclone_path = f'wcl/{uid}.conf'
                thumb_bin = row.get('thumb')
                if thumb_bin:
                    try:
                        if isinstance(thumb_bin, (bytes, bytearray)):
                            if not await aiopath.exists('Thumbnails'): await makedirs('Thumbnails')
                            async with aiopen(thumb_path, 'wb+') as f: await f.write(thumb_bin)
                        elif isinstance(thumb_bin, str):
                            for c in (thumb_bin, f'thumbnails/{uid}.jpg', f'Thumbnail/{uid}.jpg', f'thumbnail/{uid}.jpg'):
                                if await aiopath.exists(c):
                                    if c != thumb_path:
                                        if not await aiopath.exists('Thumbnails'): await makedirs('Thumbnails')
                                        async with aiopen(c, 'rb') as s: d = await s.read()
                                        async with aiopen(thumb_path, 'wb+') as d2: await d2.write(d)
                                    break
                    except: pass
                    row['thumb'] = thumb_path
                else:
                    for c in (f'thumbnails/{uid}.jpg', f'Thumbnail/{uid}.jpg', f'thumbnail/{uid}.jpg'):
                        if await aiopath.exists(c):
                            try:
                                if not await aiopath.exists('Thumbnails'): await makedirs('Thumbnails')
                                async with aiopen(c, 'rb') as s: d = await s.read()
                                async with aiopen(thumb_path, 'wb+') as d2: await d2.write(d)
                                await self.__db.users[bot_id].update_one({'_id': uid}, {'$set': {'thumb': d}}, upsert=True)
                            except: pass
                            row['thumb'] = thumb_path
                            break
                if row.get('rclone'):
                    if not await aiopath.exists('wcl'):
                        await makedirs('wcl')
                    try:
                        if isinstance(row['rclone'], (bytes, bytearray)):
                            async with aiopen(rclone_path, 'wb+') as f:
                                await f.write(row['rclone'])
                        else:
                            rclone_bin = row['rclone']
                            if isinstance(rclone_bin, str) and await aiopath.exists(rclone_bin):
                                async with aiopen(rclone_bin, 'rb') as src:
                                    data = await src.read()
                                async with aiopen(rclone_path, 'wb+') as dst:
                                    await dst.write(data)
                                row['rclone'] = rclone_path
                            else:
                                row['rclone'] = rclone_path
                    except Exception:
                        pass
                    row['rclone'] = rclone_path
                user_data[uid] = row
            LOGGER.info("Users data has been imported from Database")

        # Rss Data
        if await self.__db.rss[bot_id].find_one():
            # return a dict ==> {_id, title: {link, last_feed, last_name, inf, exf, command, paused}
            rows = self.__db.rss[bot_id].find({})
            async for row in rows:
                user_id = row['_id']
                del row['_id']
                rss_dict[user_id] = row
            LOGGER.info("Rss data has been imported from Database.")
        self.__conn.close

    async def update_deploy_config(self):
        if self.__err:
            return
        current_config = dict(dotenv_values('config.env'))
        await self.__db.settings.deployConfig.replace_one({'_id': bot_id}, current_config, upsert=True)
        self.__conn.close

    async def update_config(self, dict_):
        if self.__err:
            return
        await self.__db.settings.config.update_one({'_id': bot_id}, {'$set': dict_}, upsert=True)
        self.__conn.close

    async def update_aria2(self, key, value):
        if self.__err:
            return
        await self.__db.settings.aria2c.update_one({'_id': bot_id}, {'$set': {key: value}}, upsert=True)
        self.__conn.close

    async def update_qbittorrent(self, key, value):
        if self.__err:
            return
        await self.__db.settings.qbittorrent.update_one({'_id': bot_id}, {'$set': {key: value}}, upsert=True)
        self.__conn.close

    async def update_private_file(self, path):
        if self.__err:
            return
        if await aiopath.exists(path):
            async with aiopen(path, 'rb+') as pf:
                pf_bin = await pf.read()
        else:
            pf_bin = ''
        path = path.replace('.', '__')
        await self.__db.settings.files.update_one({'_id': bot_id}, {'$set': {path: pf_bin}}, upsert=True)
        if path == 'config.env':
            await self.update_deploy_config()
        else:
            self.__conn.close

    async def update_user_data(self, user_id):
        if self.__err:
            return
        data = user_data[user_id].copy()
        data.pop('thumb', None)
        data.pop('rclone', None)
        if data:
            await self.__db.users[bot_id].update_one({'_id': user_id}, {'$set': data}, upsert=True)
        else:
            await self.__db.users[bot_id].update_one({'_id': user_id}, {'$setOnInsert': {'_id': user_id}}, upsert=True)
        self.__conn.close

    async def update_user_doc(self, user_id, key, path=''):
        if self.__err:
            return
        if path:
            async with aiopen(path, 'rb+') as doc:
                doc_bin = await doc.read()
            await self.__db.users[bot_id].update_one({'_id': user_id}, {'$set': {key: doc_bin}}, upsert=True)
        else:
            await self.__db.users[bot_id].update_one({'_id': user_id}, {'$unset': {key: ""}}, upsert=True)
        self.__conn.close

    async def get_pm_uids(self):
        if self.__err:
            return
        return [doc['_id'] async for doc in self.__db.pm_users[bot_id].find({})]
        
    async def update_pm_users(self, user_id):
        if self.__err:
            return
        if not bool(await self.__db.pm_users[bot_id].find_one({'_id': user_id})):
            await self.__db.pm_users[bot_id].insert_one({'_id': user_id})
            LOGGER.info(f'New PM User Added : {user_id}')
        self.__conn.close
        
    async def rm_pm_user(self, user_id):
        if self.__err:
            return
        await self.__db.pm_users[bot_id].delete_one({'_id': user_id})
        self.__conn.close
        
    async def rss_update_all(self):
        if self.__err:
            return
        for user_id in list(rss_dict.keys()):
            await self.__db.rss[bot_id].replace_one({'_id': user_id}, rss_dict[user_id], upsert=True)
        self.__conn.close

    async def rss_update(self, user_id):
        if self.__err:
            return
        await self.__db.rss[bot_id].replace_one({'_id': user_id}, rss_dict[user_id], upsert=True)
        self.__conn.close

    async def rss_delete(self, user_id):
        if self.__err:
            return
        await self.__db.rss[bot_id].delete_one({'_id': user_id})
        self.__conn.close

    async def add_incomplete_task(self, cid, link, tag, msg_link, msg):
        if self.__err:
            return
        await self.__db.tasks[bot_id].insert_one({'_id': link, 'cid': cid, 'tag': tag, 'source': msg_link, 'org_msg': msg})
        self.__conn.close

    async def rm_complete_task(self, link):
        if self.__err:
            return
        await self.__db.tasks[bot_id].delete_one({'_id': link})
        self.__conn.close

    async def get_incomplete_tasks(self):
        notifier_dict = {}
        if self.__err:
            return notifier_dict
        if await self.__db.tasks[bot_id].find_one():
            # return a dict ==> {_id, cid, tag, source}
            rows = self.__db.tasks[bot_id].find({})
            async for row in rows:
                if row['cid'] in list(notifier_dict.keys()):
                    if row['tag'] in list(notifier_dict[row['cid']]):
                        notifier_dict[row['cid']][row['tag']].append({row['_id']: row['source']})
                    else:
                        notifier_dict[row['cid']][row['tag']] = [{row['_id']: row['source']}]
                else:
                    notifier_dict[row['cid']] = {row['tag']: [{row['_id']: row['source']}]}
        await self.__db.tasks[bot_id].drop()
        self.__conn.close
        return notifier_dict  # return a dict ==> {cid: {tag: [{_id: source}, {_id, source}, ...]}}

    async def trunc_table(self, name):
        if self.__err:
            return
        await self.__db[name][bot_id].drop()
        self.__conn.close

if DATABASE_URL:
    bot_loop.run_until_complete(DbManger().db_load())
