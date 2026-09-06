#!/usr/bin/env python3
#!/usr/bin/env python3
from os import path as ospath
from os import walk
from random import choice

from aiofiles.os import path as aiopath
from aiohttp import ClientSession

from ..... import LOGGER
from ....ext_utils.bot_utils import sync_to_async


class Gofile:
    def __init__(self, dluploader=None, token=None):
        self.api_url = "https://api.gofile.io/"
        self.dluploader = dluploader
        self.token = token

    @staticmethod
    async def is_goapi(token):
        if token is None:
            return False

        async with ClientSession() as session:
            async with session.get(
                f"https://api.gofile.io/accounts/getid?token={token}"
            ) as resp:
                res = await resp.json()
                if res["status"] == "ok":
                    acc_id = res["data"]["id"]
                    async with session.get(
                        f"https://api.gofile.io/accounts/{acc_id}?token={token}"
                    ) as resp:
                        return (await resp.json())["status"] == "ok"
        return False

    async def __resp_handler(self, response):
        if not isinstance(response, dict):
            raise Exception(f"Gofile returned an unreadable response: {response!r}")
        if (api_resp := response.get("status", "")) == "ok":
            return response["data"]
        # Purana code split("-")[1] bhejta tha, jisse user ko sirf "token" jaisa
        # bekaar message milta tha. Poora status dikhao.
        raise Exception(f"Gofile API error: {api_resp or 'unknown'}")

    async def __getServer(self):
        async with ClientSession() as session:
            async with session.get(f"{self.api_url}servers") as resp:
                return await self.__resp_handler(await resp.json())

    async def __getAccount(self, check_account=False):
        if self.token is None:
            raise Exception

        async with ClientSession() as session:
            async with session.get(
                f"{self.api_url}accounts/getid?token={self.token}"
            ) as resp:
                res = await resp.json()
                if res["status"] == "ok":
                    acc_id = res["data"]["id"]
                    async with session.get(f"{self.api_url}accounts/{acc_id}?token={self.token}") as resp2:
                        res2 = await resp2.json()
                        return res2["status"] == "ok" if check_account else await self.__resp_handler(res2)

    def __folder_id(self, data):
        fid = data.get("folderId") or data.get("id") if isinstance(data, dict) else None
        if not fid:
            raise Exception(f"Gofile folder create failed: {data}")
        return fid

    async def upload_folder(self, path, folderId=None):
        if not await aiopath.isdir(path):
            raise Exception(f"Path: {path} is not a valid directory")

        folder_data = await self.create_folder(
            (await self.__getAccount())["rootFolder"], ospath.basename(path)
        )
        folder_id = self.__folder_id(folder_data)
        await self.__setOptions(
            contentId=folder_id, option="public", value="true"
        )

        folderId = folderId or folder_id
        folder_ids = {".": folderId}
        for root, _, files in await sync_to_async(walk, path):
            rel_path = ospath.relpath(root, path)
            parentFolderId = folder_ids.get(ospath.dirname(rel_path), folderId)
            folder_name = ospath.basename(rel_path)
            currFolderId = self.__folder_id(
                await self.create_folder(parentFolderId, folder_name)
            )
            await self.__setOptions(
                contentId=currFolderId, option="public", value="true"
            )
            folder_ids[rel_path] = currFolderId

            for file in files:
                file_path = ospath.join(root, file)
                await self.upload_file(file_path, currFolderId)

        return folder_data["code"]

    async def upload_file(
        self,
        path: str,
        folderId: str = "",
        description: str = "",
        password: str = "",
        tags: str = "",
        expire: str = "",
    ):
        if password and len(password) < 4:
            raise ValueError("Password Length must be greater than 4")

        server = choice((await self.__getServer())["servers"])["name"]
        req_dict = {}
        if token := self.token or "":
            req_dict["token"] = token
        if folderId:
            req_dict["folderId"] = folderId
        if description:
            req_dict["description"] = description
        if password:
            req_dict["password"] = password
        if tags:
            req_dict["tags"] = tags
        if expire:
            req_dict["expire"] = expire

        if self.dluploader.is_cancelled:
            return
        # File ko disk pe rename mat karo: purana code spaces ko dots me badal kar
        # file ka naam permanently change kar deta tha, aur upload fail hone par
        # file mangled reh jaati thi. Naam sirf form field me bhejo.
        upload_name = ospath.basename(path).replace(" ", ".")
        upload_file = await self.dluploader.upload_aiohttp(
            f"https://{server}.gofile.io/contents/uploadfile",
            path,
            "file",
            req_dict,
            filename=upload_name,
        )
        return await self.__resp_handler(upload_file)

    async def upload(self, file_path):
        # Token optional hai: gofile guest (anonymous) upload bhi allow karta hai,
        # verified live. Purana code bina token ke "Invalid Gofile API Key" throw
        # karta tha aur working anonymous path block ho jaata tha.
        if self.token is not None and not await self.is_goapi(self.token):
            raise Exception("Invalid Gofile API Key, Recheck your account !!")

        if await aiopath.isfile(file_path):
            if (gCode := await self.upload_file(path=file_path)) and gCode.get(
                "downloadPage", False
            ):
                return gCode["downloadPage"]
        elif await aiopath.isdir(file_path):
            # Folder upload ke liye account ka rootFolder chahiye, isliye token zaroori.
            if self.token is None:
                raise Exception(
                    "Gofile folder upload needs an API key — set it in /usersettings."
                )
            if gCode := await self.upload_folder(path=file_path):
                return f"https://gofile.io/d/{gCode}"
        if self.dluploader.is_cancelled:
            return
        raise Exception(
            "Failed to upload file/folder to Gofile API, Retry or Try after sometimes..."
        )

    async def create_folder(self, parentFolderId, folderName):
        if self.token is None:
            raise Exception("Invalid Gofile API Key, Recheck your account !!")

        async with ClientSession() as session:
            async with session.post(
                url=f"{self.api_url}contents/createFolder",
                data={
                    "token": self.token,
                    "parentFolderId": parentFolderId,
                    "folderName": folderName,
                },
            ) as resp:
                return await self.__resp_handler(await resp.json())

    async def __setOptions(self, contentId, option, value):
        if self.token is None:
            raise Exception("Invalid Gofile API Key, Recheck your account !!")

        if option not in ["name", "description", "tags", "public", "expiry", "password"]:
            raise Exception(f"Invalid GoFile Option Specified : {option}")
        async with ClientSession() as session:
            async with session.put(
                url=f"{self.api_url}contents/{contentId}/update",
                data={
                    "token": self.token,
                    "attribute": option,
                    "attributeValue": value,
                },
            ) as resp:
                return await self.__resp_handler(await resp.json())

    async def get_content(self, contentId):
        if self.token is None:
            raise Exception("Invalid Gofile API Key, Recheck your account !!")

        async with ClientSession() as session:
            async with session.get(
                url=f"{self.api_url}contents/{contentId}",
                params={"cache": "true"},
                headers={"Authorization": f"Bearer {self.token}"},
            ) as resp:
                return await self.__resp_handler(await resp.json())

    async def copy_content(self, contentsId, folderIdDest):
        if self.token is None:
            raise Exception("Invalid Gofile API Key, Recheck your account !!")
        
        async with ClientSession() as session:
            async with session.post(
                url=f"{self.api_url}contents/copy",
                data={
                    "token": self.token,
                    "contentsId": contentsId,
                    "folderId": folderIdDest,
                },
            ) as resp:
                return await self.__resp_handler(await resp.json())

    async def delete_content(self, contentId):
        if self.token is None:
            raise Exception("Invalid Gofile API Key, Recheck your account !!")
        
        async with ClientSession() as session:
            async with session.delete(
                url=f"{self.api_url}contents/{contentId}",
                data={"token": self.token},
            ) as resp:
                return await self.__resp_handler(await resp.json())
                
