#!/usr/bin/env python3
"""
Flight Schedule Parser and Query Tool
RTU Python assignment
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# >>> CHANGE THESE TO YOUR REAL DATA <<<
STUDENT_ID = "241ADB008"  # e.g. "12345"
FIRST_NAME = "Delwin"
LAST_NAME = "Biju"

DATE_FORMAT = "%Y-%m-%d %H:%M"

# Simple whitelist of airport codes based on the examples
VALID_AIRPORTS = {
    "LHR",
    "JFK",
    "FRA",
    "RIX",
    "OSL",
    "HEL",
    "ARN",
    "CDG",
    "DXB",
    "DOH",
    "SYD",
    "AMS",
    "BRU",
    "LAX",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Flight schedule parser and query tool"
    )

    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "-i", "--input", metavar="FILE", help="Parse a single CSV file"
    )
    input_group.add_argument(
        "-d", "--dir", metavar="DIR", help="Parse all .csv files in a folder"
    )

    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Output JSON file for valid flights (default: db.json)",
    )
    parser.add_argument(
        "-j",
        "--json-db",
        metavar="FILE",
        help="Load existing JSON database instead of parsing CSVs",
    )
    parser.add_argument(
        "-q", "--query", metavar="FILE", help="Execute queries from JSON file"
    )

    return parser


def parse_datetime(value: str, kind: str, errors: List[str]) -> datetime | None:
    try:
        return datetime.strptime(value, DATE_FORMAT)
    except ValueError:
        errors.append(f"invalid {kind} datetime")
        return None


def validate_and_build_flight(
    line: str,
    lineno: int,
) -> tuple[Dict[str, Any] | None, str | None]:
    """
    Validate one CSV line (already stripped, not empty, not comment).
    Returns (flight_dict or None, error_message or None)
    """
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 6:
        return None, f"Line {lineno}: {line} \u2192 missing required fields"

    flight_id, origin, destination, dep_str, arr_str, price_str = parts
    issues: List[str] = []

    # flight_id: 2–8 alphanumeric
    if not (2 <= len(flight_id) <= 8 and flight_id.isalnum()):
        if len(flight_id) > 8:
            issues.append("flight_id too long (more than 8 characters)")
        elif len(flight_id) < 2:
            issues.append("flight_id too short (less than 2 characters)")
        else:
            issues.append("invalid flight_id")

    # origin and destination codes
    def check_airport(code: str, kind: str) -> None:
        if not (len(code) == 3 and code.isalpha() and code.isupper()):
            issues.append(f"invalid {kind} code")
        elif code not in VALID_AIRPORTS:
            issues.append(f"invalid {kind} code")

    check_airport(origin, "origin")
    check_airport(destination, "destination")

    # datetimes
    dt_issues: List[str] = []
    dep_dt = parse_datetime(dep_str, "departure", dt_issues)
    arr_dt = parse_datetime(arr_str, "arrival", dt_issues)
    issues.extend(dt_issues)

    if dep_dt and arr_dt and arr_dt <= dep_dt:
        issues.append("arrival before departure")

    # price
    try:
        price = float(price_str)
        if price < 0:
            issues.append("negative price value")
        elif price == 0:
            issues.append("non-positive price value")
    except ValueError:
        price = None
        issues.append("invalid price value")

    if issues:
        return None, f"Line {lineno}: {line} \u2192 " + ", ".join(issues)

    flight: Dict[str, Any] = {
        "flight_id": flight_id,
        "origin": origin,
        "destination": destination,
        "departure_datetime": dep_str,
        "arrival_datetime": arr_str,
        "price": price,
    }
    return flight, None


def parse_csv_file(
    path: Path,
    valid_flights: List[Dict[str, Any]],
    error_lines: List[str],
) -> None:
    with path.open(encoding="utf-8") as f:
        for lineno, raw_line in enumerate(f, start=1):
            line = raw_line.rstrip("\n")
            stripped = line.strip()

            # ignore blank lines
            if not stripped:
                continue

            # header line
            if lineno == 1 and stripped.lower().startswith(
                "flight_id,origin,destination,departure_datetime,arrival_datetime,price"
            ):
                continue

            # comment lines -> go to errors.txt as in example
            if stripped.startswith("#"):
                error_lines.append(
                    f"Line {lineno}: {stripped} \u2192 comment line, ignored for data parsing"
                )
                continue

            # real data line
            flight, err = validate_and_build_flight(line, lineno)
            if err:
                error_lines.append(err)
            elif flight:
                valid_flights.append(flight)


def save_json_db(flights: List[Dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(flights, f, indent=2)
    print(f"Saved {len(flights)} valid flights to {path}")


def save_errors(error_lines: List[str], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for line in error_lines:
            f.write(line + "\n")
    print(f"Saved {len(error_lines)} error lines to {path}")


def load_json_db(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("JSON DB must be an array of flight objects")
    return data


def load_queries(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError("Query JSON must be an object or an array of objects")


def filter_flights(
    flights: List[Dict[str, Any]],
    query: Dict[str, Any],
) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []

    dep_filter_dt = None
    arr_filter_dt = None
    if "departure_datetime" in query:
        dep_filter_dt = datetime.strptime(query["departure_datetime"], DATE_FORMAT)
    if "arrival_datetime" in query:
        arr_filter_dt = datetime.strptime(query["arrival_datetime"], DATE_FORMAT)

    for flight in flights:
        ok = True

        # exact matches
        for field in ("flight_id", "origin", "destination"):
            if field in query and flight.get(field) != query[field]:
                ok = False
                break

        if not ok:
            continue

        # departure_datetime >= query value
        if dep_filter_dt is not None:
            flight_dep = datetime.strptime(flight["departure_datetime"], DATE_FORMAT)
            if flight_dep < dep_filter_dt:
                continue

        # arrival_datetime <= query value
        if arr_filter_dt is not None:
            flight_arr = datetime.strptime(flight["arrival_datetime"], DATE_FORMAT)
            if flight_arr > arr_filter_dt:
                continue

        # price <= query value
        if "price" in query:
            if float(flight["price"]) > float(query["price"]):
                continue

        matches.append(flight)

    return matches


def run_queries_and_save(
    flights: List[Dict[str, Any]],
    queries: List[Dict[str, Any]],
) -> Path:
    responses: List[Dict[str, Any]] = []

    for q in queries:
        matches = filter_flights(flights, q)
        responses.append(
            {
                "query": q,
                "matches": matches,
            }
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    fname = FIRST_NAME.replace(" ", "")
    lname = LAST_NAME.replace(" ", "")
    filename = f"response_{STUDENT_ID}_{fname}_{lname}_{timestamp}.json"
    path = Path(filename)

    with path.open("w", encoding="utf-8") as f:
        json.dump(responses, f, indent=2)

    print(f"Saved query responses to {path}")
    return path


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    has_csv_input = bool(args.input or args.dir)

    if not has_csv_input and not args.json_db:
        parser.error("You must provide either -j or one of -i / -d")

    if args.json_db and has_csv_input:
        parser.error("Use -j OR -i/-d, not both at the same time")

    flights: List[Dict[str, Any]] = []

    # --- Mode 1: parse CSVs ---
    if has_csv_input:
        errors: List[str] = []

        if args.input:
            parse_csv_file(Path(args.input), flights, errors)

        if args.dir:
            folder = Path(args.dir)
            for csv_path in sorted(folder.glob("*.csv")):
                parse_csv_file(csv_path, flights, errors)

        output_path = Path(args.output) if args.output else Path("db.json")
        save_json_db(flights, output_path)
        save_errors(errors, Path("errors.txt"))

    # --- Mode 2: load existing JSON db ---
    if args.json_db:
        flights = load_json_db(Path(args.json_db))
        print(f"Loaded {len(flights)} flights from {args.json_db}")

    # --- Optional: run queries ---
    if args.query:
        queries = load_queries(Path(args.query))
        run_queries_and_save(flights, queries)


if __name__ == "__main__":
    main()
