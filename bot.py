import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import requests
import time
import os

# Bot Token
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8304954508:AAHLxY3YfPHwF1dnBxv8noLUhmz9YxV5MxU")
bot = telebot.TeleBot(BOT_TOKEN)

# API Configuration
API_TOKEN = os.environ.get('API_TOKEN', "7658050410:WJ8iTpuZ")
PEOPLE_API_URL = "https://leakosintapi.com/"
VEHICLE_API_URL = "https://vehicleinfo.zerovault.workers.dev/?VIN="

# Unlimited Users
UNLIMITED_USERS = ["1382801385", "5145179256", "8270660057"]

# Channels
CHANNELS = [
    {"id": -1002851939876, "url": "https://t.me/+eB_J_ExnQT0wZDU9", "name": "Main Channel"},
    {"id": -1002321550721, "url": "https://t.me/taskblixosint", "name": "Updates Channel"},
    {"id": -1002921007541, "url": "https://t.me/CHOMUDONKIMAKICHUT", "name": "News Channel"}
]

# Database setup
conn = sqlite3.connect('users.db', check_same_thread=False)

def execute_db(query, params=()):
    """Thread-safe database execution"""
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            if query.strip().upper().startswith('SELECT'):
                result = cursor.fetchone()
            else:
                result = None
            return result
    except Exception as e:
        print(f"Database error: {e}")
        return None

# Create users table
execute_db('''CREATE TABLE IF NOT EXISTS users
               (user_id TEXT PRIMARY KEY, credits INTEGER DEFAULT 3, referrals INTEGER DEFAULT 0)''')

def get_credits(user_id):
    if str(user_id) in UNLIMITED_USERS:
        return "♾️ Unlimited"
    result = execute_db("SELECT credits FROM users WHERE user_id=?", (str(user_id),))
    return result[0] if result else 0

def get_referrals_count(user_id):
    result = execute_db("SELECT referrals FROM users WHERE user_id=?", (str(user_id),))
    return result[0] if result else 0

def use_credit(user_id):
    if str(user_id) in UNLIMITED_USERS:
        return True
    credits = get_credits(user_id)
    if credits > 0:
        execute_db("UPDATE users SET credits=credits-1 WHERE user_id=?", (str(user_id),))
        return True
    return False

