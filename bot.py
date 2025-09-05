import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import requests
import time
import os
import random
import string
import datetime
import threading

# Bot Token
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8304954508:AAHLxY3YfPHwF1dnBxv8noLUhmz9YxV5MxU")
bot = telebot.TeleBot(BOT_TOKEN)

# API Configuration
API_TOKEN = os.environ.get('API_TOKEN', "7658050410:WJ8iTpuZ")
PEOPLE_API_URL = "https://leakosintapi.com/"
VEHICLE_API_URL = "https://vehicleinfo.zerovault.workers.dev/?VIN="

# Unlimited Users
UNLIMITED_USERS = [
    "1382801385", 
    "5145179256",
    "8270660057",
    "7176223037"
]

# Admin Users
ADMIN_USERS = ["8270660057"]  # Only this admin can see referral stats

# Channels
CHANNELS = [
    {"id": -1002851939876, "url": "https://t.me/+eB_J_ExnQT0wZDU9", "name": "Main Channel"},
    {"id": -1002321550721, "url": "https://t.me/taskblixosint", "name": "Updates Channel"},
    {"id": -1002921007541, "url": "https://t.me/CHOMUDONKIMAKICHUT", "name": "News Channel"}
]

# VIP Levels
VIP_LEVELS = {
    0: {"name": "Regular User", "min_credits": 0, "benefits": ["Basic searches"]},
    1: {"name": "Bronze Member", "min_credits": 50, "benefits": ["Faster searches", "Priority processing"]},
    2: {"name": "Silver Member", "min_credits": 150, "benefits": ["Advanced search options", "Daily bonus credits"]},
    3: {"name": "Gold Member", "min_credits": 500, "benefits": ["Exclusive data sources", "Priority support"]}
}

# Referral Bonuses
REFERRAL_BONUSES = {
    1: 10,    # 1 referral = 10 credits
    10: 50,   # 10 referrals = 50 credits
    150: 7    # 150 referrals = 7 daily unlimited
}

# Database setup
conn = sqlite3.connect('users.db', check_same_thread=False)

def execute_db(query, params=(), fetch_all=False):
    """Thread-safe database execution"""
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            if query.strip().upper().startswith('SELECT'):
                if fetch_all:
                    result = cursor.fetchall()
                else:
                    result = cursor.fetchone()
            else:
                result = None
            return result
    except Exception as e:
        print(f"Database error: {e}")
        return None

# Create users table
execute_db('''CREATE TABLE IF NOT EXISTS users 
             (user_id TEXT PRIMARY KEY, 
              credits INTEGER DEFAULT 3,
              daily_credits_claimed INTEGER DEFAULT 0,
              last_claim_date TEXT,
              referrals INTEGER DEFAULT 0,
              total_referrals INTEGER DEFAULT 0,
              vip_level INTEGER DEFAULT 0,
              total_earned_credits INTEGER DEFAULT 0,
              last_active_date TEXT,
              referral_bonus_claimed INTEGER DEFAULT 0)''')

# Helper Functions
def get_credits(user_id):
    if str(user_id) in UNLIMITED_USERS:
        return "♾️ Unlimited"
    result = execute_db("SELECT credits FROM users WHERE user_id=?", (str(user_id),))
    return result[0] if result else 0

def get_referrals_count(user_id):
    result = execute_db("SELECT referrals FROM users WHERE user_id=?", (str(user_id),))
    return result[0] if result else 0

def get_total_referrals(user_id):
    result = execute_db("SELECT total_referrals FROM users WHERE user_id=?", (str(user_id),))
    return result[0] if result else 0

def get_referral_bonus_claimed(user_id):
    result = execute_db("SELECT referral_bonus_claimed FROM users WHERE user_id=?", (str(user_id),))
    return result[0] if result else 0

def get_vip_level(user_id):
    result = execute_db("SELECT vip_level FROM users WHERE user_id=?", (str(user_id),))
    return result[0] if result else 0

def use_credit(user_id):
    if str(user_id) in UNLIMITED_USERS:
        return True
    
    referrals_count = get_referrals_count(user_id)
    if referrals_count >= 150:
        return True
    
    credits = get_credits(user_id)
    if credits > 0:
        execute_db("UPDATE users SET credits=credits-1 WHERE user_id=?", (str(user_id),))
        return True
    return False

def add_user(user_id):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    execute_db("INSERT OR IGNORE INTO users (user_id, last_claim_date, last_active_date) VALUES (?, ?, ?)", 
              (str(user_id), today, today))

