from flask import Flask, render_template, request, jsonify
import requests
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

def fetch_json(url):
    for attempt in range(3):  # Try up to 3 times
        try:
            resp = session.get(url, timeout=TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 500:
                print(f"NWS 500 Error on {url}. Retrying {attempt+1}/3...")
                time.sleep(1)  # Wait 1 second before retrying
                continue
        except Exception as e:
            print(f"Request failed: {e}")
        time.sleep(1)
    return {}
    
def get_weather_data(lat, lon):
    try:
        lat_f, lon_f = round(float(lat), 4), round(float(lon), 4)
        
        # 1. Get Metadata (Required for NWS URLs)
        meta = fetch_json(f"https://api.weather.gov/points/{lat_f},{lon_f}")
        if not meta or 'properties' not in meta:
            print(f"Error: Could not retrieve NWS metadata for {lat_f},{lon_f}")
            return None
            
        prop = meta['properties']
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Safe location extraction
        loc_props = prop.get('relativeLocation', {}).get('properties', {})
        city = loc_props.get('city', 'Unknown').title()
        state = loc_props.get('state', '??')
        
        print(f">>> [CITY_LOAD] Location: {city}, {state}", flush=True)
        
        # 2. Sequential Fetches
        # We fetch these one by one now. 
        daily_data = fetch_json(prop['forecast'])
        hourly_data = fetch_json(prop['forecastHourly'])
        stations_data = fetch_json(prop['observationStations'])
        alerts_data = fetch_json(f"https://api.weather.gov/alerts/active?point={lat_f},{lon_f}")
        
        env_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat_f}&longitude={lon_f}&current=us_aqi,uv_index&hourly=us_aqi&timezone=auto"
        env_data = fetch_json(env_url)
        
        yesterday_url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat_f}&longitude={lon_f}&start_date={yesterday}&end_date={yesterday}&hourly=temperature_2m&temperature_unit=fahrenheit"
        yesterday_data = fetch_json(yesterday_url)
        
        rain_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat_f}&longitude={lon_f}&minutely_15=precipitation&timezone=auto"
        rain_data = fetch_json(rain_url)

        # 3. Get Station Observation (Latest)
        obs_data = {}
        stations = stations_data.get('features', [])
        if stations:
            st_id = stations[0]['properties']['stationIdentifier']
            obs_data = fetch_json(f"https://api.weather.gov/stations/{st_id}/observations/latest").get('properties', {})

        # 4. Process Hourly
        hourly_periods = hourly_data.get('properties', {}).get('periods', [])
        if not hourly_periods: 
            return None
        
        current = hourly_periods[0]
        temp = current['temperature']
        humid = current.get('relativeHumidity', {}).get('value', 50) or 50
        
        # Wind Parsing
        wind_raw = str(current.get('windSpeed', '0')).lower()
        wind_str = wind_raw.split('to')[-1].strip().split(' ')[0] if 'to' in wind_raw else wind_raw.split(' ')[0]
        wind_val = float(wind_str) if wind_str.replace('.','',1).isdigit() else 0
        
        # Pressure
        pressure_val = obs_data.get('barometricPressure', {}).get('value')
        pressure_inhg = round(pressure_val * 0.0002953, 2) if pressure_val else "N/A"

        # Sun Times
        sun = Sun(lat_f, lon_f)
        eastern_tz = pytz.timezone('US/Eastern')
        sunrise_local = sun.get_sunrise_time().astimezone(eastern_tz)
        sunset_local = sun.get_sunset_time().astimezone(eastern_tz)

        # Yesterday Comparison
        current_hour = datetime.now().hour
        yesterday_temps = yesterday_data.get('hourly', {}).get('temperature_2m', [None]*24)
        yesterday_val = yesterday_temps[current_hour] if current_hour < len(yesterday_temps) else None

        # Rain Pulse
        raw_rain = rain_data.get('minutely_15', {}).get('precipitation', [0]*4)
        rain_pulse = [val for val in raw_rain for _ in range(3)][:12]

        # Forecasts
        daily_periods = daily_data.get('properties', {}).get('periods', [])
        daily_forecasts = [
            {
                "name": daily_periods[i]['name'], 
                "icon": daily_periods[i]['shortForecast'],
                "high": daily_periods[i]['temperature'], 
                "low": daily_periods[i+1]['temperature'] if i+1 < len(daily_periods) else daily_periods[i]['temperature'],
                "date": daily_periods[i]['startTime'][:10]
            } for i in range(0, min(len(daily_periods), 14), 2)
        ]

        processed_hourly = [
            {
                "startTime": p['startTime'], 
                "temperature": p['temperature'],
                "shortForecast": p['shortForecast'], 
                "precipProb": p.get('probabilityOfPrecipitation', {}).get('value') or 0,
                "windSpeed": float(str(p.get('windSpeed', '0')).split(' ')[0]) if str(p.get('windSpeed', '0')).split(' ')[0].replace('.','',1).isdigit() else 0
            } for p in hourly_periods[:120]
        ]

        env_hourly_raw = env_data.get('hourly', {}).get('us_aqi', [])
        aqi_24h = env_hourly_raw[current_hour : current_hour + 24] if len(env_hourly_raw) > current_hour else []

        return {
            "location": f"{city}, {state}",
            "current": current,
            "feels_like": round(calculate_feels_like(temp, humid, wind_val)),
            "wind": {"speed": wind_val, "direction": current.get('windDirection')},
            "pressure": pressure_inhg,
            "aqi": env_data.get('current', {}).get('us_aqi'),
            "hourly_aqi": aqi_24h,
            "uv": env_data.get('current', {}).get('uv_index'),
            "yesterday_temp": yesterday_val,
            "daily": daily_forecasts,
            "hourly": processed_hourly,
            "alerts": alerts_data.get('features', []),
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
        print(f"Error in get_weather_data: {e}")
        import traceback
        traceback.print_exc() # This will print the exact line causing the crash
        return None

@app.route('/')
def home(): 
    return render_template('index.html')

@app.route('/weather_data', methods=['POST'])
def weather_data():
    coords = request.get_json()
    data = get_weather_data(coords['lat'], coords['lon'])
    return jsonify(data) if data else ("API Error", 500)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)