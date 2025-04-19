import asyncio
from telegram import Bot, error
from telegram.constants import ParseMode
from module import SolanaContractExtractor, SolanaTokenInfo
import logging

# Configuration
BOT_TOKEN = '8114978169:AAGI3hLnN0jdRDlb5JxsHnOiRkGJs4l_6Hk'
CHANNEL_ID = '-1002368830271'
SOURCE_CHANNEL_ID = -1002279143316
API_ID = 27281927
API_HASH = '854aabcb64720c70db583a4ec6fd054a'
SLEEP_INTERVAL = 270
MAX_MESSAGE_LENGTH = 4096

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def process_contracts(extractor):
    """Fetch and process contract data."""
    try:
        all_contracts = await extractor.get_contracts(SOURCE_CHANNEL_ID)
        if not all_contracts:
            logger.info("No contracts found in the source channel.")
            return None

        contracts = [item['contracts'] for item in all_contracts]
        token = SolanaTokenInfo(mint_address=contracts)
        token_info = await token.summary()
        
        contract_map = {item['contracts']: item for item in all_contracts}
        
        merged_info = [
            {**item, **contract_map.get(item['mint'], {'channel': '', 'time': ''})}
            for item in token_info
        ]
        
        return merged_info
    except Exception as e:
        logger.error(f"Error processing contracts: {e}")
        return None

def generate_message_chunks(token_info):
    """Generate message chunks that fit within Telegram's length limits."""
    if not token_info:
        return ["No tokens to display."]
    
    token_messages = []
    for item in token_info:
        token_msg = (
            f"🚀 *{item.get('name', 'Unknown')}* - {item.get('symbol', '-')}\n"
            f"🧬 Mint: `{item.get('mint', '-')}`\n"
            f"💰 Market Cap: {item.get('market_cap', 'N/A')}\n"
            f"📅 Time: {item.get('time', '')}\n"
            f"📊 [MevX](https://mevx.io/solana/{item.get('mint', '-')}) "
            f"🤖 [Z99Scans](https://t.me/z99bot?start={item.get('mint', '-')})\n"
            "--------------------------"
        )
        token_messages.append(token_msg)
    
    message_chunks = []
    current_chunk = []
    current_length = 0
    
    for msg in token_messages:
        msg_length = len(msg)
        
        if current_length + msg_length > MAX_MESSAGE_LENGTH - 100:
            if current_chunk:
                message_chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_length = 0
        
        current_chunk.append(msg)
        current_length += msg_length + 2
    
    if current_chunk:
        message_chunks.append("\n\n".join(current_chunk))
    
    return message_chunks if message_chunks else ["No tokens to display."]

async def send_messages(bot, chunks):
    """Send message chunks with error handling."""
    for chunk in chunks:
        try:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=chunk,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            await asyncio.sleep(1)
        except error.TelegramError as e:
            logger.error(f"Failed to send message: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")

async def monitoring_loop():
    """Main monitoring loop."""
    bot = Bot(token=BOT_TOKEN)
    
    while True:
        try:
            async with SolanaContractExtractor(API_ID, API_HASH) as extractor:
                token_info = await process_contracts(extractor)
                message_chunks = generate_message_chunks(token_info)
                await send_messages(bot, message_chunks)
                
            logger.info(f"Message cycle completed. Sleeping for {SLEEP_INTERVAL} seconds.")
            await asyncio.sleep(SLEEP_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            await asyncio.sleep(60)

if __name__ == '__main__':
    try:
        asyncio.run(monitoring_loop())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")