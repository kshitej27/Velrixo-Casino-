import os
import random
import sqlite3
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ===== DATABASE SETUP =====
DB_FILE = "velrixo.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 1000,
                last_bonus TEXT
            )""")
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT balance, last_bonus FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (user_id, balance) VALUES (?, 1000)", (user_id,))
        conn.commit()
        conn.close()
        return 1000, None
    conn.close()
    return user

def update_balance(user_id, change):
    bal, _ = get_user(user_id)
    new_bal = bal + change
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_bal, user_id))
    conn.commit()
    conn.close()

def set_bonus_time(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def can_claim_bonus(user_id):
    _, last_bonus = get_user(user_id)
    if not last_bonus:
        return True
    last_time = datetime.fromisoformat(last_bonus)
    return datetime.now() - last_time > timedelta(hours=24)

def get_balance(user_id):
    bal, _ = get_user(user_id)
    return bal

# ===== BOT COMMANDS =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    init_db()
    await update.message.reply_text(
        f"🎰 Welcome to *Velrixo Casino*, {user.first_name}! 🎰\n\n"
        "💰 You start with 1000 coins.\n"
        "Try commands like:\n"
        "/balance — Check coins\n"
        "/dailybonus — Claim bonus\n"
        "/spin — Slot machine\n"
        "/coinflip — Flip a coin\n"
        "/blackjack — Play blackjack\n"
        "/bet <amount> — Simple bet\n"
        "/transfer @user <amount> — Send coins\n"
        "/leaderboard — Top players"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bal = get_balance(update.effective_user.id)
    await update.message.reply_text(f"💰 Your balance: {bal} coins")

async def dailybonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if can_claim_bonus(user_id):
        update_balance(user_id, 500)
        set_bonus_time(user_id)
        await update.message.reply_text("🎁 You claimed your daily bonus of 500 coins!")
    else:
        await update.message.reply_text("⏳ You’ve already claimed your bonus today!")

async def spin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bet = 100
    bal = get_balance(user_id)
    if bal < bet:
        await update.message.reply_text("❌ Not enough coins!")
        return
    symbols = ["🍒", "🍋", "🔔", "⭐", "💎"]
    result = [random.choice(symbols) for _ in range(3)]
    if len(set(result)) == 1:
        winnings = bet * 5
        update_balance(user_id, winnings)
        msg = f"🎰 {' '.join(result)} 🎰\nJACKPOT! You won {winnings} coins!"
    elif len(set(result)) == 2:
        winnings = bet * 2
        update_balance(user_id, winnings)
        msg = f"🎰 {' '.join(result)} 🎰\nNice! You won {winnings} coins!"
    else:
        update_balance(user_id, -bet)
        msg = f"🎰 {' '.join(result)} 🎰\nYou lost {bet} coins!"
    await update.message.reply_text(msg)

async def coinflip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bet = 100
    bal = get_balance(user_id)
    if bal < bet:
        await update.message.reply_text("❌ Not enough coins!")
        return
    choice = random.choice(["Heads", "Tails"])
    if random.choice([True, False]):
        update_balance(user_id, bet)
        result = f"🪙 {choice}! You won {bet} coins!"
    else:
        update_balance(user_id, -bet)
        result = f"🪙 {choice}! You lost {bet} coins!"
    await update.message.reply_text(result)

async def blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    player = random.randint(15, 23)
    dealer = random.randint(17, 21)
    if player > 21:
        result = "You busted! ❌"
        update_balance(user_id, -200)
    elif dealer > 21 or player > dealer:
        result = "You win! 🎉"
        update_balance(user_id, 300)
    elif player == dealer:
        result = "It's a tie! 😐"
    else:
        result = "Dealer wins! 😞"
        update_balance(user_id, -200)
    await update.message.reply_text(f"🃏 Your hand: {player}\nDealer: {dealer}\n{result}")

async def bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        amount = int(context.args[0])
    except:
        await update.message.reply_text("Usage: /bet <amount>")
        return
    bal = get_balance(user_id)
    if amount <= 0 or amount > bal:
        await update.message.reply_text("❌ Invalid bet amount!")
        return
    if random.random() < 0.5:
        update_balance(user_id, amount)
        await update.message.reply_text(f"🔥 You won {amount} coins!")
    else:
        update_balance(user_id, -amount)
        await update.message.reply_text(f"💀 You lost {amount} coins!")

async def transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2 or not update.message.reply_to_message:
        await update.message.reply_text("Usage: Reply to user with `/transfer <amount>`")
        return
    try:
        amount = int(context.args[0])
    except:
        await update.message.reply_text("Invalid amount.")
        return
    sender = update.effective_user.id
    receiver = update.message.reply_to_message.from_user.id
    if sender == receiver:
        await update.message.reply_text("❌ You can’t send coins to yourself!")
        return
    bal = get_balance(sender)
    if amount <= 0 or amount > bal:
        await update.message.reply_text("❌ Invalid or insufficient balance!")
        return
    update_balance(sender, -amount)
    update_balance(receiver, amount)
    await update.message.reply_text(f"💸 You sent {amount} coins to {update.message.reply_to_message.from_user.first_name}!")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10")
    top = c.fetchall()
    conn.close()
    text = "🏆 Velrixo Leaderboard 🏆\n"
    for i, (uid, bal) in enumerate(top, start=1):
        text += f"{i}. ID: {uid} — {bal} coins\n"
    await update.message.reply_text(text)

def main():
    init_db()
    token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("dailybonus", dailybonus))
    app.add_handler(CommandHandler("spin", spin))
    app.add_handler(CommandHandler("coinflip", coinflip))
    app.add_handler(CommandHandler("blackjack", blackjack))
    app.add_handler(CommandHandler("bet", bet))
    app.add_handler(CommandHandler("transfer", transfer))
    app.add_handler(CommandHandler("leaderboard", leaderboard))

    app.run_polling()

if __name__ == "__main__":
    main()
