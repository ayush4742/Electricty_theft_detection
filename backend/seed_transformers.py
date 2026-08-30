"""Generate the distribution network and 30 days of energy readings.

    python seed_transformers.py            # build network + 30 days of data
    python seed_transformers.py --days 60  # longer history
    python seed_transformers.py --reset    # wipe and rebuild

IMPORTANT - BE HONEST ABOUT THIS
--------------------------------
The data this script writes is SIMULATED. In a real deployment:

  * `transformer_readings` comes from the DT's feeder meter over SCADA / AMI.
  * `meter_readings` comes from the smart-meter head-end system (HES).
  * `meters.transformer_id` comes from the utility's GIS / consumer indexing
    survey - and getting that mapping right is genuinely the hardest part of
    rolling this out in the field.

Everything downstream of this file - the balance query, the loss maths, the
persistence rule, the API, the UI - is real logic that would run unchanged on
real data. Only the input is synthetic. Say exactly that in your README and in
your viva; it is a strength, not a weakness, that you know where the seam is.
"""

from __future__ import annotations

import argparse
import random
import sqlite3
from datetime import date, timedelta

from config import DB_PATH
import transformer_db


# Deterministic output, so your screenshots and your numbers stay consistent
# between runs. Change the seed if you want a different network.
RANDOM_SEED = 42

AREAS = [
    "Sector 4", "Sector 9", "Sector 12", "Sector 17", "Sector 21",
    "Industrial Area A", "Industrial Area B", "Model Town", "Civil Lines",
    "Old City", "Ram Nagar", "Green Park", "Shastri Nagar", "Bus Stand Road",
    "Railway Colony",
]

TARIFFS = ["Domestic", "Domestic", "Domestic", "Commercial", "Commercial", "Industrial"]

# Health profile of the network. Real distribution networks are mostly fine
# with a troubled minority - that shape is what makes the dashboard believable.
#   label      share  loss% range   description
PROFILES = [
    ("normal",   0.60, (4.0, 7.5)),   # healthy: technical loss only
    ("watch",    0.24, (9.0, 14.0)),  # borderline: worth monitoring
    ("critical", 0.16, (17.0, 28.0)), # commercial loss - theft cluster
]

TRANSFORMER_COUNT = 25
METERS_PER_DT = (35, 110)


def _wipe(connection: sqlite3.Connection) -> None:
    for table in ("transformer_readings", "meter_readings", "meters", "transformers"):
        connection.execute(f"DELETE FROM {table}")
    connection.commit()
    print("  cleared existing network data")


