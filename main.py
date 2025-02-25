from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from trading_bot import add_sol, buy_token, sell_token, show_balance, get_token_information, refresh_token_info, load_wallet, get_sol_price, get_transaction_history
from constants import TELEGRAM_BOT_TOKEN
from utils import format_large_number, cache
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Réduire les états en supprimant ceux des limit orders
(
    STATE_IDLE,
    STATE_ADD_SOL,
    STATE_BUY_TOKEN_CA,
    STATE_BUY_TOKEN_AMOUNT,
    STATE_SELL_TOKEN_CA,
    STATE_SELL_TOKEN_AMOUNT,
) = range(6)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    wallet = load_wallet(user_id)
    sol_balance = wallet["sol_balance"]
    sol_price = get_sol_price() or 0
    general_pnl = wallet.get("general_pnl", 0)
    pnl_display = f"+{general_pnl:.2f}" if general_pnl >= 0 else f"{general_pnl:.2f}"

    keyboard = [
        [
            InlineKeyboardButton("➕ Add SOL", callback_data="add_sol"),
            InlineKeyboardButton("💰 Show Balance", callback_data="show_balance")
        ],
        [
            InlineKeyboardButton("🛒 Buy Token", callback_data="buy_token"),
            InlineKeyboardButton("📉 Sell Token", callback_data="sell_token")
        ],
        [
            InlineKeyboardButton("📜 History", callback_data="show_history")  # Suppression de "Set Limit Order"
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🚀 *Welcome to the Cudly Train Trading Bot!* 🚀\n\n"
        f"SOL Balance: {sol_balance:.2f} SOL (${sol_balance * sol_price:.2f})\n"
        f"PNL wallet: {pnl_display} SOL (${general_pnl * sol_price:.2f})\n\n"
        "Select an option below to get started:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    message_id = query.message.message_id

    if query.data == "show_history":
        history_message = get_transaction_history(user_id)
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(history_message, reply_markup=reply_markup, parse_mode="Markdown")

    elif query.data == "add_sol":
        msg = await context.bot.send_message(chat_id, "Please enter the amount of SOL to add:")
        context.user_data["last_message_id"] = msg.message_id
        context.user_data["state"] = STATE_ADD_SOL

    elif query.data == "buy_token":
        msg = await context.bot.send_message(chat_id, "Please enter the contract address of the token you want to buy:")
        context.user_data["last_message_id"] = msg.message_id
        context.user_data["state"] = STATE_BUY_TOKEN_CA

    elif query.data == "sell_token":
        wallet = load_wallet(user_id)
        if not wallet.get("tokens"):
            await context.bot.send_message(chat_id, "No tokens available to sell.")
            return
        keyboard = []
        for ca, data in wallet["tokens"].items():
            token_price, market_cap, _ = get_token_information(ca)
            if token_price and market_cap:
                pnl = (market_cap - data['purchase_market_cap']) / data['purchase_market_cap'] * 100 if data['purchase_market_cap'] else 0
                profit_loss = (pnl * data['sol_spent']) / 100 if data['sol_spent'] else 0
                pnl_display = f"+{profit_loss:.2f}" if profit_loss >= 0 else f"{profit_loss:.2f}"
                button_text = f"{data['name']} ({format_large_number(data['quantity'])}) {pnl_display} SOL"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sell_{ca}")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id, "Select a token to sell:", reply_markup=reply_markup)
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)

    elif query.data.startswith("sell_"):
        ca = query.data.split("sell_")[1]
        context.user_data["contract_address"] = ca
        wallet = load_wallet(user_id)
        token_data = wallet["tokens"][ca]
        token_price, _, token_name = get_token_information(ca)
        if token_price:
            msg = await context.bot.send_message(chat_id, f"Token: {token_name}\nBalance: {format_large_number(token_data['quantity'])}\nEnter amount to sell:")
            context.user_data["last_message_id"] = msg.message_id
            context.user_data["state"] = STATE_SELL_TOKEN_AMOUNT
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        else:
            await context.bot.send_message(chat_id, "Unable to fetch token info. Try again.")

    elif query.data == "show_balance":
        balance_message = show_balance(user_id)
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_balance")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(balance_message, reply_markup=reply_markup, parse_mode="Markdown")

    elif query.data == "refresh_balance":
        cache.clear()
        balance_message = show_balance(user_id)
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_balance")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(balance_message, reply_markup=reply_markup, parse_mode="Markdown")

    elif query.data == "back_to_menu":
        wallet = load_wallet(user_id)
        sol_balance = wallet["sol_balance"]
        sol_price = get_sol_price() or 0
        general_pnl = wallet.get("general_pnl", 0)
        pnl_display = f"+{general_pnl:.2f}" if general_pnl >= 0 else f"{general_pnl:.2f}"
        keyboard = [
            [InlineKeyboardButton("➕ Add SOL", callback_data="add_sol"), InlineKeyboardButton("💰 Show Balance", callback_data="show_balance")],
            [InlineKeyboardButton("🛒 Buy Token", callback_data="buy_token"), InlineKeyboardButton("📉 Sell Token", callback_data="sell_token")],
            [InlineKeyboardButton("📜 History", callback_data="show_history")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"🚀 *Welcome to the Cudly Train Trading Bot!* 🚀\n\n"
            f"SOL Balance: {sol_balance:.2f} SOL (${sol_balance * sol_price:.2f})\n"
            f"PNL wallet: {pnl_display} SOL (${general_pnl * sol_price:.2f})\n\n"
            "Select an option below to get started:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

    elif query.data == "back_to_balance":
        balance_message = show_balance(user_id)
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_balance")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(balance_message, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    text = update.message.text
    message_id = update.message.message_id

    if "state" not in context.user_data:
        context.user_data["state"] = STATE_IDLE

    state = context.user_data["state"]
    last_message_id = context.user_data.get("last_message_id")

    try:
        if last_message_id:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_message_id)
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)

        keyboard = [
            [InlineKeyboardButton("💰 Back to Balance", callback_data="back_to_balance"),
             InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if state == STATE_ADD_SOL:
            response = add_sol(user_id, text)
            await context.bot.send_message(chat_id, response, reply_markup=reply_markup)
            context.user_data["state"] = STATE_IDLE

        elif state == STATE_BUY_TOKEN_CA:
            context.user_data["contract_address"] = text
            token_price, market_cap, token_name = get_token_information(text)
            if token_price:
                msg = await context.bot.send_message(chat_id, "Please enter the amount of SOL you want to spend:")
                context.user_data["last_message_id"] = msg.message_id
                context.user_data["state"] = STATE_BUY_TOKEN_AMOUNT
            else:
                await context.bot.send_message(chat_id, "Unable to fetch token information. Please try again.", reply_markup=reply_markup)

        elif state == STATE_BUY_TOKEN_AMOUNT:
            contract_address = context.user_data["contract_address"]
            response = buy_token(user_id, contract_address, text)
            await context.bot.send_message(chat_id, response, reply_markup=reply_markup)
            context.user_data["state"] = STATE_IDLE

        elif state == STATE_SELL_TOKEN_AMOUNT:
            contract_address = context.user_data["contract_address"]
            response = sell_token(user_id, contract_address, text)
            await context.bot.send_message(chat_id, response, reply_markup=reply_markup)
            context.user_data["state"] = STATE_IDLE

        else:
            await context.bot.send_message(chat_id, "Please select an option from the menu.", reply_markup=reply_markup)

    except Exception as e:
        keyboard = [
            [InlineKeyboardButton("💰 Back to Balance", callback_data="back_to_balance"),
             InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id, f"Error: {str(e)}. Please try again.", reply_markup=reply_markup)
        context.user_data["state"] = STATE_IDLE

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == "__main__":
    main()