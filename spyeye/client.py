import aiohttp
import json

class SpyEyeClient:
    def __init__(self, base_url: str, access_code: str):
        self.base_url = base_url
        self.access_code = access_code

    async def send_otp(self, session: aiohttp.ClientSession, app_name: str, number: str) -> dict:
        url = f"{self.base_url}/yono?app={app_name}&action=sendotp&number={number}&accesscode={self.access_code}"
        async with session.get(url, ssl=False, timeout=55) as resp:
            return await resp.json()

    async def verify_otp(self, session: aiohttp.ClientSession, app_name: str, request_id: str, otp: str) -> dict:
        url = f"{self.base_url}/yono?app={app_name}&action=verify&requestid={request_id}&otp={otp}&accesscode={self.access_code}"
        async with session.get(url, ssl=False, timeout=40) as resp:
            return await resp.json()

    async def cancel_request(self, session: aiohttp.ClientSession, app_name: str, request_id: str) -> dict:
        url = f"{self.base_url}/yono?app={app_name}&action=cancel&requestid={request_id}&accesscode={self.access_code}"
        async with session.get(url, ssl=False, timeout=20) as resp:
            return await resp.json()

    async def check_status(self, session: aiohttp.ClientSession, app_name: str, request_id: str) -> dict:
        url = f"{self.base_url}/yono?app={app_name}&action=status&requestid={request_id}&accesscode={self.access_code}"
        async with session.get(url, ssl=False, timeout=20) as resp:
            return await resp.json()

    async def get_account_info(self, session: aiohttp.ClientSession) -> dict:
        url = f"{self.base_url}/yono-api/login?accesscode={self.access_code}"
        async with session.get(url, ssl=False, timeout=20) as resp:
            return await resp.json()

    async def get_history(self, session: aiohttp.ClientSession) -> dict:
        url = f"{self.base_url}/yono-api/history?accesscode={self.access_code}"
        try:
            async with session.get(url, ssl=False, timeout=25) as resp:
                raw_text = await resp.text()
                if resp.status == 200:
                    try:
                        data = json.loads(raw_text)
                        return data
                    except Exception as json_err:
                        return {"success": False, "raw": raw_text, "msg": f"Non-JSON response: {json_err}"}
                return {"success": False, "status_code": resp.status, "raw": raw_text}
        except Exception as e:
            return {"success": False, "error": str(e)}