def add_referral(referrer_id):
    if referrer_id:
        execute_db("UPDATE users SET referrals=referrals+1, total_referrals=total_referrals+1 WHERE user_id=?", 
                  (str(referrer_id),))
        return True
    return False

def earn_credits(user_id, credit_type, amount=1):
    """User को credits earn करने के multiple ways"""
    execute_db("UPDATE users SET credits = credits + ?, total_earned_credits = total_earned_credits + ? WHERE user_id = ?",
              (amount, amount, str(user_id)))
    return f"🎉 {amount} credits added!"

def get_daily_credits(user_id):
    """Get daily credits based on referral status"""
    referrals_count = get_referrals_count(user_id)
    
    if referrals_count >= 150:
        return "♾️ Unlimited"
    
    result = execute_db("SELECT daily_credits_claimed FROM users WHERE user_id = ?", (str(user_id),))
    if result:
        daily_claimed = result[0]
        return f"{3 - daily_claimed}/3"
    return "0/3"

# Channel Functions
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

# Referral Bonus System
def calculate_referral_bonus(referrals_count):
    """Calculate bonus based on referral milestones"""
    bonus = 0
    if referrals_count >= 1:
        bonus += REFERRAL_BONUSES[1]
    if referrals_count >= 10:
        bonus += REFERRAL_BONUSES[10] 
    if referrals_count >= 150:
        bonus += REFERRAL_BONUSES[150]
    return bonus

def check_referral_milestones(user_id):
    """Check and apply referral milestone bonuses"""
    referrals_count = get_referrals_count(user_id)
    bonus_claimed = get_referral_bonus_claimed(user_id)
    
    milestones_achieved = []
    if referrals_count >= 1 and bonus_claimed < 1:
        milestones_achieved.append(1)
    if referrals_count >= 10 and bonus_claimed < 10:
        milestones_achieved.append(10)
    if referrals_count >= 150 and bonus_claimed < 150:
        milestones_achieved.append(150)
    
    return milestones_achieved

def apply_referral_bonus(user_id, milestone):
    """Apply bonus for specific milestone"""
    bonus_amount = REFERRAL_BONUSES[milestone]
    earn_credits(user_id, "referral_bonus", bonus_amount)
    
    execute_db("UPDATE users SET referral_bonus_claimed = ? WHERE user_id = ?", 
              (milestone, str(user_id)))
    
    return bonus_amount

