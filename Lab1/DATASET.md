# Bộ dữ liệu thời tiết theo giờ – khu vực Thủ Đức, TP.HCM

## Tổng quan

Dữ liệu thời tiết lịch sử theo giờ cho khu vực Thủ Đức (TP. Hồ Chí Minh), tải từ API lịch sử (Archive API) của [Open-Meteo](https://open-meteo.com/) bằng script `fetch_weather_openmeteo.py`.

| Thông tin | Giá trị |
|---|---|
| File dữ liệu | `weather_openmeteo.csv` |
| Nguồn | Open-Meteo Historical Weather API (`archive-api.open-meteo.com`) |
| Vị trí | Vĩ độ 10.85, kinh độ 106.76 (Thủ Đức, TP.HCM) |
| Múi giờ | `Asia/Ho_Chi_Minh` (UTC+7) |
| Khoảng thời gian | 01/12/2020 – 30/09/2026 |
| Độ phân giải | Theo giờ (24 dòng mỗi ngày) |
| Số dòng tối đa | 51.120 (2.130 ngày × 24 giờ), có thể ít hơn nếu thiếu dữ liệu |
| Mã hoá | UTF-8 (có BOM) |

## Các cột

| Cột | Ý nghĩa | Đơn vị / định dạng |
|---|---|---|
| `Date` | Ngày | `YYYY-MM-DD` |
| `Time` | Giờ địa phương | `HH:MM` |
| `Temperature` | Nhiệt độ không khí ở độ cao 2 m | °C |
| `Weather` | Mô tả thời tiết, đổi từ mã WMO | Văn bản (vd. `Overcast`, `Slight rain`) |
| `Wind` | Tốc độ gió ở độ cao 10 m | km/h |
| `Humidity` | Độ ẩm tương đối ở độ cao 2 m | % |
| `Barometer` | Áp suất khí quyển quy về mực nước biển | hPa |
| `Visibility` | Tầm nhìn xa | mét; **thường để trống** (xem lưu ý) |

Khoá duy nhất của mỗi dòng là cặp (`Date`, `Time`).

## Ví dụ

```csv
Date,Time,Temperature,Weather,Wind,Humidity,Barometer,Visibility
2024-12-01,00:00,26.4,Partly cloudy,8.2,84,1011.3,
2024-12-01,01:00,26.1,Mainly clear,7.5,85,1011.0,
```

(Giá trị minh hoạ, không phải số liệu thật.)

## Lưu ý khi sử dụng

- **Đây là dữ liệu tái phân tích (reanalysis), không phải số quan trắc tại một trạm đo.** Giá trị được nội suy theo lưới nên có thể lệch nhẹ so với trạm thực tế hoặc các trang như timeanddate.
- **Cột `Visibility`**: Archive API của Open-Meteo có thể không cung cấp biến này. Khi đó script bỏ qua và cột để trống. Hãy kiểm tra file thực tế trước khi dùng.
- **Cột `Weather`** là mô tả suy ra từ mã WMO (như `Clear sky`, `Overcast`, `Moderate rain`), nên chỉ có số ít giá trị khác nhau, không phải câu mô tả tự do.
- **Vài ngày cuối khoảng thời gian có thể thiếu**, do dữ liệu archive cập nhật trễ vài ngày. Chạy lại script sau đó sẽ tự bổ sung.
- **Giấy phép**: Open-Meteo miễn phí cho mục đích phi thương mại. Hãy xem điều khoản của Open-Meteo nếu dùng cho mục đích thương mại, và ghi nguồn khi công bố.

## Cách tái tạo dữ liệu

```
pip install requests
python fetch_weather_openmeteo.py
```

Script tải từng tháng, ghi dần vào CSV và có cơ chế resume: tháng nào đã đủ dữ liệu sẽ được bỏ qua khi chạy lại. Có thể đổi toạ độ và khoảng thời gian ở đầu file script (`LATITUDE`, `LONGITUDE`, `START_YEAR`, `START_MONTH`, `END_YEAR`, `END_MONTH`).

## Ghi chú về nguồn dữ liệu trước đó

Ban đầu dự định thu thập từ timeanddate.com bằng Selenium, nhưng trang chặn truy cập tự động (Cloudflare), nên chuyển sang Open-Meteo. Dữ liệu của hai nguồn khác định dạng giờ và đơn vị, không nên trộn trong cùng một file.
