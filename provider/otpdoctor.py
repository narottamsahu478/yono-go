import aiohttp


class OTPDoctorProvider:

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://otpdoctor.in/stubs/handler_api.php"

    async def buy_number(
        self, session: aiohttp.ClientSession, service_id: str
    ) -> str:
        url = f"{self.base_url}?action=getNumber&api_key={self.api_key}&service={service_id}"
        async with session.get(url, timeout=12) as response:
            res_text = (await response.text()).strip()
            print(f"OTPDoctor Buy Response: {res_text}")
            
            # Agar format ACCESS_NUMBER:<txn_id>:<phone> hai toh phone extract karein[span_1](start_span)[span_1](end_span)
            if res_text.startswith("ACCESS_NUMBER:"):
                parts = res_text.split(":")
                if len(parts) >= 3:
                    phone_number = parts[2]
                    return phone_number
            
            # Agar NO_NUMBERS ya NO_BALANCE aaya toh wahi return hoga[span_2](start_span)[span_2](end_span)
            return res_text

    async def check_status(
        self, session: aiohttp.ClientSession, txn_id: str
    ) -> str:
        url = f"{self.base_url}?action=getStatus&api_key={self.api_key}&id={txn_id}"
        async with session.get(url, timeout=5) as response:
            return (await response.text()).strip()

    async def set_status(
        self, session: aiohttp.ClientSession, txn_id: str, status: str
    ) -> str:
        url = f"{self.base_url}?action=setStatus&api_key={self.api_key}&id={txn_id}&status={status}"
        async with session.get(url, timeout=10) as response:
            return (await response.text()).strip()

    async def get_balance(self, session: aiohttp.ClientSession) -> str:
        url = f"{self.base_url}?action=getBalance&api_key={self.api_key}"
        async with session.get(url, timeout=8) as response:
            raw_bal = (await response.text()).strip()
            if "ACCESS_BALANCE:" in raw_bal:
                return raw_bal.split(":", 1)[1]
            return raw_bal
