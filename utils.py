import re
import requests
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Общая сессия для HTTP-запросов (используется в AI и др.)
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})


def fmt_time(ts):
    try:
        s = int((datetime.now() - datetime.fromisoformat(ts)).total_seconds())
        y, m, d, h, mn = s//31536000, (s%31536000)//2592000, (s%2592000)//86400, (s%86400)//3600, (s%3600)//60
        parts = []
        if y: parts.append(f"{y} {'год' if y==1 else 'года' if y<5 else 'лет'}")
        if m: parts.append(f"{m} {'месяц' if m==1 else 'месяца' if m<5 else 'месяцев'}")
        if d: parts.append(f"{d} {'день' if d==1 else 'дня' if d<5 else 'дней'}")
        if h: parts.append(f"{h} {'час' if h==1 else 'часа' if h<5 else 'часов'}")
        if mn: parts.append(f"{mn} {'минуту' if mn==1 else 'минуты' if mn<5 else 'минут'}")
        return "только что" if not parts else ", ".join(parts[:2]) + (f" и {parts[2]}" if len(parts)>2 else "")
    except:
        return "неизвестно"


def format_child_age(birthday_str):
    try:
        if not birthday_str:
            return "неизвестно"
        birthday = datetime.fromisoformat(birthday_str)
        now = datetime.now()
        delta = now - birthday
        total_seconds = delta.total_seconds()
        if total_seconds < 0:
            return "0 минут"
        if total_seconds < 60:
            return "менее минуты"
        total_minutes = total_seconds // 60
        if total_minutes < 60:
            return f"{int(total_minutes)} {'минуту' if total_minutes == 1 else 'минуты' if total_minutes < 5 else 'минут'}"
        total_hours = total_minutes // 60
        if total_hours < 24:
            minutes_remain = total_minutes % 60
            if minutes_remain == 0:
                return f"{int(total_hours)} {'час' if total_hours == 1 else 'часа' if total_hours < 5 else 'часов'}"
            return f"{int(total_hours)} {'час' if total_hours == 1 else 'часа' if total_hours < 5 else 'часов'} {int(minutes_remain)} {'минуту' if minutes_remain == 1 else 'минуты' if minutes_remain < 5 else 'минут'}"
        total_days = total_hours // 24
        if total_days < 30:
            hours_remain = total_hours % 24
            if hours_remain == 0:
                return f"{int(total_days)} {'день' if total_days == 1 else 'дня' if total_days < 5 else 'дней'}"
            return f"{int(total_days)} {'день' if total_days == 1 else 'дня' if total_days < 5 else 'дней'} {int(hours_remain)} {'час' if hours_remain == 1 else 'часа' if hours_remain < 5 else 'часов'}"
        total_months = total_days / 30.44
        if total_months < 12:
            months_int = int(total_months)
            days_remain = int((total_months - months_int) * 30.44)
            if days_remain == 0:
                return f"{months_int} {'месяц' if months_int == 1 else 'месяца' if months_int < 5 else 'месяцев'}"
            return f"{months_int} {'месяц' if months_int == 1 else 'месяца' if months_int < 5 else 'месяцев'} {days_remain} {'день' if days_remain == 1 else 'дня' if days_remain < 5 else 'дней'}"
        total_years = total_months // 12
        months_remain = int(total_months % 12)
        if months_remain == 0:
            return f"{int(total_years)} {'год' if total_years == 1 else 'года' if total_years < 5 else 'лет'}"
        return f"{int(total_years)} {'год' if total_years == 1 else 'года' if total_years < 5 else 'лет'} {months_remain} {'месяц' if months_remain == 1 else 'месяца' if months_remain < 5 else 'месяцев'}"
    except Exception as e:
        print(f"Ошибка format_child_age: {e}")
        return "неизвестно"


def get_user_id_by_screen_name(screen_name):
    try:
        response = requests.get(f"https://api.vk.com/method/users.get?user_ids={screen_name}&v=5.131")
        data = response.json()
        if 'response' in data and data['response']:
            return data['response'][0]['id']
        return None
    except:
        return None


def extract_id(text):
    if not text or not isinstance(text, str):
        return None
    patterns = [
        r'\[id(\d+)\|.*?\]',
        r'\[club(\d+)\|.*?\]',
        r'@id(\d+)',
        r'id(\d+)',
        r'vk\.com/([a-zA-Z0-9_\.]+)',
        r'm\.vk\.com/([a-zA-Z0-9_\.]+)',
        r'vk\.me/([a-zA-Z0-9_\.]+)',
        r'@([a-zA-Z0-9_\.]+)',
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            try:
                if pattern.startswith(r'vk\.com') or pattern.startswith(r'm\.vk\.com') or pattern.startswith(r'vk\.me') or pattern.startswith(r'@'):
                    screen = m.group(1)
                    if screen not in ['id', 'club', 'public']:
                        return get_user_id_by_screen_name(screen)
                else:
                    return int(m.group(1))
            except:
                pass
    return None


def remove_emoji(text):
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F700-\U0001F77F"
        u"\U0001F780-\U0001F7FF"
        u"\U0001F800-\U0001F8FF"
        u"\U0001F900-\U0001F9FF"
        u"\U0001FA00-\U0001FA6F"
        u"\U0001FA70-\U0001FAFF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)