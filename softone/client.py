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

    _client_id = None
    return None


def _ensure_session() -> str | None:
    """Ensure we have a valid session, auto-login if needed."""
    global _client_id
    if not _client_id:
        _client_id = login()
    return _client_id


def _call_s1_api(service: str, extra_payload: dict = None, retries: int = 1) -> dict:
    """Generic wrapper for SoftOne API calls with session retry logic."""
    global _client_id
    
    client_id = _ensure_session()
    if not client_id:
        return {"success": False, "error": "No valid session"}

    payload = {
        "service": service,
        "clientid": client_id,
        "appid": Config.SOFTONE_APPID,
    }
    if extra_payload:
        payload.update(extra_payload)

    try:
        response = requests.post(Config.SOFTONE_API_URL, json=payload, timeout=60)
        data = response.json()

        if not data.get("success"):
            err = str(data.get("error", "")).lower()
            # If error suggests session issues, clear ID and retry once
            if any(term in err for term in ["clientid", "session", "expired", "invalid"]):
                logger.warning(f"SoftOne session error: {err}. Clearing session and retrying...")
                _client_id = None
                if retries > 0:
                    return _call_s1_api(service, extra_payload, retries - 1)
            
            logger.error(f"SoftOne API error ({service}): {data.get('error')}")
            return data

        return data
    except Exception as e:
        logger.error(f"SoftOne API exception ({service}): {e}")
        return {"success": False, "error": str(e)}


def fetch_products(upddate_from: str = "2020-01-01T00:00:00") -> list:
    """Fetches products from SoftOne."""
    data = _call_s1_api("getItems", {"upddate_from": upddate_from})
    return data.get("data", []) if data.get("success") else []


def fetch_stock(whouse_code: str | None = None) -> list:
    """Fetches stock levels per warehouse from SoftOne."""
    params = {}
    if whouse_code:
        params["whouse_code"] = whouse_code
        
    data = _call_s1_api("getItemsStockPerWhouse", params)
    return data.get("data", []) if data.get("success") else []


def fetch_pending_orders() -> list:
    """Fetches pending sales orders from SoftOne."""
    data = _call_s1_api("getSalesDocuments")
    return data.get("data", []) if data.get("success") else []
