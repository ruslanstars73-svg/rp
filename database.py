import os
import json
from config import DATA_DIR

def load_json(f):
    if os.path.exists(f):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                print(f"📂 Загружен {f}: {len(data)} записей")
                return data
        except json.JSONDecodeError as e:
            print(f"⚠️ Ошибка декодирования JSON в {f}: {e}. Создаём новый файл.")
            with open(f, 'w', encoding='utf-8') as file:
                json.dump({}, file)
            return {}
        except Exception as e:
            print(f"⚠️ Ошибка загрузки {f}: {e}")
            return {}
    else:
        print(f"📄 Файл {f} не найден, создаётся новый")
        return {}

def save_json(f, d):
    if not f:
        return
    try:
        dirname = os.path.dirname(f)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(f, 'w', encoding='utf-8') as file:
            json.dump(d, file, ensure_ascii=False, indent=2)
        print(f"✅ Файл {f} сохранён, записей: {len(d)}")
    except Exception as e:
        print(f"❌ ОШИБКА сохранения {f}: {e}")