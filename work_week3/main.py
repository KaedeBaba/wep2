import flet as ft
import json
import urllib.request
import urllib.error
import sqlite3
from datetime import datetime

DB_NAME = "weather_data.db"

def initialize_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weather_forecast (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area_code TEXT NOT NULL,
            area_name TEXT NOT NULL,
            forecast_time TEXT NOT NULL,
            weather TEXT,
            wind TEXT,
            wave TEXT,
            min_temp REAL,
            max_temp REAL
        )
    ''')

    conn.commit()
    conn.close()

def save_weather_data_to_db(area_code, area_name, forecast_time, weather, wind, wave, min_temp, max_temp):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO weather_forecast (area_code, area_name, forecast_time, weather, wind, wave, min_temp, max_temp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (area_code, area_name, forecast_time, weather, wind, wave, min_temp, max_temp))
    
    conn.commit()
    conn.close()

def get_weather_data_from_db(area_code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT area_name, forecast_time, weather, wind, wave, min_temp, max_temp
        FROM weather_forecast
        WHERE area_code = ?
        ORDER BY forecast_time
    ''', (area_code,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return rows

def fetch_json_from_url(url):
    try:
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.URLError as e:
        print(f"Error fetching data: {e}")
        return None

def load_area_data():
    url = "https://www.jma.go.jp/bosai/common/const/area.json"
    return fetch_json_from_url(url)

def load_weather_data(area_code):
    url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{area_code}.json"
    return fetch_json_from_url(url)

def create_area_mapping(data):
    code_to_name = {}
    if data and isinstance(data, dict):
        offices = data.get("offices", {})
        for code, info in offices.items():
            code_to_name[code] = info.get("name", "不明")
    return code_to_name

def convert_weather_to_emoji(weather_text):
    weather_dict = {
        "くもり": "☁️",
        "雪": "⛄️",
        "晴れ": "☀️",
        "雷": "⚡️",
        "雨": "☔️"
    }
    for key, emoji in weather_dict.items():
        weather_text = weather_text.replace(key, emoji)
    
    weather_text = weather_text.replace("時々", "時々")
    weather_text = weather_text.replace("〜", "→")
    weather_text = weather_text.replace("朝晩", "/")
    
    return weather_text

def extract_temps_from_weather_data(weather_data):
    """気温データを正確に抽出する関数"""
    temps_dict = {}
    
    if not weather_data or not isinstance(weather_data, list):
        return temps_dict
        
    for forecast in weather_data:
        if 'timeSeries' not in forecast:
            continue
            
        for time_series in forecast['timeSeries']:
            if 'timeDefines' not in time_series or 'areas' not in time_series:
                continue
                
            time_defines = time_series['timeDefines']
            
            for area in time_series['areas']:
                if 'tempsMin' in area and 'tempsMax' in area:
                    for idx, time in enumerate(time_defines):
                        if time not in temps_dict:
                            temps_dict[time] = {'min': None, 'max': None}
                        
                        if idx < len(area['tempsMin']) and area['tempsMin'][idx]:
                            temps_dict[time]['min'] = float(area['tempsMin'][idx])
                        if idx < len(area['tempsMax']) and area['tempsMax'][idx]:
                            temps_dict[time]['max'] = float(area['tempsMax'][idx])
    
    return temps_dict

def main(page: ft.Page):
    page.title = "Weather Areas"
    page.window.width = 1500
    page.window.height = 1000
    page.padding = 0

    area_data = load_area_data()
    if not area_data:
        page.add(ft.Text("エリアデータの読み込みに失敗しました"))
        return

    code_to_name = create_area_mapping(area_data)

    left_panel = ft.Column(
        controls=[],
        width=300,
        scroll=ft.ScrollMode.AUTO,
        spacing=10,
        height=page.window.height,
    )

    right_panel = ft.Column(
        controls=[
            ft.Text("地域を選択すると天気データが表示されます", size=24)
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=10,
    )

    def show_weather_data(area_code):
        weather_data = load_weather_data(area_code)
        if weather_data:
            temps_dict = extract_temps_from_weather_data(weather_data)
            
            saved_weather = get_weather_data_from_db(area_code)

            if not saved_weather:
                time_series = weather_data[0].get('timeSeries', [])
                for series in time_series:
                    time_defines = series.get('timeDefines', [])
                    for area in series.get('areas', []):
                        area_name = area['area']['name']
                        weathers = area.get('weathers', [])
                        winds = area.get('winds', [])
                        waves = area.get('waves', [])

                        for idx, time in enumerate(time_defines):
                            weather = convert_weather_to_emoji(weathers[idx]) if idx < len(weathers) else None
                            wind = winds[idx] if idx < len(winds) else None
                            wave = waves[idx] if idx < len(waves) else None
                            
                            temps = temps_dict.get(time, {})
                            min_temp = temps.get('min')
                            max_temp = temps.get('max')

                            save_weather_data_to_db(
                                area_code, area_name, time, 
                                weather, wind, wave, min_temp, max_temp
                            )

                saved_weather = get_weather_data_from_db(area_code)

            right_panel.controls = [
                ft.Text(f"エリアコード {area_code} の天気情報:", size=24)
            ]

            for record in saved_weather:
                area_name, forecast_time, weather, wind, wave, min_temp, max_temp = record
                
                controls = [
                    ft.Text(f"日時: {forecast_time}", size=16, weight=ft.FontWeight.BOLD)
                ]
                
                if weather:
                    controls.append(ft.Text(f"天気: {weather}", size=14))
                if wind:
                    controls.append(ft.Text(f"風: {wind}", size=14))
                if wave:
                    controls.append(ft.Text(f"波: {wave}", size=14))
                if min_temp is not None:
                    controls.append(ft.Text(f"最低気温: {min_temp}°C", size=14))
                if max_temp is not None:
                    controls.append(ft.Text(f"最高気温: {max_temp}°C", size=14))

                right_panel.controls.append(
                    ft.Container(
                        content=ft.Column(controls=controls),
                        padding=10,
                        margin=10,
                        border_radius=8,
                        border=ft.border.all(1, ft.colors.GREY_300),
                        bgcolor=ft.colors.LIGHT_BLUE_50,
                    )
                )
            
            page.update()
        else:
            right_panel.controls = [
                ft.Text("天気データの取得に失敗しました", size=24)
            ]
            page.update()

    def on_area_click(e, area_code):
        show_weather_data(area_code)

    for center_key, center_value in area_data.get("centers", {}).items():
        expansion_tile = ft.ExpansionTile(
            title=ft.Text(center_value["name"]),
            subtitle=ft.Text(center_value.get("enName", "")),
            trailing=ft.Icon(ft.icons.ARROW_DROP_DOWN),
            collapsed_text_color=ft.colors.GREEN,
            text_color=ft.colors.GREEN,
            controls=[]
        )

        for child in center_value.get("children", []):
            area_name = code_to_name.get(child, f"Area {child}")
            expansion_tile.controls.append(
                ft.ListTile(
                    title=ft.Text(f"{area_name} ({child})"),
                    on_click=lambda e, code=child: on_area_click(e, code)
                )
            )
        left_panel.controls.append(expansion_tile)

    layout = ft.Row(
        controls=[
            ft.Container(
                content=left_panel,
                border=ft.border.all(1, ft.colors.GREY_400),
                padding=10,
                height=page.window.height,
            ),
            ft.Container(
                content=right_panel,
                expand=True,
                border=ft.border.all(1, ft.colors.GREY_400),
                padding=10,
                height=page.window.height,
            ),
        ],
        spacing=0,
        height=page.window.height,
    )

    page.add(layout)
    page.update()

initialize_db()

ft.app(target=main)
