"""
Tải dữ liệu thời tiết lịch sử theo giờ từ Open-Meteo (Archive API)
và lưu thành CSV cùng các cột như crawler cũ.

Cài đặt:   pip install requests
Chạy:      python fetch_weather_openmeteo.py

Đơn vị trong CSV:
    Temperature  : °C
    Humidity     : %
    Barometer    : hPa (áp suất quy về mực nước biển)
    Wind         : km/h (tốc độ gió ở độ cao 10 m)
    Visibility   : mét (để trống nếu Archive API không cung cấp)
    Weather      : mô tả chữ, đổi từ mã WMO
"""

import calendar
import csv
import os
import time
from collections import Counter

import requests


API_URL = "https://archive-api.open-meteo.com/v1/archive"

# Toạ độ khu vực Thủ Đức, TP.HCM. Có thể đổi nếu cần.
LATITUDE = 10.85
LONGITUDE = 106.76
TIMEZONE = "Asia/Ho_Chi_Minh"

START_YEAR = 2020
START_MONTH = 12

END_YEAR = 2026
END_MONTH = 9

# File riêng, tránh lẫn với dữ liệu timeanddate cũ (khác định dạng giờ/đơn vị).
OUTPUT_FILE = "weather_openmeteo.csv"

DELAY_BETWEEN_REQUESTS = 1.0
MAX_RETRIES = 5

# Các biến bắt buộc.
REQUIRED_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "pressure_msl",
    "wind_speed_10m",
    "weather_code",
]

# Biến thử lấy; nếu API từ chối thì tự bỏ đi (Visibility sẽ để trống).
OPTIONAL_VARS = ["visibility"]

HEADERS = [
    "Date",
    "Time",
    "Temperature",
    "Weather",
    "Wind",
    "Humidity",
    "Barometer",
    "Visibility",
]

# Bảng mã thời tiết WMO -> mô tả.
WMO_TEXT = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class BadRequest(Exception):
    """API trả về 400 (tham số không hợp lệ)."""


# ----------------------------------------------------------------------
# Tiện ích
# ----------------------------------------------------------------------

def month_iterator(start_year, start_month, end_year, end_month):
    """Sinh ra từng (year, month) trong khoảng thời gian."""
    year = start_year
    month = start_month

    while (year, month) <= (end_year, end_month):
        yield year, month

        month += 1
        if month == 13:
            month = 1
            year += 1


def load_existing_records():
    """
    Đọc CSV cũ để hỗ trợ resume.

    Trả về:
        existing_keys   : set các (Date, Time) đã có
        rows_per_month  : Counter số dòng đã có theo "YYYY-MM"
    """
    existing_keys = set()
    rows_per_month = Counter()

    if not os.path.exists(OUTPUT_FILE):
        return existing_keys, rows_per_month

    with open(OUTPUT_FILE, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            if row.get("Date") and row.get("Time"):
                key = (row["Date"].strip(), row["Time"].strip())

                if key not in existing_keys:
                    existing_keys.add(key)
                    rows_per_month[key[0][:7]] += 1

    return existing_keys, rows_per_month


def weather_text(code):
    """Đổi mã WMO sang mô tả chữ."""
    if code is None:
        return ""

    code = int(code)

    return WMO_TEXT.get(code, f"WMO code {code}")


def blank_if_none(value):
    return "" if value is None else value


# ----------------------------------------------------------------------
# Gọi API
# ----------------------------------------------------------------------

def error_reason(response):
    """Lấy lý do lỗi từ response."""
    try:
        return response.json().get("reason", response.text[:200])
    except Exception:
        return response.text[:200]


def request_month(year, month, variables):
    """Gọi Archive API cho cả một tháng, có retry khi lỗi mạng / 429 / 5xx."""
    last_day = calendar.monthrange(year, month)[1]

    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": f"{year}-{month:02d}-01",
        "end_date": f"{year}-{month:02d}-{last_day:02d}",
        "hourly": ",".join(variables),
        "timezone": TIMEZONE,
    }

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(API_URL, params=params, timeout=60)

        except requests.RequestException as error:
            last_error = error
            wait = 10 * attempt
            print(f"     lỗi mạng: {error}. Thử lại sau {wait}s...")
            time.sleep(wait)
            continue

        if response.status_code == 200:
            return response.json()

        reason = error_reason(response)

        if response.status_code == 400:
            raise BadRequest(reason)

        wait = 65 if response.status_code == 429 else 10 * attempt

        last_error = RuntimeError(f"HTTP {response.status_code}: {reason}")

        print(
            f"     HTTP {response.status_code}: {reason}. "
            f"Thử lại sau {wait}s ({attempt}/{MAX_RETRIES})..."
        )
        time.sleep(wait)

    raise last_error


