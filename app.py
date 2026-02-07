from flask import Flask, render_template, request, jsonify
import requests
from datetime import datetime, timedelta
import pytz
from suntime import Sun
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
HEADERS = {'User-Agent': '(MyHomeLab, maruthi.phanikumar@yopmail.com)'}
# Global session for connection pooling
session = requests.Session()
session.headers.update(HEADERS)

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

def fetch_json(url, timeout=5):
    try:
        resp = session.get(url, timeout=timeout)
        return resp.json() if resp.status_code == 200 else {}
    except:
        return {}

def get_weather_data(lat, lon):
    try:
        lat_f, lon_f = round(float(lat), 4), round(float(lon), 4)
        
        # Step 1: Initial Point Metadata (Synchronous because others depend on it)
        meta = fetch_json(f"https://api.weather.gov/points/{lat_f},{lon_f}")
        if not meta: return None
        prop = meta['properties']

        # URLs for parallel fetching
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        urls = {
            "daily": prop['forecast'],
            "hourly": prop['forecastHourly'],
            "stations": prop['observationStations'],
            "alerts": f"https://api.weather.gov/alerts/active?point={lat_f},{lon_f}",
            "env": f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat_f}&longitude={lon_f}&current=us_aqi,uv_index&timezone=auto",
            "yesterday": f"https://archive-api.open-meteo.com/v1/archive?latitude={lat_f}&longitude={lon_f}&start_date={yesterday}&end_date={yesterday}&hourly=temperature_2m&temperature_unit=fahrenheit",
            "rain": f"https://api.open-meteo.com/v1/forecast?latitude={lat_f}&longitude={lon_f}&minutely_15=precipitation&timezone=auto"
        }

        # Step 2: Fetch all other data concurrently
        with ThreadPoolExecutor(max_workers=7) as executor:
            future_to_key = {executor.submit(fetch_json, url): key for key, url in urls.items()}
            results = {future_to_key[f]: f.result() for f in future_to_key}

        # Step 3: Latest Observation (Requires station ID from step 2)
        obs_data = {}
        stations = results['stations'].get('features', [])
        if stations:
            st_id = stations[0]['properties']['stationIdentifier']
            obs_data = fetch_json(f"https://api.weather.gov/stations/{st_id}/observations/latest").get('properties', {})

        # --- Data Processing ---
        current = results['hourly']['properties']['periods'][0]
        temp = current['temperature']
        humid = current.get('relativeHumidity', {}).get('value', 50) or 50
        
        # Parse wind
        wind_raw = str(current.get('windSpeed', '0')).lower()
        wind_str = wind_raw.split('to')[-1].strip().split(' ')[0] if 'to' in wind_raw else wind_raw.split(' ')[0]
        wind_val = float(wind_str) if wind_str.replace('.','',1).isdigit() else 0
        
        pressure_inhg = round(obs_data.get('barometricPressure', {}).get('value', 0) * 0.0002953, 2) or "N/A"

        # Sun times
        sun = Sun(lat_f, lon_f)
        eastern_tz = pytz.timezone('US/Eastern')
        sunrise_local = sun.get_sunrise_time().astimezone(eastern_tz)
        sunset_local = sun.get_sunset_time().astimezone(eastern_tz)

        # Yesterday Temp Logic
        current_hour = datetime.now().hour
        yesterday_val = results['yesterday'].get('hourly', {}).get('temperature_2m', [None]*24)[current_hour]

        # Rain Pulse logic
        raw_rain = results['rain'].get('minutely_15', {}).get('precipitation', [0]*4)
        rain_pulse = [val for val in raw_rain for _ in range(3)][:12]

        # Daily Forecasts
        periods = results['daily'].get('properties', {}).get('periods', [])
        daily_forecasts = [
            {
                "name": periods[i]['name'], "icon": periods[i]['shortForecast'],
                "high": periods[i]['temperature'], "low": periods[i+1]['temperature'] if i+1 < len(periods) else periods[i]['temperature'],
                "date": periods[i]['startTime'][:10]
            } for i in range(0, min(len(periods), 14), 2)
        ]

        # Hourly Forecasts
        processed_hourly = [
            {
                "startTime": p['startTime'], "temperature": p['temperature'],
                "shortForecast": p['shortForecast'], "precipProb": p.get('probabilityOfPrecipitation', {}).get('value') or 0
            } for p in results['hourly']['properties']['periods'][:120]
        ]

        return {
            "location": f"{prop['relativeLocation']['properties']['city'].title()}, {prop['relativeLocation']['properties']['state']}",
            "current": current,
            "feels_like": round(calculate_feels_like(temp, humid, wind_val)),
            "wind": {"speed": wind_val, "direction": current.get('windDirection')},
            "pressure": pressure_inhg,
            "aqi": results['env'].get('current', {}).get('us_aqi'),
            "uv": results['env'].get('current', {}).get('uv_index'),
            "yesterday_temp": yesterday_val,
            "daily": daily_forecasts,
            "hourly": processed_hourly,
            "alerts": results['alerts'].get('features', []),
            "rain_pulse": rain_pulse,
            "is_snow": any(x in current['shortForecast'].lower() for x in ["snow", "flurries"]),
            "precip_alert": any(v > 0 for v in rain_pulse[:3]), 
            "sun": {
                "sunrise": sunrise_local.strftime("%I:%M %p"),
                "sunset": sunset_local.strftime("%I:%M %p")
            },
            "updated": datetime.now(eastern_tz).strftime("%I:%M %p"),
            "lat": lat_f, "lon": lon_f
        }
    except Exception as e:
        print(f"Error: {e}")
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