# Activity Tracking
def track_activity(user_id):
    """Track user activity and give rewards"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    result = execute_db("SELECT last_active_date, total_earned_credits FROM users WHERE user_id = ?", (str(user_id),))
    
    if result:
        last_active, total_credits = result
        
        # Daily activity bonus
        if last_active != today:
            earn_credits(user_id, "activity", 2)
            execute_db("UPDATE users SET last_active_date = ? WHERE user_id = ?", (today, str(user_id)))
        
        # Check VIP upgrade
        check_vip_upgrade(user_id)

def check_vip_upgrade(user_id):
    """Automatically check and upgrade VIP level"""
    result = execute_db("SELECT total_earned_credits, vip_level FROM users WHERE user_id = ?", (str(user_id),))
    
    if result:
        total_credits, current_level = result
        
        for level, info in VIP_LEVELS.items():
            if level > current_level and total_credits >= info["min_credits"]:
                execute_db("UPDATE users SET vip_level = ? WHERE user_id = ?", (level, str(user_id)))
                
                # Send upgrade notification
                bot.send_message(
                    user_id, 
                    f"🎉 VIP UPGRADE! You are now {info['name']}!\n\n"
                    f"✨ New Benefits: {', '.join(info['benefits'])}"
                )
                
                # Give upgrade bonus
                upgrade_bonus = level * 10
                earn_credits(user_id, "vip_bonus", upgrade_bonus)
                bot.send_message(user_id, f"🎁 Upgrade Bonus: {upgrade_bonus} credits added!")

# Admin Referral Functions
def get_all_referrals_stats():
    """सभी users के referral statistics get करें"""
    query = """
    SELECT user_id, referrals, total_referrals 
    FROM users 
    WHERE referrals > 0 
    ORDER BY referrals DESC
    """
    return execute_db(query, fetch_all=True)

# Main Handlers
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
    
    # Check for referral
    if len(message.text.split()) > 1:
        referrer_id = message.text.split()[1]
        if referrer_id != user_id:
            # Referrer को credit दें
            success = add_referral(referrer_id)
            # New user को भी extra credit दें
            execute_db("UPDATE users SET credits = credits + 1 WHERE user_id = ?", (str(user_id),))
            
            # दोनों को congratulations message
            bot.send_message(user_id, "🎉 You joined using a referral link! +1 credit added to your account!")
            
            # Referrer को message
            try:
                if success:
                    referrals_count = get_referrals_count(referrer_id)
                    total_refs = get_total_referrals(referrer_id)
                    
                    msg = f"🎉 New referral! Total: {referrals_count}/150 (All: {total_refs})"
                    
                    # Check if milestone achieved
                    milestones = check_referral_milestones(referrer_id)
                    if milestones:
                        msg += f"\n🎁 You have {len(milestones)} unclaimed bonuses! Use /referral to claim."
                    
                    bot.send_message(referrer_id, msg)
            except Exception as e:
                print(f"Could not send message to referrer: {e}")
    
    # Show main menu
    show_main_menu(user_id)
    track_activity(user_id)

def show_main_menu(user_id):
    credits = get_credits(user_id)
    daily_credits = get_daily_credits(user_id)
    referrals_count = get_referrals_count(user_id)
    vip_level = get_vip_level(user_id)
    vip_info = VIP_LEVELS[vip_level]
    
    # Special message for 150+ referrals
    if referrals_count >= 150:
        status_message = "🏆 150+ Referrals - DAILY UNLIMITED CREDITS! 🎉"
    else:
        status_message = f"👥 Referrals: {referrals_count}/150 (Need {150-referrals_count} more for unlimited)"
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📞 Number Info", callback_data="number"))
    markup.row(InlineKeyboardButton("🚗 Vehicle Info", callback_data="vehicle"))
    markup.row(InlineKeyboardButton("💳 Balance", callback_data="balance"))
    markup.row(InlineKeyboardButton("🤝 Referral Program", callback_data="referral"))
    markup.row(InlineKeyboardButton("🎁 Daily Reward", callback_data="daily"))
    
    # Admin user के लिए extra button
    if str(user_id) in ADMIN_USERS:
        markup.row(InlineKeyboardButton("👑 Admin Dashboard", callback_data="admin_dashboard"))
    
    welcome_text = f"""
👋 Welcome! ({vip_info['name']})

💎 Available Credits: {credits}
📅 Daily Credits: {daily_credits}
⭐ VIP Level: {vip_level}

{status_message}

✨ Choose an option below:
"""
    
    bot.send_message(user_id, welcome_text, reply_markup=markup)

# Callback Handlers
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = str(call.from_user.id)
    
    if call.data == "number":
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
        daily_credits = get_daily_credits(user_id)
        referrals_count = get_referrals_count(user_id)
        
        stats_text = f"""
📊 **Your Account Balance:**

💎 Available Credits: {credits}
📅 Daily Credits: {daily_credits}
👥 Successful Referrals: {referrals_count}/150

