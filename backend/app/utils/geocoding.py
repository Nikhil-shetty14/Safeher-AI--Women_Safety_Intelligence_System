"""
Reverse geocoding utility using OpenStreetMap Nominatim API.
Free, no API key required.
"""
import asyncio
import httpx
from loguru import logger
from typing import Optional

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
HEADERS = {"User-Agent": "SafeHerAI/1.0 (women-safety-platform)"}


async def reverse_geocode(latitude: float, longitude: float) -> dict:
    """
    Convert GPS coordinates to a human-readable address using Nominatim.
    Returns a structured address dict with fallback values.
    Retries up to 3 times with exponential backoff on transient failures.
    """
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(
                    NOMINATIM_URL,
                    params={
                        "lat": latitude,
                        "lon": longitude,
                        "format": "json",
                        "addressdetails": 1,
                        "accept-language": "en",
                    },
                    headers=HEADERS,
                )
                response.raise_for_status()
                data = response.json()

            addr = data.get("address", {})

            # Build structured address fields
            road = addr.get("road") or addr.get("pedestrian") or addr.get("footway") or ""
            suburb = addr.get("suburb") or addr.get("neighbourhood") or addr.get("village") or addr.get("hamlet") or ""
            city = (
                addr.get("city")
                or addr.get("town")
                or addr.get("municipality")
                or addr.get("county")
                or ""
            )
            district = addr.get("county") or addr.get("state_district") or city
            state = addr.get("state") or ""
            country = addr.get("country") or ""
            postcode = addr.get("postcode") or ""

            # Full formatted address
            parts = [p for p in [road, suburb, city, district, state, postcode, country] if p]
            formatted_address = ", ".join(parts) if parts else data.get("display_name", f"{latitude:.4f}, {longitude:.4f}")

            return {
                "formatted_address": formatted_address,
                "display_name": data.get("display_name", ""),
                "road": road,
                "locality": suburb,
                "city": city,
                "district": district,
                "state": state,
                "country": country,
                "postcode": postcode,
                "latitude": latitude,
                "longitude": longitude,
            }

        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.warning(f"Reverse geocoding attempt {attempt + 1}/3 failed (network): {e}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
        except Exception as e:
            logger.warning(f"Reverse geocoding attempt {attempt + 1}/3 failed: {e}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)

    logger.error(f"Reverse geocoding permanently failed after 3 attempts for ({latitude}, {longitude})")
    # Fallback: return bare coordinates
    return {
        "formatted_address": f"{latitude:.6f}, {longitude:.6f}",
        "display_name": f"{latitude:.6f}, {longitude:.6f}",
        "road": "",
        "locality": "",
        "city": "",
        "district": "",
        "state": "",
        "country": "",
        "postcode": "",
        "latitude": latitude,
        "longitude": longitude,
    }
