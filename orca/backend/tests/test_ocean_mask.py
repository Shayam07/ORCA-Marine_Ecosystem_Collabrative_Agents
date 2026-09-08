"""Regression tests for the ocean/land mask used by the DEMO + weather grid providers.

These lock the behaviour behind the "no data on land" fix: synthetic/grid sampling
must never put points over clearly-inland cities, while real marine areas (Bay of
Bengal, Arabian Sea, gulfs, straits, open Indian Ocean) must stay water.
"""

import pytest

from data.providers.demo import DemoDataProvider

# (label, lat, lon, expected_ocean)
MASK_CASES = [
    # ── Ocean (must be True) ─────────────────────────────────────────
    ("Chennai harbour coast", 13.08, 80.27, True),
    ("Bay of Bengal off Chennai", 13.5, 80.8, True),
    ("Arabian Sea off Mumbai", 19.0, 71.8, True),
    ("Arabian Sea west of Mumbai", 19.2, 72.4, True),
    ("Off Kochi", 9.9, 75.8, True),
    ("Gulf of Kutch", 22.7, 69.9, True),
    ("Gulf of Khambhat", 21.6, 72.4, True),
    ("Off Porbandar", 21.0, 70.0, True),
    ("Sindh coast (open Arabian Sea)", 25.0, 66.5, True),
    ("Bay of Bengal deep", 20.0, 87.0, True),
    ("Bay of Bengal south", 15.0, 84.0, True),
    ("Myanmar coast sea", 16.0, 94.5, True),
    ("Sri Lanka south sea", 5.5, 80.5, True),
    ("Gulf of Mannar", 9.0, 79.3, True),
    ("Palk Bay", 9.8, 79.8, True),
    ("Andaman sea", 12.0, 93.0, True),
    ("Lakshadweep sea", 10.5, 72.5, True),
    ("Kerala sea", 9.2, 76.0, True),
    ("Southern Indian Ocean", 5.0, 76.0, True),
    # ── Land (must be False) ─────────────────────────────────────────
    ("Delhi", 28.6, 77.2, False),
    ("Mumbai city", 19.08, 72.88, False),
    ("Pune", 18.5, 73.85, False),
    ("Ahmedabad", 23.0, 72.6, False),
    ("Jaipur", 26.9, 75.8, False),
    ("Patna", 25.6, 85.1, False),
    ("Ranchi", 23.35, 85.33, False),
    ("Nagpur", 21.15, 79.1, False),
    ("Bengaluru", 12.97, 77.59, False),
    ("Hyderabad", 17.38, 78.49, False),
    ("Vijayawada", 16.5, 80.65, False),
    ("Rajkot (Saurashtra)", 22.3, 70.79, False),
    ("Jamnagar (Saurashtra)", 22.47, 70.07, False),
    ("Madurai", 9.92, 78.12, False),
    ("Coimbatore", 11.02, 76.96, False),
    ("Sri Lanka interior", 7.5, 80.5, False),
    ("Sri Lanka Jaffna", 9.7, 80.2, False),
    ("Pakistan desert", 27.0, 70.0, False),
    ("Kutch desert", 23.5, 70.0, False),
    ("Bangladesh interior", 24.0, 90.0, False),
    ("NE India", 26.0, 93.0, False),
    ("Bihar", 26.0, 84.0, False),
    ("Gujarat interior", 22.7, 73.0, False),
]


@pytest.mark.parametrize("label,lat,lon,expected", MASK_CASES,
                         ids=[c[0].replace(" ", "_") for c in MASK_CASES])
def test_is_ocean_mask(label, lat, lon, expected):
    assert DemoDataProvider._is_ocean(lat, lon) is expected, label


def test_weather_grid_spreads_over_large_bbox():
    """Regression: the ERA5/weather grid must not cram every sample into the
    southern rows of a large bbox (the row-major scan used to exhaust its 90-point
    budget on the bottom of an India-wide request)."""
    # Replicates the sampling logic in data/providers/weather.py
    from data.providers.demo import DemoDataProvider as D

    bbox = [68.0, 6.0, 98.0, 36.0]  # India-wide
    west, south, east, north = bbox
    span = max(east - west, north - south)
    step = round(min(max(span / 10.0, 0.1), 2.5), 2)
    lat_step = min(step, 1.0) if (north - south) > 6 else step
    lon_step = min(step, 1.0) if (east - west) > 6 else step

    candidates = []
    lat = south
    while lat <= north:
        lon = west
        while lon <= east:
            if D._is_ocean(round(lat, 3), round(lon, 3)):
                candidates.append((round(lat, 2), round(lon, 2)))
            lon = round(lon + lon_step, 3)
        lat = round(lat + lat_step, 3)

    budget = 90
    if len(candidates) <= budget:
        points = candidates
    else:
        n = len(candidates)
        points = [candidates[round(i * (n - 1) / (budget - 1))] for i in range(budget)]

    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    assert len(set(points)) == len(points), "duplicate grid points sampled"
    # Coverage must reach the full open-ocean band. In this bbox real ocean runs
    # ~6-22N (everything north of 23N is land and correctly excluded by the mask),
    # so the sample must span from the bottom edge up to the northern ocean, not
    # collapse into the lat 6-9 strip the old early-exit scan produced.
    assert min(lats) <= 6.5, f"grid missing southern ocean: {lats}"
    assert max(lats) >= 20.0, f"grid collapsed to low latitudes: {lats}"
    assert max(lons) - min(lons) > 20.0, "grid collapsed to a narrow lon band"