"""
        if referrals_count >= 150:
            stats_text += "🎉 **UNLIMITED DAILY CREDITS ACTIVATED!** 🎉"
        
        bot.send_message(user_id, stats_text, parse_mode="Markdown")
    
    elif call.data == "referral":
        handle_referral(call)
    
    elif call.data == "daily":
        handle_daily_reward(call)
    
    elif call.data == "verify_join":
        not_joined = check_all_channels(call.from_user.id)
        if not_joined:
            bot.answer_callback_query(call.id, "Please join all channels first!")
            show_channel_join_menu(user_id)
        else:
            bot.answer_callback_query(call.id, "Thanks for joining!")
            show_main_menu(user_id)
    
    elif call.data == "claim_bonuses":
        handle_bonus_claim(call)
    
    elif call.data == "admin_dashboard":
        handle_admin_dashboard(call)
    
    elif call.data == "referral_stats":
        handle_referral_stats(call)
    
    elif call.data == "top_referrers":
        handle_top_referrers(call)
    
    elif call.data == "user_ref_search":
        handle_user_ref_search(call)
    
    elif call.data == "main_menu":
        show_main_menu(user_id)
    
    bot.answer_callback_query(call.id)

# Admin Dashboard Handlers
def handle_admin_dashboard(call):
    user_id = str(call.from_user.id)
    
    if user_id not in ADMIN_USERS:
        bot.answer_callback_query(call.id, "❌ Access denied!")
        return
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📊 Referral Stats", callback_data="referral_stats"))
    markup.row(InlineKeyboardButton("🏆 Top Referrers", callback_data="top_referrers"))
    markup.row(InlineKeyboardButton("📋 User Details", callback_data="user_ref_search"))
    markup.row(InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu"))
    
    bot.edit_message_text(
        chat_id=user_id,
        message_id=call.message.message_id,
        text="👑 **Admin Dashboard**\n\nSelect an option to view referral analytics:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

def handle_referral_stats(call):
    user_id = str(call.from_user.id)
    
    if user_id not in ADMIN_USERS:
        bot.answer_callback_query(call.id, "❌ Access denied!")
        return
    
    stats = get_all_referrals_stats()
    
    if not stats:
        bot.answer_callback_query(call.id, "📊 No referral data available!")
        return
    
    message_text = "🏆 **Referral Leaderboard**\n\n"
    total_referrals = 0
    active_referrers = len(stats)
    
    for i, (user_id, referrals, total_refs) in enumerate(stats, 1):
        message_text += f"{i}. User: `{user_id}` - Successful: {referrals} - Total: {total_refs}\n"
        total_referrals += referrals
    
    message_text += f"\n📈 **Total Statistics:**\n"
    message_text += f"• Successful Referrals: {total_referrals}\n"
    message_text += f"• Active Referrers: {active_referrers}\n"
    message_text += f"• Average per User: {total_referrals/active_referrers:.1f}\n"
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_dashboard"))
    
    bot.edit_message_text(
        chat_id=user_id,
        message_id=call.message.message_id,
        text=message_text,
        reply_markup=markup,
        parse_mode="Markdown"
    )

def handle_top_referrers(call):
    user_id = str(call.from_user.id)
    
    if user_id not in ADMIN_USERS:
        bot.answer_callback_query(call.id, "❌ Access denied!")
        return
    
    query = """
    SELECT user_id, referrals, total_referrals 
    FROM users 
    WHERE referrals > 0 
    ORDER BY referrals DESC 
    LIMIT 10
    """
    top_users = execute_db(query, fetch_all=True)
    
    if not top_users:
        bot.answer_callback_query(call.id, "🏆 No top referrers yet!")
        return
    
    message_text = "🎯 **Top 10 Referrers**\n\n"
    
    for i, (user_id, referrals, total_refs) in enumerate(top_users, 1):
        success_rate = (referrals/total_refs*100) if total_refs > 0 else 0
        message_text += f"{i}. `{user_id}` - {referrals} ✅ ({success_rate:.1f}% success rate)\n"
    
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_dashboard"))
    
    bot.edit_message_text(
        chat_id=user_id,
        message_id=call.message.message_id,
        text=message_text,
        reply_markup=markup,
        parse_mode="Markdown"
    )

def handle_user_ref_search(call):
    user_id = str(call.from_user.id)
    
    if user_id not in ADMIN_USERS:
        bot.answer_callback_query(call.id, "❌ Access denied!")
        return
    
    msg = bot.send_message(user_id, "🔍 Enter User ID to check referral details:")
    bot.register_next_step_handler(msg, process_user_ref_details)

def process_user_ref_details(message):
    user_id = str(message.from_user.id)
    target_user = message.text.strip()
    
    if user_id not in ADMIN_USERS:
        return
    
    # Get detailed referral info
    query = """
    SELECT user_id, referrals, total_referrals, 
           referral_bonus_claimed, last_active_date
    FROM users WHERE user_id = ?
    """
    result = execute_db(query, (target_user,))
    
    if not result:
        bot.send_message(user_id, f"❌ User `{target_user}` not found!")
        return
    
    user_id, referrals, total_refs, bonus_claimed, last_active = result
    
    message_text = f"""
📋 **User Referral Report:** `{user_id}`

✅ Successful Referrals: {referrals}
📊 Total Referral Attempts: {total_refs}
🎯 Success Rate: {(referrals/total_refs*100) if total_refs > 0 else 0:.1f}%

🏆 Bonus Level Claimed: {bonus_claimed}
📅 Last Active: {last_active if last_active else 'Never'}