def _existing_meter_ids(connection: sqlite3.Connection) -> list[str]:
    """Reuse meter ids the app has already predicted on, so the two features
    line up and clicking a real prediction lands on a real transformer."""
    try:
        rows = connection.execute(
            "SELECT DISTINCT meter_id FROM predictions WHERE meter_id IS NOT NULL AND meter_id != ''"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [str(row[0]) for row in rows]


def _build_network(connection: sqlite3.Connection, rng: random.Random) -> list[dict]:
    """Create transformers and assign every meter to exactly one of them."""
    # Weighted profile list, shuffled so the bad DTs are not all at the end.
    profile_pool: list[tuple[str, tuple[float, float]]] = []
    for label, share, loss_range in PROFILES:
        profile_pool.extend([(label, loss_range)] * round(share * TRANSFORMER_COUNT))
    while len(profile_pool) < TRANSFORMER_COUNT:
        profile_pool.append((PROFILES[0][0], PROFILES[0][2]))
    profile_pool = profile_pool[:TRANSFORMER_COUNT]
    rng.shuffle(profile_pool)

    # Decide how many meters each DT carries before assigning any ids, so the
    # real meter ids can be spread across the WHOLE network.
    meter_counts = [rng.randint(*METERS_PER_DT) for _ in range(TRANSFORMER_COUNT)]

    # Meter ids the app has already predicted on. These must be distributed
    # round-robin, not sequentially: filling DT-001 to capacity before touching
    # DT-002 would dump every real prediction onto the first few transformers
    # and leave the interesting high-loss ones with nothing to show.
    pool = _existing_meter_ids(connection)
    rng.shuffle(pool)

    assigned: list[list[str]] = [[] for _ in range(TRANSFORMER_COUNT)]
    pool_index = 0
    slot = 0
    while pool_index < len(pool) and slot < max(meter_counts):
        for index in range(TRANSFORMER_COUNT):
            if pool_index >= len(pool):
                break
            if slot < meter_counts[index]:
                assigned[index].append(pool[pool_index])
                pool_index += 1
        slot += 1

    synthetic_counter = 1
    transformers: list[dict] = []
    meter_rows: list[tuple] = []

    for index in range(TRANSFORMER_COUNT):
        transformer_id = f"DT-{index + 1:03d}"
        area = AREAS[index % len(AREAS)]
        label, loss_range = profile_pool[index]

        transformers.append(
            {
                "transformer_id": transformer_id,
                "profile": label,
                "target_loss": rng.uniform(*loss_range),
                "meters": [],
            }
        )

        connection.execute(
            """
            INSERT INTO transformers
                (transformer_id, name, area, capacity_kva, latitude, longitude, commissioned)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transformer_id,
                f"{area} DT-{index + 1}",
                area,
                rng.choice([100, 160, 200, 250, 315, 400, 630]),
                # Loosely scattered around a mid-size north Indian town
                round(28.60 + rng.uniform(-0.06, 0.06), 6),
                round(77.20 + rng.uniform(-0.06, 0.06), 6),
                f"{rng.randint(2008, 2022)}-{rng.randint(1, 12):02d}-01",
            ),
        )

        real_ids = assigned[index]
        for position in range(meter_counts[index]):
            if position < len(real_ids):
                meter_id = real_ids[position]
            else:
                meter_id = f"MTR{synthetic_counter:06d}"
                synthetic_counter += 1

            tariff = rng.choice(TARIFFS)
            if tariff == "Industrial":
                load, base = rng.uniform(15, 60), rng.uniform(90, 260)
            elif tariff == "Commercial":
                load, base = rng.uniform(5, 20), rng.uniform(25, 80)
            else:
                load, base = rng.uniform(1, 6), rng.uniform(4, 18)

            transformers[-1]["meters"].append({"meter_id": meter_id, "base": base})
            meter_rows.append(
                (meter_id, transformer_id, f"Consumer {meter_id}", tariff, round(load, 2))
            )

    connection.executemany(
        """
        INSERT OR REPLACE INTO meters
            (meter_id, transformer_id, consumer_name, tariff_type, sanctioned_load)
        VALUES (?, ?, ?, ?, ?)
        """,
        meter_rows,
    )
    connection.commit()

    reused = min(pool_index, len(pool))
    dts_with_real = sum(1 for ids in assigned if ids)
    print(f"  {TRANSFORMER_COUNT} transformers, {len(meter_rows)} meters "
          f"({reused} reused from existing predictions, spread over {dts_with_real} transformers)")
    return transformers


def _build_readings(connection: sqlite3.Connection, transformers: list[dict],
                    days: int, rng: random.Random) -> None:
    """Generate daily consumption per meter, then derive what the DT supplied.

    The direction matters. We simulate what meters BILL, then work backwards to
    what the transformer must have SUPPLIED given the loss we want that DT to
    exhibit:

        supplied = billed / (1 - loss_fraction)

    That is the honest direction - the loss is energy that left the transformer
    and never reached a bill.
    """
    today = date.today()
    meter_reading_rows: list[tuple] = []
    dt_reading_rows: list[tuple] = []

    for transformer in transformers:
        target_loss = transformer["target_loss"]
        # Some critical DTs only go bad partway through the window - that is
        # what a new illegal connection looks like, and it makes the trend
        # chart tell a story instead of drawing a flat line.
        onset_day = 0
        if transformer["profile"] == "critical" and rng.random() < 0.45:
            onset_day = rng.randint(days // 4, days // 2)

        for day_offset in range(days):
            reading_date = (today - timedelta(days=days - 1 - day_offset)).isoformat()
            weekend = (today - timedelta(days=days - 1 - day_offset)).weekday() >= 5

            billed_total = 0.0
            for meter in transformer["meters"]:
                units = meter["base"] * rng.uniform(0.80, 1.20)
                if weekend:
                    units *= rng.uniform(0.88, 1.05)
                units = round(max(0.0, units), 2)
                billed_total += units
                meter_reading_rows.append((meter["meter_id"], reading_date, units))

            if day_offset < onset_day:
                loss_pct = rng.uniform(4.0, 7.0)   # healthy before the theft starts
            else:
                loss_pct = target_loss + rng.gauss(0, 1.4)
            loss_pct = max(1.0, min(45.0, loss_pct))

            supplied = billed_total / (1.0 - loss_pct / 100.0)
            dt_reading_rows.append(
                (transformer["transformer_id"], reading_date, round(supplied, 2))
            )

    connection.executemany(
        "INSERT OR REPLACE INTO meter_readings (meter_id, reading_date, units_consumed) VALUES (?, ?, ?)",
        meter_reading_rows,
    )
    connection.executemany(
        "INSERT OR REPLACE INTO transformer_readings (transformer_id, reading_date, energy_supplied) VALUES (?, ?, ?)",
        dt_reading_rows,
    )
    connection.commit()
    print(f"  {len(dt_reading_rows)} transformer readings, "
          f"{len(meter_reading_rows)} meter readings over {days} days")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed simulated distribution network data")
    parser.add_argument("--days", type=int, default=30, help="days of history to generate")
    parser.add_argument("--reset", action="store_true", help="wipe existing network data first")
    args = parser.parse_args()

    rng = random.Random(RANDOM_SEED)

    print(f"Seeding network data into {DB_PATH}")
    transformer_db.init_transformer_tables()

    with sqlite3.connect(DB_PATH) as connection:
        if args.reset:
            _wipe(connection)
        elif connection.execute("SELECT COUNT(*) FROM transformers").fetchone()[0]:
            print("  network already seeded - use --reset to rebuild")
            return

        transformers = _build_network(connection, rng)
        _build_readings(connection, transformers, args.days, rng)

    # Print what we actually produced, so you can sanity-check the numbers
    # before ever opening the frontend.
    import energy_balance

    kpis = energy_balance.get_network_kpis(args.days)
    print("\nNetwork summary")
    print(f"  transformers   : {kpis['total_transformers']}")
    print(f"  critical       : {kpis['critical_count']}")
    print(f"  watch          : {kpis['watch_count']}")
    print(f"  normal         : {kpis['normal_count']}")
    print(f"  average loss   : {kpis['avg_loss_pct']}%")
    print(f"  revenue at risk: Rs {kpis['estimated_monthly_revenue_loss']:,.0f} / month")

    print("\nWorst five transformers")
    for row in energy_balance.get_network_summary(args.days)[:5]:
        print(f"  {row['transformer_id']}  {row['area']:<18} "
              f"{row['loss_pct']:>6.2f}%  {row['status']:<8} "
              f"{row['days_above_threshold']}/{row['days_monitored']} days  "
              f"({row['trend']})")

    print("\nDone. Start the backend and open the Network Health page.")


if __name__ == "__main__":
    main()
