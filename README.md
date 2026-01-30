# 🌦️ Weather Hub: Premium HomeLab Dashboard

A high-fidelity, real-time weather dashboard built with Flask and modern CSS/JS. Designed specifically for HomeLab environments, this app provides a "UI-rich" experience similar to premium mobile weather applications, featuring dynamic visuals that adapt to current conditions.

!

## ✨ Key Features

* **Apple-Style 7-Day Forecast:** Dynamic temperature bars that visualize the daily range relative to the week's extremes.
* **Pro Hourly Trend Graph:** A dot-less, color-coded line graph (via Chart.js) that shifts colors based on temperature (Blue for cool, Orange/Red for hot) with a deep gradient area fill.
* **Dynamic Weather Effects:** Pure CSS-based environmental animations including falling rain streaks and solar glare based on current conditions.
* **Exact Sensor Data:** Real-time extraction of US AQI (Air Quality Index) and UV Index with dynamic color-coding for health thresholds.
* **Astronomy Tracking:** Precise local sunrise and sunset times calculated via coordinates.
* **NWS Alert Integration:** Live weather advisories that specifically parse out "Instruction" fields for safety actions.
* **Persistence:** Remembers your preference for Dark/Light mode and Metric/Imperial units using browser LocalStorage.
* **Glassmorphism UI:** A modern, translucent interface designed for high-resolution dedicated displays.

## 🚀 Tech Stack

* **Backend:** Python 3, Flask
* **Frontend:** HTML5, CSS3 (Flexbox/Animations), Bootstrap 5, Chart.js
* **APIs:** * [National Weather Service (NWS)](https://www.weather.gov/documentation/services-web-api) - Forecasts & Alerts
    * [Open-Meteo](https://open-meteo.com/) - Air Quality & UV Index
    * [Unsplash API](https://unsplash.com/) - Dynamic weather backgrounds
* **Libraries:** `suntime`, `requests`

## 🛠️ Installation & Setup

### 1. Prerequisites
Ensure you have Python 3.8+ installed on your system.

### 2. Install Dependencies
Navigate to your project folder and install the required Python packages:
```bash
python3 -m pip install flask requests suntime