def get_month_data(year, month, config):
    """
    Gọi API; nếu API từ chối biến tuỳ chọn (vd visibility) thì bỏ biến đó
    và gọi lại.
    """
    while True:
        try:
            return request_month(year, month, config["variables"])

        except BadRequest as error:
            optional_in_use = [
                v for v in OPTIONAL_VARS if v in config["variables"]
            ]

            if not optional_in_use:
                raise

            print(
                f"     API không nhận {optional_in_use} ({error}). "
                f"Bỏ biến này, cột Visibility sẽ để trống."
            )

            config["variables"] = [
                v for v in config["variables"] if v not in OPTIONAL_VARS
            ]


def build_records(data):
    """Đổi JSON của API thành danh sách dòng CSV."""
    hourly = data.get("hourly")

    if not hourly:
        raise RuntimeError(f"Phản hồi không có dữ liệu hourly: {str(data)[:200]}")

    times = hourly["time"]

    temps = hourly.get("temperature_2m", [None] * len(times))
    hums = hourly.get("relative_humidity_2m", [None] * len(times))
    baros = hourly.get("pressure_msl", [None] * len(times))
    winds = hourly.get("wind_speed_10m", [None] * len(times))
    codes = hourly.get("weather_code", [None] * len(times))
    viss = hourly.get("visibility") or [None] * len(times)

    records = []

    for i, stamp in enumerate(times):
        date_str, time_str = stamp.split("T")

        # Bỏ giờ chưa có dữ liệu (thường là vài ngày cuối cùng, do độ trễ).
        if temps[i] is None and hums[i] is None and baros[i] is None:
            continue

        records.append({
            "Date": date_str,
            "Time": time_str,
            "Temperature": blank_if_none(temps[i]),
            "Weather": weather_text(codes[i]),
            "Wind": blank_if_none(winds[i]),
            "Humidity": blank_if_none(hums[i]),
            "Barometer": blank_if_none(baros[i]),
            "Visibility": blank_if_none(viss[i]),
        })

    return records


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    existing_keys, rows_per_month = load_existing_records()

    print(f"Đã tìm thấy {len(existing_keys)} record trong {OUTPUT_FILE}.")

    config = {"variables": REQUIRED_VARS + OPTIONAL_VARS}

    new_records = 0
    incomplete_months = []
    failed_months = []

    file_exists = os.path.exists(OUTPUT_FILE)

    with open(OUTPUT_FILE, "a", encoding="utf-8-sig", newline="") as file:

        writer = csv.DictWriter(file, fieldnames=HEADERS)

        if not file_exists:
            writer.writeheader()
            file.flush()

        for year, month in month_iterator(
            START_YEAR, START_MONTH, END_YEAR, END_MONTH
        ):
            label = f"{year}-{month:02d}"
            expected = calendar.monthrange(year, month)[1] * 24

            print(f"\nĐang xử lý tháng: {label}")

            # Resume: tháng đã đủ dữ liệu thì bỏ qua.
            if rows_per_month[label] >= expected:
                print(f"  đã có đủ {rows_per_month[label]} dòng, bỏ qua")
                continue

            try:
                data = get_month_data(year, month, config)
                records = build_records(data)

            except Exception as error:
                print(f"  LỖI: {error}")
                failed_months.append(label)
                continue

            added = 0

            for record in records:
                key = (record["Date"], record["Time"])

                if key in existing_keys:
                    continue

                writer.writerow(record)
                existing_keys.add(key)
                rows_per_month[label] += 1
                added += 1

            file.flush()

            new_records += added

            print(f"  thêm {added} dòng (tháng này có {rows_per_month[label]}/{expected})")

            if rows_per_month[label] < expected:
                incomplete_months.append(label)

            time.sleep(DELAY_BETWEEN_REQUESTS)

    print()
    print("=" * 60)
    print(f"Hoàn tất. Record mới: {new_records}")
    print(f"File: {OUTPUT_FILE}")

    if "visibility" not in config["variables"]:
        print("Lưu ý: Archive API không có visibility, cột Visibility để trống.")

    if incomplete_months:
        print(
            "Tháng chưa đủ dữ liệu (thường là tháng cuối do dữ liệu mới "
            "chưa kịp cập nhật, chạy lại sau vài ngày): "
            + ", ".join(incomplete_months)
        )

    if failed_months:
        print("Tháng bị lỗi, chạy lại script để thử tiếp: " + ", ".join(failed_months))

    print("=" * 60)


if __name__ == "__main__":
    main()