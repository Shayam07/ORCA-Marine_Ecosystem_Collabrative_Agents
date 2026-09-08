"""Seed demo data for ORCA.

This script can be run standalone to verify the demo data generator works.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from datetime import datetime
from data.providers.demo import DemoDataProvider


async def main():
    print("🌊 ORCA Demo Data Seeder")
    print("=" * 50)

    provider = DemoDataProvider()

    # Check health
    health = await provider.health_check()
    print(f"Provider: {health.provider_name}")
    print(f"Status: {health.status.value}")
    print(f"Message: {health.message}")
    print()

    # Generate data for Goa region
    print("Generating data for Goa region (14.5-16.5°N, 71.5-73.5°E)...")
    batch = await provider.get_data(
        bbox=[71.5, 14.5, 73.5, 16.5],
        start_date=datetime(2026, 8, 1),
        end_date=datetime(2026, 8, 28),
        variables=[
            "sea_surface_temperature",
            "chlorophyll_concentration",
            "salinity",
            "wind_speed",
            "fishing_activity",
        ],
    )

    print(f"Generated {batch.record_count} observations")
    print(f"Source: {batch.source}")
    print(f"Is demo: {batch.is_demo}")
    print()

    # Show sample observations
    print("Sample observations:")
    for obs in batch.observations[:5]:
        print(
            f"  {obs.variable}: {obs.value} {obs.unit} "
            f"at ({obs.latitude}, {obs.longitude}) "
            f"on {obs.timestamp.strftime('%Y-%m-%d')} "
            f"[{obs.source.value}]"
        )

    print()
    print("✅ Demo data generation successful!")
    print("All data is clearly labeled as SYNTHETIC — NOT LIVE OBSERVATIONS")


if __name__ == "__main__":
    asyncio.run(main())
