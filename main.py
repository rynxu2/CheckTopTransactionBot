from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telethon.sync import TelegramClient
from solders.pubkey import Pubkey
from datetime import datetime, timedelta, timezone

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')

def is_valid_solana_address(s: str) -> bool:
    try:
        key = Pubkey.from_string(s)
        return True
    except Exception:
        return False

def extract_contracts(text: str) -> list:
    if not text:
        return []
    
    words = text.split()
    return [word for word in words if is_valid_solana_address(word)]

def getContractInList(list_dict: list) -> tuple:
    result = []
    contracts = []
    
    for item in list_dict:
        contracts = extract_contracts(item['message'])
        if contracts:
            contracts_text = '\n'.join(f'🔹 <code>{c}</code>' for c in contracts)
            formatted = (
                f"🕒 <b>{item['time']}</b>\n"
                f"🔗 <a href=\"{item['link']}\">Xem tin nhắn</a>\n"
                f"{contracts_text}\n"
                "───────────────"
            )
            result.append(formatted)
            contracts.append(','.join(f'{c}' for c in contracts))
    
    if not result:
        return "❌ Không tìm thấy contract trong tin nhắn gần nhất."
    
    return ('\n'.join(result), contracts)

def split_message(text: str, max_length: int = 4096) -> list:
    parts = []
    while len(text) > max_length:
        split_index = text[:max_length].rfind("───────────────")
        if split_index == -1:
            split_index = max_length
        parts.append(text[:split_index])
        text = text[split_index:]
    parts.append(text)
    return parts
    
async def getContracts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    
    if not args:
        await update.message.reply_text(
            '⚠️ Bạn cần cung cấp channel_id hoặc username sau lệnh /getcontracts.\nVí dụ: <code>/getcontracts SolanaVolumeGroup</code>',
            parse_mode="HTML"
        )
        return
    else:
        text_after_command = ' '.join(args)
        try:
            entity = await tele.get_entity(text_after_command)
        except Exception as e:
            await update.message.reply_text(f'❌ Không tồn tại channel_id hoặc username: <code>{text_after_command}</code>', parse_mode="HTML")
            return
        
        try:
            messages = []
            time_3h_ago = datetime.now(timezone.utc) - timedelta(hours=3)
            utc_plus_7 = timezone(timedelta(hours=7))
            
            async for msg in tele.iter_messages(entity, limit=2000):
                if msg.message and msg.date >= time_3h_ago:
                    chat_id = entity.username if entity.username else entity.id
                    msg_link = f"https://t.me/{chat_id}/{msg.id}" if entity.username else "Link không khả dụng"
                    
                    msg_time_utc7 = msg.date.astimezone(utc_plus_7)

                    formatted_msg = {
                        'time': msg_time_utc7.strftime('%Y-%m-%d %H:%M:%S'),
                        'link': msg_link,
                        'message': msg.message
                    }

                    messages.append(formatted_msg)

            result = getContractInList(messages)
            parts = split_message(result)
            for part in parts:
                await update.message.reply_text(part, parse_mode="HTML", disable_web_page_preview=True)

        except Exception as e:
            await update.message.reply_text(
                f'⚠️ Lấy tin nhắn từ <code>{text_after_command}</code> thất bại.\nChi tiết lỗi: <code>{str(e)}</code>',
                parse_mode="HTML"
            )

async def getChannel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    list_channel = [
        {
            "Name": "Savannah Wakanda ℗",
            "Username": "SAVANNAHCALLS",
            "Channel ID": 1988420013,
            "Chat ID": -1001988420013,
            "Access Hash": -9026806317101833705
        },
        {
            "Name": "SolHouse Signal",
            "Username": "solhousesignal",
            "Channel ID": 2483474049,
            "Chat ID": -1002483474049,
            "Access Hash": 217355861951195198
        },
        {
            "Name": "4AM Pumpfun Volume Signal",
            "Username": "pumpfunvolumeby4AM",
            "Channel ID": 2279143316,
            "Chat ID": -1002279143316,
            "Access Hash": -8731519781168107242
        },
        {
            "Name": "4AM Solana Volume Signal",
            "Username": "signalsolanaby4am",
            "Channel ID": 2265463352,
            "Chat ID": -1002265463352,
            "Access Hash": -8555892522894252349,
        }
    ]
    message = "📡 <b>Danh sách các channel:</b>\n\n"
    for i, channel in enumerate(list_channel, 1):
        message += (
            f"<b>{i}. {channel['Name']}</b>\n"
            f"├ Channel ID: <code>{channel['Channel ID']}</code>\n"
            f"├ Username: <code>{channel['Username']}</code>\n"
            f"├ Chat ID: <code>{channel['Chat ID']}</code>\n"
            f"└ Access Hash: <code>{channel['Access Hash']}</code>\n\n"
        )
        
    await update.message.reply_text(message, parse_mode="HTML")

bot = ApplicationBuilder().token("8114978169:AAGI3hLnN0jdRDlb5JxsHnOiRkGJs4l_6Hk").build()
tele = TelegramClient('telegramClient', api_id=27281927, api_hash='854aabcb64720c70db583a4ec6fd054a')

tele.start()

bot.add_handler(CommandHandler("start", hello))
bot.add_handler(CommandHandler("getcontracts", getContracts))
bot.add_handler(CommandHandler("listchannels", getChannel))

bot.run_polling()
