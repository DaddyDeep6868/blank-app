import tkinter as tk
from tkinter import messagebox
import requests

# Function to get weather data
def get_weather():
    city = city_entry.get()
    api_key = '9ee22cfb8dcb6e22c15358fe46c079d8'  # Use your provided API key
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric'

    try:
        response = requests.get(url)
        data = response.json()

        if data['cod'] == '404':
            messagebox.showerror("Error", "City not found!")
        else:
            main = data['main']
            weather = data['weather'][0]
            temperature = main['temp']
            pressure = main['pressure']
            humidity = main['humidity']
            weather_desc = weather['description']

            # Display weather details
            result_label.config(text=f"Temperature: {temperature}°C\n"
                                    f"Pressure: {pressure} hPa\n"
                                    f"Humidity: {humidity}%\n"
                                    f"Weather: {weather_desc.capitalize()}")

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {str(e)}")

# Create main window
root = tk.Tk()
root.title("Weather Prediction App")

# Set window size
root.geometry('400x300')

# City input label and text box
city_label = tk.Label(root, text="Enter City:")
city_label.pack(pady=10)

city_entry = tk.Entry(root, width=30)
city_entry.pack(pady=5)

# Get weather button
get_weather_button = tk.Button(root, text="Get Weather", command=get_weather)
get_weather_button.pack(pady=20)

# Result label for displaying weather data
result_label = tk.Label(root, text="", font=("Helvetica", 12))
result_label.pack(pady=10)

# Run the application
root.mainloop()