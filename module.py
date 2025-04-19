from datetime import datetime, timedelta, timezone
from solders.pubkey import Pubkey
from solana.rpc.api import Client
from telethon import TelegramClient
import asyncio
import base64
import aiohttp
import json
from typing import List, Dict, Union, Optional

class SolanaTokenInfo:
    def __init__(self, mint_address: Union[str, List[str]]):
        self.client = Client("https://api.mainnet-beta.solana.com")
        self.api_key = "51dd6cb2-b4be-4424-9664-9ff46ea49de9"
        self.metadata_program_id = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")
        self.session = aiohttp.ClientSession()
        
        self.mint_addresses = [mint_address] if isinstance(mint_address, str) else mint_address
        self.tokens = []
        self._cache = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    def get_metadata_pda(self, mint: Pubkey) -> Pubkey:
        cache_key = f"metadata_pda_{mint}"
        if cache_key not in self._cache:
            self._cache[cache_key] = Pubkey.find_program_address(
                [b"metadata", bytes(self.metadata_program_id), bytes(mint)],
                self.metadata_program_id
            )[0]
        return self._cache[cache_key]

    async def fetch_market_cap(self, mints: List[str]) -> Dict:
        cache_key = f"market_cap_{'_'.join(sorted(mints))}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        headers = {"accept": "application/json", "x-api-key": self.api_key}
        url = f"https://data.solanatracker.io/price/multi?tokens={','.join(mints)}"
        
        async with self.session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                self._cache[cache_key] = data
                return data
            return {}

    async def fetch_metadata_uri(self, metadata_account: Pubkey) -> Optional[str]:
        cache_key = f"metadata_uri_{metadata_account}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        account_info = await asyncio.to_thread(self.client.get_account_info, metadata_account)
        if not account_info.value:
            return None
            
        raw_data = base64.b64decode(json.loads(account_info.to_json())['result']['value']['data'][0])
        uri_start = 115
        uri = raw_data[uri_start:uri_start + 200].decode("utf-8", errors="ignore").strip("\x00")
        self._cache[cache_key] = uri
        return uri

    async def fetch_offchain_metadata(self, uri: str) -> Dict:
        cache_key = f"offchain_metadata_{uri}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        try:
            async with self.session.get(uri) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = {
                        "name": data.get("name"),
                        "symbol": data.get("symbol"),
                        "image": data.get("image"),
                        "social_links": {
                            "twitter": data.get("twitter"),
                            "website": data.get("website"),
                            "discord": data.get("discord")
                        }
                    }
                    self._cache[cache_key] = result
                    return result
        except Exception:
            pass
        return {}

    def format_short_number(self, n: Union[int, float]) -> str:
        if n is None:
            return "N/A"
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
        elif n >= 1_000:
            return f"{n / 1_000:.1f}K".replace(".0K", "K")
        return str(int(n)) if n == int(n) else str(n)
        
    async def process_mint(self, mint_str: str, market_data: Dict) -> Optional[Dict]:
        try:
            mint = Pubkey.from_string(mint_str)
            metadata_account = self.get_metadata_pda(mint)
            uri = await self.fetch_metadata_uri(metadata_account)
            if not uri:
                return None
                
            meta = await self.fetch_offchain_metadata(uri)
            raw_market_cap = market_data.get(mint_str, {}).get("marketCap")
            
            # Skip if market cap is too small or missing
            if raw_market_cap is None or raw_market_cap < 10_000:
                return None

            return {
                "mint": mint_str,
                "name": meta.get("name"),
                "symbol": meta.get("symbol"),
                "image": meta.get("image"),
                "uri": uri,
                "market_cap": self.format_short_number(raw_market_cap),
                "social_links": meta.get("social_links", {})
            }
        except Exception as e:
            print(f"⚠️ Error processing {mint_str}: {str(e)}")
            return None

    async def summary(self) -> List[Dict]:
        market_data = await self.fetch_market_cap(self.mint_addresses)
        
        tasks = [self.process_mint(mint, market_data) for mint in self.mint_addresses]
        results = await asyncio.gather(*tasks)
        
        self.tokens = [r for r in results if r is not None]
        return self.tokens

        
