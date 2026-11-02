from bot import VKBot

print("🚀 ЗАГРУЗКА ГЛАВНОГО ФАЙЛА...")  # <--- ДОБАВЬ ЭТО
from bot import VKBot

if __name__ == "__main__":
    print("🚀 СОЗДАНИЕ БОТА...")       # <--- И ЭТО
    bot = VKBot()
    print("🚀 ИНИЦИАЛИЗАЦИЯ...")       # <--- И ЭТО
    if bot.init():
        bot.run()

if __name__ == "__main__":
    print("🚀 Запуск RP-бота...")
    bot = VKBot()
    if bot.init():
        bot.run()
    else:
        print("❌ Не удалось запустить")
