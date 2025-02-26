import os
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
print(f"Telegram Bot Token loaded: {TELEGRAM_BOT_TOKEN}")


WALLET_FILE = "wallet.json"
WALLETS_DIR = "/data/wallets"
# URLs des API
BINANCE_API_URL = "https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT"
DEX_API_URL = "https://api.dexscreener.com/tokens/v1/solana/"
BIRDEYE_API_URL = "https://public-api.birdeye.so/defi/price?address="
RPC_URL = "https://api.mainnet-beta.solana.com"  # URL du RPC public

BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY")

# Cache
CACHE_TTL = 10  # 3 minutes
CACHE_MAXSIZE = 128

# Répertoire telegram_token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
import os
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
print(f"Telegram Bot Token loaded: {TELEGRAM_BOT_TOKEN}")


WALLET_FILE = "wallet.json"
# Utiliser /tmp pour le cloud gratuit (Railway), /data pour persistance si payant
WALLETS_DIR = "/tmp/wallets" if os.getenv("RAILWAY_ENVIRONMENT") else "C:\\Users\\zacha\\Desktop\\VScode\\DemoBot\\cuddly-train\\wallets"
LIMIT_ORDERS_DIR = "/tmp/limit_orders" if os.getenv("RAILWAY_ENVIRONMENT") else "C:\\Users\\zacha\\Desktop\\VScode\\DemoBot\\cuddly-train\\limit_orders"
# URLs des API
BINANCE_API_URL = "https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT"
DEX_API_URL = "https://api.dexscreener.com/tokens/v1/solana/"
BIRDEYE_API_URL = "https://public-api.birdeye.so/defi/price?address="
RPC_URL = "https://api.mainnet-beta.solana.com"  # URL du RPC public

BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY")

# Cache
CACHE_TTL = 10  # 3 minutes
CACHE_MAXSIZE = 128

# Répertoire telegram_token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
