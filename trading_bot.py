import requests
import logging
import time
from cachetools import TTLCache, cached
from colorama import Fore, Style, init
from constants import BINANCE_API_URL, DEX_API_URL, BIRDEYE_API_URL, BIRDEYE_API_KEY, CACHE_TTL, CACHE_MAXSIZE
from utils import cache, format_large_number, load_wallet, save_wallet


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

RPC_URL = "https://api.mainnet-beta.solana.com"

def get_sol_price():
    try:
        response = requests.get(BINANCE_API_URL)
        response.raise_for_status()
        price_data = response.json()
        return float(price_data.get("price", 0))
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching Solana price from Binance API: {e}")
        return None

@cached(cache=TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL))
def get_token_information(contract_address):
    birdeye_url = f"{BIRDEYE_API_URL}{contract_address}"
    headers = {"accept": "application/json", "x-chain": "solana", "X-API-KEY": BIRDEYE_API_KEY}
    for attempt in range(3):
        try:
            response = requests.get(birdeye_url, headers=headers)
            response.raise_for_status()
            price_data = response.json()
            token_price = price_data.get("data", {}).get("value")
            if token_price is None:
                logging.error(f"Birdeye API did not return a valid price for {contract_address}")
                return None, None, None
            break
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logging.warning(f"Too Many Requests from Birdeye API. Retrying in {2 ** attempt} seconds...")
                time.sleep(2 ** attempt)
            else:
                logging.error(f"Error fetching token price from Birdeye API: {e}")
                return None, None, None
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching token price from Birdeye API: {e}")
            return None, None, None
    else:
        logging.error(f"Failed to fetch price from Birdeye after retries for {contract_address}")
        return None, None, None

    payload = {"jsonrpc": "2.0", "id": 1, "method": "getTokenSupply", "params": [contract_address]}
    try:
        response = requests.post(RPC_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        if "result" in data and "value" in data["result"]:
            supply_in_lamports = int(data["result"]["value"]["amount"])
            total_supply = supply_in_lamports / 10**6
        else:
            logging.error(f"No supply data found in RPC response for {contract_address}")
            return None, None, None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching token supply from RPC: {e}")
        return None, None, None

    dex_url = f"{DEX_API_URL}{contract_address}"
    try:
        response = requests.get(dex_url)
        response.raise_for_status()
        data = response.json()
        if not data or not isinstance(data, list) or len(data) == 0:
            logging.error(f"No data found in DexScreener response for {contract_address}")
            return None, None, None
        token_data = data[0]
        token_name = token_data["baseToken"]["name"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching token name from DexScreener: {e}")
        return None, None, None

    real_market_cap = float(token_price) * total_supply if token_price and total_supply else None
    return token_price, real_market_cap, token_name

def add_sol(user_id, amount):
    try:
        amount = float(amount)
        if amount <= 0:
            return "Amount must be greater than zero."
        wallet = load_wallet(user_id)
        wallet["sol_balance"] += amount
        save_wallet(user_id, wallet)
        return f"Added {amount} SOL to your wallet."
    except ValueError:
        return "Invalid amount. Please enter a number."

def refresh_token_info(contract_address):
    try:
        cache.pop(contract_address, None)
        return get_token_information(contract_address)
    except Exception as e:
        logging.error(f"Error refreshing token info for {contract_address}: {e}")
        return None, None, None

def buy_token(user_id, contract_address, amount_sol):
    wallet = load_wallet(user_id)
    sol_balance = wallet["sol_balance"]
    
    sol_price = get_sol_price()
    if not sol_price:
        return "Unable to fetch Solana price. Try again later."

    token_price, market_cap, token_name = get_token_information(contract_address)
    if not token_price or not market_cap:
        return f"Unable to fetch data for token with contract address: {contract_address}. Try again later."
    
    try:
        amount_sol = float(amount_sol)
        if amount_sol <= 0:
            return "Amount must be greater than zero."
        if amount_sol > sol_balance:
            return "Not enough SOL in your wallet."

        num_tokens = (sol_price / token_price) * amount_sol

        wallet["sol_balance"] -= amount_sol
        if contract_address not in wallet["tokens"]:
            wallet["tokens"][contract_address] = {"name": token_name, "quantity": 0, "purchase_market_cap": market_cap, "purchase_price": token_price, "sol_spent": 0, "sol_sold": 0}

        if wallet["tokens"][contract_address]["quantity"] == 0:
            wallet["tokens"][contract_address]["purchase_market_cap"] = market_cap

        AVG_MarketCap = (wallet["tokens"][contract_address]["purchase_market_cap"] * wallet["tokens"][contract_address]["quantity"] + market_cap * num_tokens) / (wallet["tokens"][contract_address]["quantity"] + num_tokens)
        
        wallet["tokens"][contract_address]["quantity"] += round(num_tokens, 2)
        wallet["tokens"][contract_address]["purchase_market_cap"] = AVG_MarketCap
        wallet["tokens"][contract_address]["sol_spent"] += amount_sol

        # Ajouter à l'historique
        if "history" not in wallet:
            wallet["history"] = []
        wallet["history"].append({
            "type": "buy",
            "token": token_name,
            "contract_address": contract_address,
            "quantity": round(num_tokens, 2),
            "sol_amount": amount_sol,
            "price_usd": token_price,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })

        save_wallet(user_id, wallet)
        return (
            f"You have purchased:\n"
            f"Token Name: {token_name}\n"
            f"Market Cap: ${format_large_number(market_cap)}\n"
            f"Number of tokens: {format_large_number(num_tokens)}\n"
            f"SOL used: {amount_sol} SOL (${amount_sol * sol_price:.2f})."
        )
    except ValueError:
        return "Invalid amount. Please enter a valid number."

def sell_token(user_id, contract_address, amount_tokens):
    """Vend un token pour du SOL pour un utilisateur donné."""
    wallet = load_wallet(user_id)
    
    if contract_address not in wallet["tokens"]:
        return f"No tokens found for contract address: {contract_address}"
    
    token_data = wallet["tokens"][contract_address]
    token_quantity = token_data["quantity"]
    
    if token_quantity <= 0.01:
        return f"No tokens available to sell for contract address: {contract_address}"

    token_price, _, token_name = get_token_information(contract_address)
    if not token_price:
        return f"Unable to fetch data for token with contract address: {contract_address}. Try again later."
    
    try:
        if "%" in amount_tokens:
            percentage = float(amount_tokens.replace("%", "").strip())
            if 0 <= percentage <= 100:
                amount_tokens = (percentage / 100) * token_quantity 
            else:
                return "Error: Percentage must be between 0 and 100."
        else:
            amount_tokens = float(amount_tokens)
            if amount_tokens <= 0.01:
                return "Amount must be greater than zero."
            if amount_tokens > token_quantity:
                return "Not enough tokens in your wallet."
        
        sol_price = get_sol_price()
        if not sol_price:
            return "Unable to fetch Solana price. Try again later."

        amount_sol = (token_price / sol_price) * amount_tokens
        
        # Calcul du PNL pour cette vente
        proportion_sold = amount_tokens / token_quantity
        sol_spent_for_sold = token_data["sol_spent"] * proportion_sold
        trade_pnl = amount_sol - sol_spent_for_sold  # PNL de cette transaction
        
        # Mise à jour du PNL général et du sol_balance (toujours exécuté)
        wallet["general_pnl"] = wallet.get("general_pnl", 0) + trade_pnl
        wallet["sol_balance"] += amount_sol  # Déplacé ici pour tous les cas

        # Gestion de la quantité restante
        if wallet["tokens"][contract_address]["quantity"] - amount_tokens < 0.01:
            del wallet["tokens"][contract_address]
            result = f"You have sold all {token_name} tokens ({amount_tokens:.2f}) for {amount_sol:.2f} SOL (${amount_sol * sol_price:.2f})."
        else:
            sol_pnl = ((amount_sol - token_data["sol_spent"]) / token_data["sol_spent"]) * 100
            Profit_Loss = (sol_pnl * token_data["sol_spent"]) / 100
            
            wallet["tokens"][contract_address]["quantity"] -= amount_tokens
            wallet["tokens"][contract_address]["sol_sold"] += amount_sol
            
            result = (
                f"You have sold {amount_tokens:.2f} of {token_name} tokens for {amount_sol:.2f} SOL (${amount_sol * sol_price:.2f}).\n"
            )
            if sol_pnl >= 0:
                result += f"You made {format_large_number(Profit_Loss)} ({sol_pnl:.2f}%) SOL."
            else:
                result += f"You lost {format_large_number(Profit_Loss)} ({sol_pnl:.2f}%) SOL."
            
            if wallet["tokens"][contract_address]["quantity"] < 0.01:
                del wallet["tokens"][contract_address]
                result += "\nRemaining quantity too small, token removed from wallet."

        # Ajouter à l'historique
        if "history" not in wallet:
            wallet["history"] = []
        wallet["history"].append({
            "type": "sell",
            "token": token_name,
            "contract_address": contract_address,
            "quantity": amount_tokens,
            "sol_amount": amount_sol,
            "price_usd": token_price,
            "pnl": trade_pnl,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })

        save_wallet(user_id, wallet)
        return result
    except ValueError:
        return "Invalid amount. Please enter a valid number."

init(autoreset=True)

def show_balance(user_id):
    wallet = load_wallet(user_id)
    sol_balance = wallet["sol_balance"]
    general_pnl = wallet.get("general_pnl", 0)
    sol_price = get_sol_price()

    balance_message = (
        "🚀 Your Wallet Balance 🚀\n\n"
        f"SOL Balance: {sol_balance:.2f} SOL (${sol_balance * sol_price:.2f})\n\n")
    
    if general_pnl == 0:
        balance_message += f"General PNL: {general_pnl:.2f} SOL\n\n"
    elif general_pnl > 0:
        balance_message += f"General PNL: +{general_pnl:.2f} SOL🟢\n\n"
    else:
        balance_message += f"General PNL: {general_pnl:.2f} SOL🔴\n\n"

    if "tokens" in wallet and wallet["tokens"]:
        balance_message += "📊 Tokens in your wallet:\n"
        for contract_address, data in wallet["tokens"].items():
            token_price, market_cap, token_name = get_token_information(contract_address)
            if not token_price or not market_cap:
                balance_message += (
                    f"\n➤ Token Name: {data['name']}\n"
                    f"   {contract_address}\n"
                    f"   Balance: {format_large_number(data['quantity'])}\n"
                    f"   Data unavailable due to API limits.\n"
                )
                continue

            pnl = (market_cap - data['purchase_market_cap']) / data['purchase_market_cap'] * 100 if data['purchase_market_cap'] else 0
            profit_loss = (pnl * data['sol_spent']) / 100 if data['sol_spent'] else 0

            balance_message += (
                f"\n➤ Token Name: {token_name}\n"
                f"   {contract_address}\n"
                f"   Balance: {format_large_number(data['quantity'])}\n"
                f"   Purchase Market Cap: ${format_large_number(data['purchase_market_cap'])}\n"
                f"   Current Market Cap: ${format_large_number(market_cap)}\n"
                f"   Buys {data['sol_spent']} SOL\n"
                f"   Sells {data['sol_sold']} SOL\n"
            )

            if pnl > 0:
                balance_message += f"   PNL: +{pnl:.2f}% (+{profit_loss:.2f} SOL)🟢\n"
            else:
                balance_message += f"   PNL: {pnl:.2f}% ({profit_loss:.2f} SOL)🔴\n"
    else:
        balance_message += "No tokens in your wallet.\n"
    return balance_message

def get_transaction_history(user_id):
    wallet = load_wallet(user_id)
    if "history" not in wallet or not wallet["history"]:
        return "No transaction history available."
    
    history_message = "📜 *Transaction History* 📜\n\n"
    for tx in wallet["history"][-10:]:  # Limite aux 10 dernières transactions
        if tx["type"] == "buy":
            history_message += (
                f"[{tx['timestamp']}] BUY {tx['token']}\n"
                f"Quantity: {format_large_number(tx['quantity'])}\n"
                f"SOL: {tx['sol_amount']:.2f} @ ${tx['price_usd']:.4f}\n\n"
            )
        elif tx["type"] == "sell":
            history_message += (
                f"[{tx['timestamp']}] SELL {tx['token']}\n"
                f"Quantity: {format_large_number(tx['quantity'])}\n"
                f"SOL: {tx['sol_amount']:.2f} @ ${tx['price_usd']:.4f}\n"
                f"PNL: {tx['pnl']:+.2f} SOL\n\n"
            )
    return history_message