📈 **Milestone Progress:**
• 1 Referral: {'✅' if referrals >= 1 else '❌'} (10 credits)
• 10 Referrals: {'✅' if referrals >= 10 else '❌'} (50 credits)  
• 150 Referrals: {'✅' if referrals >= 150 else '❌'} (7 daily unlimited)
"""
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_dashboard"))
    
    bot.send_message(user_id, message_text, reply_markup=markup, parse_mode="Markdown")

# Referral Handler
def handle_referral(call):
    user_id = str(call.from_user.id)
    referral_link = f"https://t.me/rajputteam_bot?start={user_id}"
    
    referrals_count = get_referrals_count(user_id)
    total_referrals = get_total_referrals(user_id)
    
    milestones = check_referral_milestones(user_id)
    
    message_text = f"""
🤝 **Referral Program - Earn Unlimited Credits!**

🔗 **Your Referral Link:**
`{referral_link}`

📊 **Your Referral Stats:**
• 👥 Successful Referrals: {referrals_count}
• 📈 Total Referrals: {total_referrals}

🎯 **Referral Milestones:**
"""
    for milestone, bonus in REFERRAL_BONUSES.items():
        status = "✅ Achieved" if referrals_count >= milestone else "❌ Not achieved"
        if milestone == 150:
            bonus_text = "7 Daily Unlimited Credits"
        else:
            bonus_text = f"{bonus} Credits"
        
        message_text += f"\n{milestone} Referrals: {bonus_text} {status}"
    
    if milestones:
        message_text += f"\n\n🎁 **Unclaimed Bonuses:** {len(milestones)} available!"
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🎁 Claim Bonuses", callback_data="claim_bonuses"))
    else:
        markup = None
    
    message_text += f"""

📣 **How it works:**
1. Share your referral link with friends
2. When they join using your link
3. You get credits automatically
4. Reach milestones for bigger bonuses!

💎 **Special Reward:** 150 Referrals = 7 Daily Unlimited Credits!
"""
    
    bot.send_message(user_id, message_text, reply_markup=markup, parse_mode="Markdown")

# Daily Reward Handler
def handle_daily_reward(call):
    user_id = str(call.from_user.id)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    result = execute_db("SELECT last_claim_date FROM users WHERE user_id = ?", (str(user_id),))
    
    if result and result[0] == today:
        bot.send_message(user_id, "❌ You've already claimed your daily reward today!")
        return
    
    daily_credits = random.randint(1, 5)
    earn_credits(user_id, "daily", daily_credits)
    
    execute_db("UPDATE users SET last_claim_date = ? WHERE user_id = ?", (today, str(user_id)))
    
    bot.send_message(user_id, f"🎁 Daily Reward: {daily_credits} credits added! Total: {get_credits(user_id)}")

# Bonus Claim Handler
def handle_bonus_claim(call):
    user_id = str(call.from_user.id)
    milestones = check_referral_milestones(user_id)
    
    if not milestones:
        bot.answer_callback_query(call.id, "No bonuses available to claim!")
        return
    
    total_bonus = 0
    for milestone in milestones:
        bonus = apply_referral_bonus(user_id, milestone)
        total_bonus += bonus
    
    bot.send_message(user_id, f"🎉 Congratulations! You claimed {len(milestones)} bonuses totaling {total_bonus} credits!")
    bot.answer_callback_query(call.id, "Bonuses claimed successfully!")

# Search Processing Functions
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

def process_number(message):
    user_id = str(message.from_user.id)
    phone = message.text.strip()
    
    not_joined = check_all_channels(message.from_user.id)
    if not_joined:
        show_channel_join_menu(user_id)
        return
    
    phone = phone.replace('+', '').replace(' ', '').replace('-', '')
    
    if not phone.isdigit():
        bot.send_message(user_id, "❌ Please enter numbers only (e.g., 9565982635)")
        return start(message)
    
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

def process_vehicle(message):
    user_id = str(message.from_user.id)
    
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

# Background Scheduler for Daily Resets
def daily_reset_scheduler():
    """Run daily reset at midnight"""
    while True:
        now = datetime.datetime.now()
        if now.hour == 0 and now.minute == 0:
            today = now.strftime("%Y-%m-%d")
            execute_db("UPDATE users SET daily_credits_claimed = 0, last_claim_date = ? WHERE last_claim_date != ?", 
                      (today, today))
            print("Daily credits reset for all users")
        time.sleep(60)

# Start scheduler in background thread
scheduler_thread = threading.Thread(target=daily_reset_scheduler, daemon=True)
scheduler_thread.start()

# Run bot
if __name__ == "__main__":
    print("🤖 Bot is running...")
    print("♾️ Unlimited users:", UNLIMITED_USERS)
    print("👑 Admin users:", ADMIN_USERS)
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Bot error: {e}")
