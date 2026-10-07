import aiohttp


class TemporaSMSProvider:
    """TemporaSMS handler_api.php client."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.temporasms.com/stubs/handler_api.php"

    async def _get(self, session, action, params=None, timeout=10):
        query = {"api_key": self.api_key, "action": action}
        if params:
            query.update(params)
        async with session.get(self.base_url, params=query, timeout=timeout) as response:
            return (await response.text()).strip()

    async def get_balance(self, session):
        return await self._get(session, "getBalance", timeout=8)

    async def buy_number(self, session, service: str, country: str = "22", operator: str = "10"):
        # TemporaSMS follows the 5SIM-style handler_api contract:
        # getNumber -> ACCESS_NUMBER:<activation_id>:<phone>.
        params = {"service": service, "country": country}
        if operator:
            params["operator"] = operator
        return await self._get(session, "getNumber", params=params, timeout=15)

    # Backward-compatible alias for any older code path.
    async def get_number(self, session, service: str, country: str = "22", operator: str = "10"):
        return await self.buy_number(session, service, country, operator)

    async def get_status(self, session, txn_id: str):
        return await self._get(session, "getStatus", params={"id": txn_id}, timeout=5)

    async def set_status(self, session, txn_id: str, status: str):
        return await self._get(session, "setStatus", params={"id": txn_id, "status": status}, timeout=10)