def add_user(user_id):
    execute_db("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (str(user_id),))

def add_referral(referrer_id):
    if referrer_id:
        execute_db("UPDATE users SET credits=credits+1, referrals=referrals+1 WHERE user_id=?", (str(referrer_id),))
        return True
    return False

def is_user_joined(user_id, channel_id):
    try:
        member = bot.get_chat_member(channel_id, user_id)
        return member.status not in ['left', 'kicked']
    except:
        return False

def check_all_channels(user_id):
    not_joined = []
    for channel in CHANNELS:
        if not is_user_joined(user_id, channel["id"]):
            not_joined.append(channel)
    return not_joined

def show_channel_join_menu(user_id):
    markup = InlineKeyboardMarkup()
    for channel in CHANNELS:
        markup.add(InlineKeyboardButton(f"📢 Join {channel['name']}", url=channel["url"]))
    markup.add(InlineKeyboardButton("✅ I've Joined", callback_data="verify_join"))
    
    bot.send_message(user_id, "🤖 To use this bot, please join all our channels first:", reply_markup=markup)

# Start command
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    
    # Check channel joining
    not_joined = check_all_channels(message.from_user.id)
    if not_joined:
        show_channel_join_menu(user_id)
        return
    
    # Add user if not exists
    add_user(user_id)
    
    # Check for referral - FIXED LOGIC
    if len(message.text.split()) > 1:
        referrer_id = message.text.split()[1]
        if referrer_id != user_id:
            # Referrer को credit दें
            add_referral(referrer_id)
            # New user को भी extra credit दें
            execute_db("UPDATE users SET credits=credits+1 WHERE user_id=?", (str(user_id),))
            
            # दोनों को congratulations message
            bot.send_message(user_id, "🎉 You joined using a referral link! +1 credit added to your account!")
            
            # Referrer को message (error handling के साथ)
            try:
                referrals_count = get_referrals_count(referrer_id)
                bot.send_message(referrer_id, f"🎉 Congratulations! You got +1 credit for referral! Total referrals: {referrals_count}")
            except Exception as e:
                print(f"Could not send message to referrer: {e}")
    
    # Show main menu
    show_main_menu(user_id)

def show_main_menu(user_id):
    credits = get_credits(user_id)
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📞 Number Info", callback_data="number"))
    markup.row(InlineKeyboardButton("🚗 Vehicle Info", callback_data="vehicle"))
    markup.row(InlineKeyboardButton("💳 Balance", callback_data="balance"))
    markup.row(InlineKeyboardButton("🤝 Referral", callback_data="referral"))
    
    bot.send_message(user_id, f"👋 Welcome!\n💎 Credits: {credits}\nChoose option:", reply_markup=markup)

# Callback handler
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = str(call.from_user.id)
    
    if call.data == "number":
        # Check channels first
        not_joined = check_all_channels(call.from_user.id)
        if not_joined:
            show_channel_join_menu(user_id)
        else:
            msg = bot.send_message(user_id, "📞 Enter phone number (10 digits only):\n• Example: 9565982635\n• Only numbers, no +91")
            bot.register_next_step_handler(msg, process_number)
    
    elif call.data == "vehicle":
        not_joined = check_all_channels(call.from_user.id)
        if not_joined:
            show_channel_join_menu(user_id)
        else:
            msg = bot.send_message(user_id, "🚗 Enter vehicle VIN:")
            bot.register_next_step_handler(msg, process_vehicle)
    
    elif call.data == "balance":
        credits = get_credits(user_id)
        bot.send_message(user_id, f"💎 Your credits: {credits}")
    
    elif call.data == "referral":
        referral_link = f"https://t.me/rajputteam_bot?start={user_id}"
        bot.send_message(user_id, f"🤝 Your referral link:\n`{referral_link}`\n\nShare this link with friends to get +1 credit when they join!", parse_mode="Markdown")
    
    elif call.data == "verify_join":
        not_joined = check_all_channels(call.from_user.id)
        if not_joined:
            bot.answer_callback_query(call.id, "Please join all channels first!")
            show_channel_join_menu(user_id)
        else:
            bot.answer_callback_query(call.id, "Thanks for joining!")
            show_main_menu(user_id)
    
    bot.answer_callback_query(call.id)

# Animation function
def show_animation(user_id, target):
    steps = [
        "🟢 Starting search...",
        "⚡ Scanning databases...",
        f"🔍 Searching for: {target}",
        "📊 Collecting information...",
        "✅ Almost done..."
    ]
    for step in steps:
        try:
            bot.send_message(user_id, step)
            time.sleep(0.5)
        except:
            pass

# Process number with API
def process_number(message):
    user_id = str(message.from_user.id)
    phone = message.text.strip()
    
    # Check channels again
    not_joined = check_all_channels(message.from_user.id)
    if not_joined:
        show_channel_join_menu(user_id)
        return
    
    # Clean phone number
    phone = phone.replace('+', '').replace(' ', '').replace('-', '')
    
    if not phone.isdigit():
        bot.send_message(user_id, "❌ Please enter numbers only (e.g., 9565982635)")
        return start(message)
    
    # Ensure 10 digits and add 91 prefix
    if len(phone) == 10:
        phone_with_prefix = "91" + phone
    elif len(phone) == 12 and phone.startswith("91"):
        phone_with_prefix = phone
    else:
        bot.send_message(user_id, "❌ Please enter 10 digit number (e.g., 9565982635)")
        return start(message)
    
    if not use_credit(user_id):
        bot.send_message(user_id, "❌ Not enough credits!")
        return start(message)
    
    show_animation(user_id, phone_with_prefix)
    
    try:
        # API request
        data = {
            "token": API_TOKEN,
            "request": phone_with_prefix,
            "limit": 300,
            "lang": "en"
        }
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.post(PEOPLE_API_URL, json=data, headers=headers, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            
            if "Error code" in result:
                bot.send_message(user_id, f"❌ API Error: {result['Error code']}")
                return
            
            result_texts = []
            
            if "List" in result and result["List"]:
                for db_name, db_result in result["List"].items():
                    for record in db_result.get("Data", []):
                        lines = []
                        if "FullName" in record and record["FullName"]: 
                            lines.append(f"🧑 Name: {record['FullName']}")
                        if "FatherName" in record and record["FatherName"]: 
                            lines.append(f"👨 Father: {record['FatherName']}")
                        if "DocNumber" in record and record["DocNumber"]: 
                            lines.append(f"🆔 Document: {record['DocNumber']}")
                        if "Region" in record and record["Region"]: 
                            lines.append(f"📍 Region: {record['Region']}")
                        if "Address" in record and record["Address"]: 
                            lines.append(f"🏠 Address: {record['Address']}")
                        
                        phones = [v for k, v in record.items() if k.startswith("Phone") and v]
                        if phones:
                            phone_lines = "\n".join([f"  📞 {p}" for p in phones])
                            lines.append(f"Phones:\n{phone_lines}")
                        
                        if lines:
                            result_texts.append("\n".join(lines))
            
            if result_texts:
                full_result = "\n\n".join(result_texts)
                if len(full_result) > 4000:
                    parts = [full_result[i:i+4000] for i in range(0, len(full_result), 4000)]
                    for part in parts:
                        bot.send_message(user_id, part)
                else:
                    bot.send_message(user_id, full_result)
            else:
                bot.send_message(user_id, "❌ No information found for this number")
        else:
            bot.send_message(user_id, f"❌ API server error (Status: {response.status_code})")
            
    except Exception as e:
        bot.send_message(user_id, f"❌ Error: {str(e)}")
    
    bot.send_message(user_id, "✅ Search completed!")
    show_main_menu(user_id)

# Process vehicle with API
def process_vehicle(message):
    user_id = str(message.from_user.id)
    
    # Check channels again
    not_joined = check_all_channels(message.from_user.id)
    if not_joined:
        show_channel_join_menu(user_id)
        return
    
    vin = message.text.strip()
    
    if not use_credit(user_id):
        bot.send_message(user_id, "❌ Not enough credits!")
        return start(message)
    
    show_animation(user_id, vin)
    
    try:
        response = requests.get(VEHICLE_API_URL + vin, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            
            if "error" in result:
                bot.send_message(user_id, "❌ Vehicle not found")
            else:
                result_text = "🚗 **Vehicle Information:**\n\n"
                for key, value in result.items():
                    if value and str(value).lower() not in ["null", "none", ""]:
                        formatted_key = key.replace('_', ' ').title()
                        result_text += f"• **{formatted_key}:** {value}\n"
                
                bot.send_message(user_id, result_text, parse_mode="Markdown")
        else:
            bot.send_message(user_id, "❌ Vehicle API error")
            
    except Exception as e:
        bot.send_message(user_id, f"❌ Error: {str(e)}")
    
    bot.send_message(user_id, "✅ Search completed!")
    show_main_menu(user_id)

# Run bot
if __name__ == "__main__":
    print("🤖 Bot is running...")
    print("♾️ Unlimited users:", UNLIMITED_USERS)
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Bot error: {e}")
