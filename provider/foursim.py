import aiohttp


class FourSimProvider:

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.4sim.st"

    async def buy_number(
        self, session: aiohttp.ClientSession, service_id: str, country: str = "22"
    ) -> dict:
        url = f"{self.base_url}/buyNumber?apikey={self.api_key}&id={service_id}&country={country}"
        async with session.get(url, timeout=12) as response:
            return await response.json()

    async def check_sms(self, session: aiohttp.ClientSession, txn_id: str) -> dict:
        url = f"{self.base_url}/checkSms?apikey={self.api_key}&id={txn_id}"
        async with session.get(url, timeout=5) as response:
            return await response.json()

    async def cancel_number(
        self, session: aiohttp.ClientSession, txn_id: str
    ) -> str:
        url = f"{self.base_url}/cancelNumber?apikey={self.api_key}&id={txn_id}"
        async with session.get(url, timeout=10) as response:
            return (await response.text()).strip()

    async def finish_order(
        self, session: aiohttp.ClientSession, txn_id: str
    ) -> str:
        url = f"{self.base_url}/finishOrder?apikey={self.api_key}&id={txn_id}"
        async with session.get(url, timeout=10) as response:
            return (await response.text()).strip()

    async def get_balance(self, session: aiohttp.ClientSession) -> dict:
        url = f"{self.base_url}/getBalance?apikey={self.api_key}"
        async with session.get(url, timeout=8) as response:
            return await response.json()
