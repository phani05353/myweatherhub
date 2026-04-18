# Weather Hub — Premium HomeLab Dashboard

A high-fidelity, real-time weather dashboard built with Flask and modern CSS/JS. Designed for HomeLab environments, this app provides a UI-rich experience similar to premium mobile weather applications, with dynamic visuals that adapt to current conditions.

## Features

- **Current Conditions** — Temperature, feels-like, humidity, wind speed, and short forecast description from the NWS API
- **7-Day Forecast** — Apple-style temperature range bars visualizing the daily high/low relative to the week's extremes
- **24-Hour Hourly Strip** — Scrollable hourly cards with weather icons, temperature, and precipitation probability; sunrise/sunset events inserted inline at the correct time slot
- **Yesterday Comparison** — "X° warmer/colder than yesterday" badge using Open-Meteo archive data
- **Precipitation Pulse** — Minutely rain/snow forecast bar for the next 60 minutes (Open-Meteo)
- **Air Quality & UV** — US AQI and UV Index with dynamic color-coding from Open-Meteo, with a 24-hour AQI trend chart
- **Wind Forecast Chart** — 24-hour sustained wind + gust overlay chart
- **Humidity Chart** — 24-hour humidity trend chart
- **Outdoor Activity Score** — Composite score (0–100) based on temperature, AQI, UV, wind, and humidity
- **Road Safety Rating** — Safe / Caution / Hazardous evaluation based on visibility, gusts, temperature, and precipitation
- **Clothing Advice** — Context-aware outfit suggestion based on current conditions
- **NWS Alert Integration** — Live weather advisories with pulsing badge; tapping shows full alert details and expiry
- **Astronomy Tracking** — Precise local sunrise/sunset times calculated from coordinates via `suntime`
- **Live Radar** — Windy radar embed centered on your coordinates
- **City Search** — Geocoding search via Open-Meteo to load weather for any location worldwide
- **Dynamic Backgrounds** — Condition-matched Unsplash photos (sunny, cloudy, rain, snow, thunder, night)
- **CSS Weather Effects** — Pure CSS rain streaks, snowflakes, and lightning flash animations
- **Dynamic Blur** — Backdrop blur intensity scales with humidity and visibility
- **Pull-to-Refresh** — Touch gesture support on mobile
- **Theme Switching** — Light/Dark mode with persistence via localStorage
- **Unit Toggle** — °F / °C toggle with instant UI re-render; persisted via localStorage
- **PWA Support** — Service Worker + `manifest.json` for installable app experience

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, Flask, Gunicorn |
| Frontend | HTML5, CSS3, Bootstrap 5, Chart.js, Weather Icons 2.0 |
| Weather Data | [National Weather Service (NWS)](https://www.weather.gov/documentation/services-web-api) |
| Air Quality / UV | [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api) |
| Precipitation (minutely) | [Open-Meteo Forecast API](https://open-meteo.com/en/docs) |
| Historical Comparison | [Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api) |
| Geocoding | [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api) |
| Radar | [Windy Embed](https://windy.com/) |
| Backgrounds | [Unsplash](https://unsplash.com/) (static photo IDs, no API key required) |
| Sunrise/Sunset | `suntime` Python library |
| Timezone Detection | `timezonefinder` + `pytz` |

## Installation

### Prerequisites

Python 3.8+ required.

### 1. Clone & Install

```bash
git clone https://github.com/phani05353/myweatherhub.git
cd myweatherhub
pip install -r requirements.txt
```

`requirements.txt` includes: `flask`, `requests`, `pytz`, `suntime`, `gunicorn`, `timezonefinder`

### 2. Run (Development)

```bash
python app.py
```

Open `http://localhost:5000` in your browser. The app requests geolocation on load; if denied, it defaults to Laramie, WY.

### 3. Run (Production)

```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
```

### 4. Run with Docker

```bash
docker build -t weatherhub .
docker run -p 5000:5000 weatherhub
```

## Notes

- **NWS coverage**: The NWS API only covers US locations. Searching for international cities will return an error — international forecast support would require an additional provider.
- **No API keys needed**: All external APIs used are free and keyless.
- **PWA install**: On Chrome/Edge, use the browser's "Install app" option after opening the app. On Safari iOS, use "Add to Home Screen".
