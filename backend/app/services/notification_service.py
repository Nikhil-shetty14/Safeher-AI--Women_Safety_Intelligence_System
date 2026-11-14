import asyncio
import httpx
from app.core.config import settings
from loguru import logger


async def send_push_notification(fcm_token: str, title: str, body: str, data: dict = None) -> bool:
    if not settings.FCM_SERVER_KEY:
        logger.warning(f"[MOCK PUSH] Title: {title} | Body: {body}")
        return True

    headers = {
        "Authorization": f"key={settings.FCM_SERVER_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "to": fcm_token,
        "notification": {
            "title": title,
            "body": body,
            "sound": "emergency_alert",
            "priority": "high",
        },
        "data": data or {},
        "priority": "high",
        "content_available": True,
    }

    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://fcm.googleapis.com/fcm/send",
                    json=payload,
                    headers=headers,
                    timeout=10.0,
                )
                if response.status_code == 200:
                    logger.info(f"Push notification sent to token ending: ...{fcm_token[-6:]}")
                    return True
                else:
                    logger.error(f"FCM error: {response.status_code} - {response.text}")
                    # Don't retry on client errors (4xx)
                    if 400 <= response.status_code < 500:
                        return False
        except Exception as e:
            logger.error(f"Push notification attempt {attempt + 1}/3 failed: {e}")

        if attempt < 2:
            await asyncio.sleep(2 ** attempt)

    logger.error(f"Push notification permanently failed after 3 attempts for token ...{fcm_token[-6:]}")
    return False


async def send_bulk_notifications(tokens: list, title: str, body: str, data: dict = None) -> dict:
    results = {"success": 0, "failure": 0}
    total = len(tokens)
    for i, token in enumerate(tokens, 1):
        success = await send_push_notification(token, title, body, data)
        if success:
            results["success"] += 1
        else:
            results["failure"] += 1
        if total >= 10 and i % max(1, total // 10) == 0:
            logger.info(f"Bulk notification progress: {i}/{total} sent ({results['success']} ok, {results['failure']} failed)")
    logger.info(f"Bulk notification complete: {results['success']}/{total} succeeded, {results['failure']} failed")
    return results
