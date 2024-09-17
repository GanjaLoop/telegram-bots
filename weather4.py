import os
import requests
import logging
import time
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler

# Настройки
TELEGRAM_TOKEN = 'TOKEN'
YANDEX_API_KEY = 'API'
YANДЕК_GEOCODER_API_KEY = 'API'
INTERVAL_SECONDS = 7200  # Период мониторинга в секундах (2 часа)

LAT = None  # Широта
LON = None  # Долгота
CHAT_ID = None  # ID чата пользователя, будет установлена после ввода команды /start

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
CHOOSING_CITY = 0

# Функция для запроса к Яндекс.Погоде
def get_weather():
    global LAT, LON
    url = f"https://api.weather.yandex.ru/v2/forecast?lat={LAT}&lon={LON}&extra=true"
    headers = {
        "X-Yandex-API-Key": '97b1b7d3-fa75-454d-af31-2f5e34301d06'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        logger.error(f"Ошибка при запросе к Яндекс.Погоде: {response.status_code}")
        return None

# Функция для получения координат по названию города
def get_coordinates(city_name):
    url = f"https://geocode-maps.yandex.ru/1.x/?apikey={'88a8bde5-d767-4ea7-8651-bd8a7bc879dd'}&geocode={city_name}&format=json"
    response = requests.get(url)
    if response.status_code == 200:
        json_response = response.json()
        pos = json_response['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['Point']['pos']
        lon, lat = map(float, pos.split(' '))
        return lat, lon
    else:
        logger.error(f"Ошибка при запросе к Яндекс Геокодеру: {response.status_code}")
        return None, None

# Функция для формирования сообщения с погодой
def generate_weather_message(data):
    fact = data['fact']
    forecast = data['forecasts'][0]['hours']

    temp_now = fact['temp']
    # Возьмем среднюю температуру за два ближайших часа
    temp_2_hours = (forecast[0]['temp'] + forecast[1]['temp']) / 2

    condition_now = fact['condition']
    # Возьмем прогнозируемое погодное условие через два часа
    condition_2_hours = forecast[1]['condition']

    wind_speed = fact['wind_speed']
    humidity = fact['humidity']

    message = (
        f"Температура на данный момент: {temp_now}°C\n"
        f"Ожидаемая температура в течение 2-х часов: {temp_2_hours}°C\n"
        f"Погодные условия на данный момент: {condition_now}\n"
        f"Ожидаемые погодные условия в течение 2-х часов: {condition_2_hours}\n"
        f"Скорость ветра: {wind_speed} м/с\n"
        f"Влажность: {humidity}%\n"
    )

    # Советы по одежде и необходимости зонта
    if temp_now < 0:
        message += "Совет: Одевайтесь тепло, чтобы не замерзнуть!\n"
    elif temp_now < 10:
        message += "Совет: Оденьте куртку, на улице прохладно.\n"
    elif temp_now < 20:
        message += "Совет: Вполне можно обойтись свитером или легкой курткой.\n"
    else:
        message += "Совет: Одевайтесь по-летнему, на улице тепло.\n"

    if 'дождь' in condition_now or 'осадки' in condition_now:
        message += "Не забудьте зонт, возможны осадки!\n"
    else:
        message += "Зонт не понадобится.\n"

    return message


# Функция для мониторинга и отправки информации
def monitor_and_send():
    bot = Bot(token='7462670440:AAE4KBgh_l2a_Bks-LJOWF9UJPbzcQLHlDo')
    while True:
        logger.info("Запрос данных о погоде...")
        weather_data = get_weather()
        if weather_data:
            message = generate_weather_message(weather_data)
            try:
                bot.send_message(chat_id=CHAT_ID, text=message)
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения: {e}")
        else:
            try:
                bot.send_message(chat_id=CHAT_ID, text="Не удалось получить информацию о погоде.")
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения: {e}")
        time.sleep(INTERVAL_SECONDS)

# Команда /start для приветствия и запроса города
def start(update: Update, context: CallbackContext):
    user = update.message.from_user.username
    global CHAT_ID
    CHAT_ID = update.message.chat_id
    greeting_message = f"Привет, {user}! Введите название города, в котором вы живете."
    context.bot.send_message(chat_id=update.effective_chat.id, text=greeting_message)
    return CHOOSING_CITY

# Обработка ввода города
def choose_city(update: Update, context: CallbackContext):
    global LAT, LON
    city_name = update.message.text
    LAT, LON = get_coordinates(city_name)
    if LAT is not None and LON is not None:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"Город {city_name} выбран. Координаты: {LAT}, {LON}.")
        weather_data = get_weather()
        if weather_data:
            weather_message = generate_weather_message(weather_data)
            context.bot.send_message(chat_id=update.effective_chat.id, text=weather_message)
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text="Не удалось получить информацию о погоде.")
        return ConversationHandler.END
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Не удалось получить координаты. Попробуйте еще раз.")
        return CHOOSING_CITY

# Команда /weather для немедленного получения информации о погоде
def weather(update: Update, context: CallbackContext):
    logger.info("Запрос данных о погоде по команде /weather...")
    weather_data = get_weather()
    if weather_data:
        weather_message = generate_weather_message(weather_data)
        context.bot.send_message(chat_id=update.effective_chat.id, text=weather_message)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Не удалось получить информацию о погоде.")

# Команда /change_location для смены города
def change_location(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Введите название нового города:")
    return CHOOSING_CITY

# Главная функция для запуска бота
def main():
    logger.info("Запуск бота...")
    updater = Updater('7462670440:AAE4KBgh_l2a_Bks-LJOWF9UJPbzcQLHlDo', use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CommandHandler('change_location', change_location)],
        states={
            CHOOSING_CITY: [MessageHandler(Filters.text & ~Filters.command, choose_city)]
        },
        fallbacks=[]
    )

    dp.add_handler(conv_handler)
    dp.add_handler(CommandHandler("weather", weather))

    # Запустите мониторинг в отдельном потоке
    from threading import Thread
    monitor_thread = Thread(target=monitor_and_send)
    monitor_thread.start()
    
    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
