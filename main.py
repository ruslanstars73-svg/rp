from bot import VKBot

if __name__ == "__main__":
    print("🚀 Запуск RP-бота...")
    bot = VKBot()
    if bot.init():
        bot.run()
    else:
        print("❌ Не удалось запустить")