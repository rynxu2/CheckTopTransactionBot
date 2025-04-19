import asyncio
from telegram import Bot
from temp.module import SolanaContractExtractor, SolanaTokenInfo

BOT_TOKEN = '8114978169:AAGI3hLnN0jdRDlb5JxsHnOiRkGJs4l_6Hk'
CHANNEL_ID = '-1002368830271'

api_id = 27281927
api_hash = '854aabcb64720c70db583a4ec6fd054a'

async def send_periodic():
    bot = Bot(token=BOT_TOKEN)
    while True:
        async with SolanaContractExtractor(api_id, api_hash) as extractor:
            all_contracts = await extractor.get_contracts(-1002279143316)
            contracts = [item['contracts'] for item in all_contracts]
            token = SolanaTokenInfo(mint_address=contracts)
            info = await token.summary()
            
            all_contracts = {item['contracts']: item for item in all_contracts}
            info = [
                {**item, **all_contracts.get(item['mint'], {'channel': '', 'time': ''})}
                for item in info
            ]
            
            message_lines = []
            for item in info:
                message_lines.append(
                    f"🚀 *{item.get('name', 'Unknown')}* - {item.get('symbol', '-')}\n"
                    f"🧬 Mint: `{item.get('mint', '-')}`\n"
                    f"💰 Market Cap: {item.get('market_cap', 'N/A')}\n"
                    f"📅 Time: {item.get('time', '')}\n"
                    f"📊 [MevX](https://mevx.io/solana/{item.get('mint', '-')}) 🤖 [Z99Scans](https://t.me/z99bot?start={item.get('mint', '-')})\n"
                    "--------------------------"
                )

            MESSAGE = "\n\n".join(message_lines) or "Không có token nào để hiển thị."

            await bot.send_message(chat_id=CHANNEL_ID, text=MESSAGE, parse_mode="Markdown")
        print("Tin nhắn đã gửi.")
        await asyncio.sleep(300)  # 5 phút

if __name__ == '__main__':
    asyncio.run(send_periodic())
