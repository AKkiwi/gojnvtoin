import os
import json
from cachetools import TTLCache, cached
from colorama import Fore, Style
from constants import WALLETS_DIR, CACHE_TTL, CACHE_MAXSIZE


# Initialisation du cache
cache = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)

def get_wallet_file(user_id):
    """Retourne le chemin du fichier de portefeuille pour un utilisateur donné."""
    if not os.path.exists(WALLETS_DIR):
        os.makedirs(WALLETS_DIR)
    return os.path.join(WALLETS_DIR, f"wallet_{user_id}.json")

def load_wallet(user_id):
    """Charge les données du portefeuille pour un utilisateur donné."""
    wallet_file = get_wallet_file(user_id)
    if not os.path.exists(wallet_file):
        with open(wallet_file, "w") as file:
            json.dump({"sol_balance": 0, "tokens": {}, "general_pnl": 0, "history" :[]}, file)
    
    with open(wallet_file, "r") as file:
        return json.load(file)

def save_wallet(user_id, wallet):
    """Sauvegarde les données du portefeuille pour un utilisateur donné."""
    wallet_file = get_wallet_file(user_id)
    # Supprime les tokens avec une quantité inférieure à 1
    tokens_to_remove = [address for address, info in wallet["tokens"].items() if info["quantity"] < 1]
    for address in tokens_to_remove:
        del wallet["tokens"][address]

    with open(wallet_file, "w") as file:
        json.dump(wallet, file, indent=4)


def format_large_number(number):
    """Formate un grand nombre avec des suffixes comme k, M, B."""
    if number >= 1e9:
        return f"{number / 1e9:.2f}B"
    elif number >= 1e6:
        return f"{number / 1e6:.2f}M"
    elif number >= 1e3:
        return f"{number / 1e3:.2f}k"
    else:
        return f"{number:.2f}"
    
def clear_console():
    """Efface la console."""
    os.system("cls" if os.name == "nt" else "clear")    

def refresh_cache():
    """Rafraîchit le cache."""
