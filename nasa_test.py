import requests

print("📡 Connecting to NASA Satellites...")

# 1. Define the location (Latitude and Longitude for Guwahati)
lat = 26.18
lon = 91.69

# 2. Build the exact API URL
# We are asking for Climatology (long-term averages) for Renewable Energy (RE)
# Parameters: ALLSKY_SFC_SW_DWN (Solar Radiation) and T2M (Temperature at 2 Meters)
nasa_url = f"https://power.larc.nasa.gov/api/temporal/climatology/point?parameters=ALLSKY_SFC_SW_DWN,T2M&community=RE&longitude={lon}&latitude={lat}&format=JSON"

# 3. Open the valve and fetch the data
response = requests.get(nasa_url)

# 4. Convert the data pipeline into a readable Python dictionary
data = response.json()

# 5. Extract the exact numbers we need from the massive data package
# We are pulling the 'ANN' (Annual Average) values
annual_solar_rad = data['properties']['parameter']['ALLSKY_SFC_SW_DWN']['ANN']
annual_temp = data['properties']['parameter']['T2M']['ANN']

# 6. Output the results
print("\n✅ Data Received Successfully!")
print("-----------------------------------")
print(f"Location: Latitude {lat}, Longitude {lon}")
print(f"Average Daily Solar Radiation: {annual_solar_rad} kWh/m²/day")
print(f"Average Ambient Temperature: {annual_temp} °C")