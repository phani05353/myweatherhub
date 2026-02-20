from flask import Flask, render_template, request, jsonify
import requests
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timedelta
import pytz
import time
from suntime import Sun
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

HEADERS = {'User-Agent': '(MyHomeLab, maruthi.phanikumar@yopmail.com)'}
TIMEOUT = 5 

session = requests.Session()
session.headers.update(HEADERS)
executor = ThreadPoolExecutor(max_workers=15)

def calculate_feels_like(temp_f, humidity, wind_speed_mph):
    if temp_f <= 50 and wind_speed_mph > 3:
        v = pow(wind_speed_mph, 0.16)
        return 35.74 + (0.6215 * temp_f) - (35.75 * v) + (0.4275 * temp_f * v)
    if temp_f >= 80:
        T, R = temp_f, humidity
        hi = 0.5 * (T + 61.0 + ((T - 68.0) * 1.2) + (R * 0.094))
        if hi > 80:
            hi = -42.379 + 2.04901523*T + 10.14333127*R - 0.22475541*T*R - \
                 0.00683783*T*T - 0.05481717*R*R + 0.00122874*T*T*R + \
                 0.00085282*T*R*R - 0.00000199*T*T*R*R
        return hi
    return temp_f

def calculate_activity_score(temp, aqi, uv, wind, humid):
    temp = temp if temp is not None else 70
    aqi = aqi if aqi is not None else 0
    uv = uv if uv is not None else 0
    wind = wind if wind is not None else 0
    humid = humid if humid is not None else 50
    
    score = 100
    if temp < 65: score -= (65 - temp) * 2.5
    elif temp > 80: score -= (temp - 80) * 3.5
    if aqi > 50: score -= (aqi - 50) * 0.5
    if wind > 15: score -= (wind - 15) * 2
    if uv > 7: score -= (uv - 7) * 5
    if humid > 70: score -= (humid - 70) * 0.5
    
    return max(0, min(100, round(score)))

def fetch_json(url):
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    try:
        resp = session.get(url, timeout=10) 
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Fetch failed for {url}: {e}")
    return {}

def fetch_aqi_waqi(lat, lon):
    token = os.environ.get("WAQI_TOKEN")
    if not token:
        print("WAQI_TOKEN missing from environment variables!")
        return {"aqi": 0, "station": "Unknown"}
    
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={token}"
    data = fetch_json(url)
    
    if data.get('status') == 'ok':
        return {
            "aqi": data['data']['aqi'],
            "station": data['data']['city']['name']
        }
    return {"aqi": 0, "station": "N/A"}

