from flask import Flask, render_template, request, jsonify
from flask import send_from_directory
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from suntime import Sun

app = Flask(__name__)

HEADERS = {'User-Agent': '(WeatherHubProject, maruthi.phanikumar@yopmail.com)'}

def fetch_json(url):
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    
    try:
        resp = session.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return {}

def get_weather_data(lat, lon):
    try:
        lat_f, lon_f = round(float(lat), 4), round(float(lon), 4)
        
        meta = fetch_json(f"https://api.weather.gov/points/{lat_f},{lon_f}")
        if not meta or 'properties' not in meta:
            return None
            
        prop = meta['properties']
        
        loc_props = prop.get('relativeLocation', {}).get('properties', {})
        city = loc_props.get('city', 'Unknown').title()
        state = loc_props.get('state', '??')
        
        daily_data = fetch_json(prop['forecast'])
        hourly_data = fetch_json(prop['forecastHourly'])
        alerts_data = fetch_json(f"https://api.weather.gov/alerts/active?point={lat_f},{lon_f}")
        
        hourly_periods = hourly_data.get('properties', {}).get('periods', [])
        if not hourly_periods:
            return None

        sun = Sun(lat_f, lon_f)
        sunrise = sun.get_sunrise_time()
        sunset = sun.get_sunset_time()

        daily_periods = daily_data.get('properties', {}).get('periods', [])
        daily_forecasts = []
        seen_dates = set()

        for i, p in enumerate(daily_periods):
            date_str = p['startTime'][:10]
            if date_str not in seen_dates:
                if p['isDaytime']:
                    high = p['temperature']
                    low = daily_periods[i+1]['temperature'] if i+1 < len(daily_periods) else high
                else:
                    high = hourly_periods[0]['temperature']
                    low = p['temperature']

                daily_forecasts.append({
                    "date": date_str,
                    "high": high,
                    "low": low,
                    "icon": p['shortForecast']
                })
                seen_dates.add(date_str)
            if len(daily_forecasts) >= 7: break
            
        processed_hourly = [
            {
                "startTime": p['startTime'],
                "temperature": p['temperature'],
                "shortForecast": p['shortForecast'],
                "precipProb": p.get('probabilityOfPrecipitation', {}).get('value') or 0,
                "humidity": p.get('relativeHumidity', {}).get('value') or 0,
                "windSpeed": float(str(p.get('windSpeed', '0')).split(' ')[0]) if str(p.get('windSpeed', '0')).split(' ')[0].replace('.','',1).isdigit() else 0
            } for p in hourly_periods[:120]
        ]

        print(f"User location: {city}, {state}", flush=True)

        return {
            "location": f"{city}, {state}",
            "lat": lat_f,
            "lon": lon_f,
            "current": hourly_periods[0],
            "daily": daily_forecasts,
            "hourly": processed_hourly,
            "alerts": alerts_data.get('features', []),
            "sun": {
                "sunrise": sunrise.isoformat(),
                "sunset": sunset.isoformat()
            }
        }
    except Exception as e:
        print(f"Server Error: {e}")
        return None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('.', 'manifest.json')

@app.route('/sw.js')
def serve_sw():
    return send_from_directory('static', 'sw.js')

@app.route('/weather_data', methods=['POST'])
def weather_data():
    coords = request.get_json()
    if not coords or 'lat' not in coords or 'lon' not in coords:
        return jsonify({"error": "Missing coordinates"}), 400
        
    data = get_weather_data(coords['lat'], coords['lon'])
    if data:
        return jsonify(data)
    return jsonify({"error": "Failed to fetch NWS data"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)