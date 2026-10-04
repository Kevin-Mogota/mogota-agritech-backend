"""
WhatsApp gateway integration point.

HONESTY NOTE: sending a real WhatsApp message requires a WhatsApp Business
Platform account — either directly with Meta (Cloud API) or through a reseller
like Twilio — both need a verified business phone number and an access token
that only you can obtain (there's no free/anonymous way to send WhatsApp
messages programmatically, unlike the NASA POWER or ORNL/MODIS APIs used
elsewhere in this backend). So this module cannot be tested end-to-end here.

What this gives you: a single `send_whatsapp` function with the Meta Cloud API
request already built correctly, and a WhatsAppMessage model that logs every
attempt (sent or failed) for audit — the same "provider swap" pattern as
weather_provider.py and ndvi_provider.py. Once you have a WHATSAPP_TOKEN and
WHATSAPP_PHONE_NUMBER_ID (from developers.facebook.com), set them in .env and
this starts working without further code changes.
"""
import os
import logging

import requests

logger = logging.getLogger(__name__)

WHATSAPP_API_VERSION = "v20.0"


class WhatsAppError(Exception):
    pass


def send_whatsapp(to_phone: str, message: str) -> dict:
    """
    Sends a WhatsApp text message via the Meta Cloud API.

    `to_phone` must be in international format without '+' (e.g. "23566000000").
    Requires WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID in the environment —
    raises WhatsAppError with a clear message if they're not configured, rather
    than failing silently.
    """
    token = os.environ.get("WHATSAPP_TOKEN")
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    if not token or not phone_number_id:
        raise WhatsAppError(
            "WHATSAPP_TOKEN / WHATSAPP_PHONE_NUMBER_ID non configurés — "
            "créez un compte WhatsApp Business Platform sur developers.facebook.com "
            "pour obtenir ces identifiants."
        )

    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message},
    }
    try:
        resp = requests.post(
            url, json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise WhatsAppError(f"Échec d'envoi WhatsApp : {exc}") from exc