def get_weather_data(lat, lon):
    try:
        lat_f, lon_f = round(float(lat), 4), round(float(lon), 4)
        
        # 1. NWS Metadata
        meta = fetch_json(f"https://api.weather.gov/points/{lat_f},{lon_f}")
        if not meta or 'properties' not in meta:
            return None
            
        prop = meta['properties']
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        loc_props = prop.get('relativeLocation', {}).get('properties', {})
        city_name = loc_props.get('city', 'Unknown').title()
        state_name = loc_props.get('state', '??')

        # 2. Parallel Fetches (Optional optimization, but sequential works for now)
        daily_data = fetch_json(prop['forecast'])
        hourly_data = fetch_json(prop['forecastHourly'])
        stations_data = fetch_json(prop['observationStations'])
        alerts_data = fetch_json(f"https://api.weather.gov/alerts/active?point={lat_f},{lon_f}")
        
        # WAQI AQI Replace Open-Meteo
        aqi_data = fetch_aqi_waqi(lat_f, lon_f)
        
        yesterday_url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat_f}&longitude={lon_f}&start_date={yesterday}&end_date={yesterday}&hourly=temperature_2m&temperature_unit=fahrenheit"
        yesterday_data = fetch_json(yesterday_url)
        
        rain_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat_f}&longitude={lon_f}&minutely_15=precipitation&timezone=auto"
        rain_data = fetch_json(rain_url)

        # 3. Station Obs
        obs_data = {}
        stations = stations_data.get('features', [])
        if stations:
            st_id = stations[0]['properties']['stationIdentifier']
            obs_data = fetch_json(f"https://api.weather.gov/stations/{st_id}/observations/latest").get('properties', {})

        # 4. Processing
        hourly_periods = hourly_data.get('properties', {}).get('periods', [])
        if not hourly_periods: return None
        
        current = hourly_periods[0]
        temp = current['temperature']
        humid = current.get('relativeHumidity', {}).get('value', 50) or 50
        
        wind_raw = str(current.get('windSpeed', '0')).lower()
        wind_str = wind_raw.split('to')[-1].strip().split(' ')[0] if 'to' in wind_raw else wind_raw.split(' ')[0]
        wind_val = float(wind_str) if wind_str.replace('.','',1).isdigit() else 0
        
        pressure_val = obs_data.get('barometricPressure', {}).get('value')
        pressure_inhg = round(pressure_val * 0.0002953, 2) if pressure_val else "N/A"

        sun = Sun(lat_f, lon_f)
        eastern_tz = pytz.timezone('US/Eastern')
        sunrise_local = sun.get_sunrise_time().astimezone(eastern_tz)
        sunset_local = sun.get_sunset_time().astimezone(eastern_tz)

        current_hour = datetime.now().hour
        yesterday_temps = yesterday_data.get('hourly', {}).get('temperature_2m', [None]*24)
        yesterday_val = yesterday_temps[current_hour] if current_hour < len(yesterday_temps) else None

        raw_rain = rain_data.get('minutely_15', {}).get('precipitation', [0]*4)
        rain_pulse = [val for val in raw_rain for _ in range(3)][:12]

        daily_forecasts = []
        seen_dates = set()
        for i, p in enumerate(daily_data.get('properties', {}).get('periods', [])):
            date_str = p['startTime'][:10]
            if date_str not in seen_dates:
                daily_forecasts.append({
                    "name": p['name'], "icon": p['shortForecast'],
                    "high": p['temperature'] if p['isDaytime'] else hourly_periods[0]['temperature'],
                    "low": p['temperature'] if not p['isDaytime'] else (daily_data['properties']['periods'][i+1]['temperature'] if i+1 < len(daily_data['properties']['periods']) else p['temperature']),
                    "date": date_str
                })
                seen_dates.add(date_str)
            if len(daily_forecasts) >= 7: break

        processed_hourly = [
            {
                "startTime": p['startTime'], "temperature": p['temperature'],
                "shortForecast": p['shortForecast'], "precipProb": p.get('probabilityOfPrecipitation', {}).get('value') or 0,
                "humidity": p.get('relativeHumidity', {}).get('value') or 0,
                "windSpeed": float(str(p.get('windSpeed', '0')).split(' ')[0]) if str(p.get('windSpeed', '0')).split(' ')[0].replace('.','',1).isdigit() else 0
            } for p in hourly_periods[:120]
        ]

        return {
            "location": f"{city_name}, {state_name}",
            "current": current,
            "feels_like": round(calculate_feels_like(temp, humid, wind_val)),
            "wind": {"speed": wind_val, "direction": current.get('windDirection')},
            "pressure": pressure_inhg,
            "aqi": aqi_data['aqi'],
            "aqi_station": aqi_data['station'],
            "hourly_aqi": [], # WAQI Free doesn't provide hourly via geo feed
            "uv": 0, # Note: UV was from Open-Meteo; NWS or another source needed for UV
            "hourly_uv": [],
            "yesterday_temp": yesterday_val,
            "daily": daily_forecasts,
            "hourly": processed_hourly,
            "alerts": alerts_data.get('features', []),
            "rain_pulse": rain_pulse,
            "activity_score": calculate_activity_score(temp, aqi_data['aqi'], 0, wind_val, humid),
            "is_snow": any(x in current['shortForecast'].lower() for x in ["snow", "flurries"]),
            "precip_alert": any(v > 0 for v in rain_pulse[:3]), 
            "sun": {"sunrise": sunrise_local.strftime("%I:%M %p"), "sunset": sunset_local.strftime("%I:%M %p")},
            "updated": datetime.now(eastern_tz).strftime("%I:%M %p"),
            "lat": lat_f, "lon": lon_f
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None

@app.route('/')
def home(): return render_template('index.html')

@app.route('/weather_data', methods=['POST'])
def weather_data():
    coords = request.get_json()
    data = get_weather_data(coords['lat'], coords['lon'])
    return jsonify(data) if data else ("API Error", 500)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)