class SolanaContractExtractor:
    def __init__(self, api_id: int, api_hash: str, session_name: str = 'telegramClient'):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self._client = None
        self._address_cache = set()

    async def __aenter__(self):
        self._client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        await self._client.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.disconnect()
        
    def format_timedelta(self, delta: timedelta) -> str:
        seconds = int(delta.total_seconds())
        periods = [
            ('ngày', 86400),
            ('giờ', 3600),
            ('phút', 60),
            ('giây', 1)
        ]
        
        for period_name, period_seconds in periods:
            if seconds >= period_seconds:
                period_value = seconds // period_seconds
                return f"{period_value} {period_name} trước"
        return "vừa xong"

    async def get_entity_messages(self, entity, time_limit: datetime) -> List[Dict]:
        messages = []
        channel_username = entity.username or entity.title
        
        async for message in self._client.iter_messages(entity):
            message_date = message.date.astimezone(timezone.utc)
            if message_date < time_limit:
                break
                
            messages.append({
                'message': message.message,
                'channel': channel_username,
                'time': self.format_timedelta(datetime.now(timezone.utc) - message_date),
                'link': f"https://t.me/{channel_username}/{message.id}"
            })
            
            # Small sleep to prevent flooding
            await asyncio.sleep(0.05)
            
        return messages

    async def get_messages_channel(self, chat_id: Union[int, str]) -> List[Dict]:
        entity = await self._client.get_entity(chat_id)
        time_limit = datetime.now(timezone.utc) - timedelta(hours=3)
        return await self.get_entity_messages(entity, time_limit)

    async def get_messages_many_channels(self, chat_ids: List[Union[int, str]]) -> List[Dict]:
        time_limit = datetime.now(timezone.utc) - timedelta(hours=3)
        
        async def fetch_channel(chat_id):
            try:
                entity = await self._client.get_entity(chat_id)
                return await self.get_entity_messages(entity, time_limit)
            except Exception as e:
                print(f"Error fetching channel {chat_id}: {str(e)}")
                return []

        results = await asyncio.gather(*[fetch_channel(chat_id) for chat_id in chat_ids])
        return [msg for messages in results for msg in messages]

    def is_valid_solana_address(self, s: str) -> bool:
        if s in self._address_cache:
            return True
            
        try:
            Pubkey.from_string(s)
            self._address_cache.add(s)
            return True
        except Exception:
            return False

    def extract_contracts(self, text: str) -> List[str]:
        if not text:
            return []
            
        # Check if text is likely to contain Solana addresses
        if not any(c in text for c in [' ', '\n', ',']):
            return [text] if self.is_valid_solana_address(text) else []
            
        # More comprehensive extraction
        words = text.replace('\n', ' ').replace(',', ' ').split()
        return list({word for word in words if self.is_valid_solana_address(word)})

    async def get_contracts(self, chat_id: Union[int, str]) -> List[Dict]:
        messages = await self.get_messages_channel(chat_id)
        if not messages:
            return [{"error": "❌ Không tìm thấy tin nhắn trong 3 giờ gần nhất."}]

        results = []
        seen_contracts = set()
        
        for message in messages:
            contracts = self.extract_contracts(message['message'])
            for contract in contracts:
                if contract not in seen_contracts:
                    seen_contracts.add(contract)
                    results.append({
                        'contracts': contract,
                        'channel': message['channel'],
                        'time': message['time'],
                        'link': message['link']
                    })

        return results or [{"error": "❌ Không tìm thấy contract hợp lệ trong tin nhắn gần nhất."}]

    async def get_contracts_in_list(self, chat_ids: List[Union[int, str]]) -> List[Dict]:
        all_messages = await self.get_messages_many_channels(chat_ids)
        if not all_messages:
            return [{"error": "❌ Không tìm thấy tin nhắn trong 3 giờ gần nhất."}]

        contracts_dict = {}
        
        for message in all_messages:
            for contract in self.extract_contracts(message['message']):
                if contract not in contracts_dict:
                    contracts_dict[contract] = {
                        'contracts': contract,
                        'channels': [message['channel']],
                        'time': message['time'],
                        'links': [message['link']]
                    }
                else:
                    if message['channel'] not in contracts_dict[contract]['channels']:
                        contracts_dict[contract]['channels'].append(message['channel'])
                    if message['link'] not in contracts_dict[contract]['links']:
                        contracts_dict[contract]['links'].append(message['link'])
                    # Keep the earliest time
                    if message['time'] < contracts_dict[contract]['time']:
                        contracts_dict[contract]['time'] = message['time']

        return list(contracts_dict.values()) or [{"error": "❌ Không tìm thấy contract hợp lệ trong tin nhắn gần nhất."}]