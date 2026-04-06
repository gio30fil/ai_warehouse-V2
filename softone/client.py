import requests
import logging
from config import Config

logger = logging.getLogger(__name__)

# Cached clientId returned after a successful login
_client_id = None


def login() -> str | None:
    """Authenticate against SoftOne web services."""
    global _client_id

    payload = {
        "service": "login",
        "username": Config.SOFTONE_USERNAME,
        "password": Config.SOFTONE_PASSWORD,
        "appId": Config.SOFTONE_APPID,
        "company": Config.SOFTONE_COMPANY,
        "branch": Config.SOFTONE_BRANCH,
        "module": Config.SOFTONE_MODULE,
        "refid": Config.SOFTONE_REFID,
    }

    try:
        response = requests.post(Config.SOFTONE_LOGIN_URL, json=payload, timeout=30)
        data = response.json()

        if data.get("success"):
            _client_id = data.get("clientID")
            logger.info(f"SoftOne login OK — clientId: {_client_id[:20]}...")
            return _client_id

        logger.error(f"SoftOne login failed: {data.get('error')}")
    except Exception as e:
        logger.error(f"SoftOne login exception: {e}")

    return None


def _ensure_session() -> str | None:
    """Ensure we have a valid session, auto-login if needed."""
    global _client_id
    if not _client_id:
        _client_id = login()
    return _client_id


def fetch_products(upddate_from: str = "2026-01-01T00:00:00") -> list:
    """Fetches products from SoftOne."""
    client_id = _ensure_session()
    if not client_id:
        return []

    payload = {
        "service": "getItems",
        "clientid": client_id,
        "appid": Config.SOFTONE_APPID,
        "upddate_from": upddate_from,
    }

    try:
        response = requests.post(Config.SOFTONE_API_URL, json=payload, timeout=60)
        data = response.json()

        if data.get("success"):
            products = data.get("data", [])
            logger.info(f"Fetched {len(products)} products from SoftOne")
            return products

        logger.error(f"fetch_products error: {data.get('error')}")
    except Exception as e:
        logger.error(f"fetch_products exception: {e}")

    return []


def fetch_stock(whouse_code: str | None = None) -> list:
    """Fetches stock levels per warehouse from SoftOne."""
    client_id = _ensure_session()
    if not client_id:
        return []

    payload = {
        "service": "getItemsStockPerWhouse",
        "clientid": client_id,
        "appid": Config.SOFTONE_APPID,
    }

    if whouse_code:
        payload["whouse_code"] = whouse_code

    try:
        response = requests.post(Config.SOFTONE_API_URL, json=payload, timeout=60)
        data = response.json()

        if data.get("success"):
            return data.get("data", [])

        logger.error(f"fetch_stock error: {data.get('error')}")
    except Exception as e:
        logger.error(f"fetch_stock exception: {e}")

    return []


def fetch_pending_orders() -> list:
    """Fetches pending sales orders from SoftOne."""
    client_id = _ensure_session()
    if not client_id:
        return []

    payload = {
        "service": "getSalesDocuments",
        "clientid": client_id,
        "appid": Config.SOFTONE_APPID,
    }

    try:
        response = requests.post(Config.SOFTONE_API_URL, json=payload, timeout=60)
        data = response.json()

        if data.get("success"):
            return data.get("data", [])

        logger.error(f"fetch_pending_orders error: {data.get('error')}")
    except Exception as e:
        logger.error(f"fetch_pending_orders exception: {e}")

    return []
