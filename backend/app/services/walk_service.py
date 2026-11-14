import asyncio
import httpx
from typing import Dict, List
from loguru import logger
from app.core.config import settings
try:
    # pyrefly: ignore [missing-import]
    from polyline import decode as decode_polyline
except ImportError:  # fallback implementation
    def decode_polyline(encoded_str: str):
        """Decode a polyline encoded string into a list of (lat, lng) tuples.
        This is a minimal pure‑Python implementation of the Google polyline
        algorithm, sufficient for our route decoding needs.
        """
        result = []
        index = lat = lng = 0
        shifts = []
        while index < len(encoded_str):
            shift = result_shift = 0
            while True:
                b = ord(encoded_str[index]) - 63
                index += 1
                result_shift |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            dlat = ~(result_shift >> 1) if (result_shift & 1) else (result_shift >> 1)
            lat += dlat
            shift = result_shift = 0
            while True:
                b = ord(encoded_str[index]) - 63
                index += 1
                result_shift |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            dlng = ~(result_shift >> 1) if (result_shift & 1) else (result_shift >> 1)
            lng += dlng
            result.append((lat / 1e5, lng / 1e5))
        return result

class WalkService:
    @staticmethod
    async def get_route(origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float) -> Dict:
        """Call Google Maps Directions API to retrieve a walking route.
        Returns a dict with 'polyline' (list of {'latitude', 'longitude'}) and 'route_id'."""

        # Input validation
        if not (-90 <= origin_lat <= 90) or not (-90 <= destination_lat <= 90):
            raise ValueError(f"Latitude must be between -90 and 90, got origin={origin_lat}, dest={destination_lat}")
        if not (-180 <= origin_lng <= 180) or not (-180 <= destination_lng <= 180):
            raise ValueError(f"Longitude must be between -180 and 180, got origin={origin_lng}, dest={destination_lng}")

        api_key = settings.GOOGLE_MAPS_API_KEY
        if not api_key:
            raise ValueError('Google Maps API key not configured')
        url = 'https://maps.googleapis.com/maps/api/directions/json'
        params = {
            'origin': f"{origin_lat},{origin_lng}",
            'destination': f"{destination_lat},{destination_lng}",
            'mode': 'walking',
            'key': api_key,
            'alternatives': 'false',
        }

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(url, params=params)
                data = resp.json()
                if data.get('status') != 'OK' or not data.get('routes'):
                    raise RuntimeError(f"Google Directions API error: {data.get('status')}")
                route = data['routes'][0]
                points = decode_polyline(route['overview_polyline']['points'])
                polyline = [{'latitude': lat, 'longitude': lng} for lat, lng in points]
                logger.info(f"Route fetched: {len(polyline)} points from ({origin_lat},{origin_lng}) to ({destination_lat},{destination_lng})")
                return {'polyline': polyline, 'route_id': route.get('overview_polyline', {}).get('points', '')}
            except (httpx.RequestError, httpx.TimeoutException) as e:
                logger.warning(f"Route request attempt {attempt + 1}/3 failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error(f"Route request permanently failed after 3 attempts: {e}")
                    raise RuntimeError(f"Failed to fetch route after 3 attempts: {e}") from e
            except RuntimeError:
                raise
            except Exception as e:
                logger.error(f"Unexpected error fetching route: {e}")
                raise
