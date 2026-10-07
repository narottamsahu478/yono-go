import json
import aiohttp


class TempOTPProvider:
    """TEMPOTP API client based on the documented endpoints.

    Endpoints: getBalance, getServers, getServices, buyNumber, checkSms,
    cancelNumber, getActivations and getTransactions.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.tempotp.online"

    async def _get(self, session, path, params=None, timeout=10):
        query = {"apikey": self.api_key}
        if params:
            query.update(params)
        async with session.get(
            f"{self.base_url}/{path}", params=query, timeout=timeout
        ) as response:
            text = (await response.text()).strip()
            try:
                return json.loads(text)
            except Exception:
                return text

    async def get_balance(self, session):
        return await self._get(session, "getBalance", timeout=8)

    async def get_servers(self, session):
        return await self._get(session, "getServers")

    async def get_services(self, session, server_id=None, international=0):
        params = {"international": international}
        if server_id:
            params["id"] = server_id
        return await self._get(session, "getServices", params=params)

    async def buy_number(self, session, service_id: str, country: str = "22"):
        return await self._get(
            session,
            "buyNumber",
            params={"id": service_id, "country": country},
            timeout=12,
        )

    async def check_sms(self, session, txn_id: str):
        return await self._get(
            session, "checkSms", params={"id": txn_id}, timeout=5
        )

    async def cancel_number(self, session, txn_id: str):
        return await self._get(
            session, "cancelNumber", params={"id": txn_id}, timeout=10
        )
