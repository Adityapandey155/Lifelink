import math

EARTH_RADIUS_KM = 6371.0
_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def estimate_travel_minutes(distance_km, avg_speed_kmh=25):
    if distance_km is None:
        return None
    return round((distance_km / avg_speed_kmh) * 60, 1)


def geohash_encode(lat, lon, precision=6):
    lat_range = (-90.0, 90.0)
    lon_range = (-180.0, 180.0)
    geohash = []
    bits = [16, 8, 4, 2, 1]
    bit = 0
    ch = 0
    even = True
    while len(geohash) < precision:
        if even:
            mid = (lon_range[0] + lon_range[1]) / 2
            if lon > mid:
                ch |= bits[bit]
                lon_range = (mid, lon_range[1])
            else:
                lon_range = (lon_range[0], mid)
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat > mid:
                ch |= bits[bit]
                lat_range = (mid, lat_range[1])
            else:
                lat_range = (lat_range[0], mid)
        even = not even
        if bit < 4:
            bit += 1
        else:
            geohash.append(_BASE32[ch])
            bit = 0
            ch = 0
    return "".join(geohash)


def jitter_coordinate(lat, lon, seed, max_offset_km=1.2):
    """Deterministic small fuzz for public map display (privacy)."""
    import random
    rnd = random.Random(seed)
    d_lat = (rnd.random() - 0.5) * (max_offset_km / 111.0) * 2
    d_lon = (rnd.random() - 0.5) * (max_offset_km / 111.0) * 2
    return lat + d_lat, lon + d_lon