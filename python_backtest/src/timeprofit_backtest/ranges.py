from __future__ import annotations


def parse_int_values(raw: str) -> list[int]:
    raw = raw.strip()
    if not raw:
        raise ValueError("Empty integer range.")

    if ":" in raw:
        parts = [int(part) for part in raw.split(":")]
        if len(parts) not in (2, 3):
            raise ValueError(f"Invalid range: {raw}. Use start:end[:step].")
        start, end = parts[0], parts[1]
        step = parts[2] if len(parts) == 3 else 1
        if step <= 0:
            raise ValueError("Range step must be positive.")
        return list(range(start, end + 1, step))

    values = sorted({int(part.strip()) for part in raw.split(",") if part.strip()})
    if not values:
        raise ValueError(f"No integer values parsed from: {raw}")
    return values
