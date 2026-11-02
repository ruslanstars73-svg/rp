import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import random
import re
import json
import os
import time
import sys
import requests
import urllib3
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import lyricsgenius

from config import (
    BOT_TOKEN, USER_TOKEN, GROUP_ID,
    RP_FILE, STATS_FILE, MARRIAGE_FILE, CHILDREN_FILE,
    PREGNANCY_FILE, CHAT_STATS_FILE, MUTED_FILE,
    CHILD_PHOTO_MALE, CHILD_PHOTO_FEMALE,
    GIGACHAT_AUTH_KEY, GIGACHAT_CLIENT_ID,
    GENIUS_TOKEN, MOODS, DEFAULT_RP,
)
from database import load_json, save_json
from utils import (
    fmt_time, extract_id, remove_emoji,
    get_user_id_by_screen_name, format_child_age, session,
)
from keyboards import KeyboardMixin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ====== AI (было modules/ai.py) ======
ai_contexts = {}
gigachat_token = None

def get_gigachat_token():
    global gigachat_token
    try:
        r = session.post(
            "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'RqUID': GIGACHAT_CLIENT_ID,
                'Authorization': f'Basic {GIGACHAT_AUTH_KEY}'
            },
            data="scope=GIGACHAT_API_PERS",
            timeout=30, verify=False
        )
        if r.status_code == 200:
            gigachat_token = r.json().get('access_token')
            return gigachat_token
    except Exception:
        pass
    return None

def get_ai(user_id, prompt):
    try:
        ai_contexts.setdefault(user_id, []).append({"role": "user", "content": prompt})
        token = get_gigachat_token()
        if not token:
            return "❌ Ошибка токена"
        r = session.post(
            "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json={"model": "GigaChat:latest", "messages": ai_contexts[user_id][-10:], "temperature": 0.7, "max_tokens": 500},
            timeout=45, verify=False
        )
        if r.status_code == 200:
            ans = r.json()['choices'][0]['message']['content']
            if ans:
                ai_contexts[user_id].append({"role": "assistant", "content": ans})
                return ans
    except Exception as e:
        print(f"❌ Ошибка GigaChat: {e}")
    return "❌ Ошибка GigaChat"


class VKBot(KeyboardMixin):

    def __init__(self):
        self.vk = self.vk_user = self.longpoll = None
        self.custom_rp = load_json(RP_FILE)
        self.stats = load_json(STATS_FILE)
        self.marriages = load_json(MARRIAGE_FILE)
        self.children = load_json(CHILDREN_FILE)
        self.pregnancies = load_json(PREGNANCY_FILE)
        self.chat_stats = load_json(CHAT_STATS_FILE)
        self.muted = load_json(MUTED_FILE)
        self.history = {}
        self.mutual = {}
        self.favorites_rp = {}
        self.dice_games = {}
        self.tic_tac_toe_games = {}
        self.cache = {}
        self.keyboard_enabled = {}
        self.cooldowns = {}
        self.music_cooldowns = {}
        self.child_counter = len(self.children)
        self.temp_names = {}
        self.status_messages = {}
        self.GROUP_ID = GROUP_ID

        for uid in self.chat_stats:
            for key in ["text","sticker","voice","video","photo","doc","other","total"]:
                if key not in self.chat_stats[uid]:
                    self.chat_stats[uid][key] = 0
        save_json(CHAT_STATS_FILE, self.chat_stats)

        if self.children:
            for child_id in list(self.children.keys()):
                self.update_child_stats(child_id)
            print(f"👶 Восстановлены статусы {len(self.children)} детей")
        print(f"📊 Загружено браков: {len(self.marriages)}")
        print(f"🤰 Загружено беременностей: {len(self.pregnancies)}")

    def save_all(self):
        save_json(MARRIAGE_FILE, self.marriages)
        save_json(CHILDREN_FILE, self.children)
        save_json(PREGNANCY_FILE, self.pregnancies)
        save_json(STATS_FILE, self.stats)
        save_json(RP_FILE, self.custom_rp)
        save_json(CHAT_STATS_FILE, self.chat_stats)
        save_json(MUTED_FILE, self.muted)

    def init(self):
        try:
            self.vk = vk_api.VkApi(token=BOT_TOKEN)
            self.longpoll = VkBotLongPoll(self.vk, GROUP_ID)
            if USER_TOKEN and USER_TOKEN != "ВАШ_ПОЛЬЗОВАТЕЛЬСКИЙ_ТОКЕН":
                self.vk_user = vk_api.VkApi(token=USER_TOKEN)
                try:
                    self.vk_user.method("users.get", {"user_ids": 1})
                except:
                    print("⚠️ Пользовательский токен не работает, музыка недоступна.")
                    self.vk_user = None
            print("✅ Бот запущен!")
            return True
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False

    # ====== ХЕЛПЕРЫ ======
    def user_name(self, uid):
        try:
            if uid not in self.cache:
                u = self.vk.method('users.get', {'user_ids': uid})
                self.cache[uid] = f"{u[0]['first_name']} {u[0]['last_name']}" if u else f"ID{uid}"
            return self.cache[uid]
        except:
            return f"ID{uid}"

    def user_link(self, uid):
        return f"[id{uid}|{self.user_name(uid)}]"

    def clean_text(self, text):
        return re.sub(r'\[club\d+\|.*?\]', '', text).strip()

    def get_target_user(self, msg, raw_text):
        target = extract_id(raw_text)
        if target:
            return target
        if msg.get('reply_message'):
            return msg['reply_message'].get('from_id')
        numbers = re.findall(r'\b\d{5,}\b', raw_text)
        return int(numbers[0]) if numbers else None

    def get_user_id_info(self, user_id, target_id=None):
        if target_id:
            return f"👤 ID пользователя {self.user_name(target_id)}: #{target_id}"
        return f"👤 Ваш ID: #{user_id}"

    def send(self, peer, text, keyboard=None):
        try:
            if keyboard is None and self.keyboard_enabled.get(peer, True):
                keyboard = self.get_main_keyboard()
            elif keyboard is None:
                keyboard = self.get_empty_keyboard()
            params = {'peer_id': peer, 'message': text, 'random_id': random.randint(1, 10**9)}
            if keyboard:
                params['keyboard'] = keyboard
            self.vk.method('messages.send', params)
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")

    def send_photo(self, peer, text, photo):
        try:
            self.vk.method('messages.send', {
                'peer_id': peer, 'message': text,
                'attachment': f"photo-{GROUP_ID}_{photo}",
                'random_id': random.randint(1, 10**9)
            })
        except:
            self.send(peer, text)

    def cd(self, uid, cmd, sec=86400):
        k = f"{uid}_{cmd}"
        now = time.time()
        if k in self.cooldowns and now - self.cooldowns[k] < sec:
            r = int(sec - (now - self.cooldowns[k]))
            return False, f"⏳ Подожди {r//3600}ч {(r%3600)//60}мин"
        self.cooldowns[k] = now
        return True, "✅"

    # ====== ДЕТИ ======
    def update_child_stats(self, child_id):
        try:
            if child_id not in self.children:
                return False
            data = self.children[child_id]
            last = datetime.fromisoformat(data["last_update"])
            now = datetime.now()
            diff = (now - last).total_seconds() // 3600
            if diff > 0:
                dec = int(diff) * 3
                data["hunger"] = max(0, data["hunger"] - dec)
                data["sleep"] = max(0, data["sleep"] - dec)
                data["mood"] = max(0, data["mood"] - dec)
                data["health"] = max(0, data["health"] - dec)
                data["last_update"] = now.isoformat()
                self.children[child_id] = data
                self.save_all()
                return True
            return False
        except:
            return False

    def update_all_children(self):
        try:
            if not self.children:
                return 0
            updated = 0
            for child_id in list(self.children.keys()):
                if self.update_child_stats(child_id):
                    updated += 1
            if updated > 0:
                self.save_all()
            return updated
        except:
            return 0

    def get_child(self, user_id, partner_id=None):
        try:
            if partner_id:
                for child_id, data in self.children.items():
                    if (data["parent1"] == user_id and data["parent2"] == partner_id) or \
                       (data["parent1"] == partner_id and data["parent2"] == user_id):
                        return child_id, data
                return None, None
            for child_id, data in self.children.items():
                if data["parent1"] == user_id or data["parent2"] == user_id:
                    return child_id, data
            return None, None
        except:
            return None, None

    def get_children_in_marriage(self, user_id, partner_id):
        result = []
        for child_id, data in self.children.items():
            if (data["parent1"] == user_id and data["parent2"] == partner_id) or \
               (data["parent1"] == partner_id and data["parent2"] == user_id):
                result.append(data)
        return result

    def feed_child(self, user_id):
        try:
            child_id, data = self.get_child(user_id)
            if not data:
                return "У вас нет ребенка!"
            self.update_child_stats(child_id)
            if data["hunger"] >= 100:
                return f"{data['name']} уже сыт!"
            data["hunger"] = min(100, data["hunger"] + 30)
            data["mood"] = min(100, data["mood"] + 5)
            self.children[child_id] = data
            self.save_all()
            return f"🍼 {data['name']} покормлен! Голод: {data['hunger']}%"
        except Exception as e:
            return f"❌ Ошибка: {e}"

    def play_with_child(self, user_id):
        try:
            child_id, data = self.get_child(user_id)
            if not data:
                return "У вас нет ребенка!"
            self.update_child_stats(child_id)
            if data["mood"] >= 100:
                return f"{data['name']} уже весел!"
            data["mood"] = min(100, data["mood"] + 25)
            data["sleep"] = max(0, data["sleep"] - 10)
            self.children[child_id] = data
            self.save_all()
            return f"🎮 {data['name']} поиграл! Настроение: {data['mood']}%"
        except Exception as e:
            return f"❌ Ошибка: {e}"

    def sleep_child(self, user_id):
        try:
            child_id, data = self.get_child(user_id)
            if not data:
                return "У вас нет ребенка!"
            self.update_child_stats(child_id)
            if data["sleep"] >= 100:
                return f"{data['name']} уже выспался!"
            data["sleep"] = min(100, data["sleep"] + 30)
            data["mood"] = min(100, data["mood"] + 5)
            self.children[child_id] = data
            self.save_all()
            return f"😴 {data['name']} уложен спать! Сон: {data['sleep']}%"
        except Exception as e:
            return f"❌ Ошибка: {e}"

    def treat_child(self, user_id):
        try:
            child_id, data = self.get_child(user_id)
            if not data:
                return "У вас нет ребенка!"
            self.update_child_stats(child_id)
            if data["health"] >= 100:
                return f"{data['name']} уже здоров!"
            data["health"] = min(100, data["health"] + 30)
            data["mood"] = max(0, data["mood"] - 10)
            data["sleep"] = max(0, data["sleep"] - 10)
            self.children[child_id] = data
            self.save_all()
            return f"💊 {data['name']} вылечен! Здоровье: {data['health']}%"
        except Exception as e:
            return f"❌ Ошибка: {e}"

    def get_child_status(self, user_id):
        try:
            child_id, data = self.get_child(user_id)
            if not data:
                return None, None
            self.update_child_stats(child_id)
            gender = "👦" if data.get("gender", "male") == "male" else "👧"
            p1 = self.user_link(data["parent1"])
            p2 = self.user_link(data["parent2"])
            age = format_child_age(data.get('birthday', ''))
            status = f"👶 {data['name']} {gender} | {age}\n"
            status += f"👨‍👩‍👦 Родители: {p1} и {p2}\n"
            status += f"🍼 Голод: {data['hunger']}% | 😴 Сон: {data['sleep']}% | 😊 Настроение: {data['mood']}%\n"
            status += f"❤️ Здоровье: {data['health']}%\n\n"
            if data["health"] < 30:
                status += "⚠️ Ребенок болен!"
            elif data["hunger"] < 20:
                status += "🍽️ Ребенок голоден! Покормите!"
            elif data["sleep"] < 20:
                status += "😴 Ребенок хочет спать!"
            elif data["mood"] < 20:
                status += "😢 Ребенок грустный! Поиграйте!"
            else:
                status += "😊 Ребенок счастлив!"
            return status, child_id
        except:
            return "❌ Ошибка получения статуса", None

    def get_children_list(self):
        try:
            if not self.children:
                return "Детей нет"
            result = "👶 Список детей:\n\n"
            for child_id, data in self.children.items():
                p1 = self.user_link(data["parent1"])
                p2 = self.user_link(data["parent2"])
                gender = "👦" if data.get("gender", "male") == "male" else "👧"
                age = format_child_age(data.get('birthday', ''))
                result += f"{gender} {data['name']} ({p1} и {p2}) — {age}\n"
            return result
        except:
            return "❌ Ошибка получения списка"

    def send_child_status(self, user_id, peer_id, edit=False, conv_msg_id=None):
        status, child_id = self.get_child_status(user_id)
        if not status:
            self.send(peer_id, "❌ У вас нет ребенка!")
            return
        keyboard = self.get_child_status_keyboard(user_id)
        attachment = None
        if child_id:
            data = self.children.get(child_id, {})
            gender = data.get('gender', 'male')
            if gender == 'male' and CHILD_PHOTO_MALE:
                attachment = CHILD_PHOTO_MALE
            elif gender == 'female' and CHILD_PHOTO_FEMALE:
                attachment = CHILD_PHOTO_FEMALE
        if edit:
            if not conv_msg_id and user_id in self.status_messages:
                saved = self.status_messages[user_id]
                conv_msg_id = saved.get("conv_msg_id")
                peer_id = saved.get("peer_id", peer_id)
                if not attachment:
                    attachment = saved.get("attachment")
            if conv_msg_id:
                try:
                    params = {'peer_id': peer_id, 'message': status,
                              'conversation_message_id': conv_msg_id, 'keyboard': keyboard}
                    if attachment:
                        params['attachment'] = attachment
                    self.vk.method('messages.edit', params)
                    self.status_messages[user_id] = {"peer_id": peer_id, "conv_msg_id": conv_msg_id, "attachment": attachment}
                    return
                except Exception as e:
                    print(f"❌ Ошибка редактирования статуса: {e}")
                    edit = False
        try:
            params = {'peer_id': peer_id, 'message': status, 'keyboard': keyboard,
                      'random_id': random.randint(1, 10**9)}
            if attachment:
                params['attachment'] = attachment
            result = self.vk.method('messages.send', params)
            if isinstance(result, dict):
                conv_id = result.get('conversation_message_id')
                if conv_id:
                    self.status_messages[user_id] = {"peer_id": peer_id, "conv_msg_id": conv_id, "attachment": attachment}
        except Exception as e:
            print(f"❌ Ошибка отправки статуса: {e}")
            self.send(peer_id, status, keyboard=keyboard)

    def get_family_help(self):
        return """👶 Семья и дети

забеременеть от @юз — начать беременность
ребенок имя — дать имя ребенку
ребенок пол мальчик/девочка — выбрать пол
статус — состояние ребенка (с кнопками)
дети — список детей
обновить детей — обновить статусы всех детей
помощь семья — помощь по семье"""

    # ====== БРАКИ ======
    def marriage_add(self, u1, u2, date=None):
        try:
            u1s, u2s = str(u1), str(u2)
            if u1s in self.marriages or u2s in self.marriages:
                return False, "❌ Кто-то уже в браке"
            ts = date.isoformat() if date else datetime.now().isoformat()
            self.marriages[u1s] = {"partner": u2, "since": ts}
            self.marriages[u2s] = {"partner": u1, "since": ts}
            self.save_all()
            return True, "✅"
        except Exception as e:
            return False, f"❌ Ошибка: {e}"

    def marriage_remove(self, uid):
        try:
            u = str(uid)
            if u not in self.marriages:
                return False, "❌ Не в браке"
            p = self.marriages[u]["partner"]
            del self.marriages[u], self.marriages[str(p)]
            self.save_all()
            return True, "✅"
        except Exception as e:
            return False, f"❌ Ошибка: {e}"

    def marriage_status(self, uid):
        try:
            u = str(uid)
            if u not in self.marriages:
                return None
            d = self.marriages[u]
            partner = d["partner"]
            children = self.get_children_in_marriage(uid, partner)
            status = f"💕 В браке с {self.user_link(partner)} уже {fmt_time(d['since'])}"
            if children:
                status += "\n\n👶 Дети в браке:"
                for child in children:
                    gender = "👦" if child.get("gender", "male") == "male" else "👧"
                    age = format_child_age(child['birthday'])
                    status += f"\n{gender} {child['name']} ({age})"
            return status
        except:
            return "❌ Ошибка получения статуса"

    # ====== БЕРЕМЕННОСТЬ ======
    def confirm_pregnancy(self, partner_id, user_id, action):
        try:
            if user_id not in self.pregnancies:
                return False, "Нет активной беременности"
            preg = self.pregnancies[user_id]
            if preg["partner"] != partner_id:
                return False, "Не та пара"
            if action == "no":
                del self.pregnancies[user_id]
                self.save_all()
                return False, "Отказ"
            preg["status"] = "pending"
            self.pregnancies[user_id] = preg
            self.save_all()
            return True, "ok"
        except Exception as e:
            return False, f"Ошибка: {e}"

    def create_child_from_pregnancy(self, user_id, name, gender):
        try:
            if user_id not in self.pregnancies:
                return False, "Нет беременности"
            preg = self.pregnancies[user_id]
            if preg["status"] != "pending":
                return False, "Статус не pending"
            partner = preg["partner"]
            self.child_counter += 1
            child_id = f"child_{self.child_counter}"
            now = datetime.now().isoformat()
            self.children[child_id] = {
                "name": name, "gender": gender,
                "parent1": user_id, "parent2": partner,
                "birthday": now,
                "hunger": 70, "sleep": 70, "mood": 70, "health": 90,
                "last_update": now
            }
            del self.pregnancies[user_id]
            self.save_all()
            self.update_all_children()
            return True, f"Ребенок {name} родился! 🎉"
        except Exception as e:
            return False, f"Ошибка: {e}"

    # ====== RP ======
    def rp_do(self, peer, uid, name, data, targets):
        try:
            t = targets[0]
            text = f"💫 {self.user_link(uid)} {data['description']} {self.user_link(t)}" if t != uid else f"😄 {self.user_link(uid)} {data['description']} сам(а) себя"
            photo = data.get('vk_photo_id') or data.get('photo', '')
            self.send_photo(peer, text, photo)
            self.stats[name] = self.stats.get(name, 0) + 1
            self.save_all()
        except Exception as e:
            print(f"❌ Ошибка RP: {e}")
            self.send(peer, "⚠️ Ошибка выполнения RP")

    def rp_all(self):
        all_rp = DEFAULT_RP.copy()
        all_rp.update(self.custom_rp)
        return all_rp

    def rp_top(self):
        all_actions = {}
        for u, acts in self.favorites_rp.items():
            for act, cnt in acts.items():
                all_actions[act] = all_actions.get(act, 0) + cnt
        return all_actions

    # ====== ИГРЫ ======
    def start_dice_game(self, peer_id, user_id, target_id):
        try:
            if peer_id in self.dice_games and self.dice_games[peer_id].get("active", False):
                return "❌ В этом чате уже идет игра в кости!"
            if target_id == user_id:
                return "❌ Нельзя играть с самим собой!"
            self.dice_games[peer_id] = {
                "player1": user_id, "player2": target_id, "turn": user_id,
                "move1": None, "move2": None, "active": True
            }
            text = f"🎲 Игра: Кости\n\n👤 {self.user_link(user_id)} vs {self.user_link(target_id)}\n\n🟢 Ход: {self.user_link(user_id)}"
            self.vk.method('messages.send', {
                'peer_id': peer_id, 'message': text,
                'keyboard': self.get_dice_keyboard(),
                'random_id': random.randint(1, 10**9)
            })
            return "✅ Игра начата!"
        except Exception as e:
            return f"❌ Ошибка: {e}"

    def handle_dice_turn(self, peer_id, user_id):
        try:
            if peer_id not in self.dice_games or not self.dice_games[peer_id].get("active", False):
                return "❌ Игра уже завершена!"
            game = self.dice_games[peer_id]
            if user_id not in (game["player1"], game["player2"]):
                return "❌ Вы не участвуете в этой игре!"
            if game["turn"] != user_id:
                return f"❌ Не ваш ход! Сейчас ходит {self.user_link(game['turn'])}"
            dice1 = random.randint(1, 6); dice2 = random.randint(1, 6)
            total = dice1 + dice2
            emojis = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
            result = f"🎲 {self.user_link(user_id)} бросил кости!\n{emojis[dice1-1]} + {emojis[dice2-1]} = **{total}**"
            if user_id == game["player1"]:
                game["move1"] = total
            else:
                game["move2"] = total
            self.dice_games[peer_id] = game
            if game["move1"] is not None and game["move2"] is not None:
                return result + "\n\n" + self.finish_dice_game(peer_id)
            next_player = game["player2"] if user_id == game["player1"] else game["player1"]
            game["turn"] = next_player
            self.dice_games[peer_id] = game
            text = f"🎲 Игра: Кости\n\n👤 {self.user_link(game['player1'])} vs {self.user_link(game['player2'])}\n\n🟢 Ход: {self.user_link(next_player)}"
            self.vk.method('messages.send', {
                'peer_id': peer_id, 'message': text,
                'keyboard': self.get_dice_keyboard(),
                'random_id': random.randint(1, 10**9)
            })
            return result + f"\n\n🟢 Теперь ход: {self.user_link(next_player)}"
        except Exception as e:
            return f"❌ Ошибка: {e}"

    def finish_dice_game(self, peer_id):
        try:
            game = self.dice_games[peer_id]
            u1, u2 = game["player1"], game["player2"]
            m1, m2 = game["move1"], game["move2"]
            if m1 == m2:
                emoji, rt = "🤝", "Ничья!"
            elif m1 > m2:
                emoji, rt = "🎉", f"Победил: {self.user_link(u1)}!"
            else:
                emoji, rt = "🎉", f"Победил: {self.user_link(u2)}!"
            text = f"🎲 Игра: Кости (ЗАВЕРШЕНА)\n\n👤 {self.user_link(u1)} vs {self.user_link(u2)}\n\n⚀ {self.user_link(u1)}: {m1}\n⚁ {self.user_link(u2)}: {m2}\n\n{emoji} {rt}"
            game["active"] = False
            self.dice_games[peer_id] = game
            self.vk.method('messages.send', {
                'peer_id': peer_id, 'message': text,
                'keyboard': json.dumps({"buttons": []}, ensure_ascii=False),
                'random_id': random.randint(1, 10**9)
            })
            time.sleep(3)
            if peer_id in self.dice_games:
                del self.dice_games[peer_id]
            return text
        except:
            return "❌ Ошибка завершения игры"

    def start_ttt_game(self, peer_id, user1, user2):
        try:
            if user1 == user2:
                return "❌ Нельзя играть с самим собой!"
            if peer_id in self.tic_tac_toe_games:
                return "❌ В этом чате уже идет игра! Дождись окончания."
            game_id = f"ttt_{peer_id}_{int(time.time())}"
            board = [""] * 9
            self.tic_tac_toe_games[peer_id] = {
                "game_id": game_id, "board": board, "players": [user1, user2],
                "turn": user1, "active": True, "winner": None, "message_ids": []
            }
            text = f"🎮 Крестики-нолики!\n\n❌ {self.user_link(user1)} (X) vs ⭕ {self.user_link(user2)} (O)\n🟢 Ход: {self.user_link(user1)} (X)"
            result = self.vk.method('messages.send', {
                'peer_id': peer_id, 'message': text,
                'keyboard': self.get_ttt_keyboard(board, game_id),
                'random_id': random.randint(1, 10**9)
            })
            msg_id = result.get('message_id') if isinstance(result, dict) else result
            self.tic_tac_toe_games[peer_id]["message_ids"].append(msg_id)
            return "✅ Игра начата!"
        except Exception as e:
            return f"❌ Ошибка: {e}"

    def handle_ttt_move(self, peer_id, user_id, pos, game_id):
        try:
            if peer_id not in self.tic_tac_toe_games:
                return
            game = self.tic_tac_toe_games[peer_id]
            if not game.get("active", False) or game["turn"] != user_id or game["board"][pos] != "":
                return
            player1 = game["players"][0]
            symbol = "X" if user_id == player1 else "O"
            game["board"][pos] = symbol
            winner = self.check_ttt_winner(game["board"])
            if winner:
                game["active"] = False
                game["winner"] = winner
                winner_id = player1 if winner == "X" else game["players"][1]
                text = f"🎮 Крестики-нолики! 🏆\n\n❌ {self.user_link(game['players'][0])} (X) vs ⭕ {self.user_link(game['players'][1])} (O)\n🎉 Победил: {self.user_link(winner_id)}!"
                self.vk.method('messages.send', {'peer_id': peer_id, 'message': text, 'random_id': random.randint(1, 10**9)})
                for msg_id in game.get("message_ids", []):
                    try:
                        self.vk.method('messages.delete', {'peer_id': peer_id, 'message_ids': [msg_id], 'delete_for_all': 1})
                    except: pass
                time.sleep(5)
                if peer_id in self.tic_tac_toe_games:
                    del self.tic_tac_toe_games[peer_id]
                return
            if all(cell != "" for cell in game["board"]):
                game["active"] = False
                text = f"🎮 Крестики-нолики! 🤝\n\n❌ {self.user_link(game['players'][0])} (X) vs ⭕ {self.user_link(game['players'][1])} (O)\n🤝 Ничья!"
                self.vk.method('messages.send', {'peer_id': peer_id, 'message': text, 'random_id': random.randint(1, 10**9)})
                for msg_id in game.get("message_ids", []):
                    try:
                        self.vk.method('messages.delete', {'peer_id': peer_id, 'message_ids': [msg_id], 'delete_for_all': 1})
                    except: pass
                time.sleep(5)
                if peer_id in self.tic_tac_toe_games:
                    del self.tic_tac_toe_games[peer_id]
                return
            next_player = game["players"][1] if user_id == game["players"][0] else game["players"][0]
            game["turn"] = next_player
            self.tic_tac_toe_games[peer_id] = game
            text = f"🎮 Крестики-нолики!\n\n❌ {self.user_link(game['players'][0])} (X) vs ⭕ {self.user_link(game['players'][1])} (O)\n🟢 Ход: {self.user_link(next_player)} ({'X' if next_player == game['players'][0] else 'O'})"
            old_ids = game.get("message_ids", [])
            if old_ids:
                last_id = old_ids[-1]
                try:
                    self.vk.method('messages.delete', {'peer_id': peer_id, 'message_ids': [last_id], 'delete_for_all': 1})
                except: pass
                game["message_ids"] = old_ids[:-1]
            result = self.vk.method('messages.send', {
                'peer_id': peer_id, 'message': text,
                'keyboard': self.get_ttt_keyboard(game["board"], game.get("game_id")),
                'random_id': random.randint(1, 10**9)
            })
            new_msg_id = result.get('message_id') if isinstance(result, dict) else result
            game["message_ids"].append(new_msg_id)
            self.tic_tac_toe_games[peer_id] = game
        except Exception as e:
            print(f"❌ Ошибка TTT: {e}")

    def check_ttt_winner(self, board):
        wins = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]]
        for c in wins:
            if board[c[0]] and board[c[0]] == board[c[1]] == board[c[2]]:
                return board[c[0]]
        return None

    # ====== МУЗЫКА ======
    def music_search(self, uid, q=None, mood=None):
        if not self.vk_user:
            return None, "❌ Музыка недоступна"
        try:
            if q:
                search_query = q
                if mood and mood in MOODS:
                    search_query += f" {MOODS[mood]}"
                r = self.vk_user.method("audio.search", {"q": search_query, "count": 50, "sort": 2, "auto_complete": 0})
                if not r or not r.get('items'):
                    return None, "❌ Не найдено"
                q_lower = q.lower()
                filtered = []
                for track in r['items']:
                    title = track.get('title', '').lower()
                    artist = track.get('artist', '').lower()
                    if q_lower == artist: filtered.insert(0, track)
                    elif q_lower == title: filtered.insert(0, track)
                    elif q_lower in artist or q_lower in title: filtered.append(track)
                if not filtered:
                    filtered = r['items'][:5]
                random.shuffle(filtered)
                return filtered[:3], None
            else:
                t = self.vk_user.method("audio.get", {"owner_id": uid, "count": 200})
                if not t or not t.get('items'):
                    return None, "❌ Нет твоих треков"
                tr = random.choice(t['items'])
                r = self.vk_user.method("audio.getRecommendations", {
                    "target_audio": f"{tr['owner_id']}_{tr['id']}", "count": 20, "shuffle": 1
                })
                if not r or not r.get('items'):
                    return None, "❌ Не найдено"
                random.shuffle(r['items'])
                return r['items'][:3], None
        except Exception as e:
            return None, f"❌ Ошибка музыки: {e}"

    def send_music(self, peer, uid, q=None, mood=None, edit_conv_msg_id=None, owner_id=None):
        if owner_id is None:
            owner_id = uid
        tracks, err = self.music_search(uid, q, mood)
        keyboard = self.get_music_keyboard(owner_id)
        if err:
            self.send(peer, err)
            return
        if not tracks:
            self.send(peer, "❌ Нет треков")
            return
        att = ','.join([f"audio{t['owner_id']}_{t['id']}" for t in tracks])
        msg = f"{self.user_link(uid)}, ваши результаты{f' по запросу «{q}»' if q else ''}:"
        try:
            if edit_conv_msg_id:
                self.vk.method('messages.edit', {
                    'peer_id': peer, 'message': msg, 'attachment': att,
                    'keyboard': keyboard, 'conversation_message_id': edit_conv_msg_id
                })
            else:
                self.vk.method('messages.send', {
                    'peer_id': peer, 'message': msg, 'attachment': att,
                    'keyboard': keyboard, 'random_id': random.randint(1, 10**9)
                })
        except Exception as e:
            print(f"⚠️ Ошибка отправки музыки: {e}")

    def lyrics(self, artist, title):
        try:
            s = lyricsgenius.Genius(GENIUS_TOKEN)
            s.verbose = False
            song = s.search_song(title, artist)
            if song:
                lyrics = re.sub(r'\[.*?\]', '', song.lyrics).strip()
                return f"🎵 {song.title} — {song.artist}\n\n{lyrics}", None
            return None, f"❌ Не найдено: {artist} — {title}"
        except Exception as e:
            return None, f"❌ Ошибка: {e}"

    # ====== СТАТИСТИКА ======
    def get_user_stats(self, user_id):
        stats = self.chat_stats.get(str(user_id), {})
        return {k: stats.get(k, 0) for k in
                ["text","sticker","voice","video","photo","doc","other","total"]}

    def get_top_by_type(self, stat_type, limit=10):
        return sorted(self.chat_stats.items(), key=lambda x: x[1].get(stat_type, 0), reverse=True)[:limit]

    def format_top(self, sorted_items, stat_type, label):
        if not sorted_items:
            return f"📭 Нет данных по {label}"
        medals = ['1.','2.','3.','4.','5.','6.','7.','8.','9.','10.']
        result = f"🏆 Топ по {label}:\n\n"
        for i, (uid, data) in enumerate(sorted_items):
            medal = medals[i] if i < len(medals) else f"{i+1}."
            result += f"{medal} {self.user_link(int(uid))} — {data.get(stat_type, 0)} сообщений\n"
        return result

    # ====== МУТ ======
    def mute_user(self, peer_id, user_id):
        try:
            self.vk.method('messages.muteChat', {'peer_id': peer_id, 'user_id': user_id})
            key = str(peer_id)
            self.muted.setdefault(key, [])
            if user_id not in self.muted[key]:
                self.muted[key].append(user_id)
                self.save_all()
            return True, None
        except Exception as e:
            return False, str(e)

    def unmute_user(self, peer_id, user_id):
        try:
            self.vk.method('messages.unmuteChat', {'peer_id': peer_id, 'user_id': user_id})
            key = str(peer_id)
            if key in self.muted and user_id in self.muted[key]:
                self.muted[key].remove(user_id)
                if not self.muted[key]:
                    del self.muted[key]
                self.save_all()
            return True, None
        except Exception as e:
            return False, str(e)

    def get_muted_list(self, peer_id):
        return self.muted.get(str(peer_id), [])

    # ====== СЕРТИФИКАТ ======
    def generate_certificate(self, recipient_id, recipient_name, issuer_name):
        width, height = 800, 600
        img = Image.new('RGB', (width, height), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        for _ in range(6000):
            x, y = random.randint(0, width), random.randint(0, height)
            c = random.randint(20, 50)
            draw.point((x, y), fill=(c, c, c))
        for _ in range(15):
            x, y = random.randint(0, width), random.randint(0, height)
            r = random.randint(40, 130)
            draw.ellipse((x-r, y-r, x+r, y+r), outline=(80, 70, 40), width=2)
        for i in range(-height, width+height, 20):
            draw.line((i, 0, i+height, height), fill=(40, 40, 40), width=1)
            draw.line((i, height, i+height, 0), fill=(40, 40, 40), width=1)
        border = 30
        draw.rectangle([border, border, width-border, height-border], outline=(200, 170, 80), width=4)
        draw.rectangle([border+12, border+12, width-border-12, height-border-12], outline=(200, 170, 80), width=2)
        def corner(x, y, size=50):
            for r in range(size, 0, -10):
                draw.arc((x-r, y-r, x+r, y+r), 0, 90, fill=(200, 170, 80), width=2)
            draw.line((x, y, x+size, y), fill=(200, 170, 80), width=2)
            draw.line((x, y, x, y+size), fill=(200, 170, 80), width=2)
        corner(border+5, border+5, 55)
        corner(width-border-5, border+5, 55)
        corner(border+5, height-border-5, 55)
        corner(width-border-5, height-border-5, 55)
        for (x, y) in [(border+15, border+15), (border+15, height//2), (border+15, height-border-15),
                       (width-border-15, border+15), (width-border-15, height//2), (width-border-15, height-border-15),
                       (width//2, border+15), (width//2, height-border-15)]:
            draw.ellipse((x-5, y-5, x+5, y+5), fill=(200, 170, 80))
            draw.ellipse((x-3, y-3, x+3, y+3), fill=(255, 220, 140))
        def get_font(size):
            for p in ["DejaVuSans.ttf", "arial.ttf",
                      "/system/fonts/Roboto-Regular.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
                try: return ImageFont.truetype(p, size)
                except: continue
            return ImageFont.load_default()
        font_title = get_font(48); font_name = get_font(38); font_diagnosis = get_font(40)
        font_footer = get_font(28); font_date = get_font(26); font_small = get_font(20)
        def glow(text, x, y, font, color, glow_color=None, glow_size=2):
            if glow_color is None: glow_color = color
            for i in range(glow_size, 0, -1):
                alpha = int(30 * (1 - i/glow_size))
                for dx, dy in [(-i,-i),(i,-i),(-i,i),(i,i)]:
                    draw.text((x+dx, y+dy), text, font=font, fill=(*glow_color, alpha))
            draw.text((x, y), text, font=font, fill=color)
        title = "СЕРТИФИКАТ ВРУЧЕН"
        tw = draw.textlength(title, font=font_title)
        tx, ty = (width - tw) // 2, 40
        glow(title, tx, ty, font_title, (220, 180, 60), (200, 160, 40), 3)
        under_y = ty + font_title.getbbox(title)[3] + 5
        draw.line((tx, under_y, tx + tw, under_y), fill=(220, 180, 60), width=3)
        sc = (width - 90, height - 90); sr = 55
        for i in range(3, 0, -1):
            draw.ellipse((sc[0]-sr-i, sc[1]-sr-i, sc[0]+sr+i, sc[1]+sr+i), outline=(180, 60, 60), width=2)
        draw.ellipse((sc[0]-sr, sc[1]-sr, sc[0]+sr, sc[1]+sr), outline=(200, 80, 80), width=5)
        draw.text((sc[0]-35, sc[1]-10), "ПЕЧАТЬ", font=font_small, fill=(200, 80, 80))
        draw.text((40, height-50), f"№ {random.randint(100000, 999999)}", font=font_small, fill=(200, 170, 80))
        sc2 = (width//2, height-60); sr2 = 40
        for i in range(3, 0, -1):
            draw.ellipse((sc2[0]-sr2-i, sc2[1]-sr2-i, sc2[0]+sr2+i, sc2[1]+sr2+i), outline=(200, 170, 80), width=2)
        draw.ellipse((sc2[0]-sr2, sc2[1]-sr2, sc2[0]+sr2, sc2[1]+sr2), outline=(220, 190, 120), width=4)
        fw, fh = 30, 20
        fx, fy = sc2[0]-fw//2, sc2[1]-fh//2
        draw.rectangle((fx, fy, fx+fw//3, fy+fh), fill=(255, 255, 255))
        draw.rectangle((fx+fw//3, fy, fx+2*fw//3, fy+fh), fill=(0, 50, 255))
        draw.rectangle((fx+2*fw//3, fy, fx+fw, fy+fh), fill=(255, 0, 0))
        sy = height - 100
        draw.line((width-250, sy, width-50, sy), fill=(200, 170, 80), width=3)
        draw.text((width-200, sy+5), "Подпись врача", font=font_small, fill=(200, 170, 80))
        av_size = 120; av_x, av_y = 60, 130
        try:
            user_data = self.vk.method('users.get', {'user_ids': recipient_id, 'fields': 'photo_200'})
            if user_data and 'photo_200' in user_data[0]:
                resp = requests.get(user_data[0]['photo_200'], timeout=10)
                if resp.status_code == 200:
                    av = Image.open(BytesIO(resp.content)).resize((av_size, av_size), Image.Resampling.LANCZOS)
                    mask = Image.new('L', (av_size, av_size), 0)
                    ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
                    img.paste(av, (av_x, av_y), mask)
                    draw.ellipse((av_x, av_y, av_x+av_size, av_y+av_size), outline=(220, 190, 120), width=3)
        except Exception as e:
            print(f"⚠️ Аватарка: {e}")
        label = "КОМУ:"
        label_x = av_x + av_size + 40; label_y = av_y + 15
        glow(label, label_x, label_y, font_name, (220, 180, 60), (200, 160, 40), 2)
        label_width = draw.textlength(label, font=font_name)
        name_text = recipient_name.upper()
        name_x = label_x + label_width + 15
        glow(name_text, name_x, label_y, font_name, (255, 255, 255), (200, 200, 220), 3)
        full_w = draw.textlength(label + " " + name_text, font=font_name)
        under_y2 = label_y + font_name.getbbox(name_text)[3] + 5
        draw.line((label_x, under_y2, label_x + full_w, under_y2), fill=(220, 180, 60), width=2)
        diagnosis = "ДИАГНОЗ: Редкостный Еблан"
        dw = draw.textlength(diagnosis, font=font_diagnosis)
        dx, dy = (width - dw) // 2, av_y + av_size + 50
        glow(diagnosis, dx, dy, font_diagnosis, (220, 60, 60), (180, 40, 40), 3)
        under_y3 = dy + font_diagnosis.getbbox(diagnosis)[3] + 5
        draw.line((dx, under_y3, dx + dw, under_y3), fill=(220, 60, 60), width=2)
        footer_label = "ВЫДАН ЛИЧНО ОТ:"
        issuer_text = issuer_name.upper()
        fl_w = draw.textlength(footer_label, font=font_footer)
        it_w = draw.textlength(issuer_text, font=font_footer)
        fx = (width - fl_w - 20 - it_w) // 2
        fy = dy + 60
        glow(footer_label, fx, fy, font_footer, (220, 180, 60), (200, 160, 40), 2)
        issuer_x = fx + fl_w + 15
        glow(issuer_text, issuer_x, fy, font_footer, (255, 255, 255), (200, 200, 220), 3)
        full_fw = draw.textlength(footer_label + " " + issuer_text, font=font_footer)
        under_y4 = fy + font_footer.getbbox(issuer_text)[3] + 5
        draw.line((fx, under_y4, fx + full_fw, under_y4), fill=(220, 180, 60), width=2)
        date_str = datetime.now().strftime("%d.%m.%Y")
        dtx, dty = width - 200, height - 60
        glow(date_str, dtx, dty, font_date, (220, 180, 60), (200, 160, 40), 2)
        dt_w = draw.textlength(date_str, font=font_date)
        under_y5 = dty + font_date.getbbox(date_str)[3] + 5
        draw.line((dtx, under_y5, dtx + dt_w, under_y5), fill=(220, 180, 60), width=2)
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        return img_bytes

    # ====== ДЕМОТИВАТОР ======
    def create_demotivator(self, peer_id, user_id, text, event):
        try:
            msg_id = event.message_id if hasattr(event, 'message_id') else event.message['id']
            msg_info = self.vk.method('messages.getById', {'message_ids': [msg_id]})['items'][0]
            photo_url = None
            for att in msg_info.get('attachments', []):
                if att['type'] == 'photo':
                    sizes = att['photo'].get('sizes', [])
                    if sizes:
                        photo_url = sizes[-1]['url']
                    break
            if not photo_url and 'reply_message' in msg_info:
                for att in msg_info['reply_message'].get('attachments', []):
                    if att['type'] == 'photo':
                        sizes = att['photo'].get('sizes', [])
                        if sizes:
                            photo_url = sizes[-1]['url']
                        break
            if not photo_url:
                self.send(peer_id, "❌ Прикрепите фото или ответьте на сообщение с фото!")
                return
            bottom_text = text.upper().strip() if text else "ТУТ ДОЛЖЕН БЫТЬ ТЕКСТ"
            resp = requests.get(photo_url, timeout=15)
            if resp.status_code != 200:
                self.send(peer_id, "❌ Не удалось загрузить фото")
                return
            original_img = Image.open(BytesIO(resp.content))
            img_width, img_height = original_img.size
            bb = 40; bw = 10; bp = 180
            nw = img_width + (bb + bw) * 2
            nh = img_height + (bb + bw) * 2 + bp
            result = Image.new('RGB', (nw, nh), color=(0, 0, 0))
            px, py = bb + bw, bb + bw
            result.paste(original_img, (px, py))
            draw = ImageDraw.Draw(result)
            draw.rectangle([px-bw, py-bw, px+img_width+bw, py+img_height+bw], outline=(255, 255, 255), width=bw)
            font_size = 52
            font = None
            for path in ["Arial.ttf", "DejaVuSans.ttf",
                         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                         "/system/fonts/Roboto-Regular.ttf", "arial.ttf"]:
                try:
                    font = ImageFont.truetype(path, font_size); break
                except: continue
            if font is None:
                f = ImageFont.load_default()
                cw, ch = 16, 24
                max_chars = 18
                lines, cur = [], ""
                for word in bottom_text.split():
                    if len(cur) + len(word) + 1 <= max_chars:
                        cur = (cur + " " + word) if cur else word
                    else:
                        lines.append(cur); cur = word
                if cur: lines.append(cur)
                if not lines: lines = [bottom_text[:18]]
                lines = lines[:4]
                ty = nh - bp + 30
                for line in lines:
                    tx = (nw - len(line) * cw) // 2
                    for i, ch2 in enumerate(line):
                        x = tx + i * cw
                        for dx, dy in [(0,0),(1,0),(0,1),(1,1)]:
                            draw.text((x+dx, ty+dy), ch2, fill=(255,255,255), font=f)
                        for dx, dy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
                            draw.text((x+dx, ty+dy), ch2, fill=(0,0,0), font=f)
                    ty += ch + 8
            else:
                max_chars = 25
                lines, cur = [], ""
                for word in bottom_text.split():
                    if len(cur) + len(word) + 1 <= max_chars:
                        cur = (cur + " " + word) if cur else word
                    else:
                        lines.append(cur); cur = word
                if cur: lines.append(cur)
                if not lines: lines = [bottom_text[:25]]
                lines = lines[:4]
                ty = nh - bp + 30
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    tx = (nw - (bbox[2] - bbox[0])) // 2
                    for dx, dy in [(-2,-2),(-2,0),(-2,2),(0,-2),(0,2),(2,-2),(2,0),(2,2)]:
                        draw.text((tx+dx, ty+dy), line, fill=(0,0,0), font=font)
                    draw.text((tx, ty), line, fill=(255,255,255), font=font)
                    ty += font_size + 15
            img_bytes = BytesIO()
            result.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            upload_server = self.vk.method('photos.getMessagesUploadServer', {})
            files = {'photo': ('demotivator.png', img_bytes, 'image/png')}
            upload_response = requests.post(upload_server['upload_url'], files=files).json()
            photo = self.vk.method('photos.saveMessagesPhoto', {
                'photo': upload_response['photo'],
                'server': upload_response['server'],
                'hash': upload_response['hash']
            })
            self.vk.method('messages.send', {
                'peer_id': peer_id,
                'message': '🖼 Демотиватор готов:',
                'attachment': f"photo{photo[0]['owner_id']}_{photo[0]['id']}",
                'random_id': random.randint(1, 10**9)
            })
        except Exception as e:
            print(f"❌ Ошибка демотиватора: {e}")
            self.send(peer_id, f"⚠️ Ошибка: {str(e)[:100]}")

    # ====== ХЕЛП ======
    def get_help(self):
        return """
🎮 Рп: рп действие · рп +рандом · рп +список рп · +топ рп
🎵 Музыка: рек [запрос] · текст артист/трек · обновить микс
🤖 ИИ: ии текст
💍 Браки: +брак (@user) · -брак · мой брак · браки
👶 Семья: помощь семья
🎲 Игры: !кости (@user) · бросок · !крестики (@user)
📊 Стат: +стат · топ · +топ смс/стикеры/гс/видео/фото/общение
🎯 Разное: .кто · .вероятность · .выбери · .сертификат · дем
"""

    # ====== ОБРАБОТКА ======
    def handle(self, event):
        try:
            # callback
            if event.type == VkBotEventType.MESSAGE_EVENT:
                payload = event.object.get('payload', {})
                user_id = event.object.get('user_id')
                peer_id = event.object.get('peer_id')
                event_id = event.object.get('event_id')
                conv_msg_id = event.object.get('conversation_message_id')

                def answer(text):
                    try:
                        self.vk.method('messages.sendMessageEventAnswer', {
                            'event_id': event_id, 'user_id': user_id, 'peer_id': peer_id,
                            'event_data': json.dumps({"type": "show_snackbar", "text": text})
                        })
                    except: pass

                if payload.get('action') in ['update_list', 'update_mix']:
                    owner = payload.get('owner') or 0
                    if user_id != owner:
                        answer("не кликай по чужим кнопкам"); return
                    now = time.time()
                    last = self.music_cooldowns.get(peer_id, 0)
                    cd = 10 if peer_id == user_id else 5
                    if now - last < cd:
                        answer(f"⏳ Подожди {int(cd - (now - last))} сек"); return
                    self.music_cooldowns[peer_id] = now
                    self.send_music(peer_id, owner, None, None, edit_conv_msg_id=conv_msg_id, owner_id=owner)
                    answer("🔄 Обновляю..."); return

                if payload.get('preg'):
                    action = payload.get('preg'); target_user = payload.get('user')
                    if action == "no":
                        self.send(target_user, f"❌ {self.user_link(user_id)} отказался от ребенка!")
                        if target_user in self.pregnancies:
                            del self.pregnancies[target_user]; self.save_all()
                        try:
                            self.vk.method('messages.edit', {
                                'peer_id': peer_id,
                                'message': f"🤰 {self.user_link(target_user)} хотел(а) ребенка от {self.user_link(user_id)}!\n\n❌ {self.user_link(user_id)} отказался(ась)!",
                                'keyboard': json.dumps({"buttons": []}, ensure_ascii=False),
                                'conversation_message_id': conv_msg_id
                            })
                        except: pass
                        answer("❌ Отказано!"); return
                    if action == "yes":
                        ok, result = self.confirm_pregnancy(user_id, target_user, action)
                        if ok:
                            self.send(target_user, "✅ Партнер согласился! Придумай имя: ребенок имя")
                            self.send(peer_id, "✅ Ты согласился! Партнер выберет имя.")
                            try:
                                self.vk.method('messages.edit', {
                                    'peer_id': peer_id,
                                    'message': f"🤰 {self.user_link(target_user)} хочет ребенка от {self.user_link(user_id)}!\n\n✅ {self.user_link(user_id)} согласился(ась)!",
                                    'keyboard': json.dumps({"buttons": []}, ensure_ascii=False),
                                    'conversation_message_id': conv_msg_id
                                })
                            except: pass
                            answer("✅ Согласие получено!")
                        else:
                            answer(f"❌ {result}")
                        return

                if payload.get('action') in ['feed', 'play', 'sleep', 'treat']:
                    child_id, data = self.get_child(user_id)
                    if not data:
                        answer("❌ У вас нет ребенка!"); return
                    action = payload.get('action')
                    {'feed': self.feed_child, 'play': self.play_with_child,
                     'sleep': self.sleep_child, 'treat': self.treat_child}[action](user_id)
                    self.send_child_status(user_id, peer_id, edit=True, conv_msg_id=conv_msg_id)
                    answer("✅ Готово!"); return

                if payload.get('ttt'):
                    self.handle_ttt_move(peer_id, user_id, payload.get('pos'), payload.get('ttt'))
                    answer("✅ Ход сделан!"); return
                return

            if not hasattr(event, 'message'):
                return

            msg = event.message
            uid = msg.get('from_id')
            pid = msg.get('peer_id')
            raw_text = msg.get('text', '').strip()
            if not raw_text or not uid or not pid:
                return

            content_type = "text"
            if msg.get('sticker') is not None:
                content_type = "sticker"
            elif msg.get('attachments'):
                for a in msg['attachments']:
                    atype = a['type']
                    if atype == 'sticker': content_type = "sticker"; break
                    elif atype == 'audio_message': content_type = "voice"; break
                    elif atype == 'video': content_type = "video"; break
                    elif atype == 'photo': content_type = "photo"; break
                    elif atype == 'doc': content_type = "doc"; break
                    else: content_type = "other"; break

            u = str(uid)
            self.chat_stats.setdefault(u, {k: 0 for k in ["text","sticker","voice","video","photo","doc","other","total"]})
            self.chat_stats[u][content_type] = self.chat_stats[u].get(content_type, 0) + 1
            self.chat_stats[u]["total"] = self.chat_stats[u].get("total", 0) + 1
            save_json(CHAT_STATS_FILE, self.chat_stats)

            clean_text = self.clean_text(raw_text)
            cmd = remove_emoji(clean_text).strip().lower()

            # админ
            if cmd == '//restart':
                try:
                    user = self.vk.method('users.get', {'user_ids': uid, 'fields': 'screen_name'})
                    if user and user[0].get('screen_name', '').lower() != 'karp1k69':
                        self.send(pid, '❌ Только для @karp1k69!'); return
                except:
                    self.send(pid, '❌ Ошибка проверки'); return
                self.send(pid, '🔄 Перезапуск...')
                self.save_all()
                os.execl(sys.executable, sys.executable, *sys.argv)
                return

            if cmd == '+клава':
                self.keyboard_enabled[uid] = True
                self.send(pid, '⌨️ Клавиатура включена!'); return

            if cmd == '-клава':
                self.keyboard_enabled[uid] = False
                self.send(pid, '⌨️ Клавиатура скрыта!', self.get_empty_keyboard()); return

            if cmd == '/chatstats':
                if pid < 2000000000:
                    self.send(pid, "❌ Только в беседах."); return
                try:
                    members = self.vk.method('messages.getConversationMembers', {'peer_id': pid})
                    is_admin = any(m['member_id'] == uid and m.get('is_admin', False) for m in members['items'])
                    if not is_admin:
                        self.send(pid, "❌ Только для админов."); return
                except Exception as e:
                    self.send(pid, f"❌ {e}"); return
                total_msgs = sum(d.get('total', 0) for d in self.chat_stats.values())
                top = sorted(self.chat_stats.items(), key=lambda x: x[1].get('total', 0), reverse=True)[:5]
                top_text = "\n".join([f"{i+1}. {self.user_link(int(u2))} — {d.get('total', 0)}" for i,(u2,d) in enumerate(top)]) or "Нет данных"
                self.send(pid, f"📊 Статистика:\n\n👥 Участников: {len(self.chat_stats)}\n💬 Всего: {total_msgs}\n\n🏆 Топ-5:\n{top_text}")
                return

            if cmd == '/botinfo':
                if pid < 2000000000:
                    self.send(pid, "❌ Только в беседах."); return
                try:
                    members = self.vk.method('messages.getConversationMembers', {'peer_id': pid})
                    is_admin = any(m['member_id'] == uid and m.get('is_admin', False) for m in members['items'])
                    if not is_admin:
                        self.send(pid, "❌ Только для админов."); return
                except: return
                bot_id = -self.GROUP_ID
                bi = next((m for m in members['items'] if m['member_id'] == bot_id), None)
                if not bi:
                    self.send(pid, "❌ Бот не найден."); return
                response = "🤖 Информация о боте:\n\n"
                for label, key in [("Администратор","is_admin"),("Удалять","can_delete_messages"),
                                   ("Заглушать","can_mute"),("Исключать","can_ban"),
                                   ("Менять инфо","can_change_info"),("Закреплять","can_pin"),
                                   ("Назначать админов","can_promote")]:
                    response += f"{label}: {'✅' if bi.get(key, False) else '❌'}\n"
                self.send(pid, response); return

            if cmd.startswith('/clearsms '):
                target = self.get_target_user(msg, raw_text)
                if not target:
                    self.send(pid, "❌ Укажите пользователя"); return
                try:
                    user = self.vk.method('users.get', {'user_ids': uid, 'fields': 'screen_name'})
                    if user[0].get('screen_name', '').lower() != 'karp1k69':
                        self.send(pid, '❌ Только для @karp1k69!'); return
                except: return
                u2 = str(target)
                self.chat_stats[u2] = {k: 0 for k in ["text","sticker","voice","video","photo","doc","other","total"]}
                save_json(CHAT_STATS_FILE, self.chat_stats)
                self.send(pid, f"✅ Статистика {self.user_link(target)} обнулена."); return

            if cmd.startswith('/givesms '):
                parts = cmd.split()
                if len(parts) < 3:
                    self.send(pid, "❌ /givesms @user N"); return
                target = self.get_target_user(msg, raw_text)
                if not target:
                    self.send(pid, "❌ Не определен пользователь"); return
                try: amount = int(parts[-1])
                except: self.send(pid, "❌ Число"); return
                try:
                    user = self.vk.method('users.get', {'user_ids': uid, 'fields': 'screen_name'})
                    if user[0].get('screen_name', '').lower() != 'karp1k69':
                        self.send(pid, '❌ Только для @karp1k69!'); return
                except: return
                u2 = str(target)
                self.chat_stats.setdefault(u2, {k: 0 for k in ["text","sticker","voice","video","photo","doc","other","total"]})
                self.chat_stats[u2]["text"] = self.chat_stats[u2].get("text", 0) + amount
                self.chat_stats[u2]["total"] = sum(self.chat_stats[u2].get(k,0) for k in ["text","sticker","voice","video","photo","doc","other"])
                save_json(CHAT_STATS_FILE, self.chat_stats)
                self.send(pid, f"✅ +{amount} {self.user_link(target)}."); return

            # базовые
            if cmd == 'хелп':
                self.send(pid, self.get_help()); return
            if cmd.startswith('ии '):
                prompt = clean_text[3:].strip()
                if not prompt:
                    self.send(pid, "❌ Напиши запрос"); return
                self.send(pid, "🤔 Думаю...")
                self.send(pid, get_ai(uid, prompt)); return
            if cmd == 'ид':
                target = self.get_target_user(msg, raw_text)
                self.send(pid, self.get_user_id_info(uid, target)); return

            if cmd.startswith('.кто '):
                q = cmd[4:].strip()
                if not q:
                    self.send(pid, "❌ Напиши запрос"); return
                if pid > 2000000000:
                    try:
                        members = self.vk.method('messages.getConversationMembers', {'peer_id': pid})
                        cand = [m['member_id'] for m in members['items'] if m['member_id'] > 0]
                        if len(cand) < 2:
                            self.send(pid, "❌ Мало участников"); return
                        self.send(pid, f"🔮Это: {self.user_link(random.choice(cand))} «{q}»")
                    except Exception as e:
                        self.send(pid, f"❌ {e}")
                else:
                    self.send(pid, f"это {self.user_link(uid)} {q}")
                return

            if cmd.startswith('.вероятность '):
                q = cmd[12:].strip()
                if not q:
                    self.send(pid, "❌ Напиши запрос"); return
                self.send(pid, f"🔮Вероятность «{q}» равна: {random.randint(0, 100)}%"); return

            if cmd.startswith('.выбери '):
                raw = cmd[7:].strip()
                if not raw:
                    self.send(pid, "❌ Варианты"); return
                opts = [o.strip() for o in re.split(r',\s*|\s+или\s+', raw) if o.strip()]
                if len(opts) < 2:
                    self.send(pid, "❌ Минимум 2"); return
                self.send(pid, f"🤯Выбор: «{random.choice(opts)}»"); return

            if cmd.startswith('.сертификат '):
                target = self.get_target_user(msg, raw_text)
                if not target:
                    self.send(pid, "❌ .сертификат @user"); return
                try:
                    img_bytes = self.generate_certificate(target, self.user_name(target), self.user_name(uid))
                    upload_server = self.vk.method('photos.getMessagesUploadServer', {'peer_id': pid})
                    img_bytes.seek(0)
                    files = {'photo': ('cert.png', img_bytes.getvalue(), 'image/png')}
                    upload_response = requests.post(upload_server['upload_url'], files=files).json()
                    if 'error' in upload_response:
                        self.send(pid, f"❌ {upload_response['error']['error_msg']}"); return
                    photo = self.vk.method('photos.saveMessagesPhoto', {
                        'photo': upload_response['photo'],
                        'server': upload_response['server'],
                        'hash': upload_response['hash']
                    })
                    self.vk.method('messages.send', {
                        'peer_id': pid, 'message': '📜 Сертификат:',
                        'attachment': f"photo{photo[0]['owner_id']}_{photo[0]['id']}",
                        'random_id': random.randint(1, 10**9)
                    })
                except Exception as e:
                    self.send(pid, f"❌ {e}")
                return

            if cmd.startswith('.мут '):
                if pid < 2000000000:
                    self.send(pid, "❌ В беседах!"); return
                target = self.get_target_user(msg, raw_text)
                if not target:
                    self.send(pid, "❌ .мут @user"); return
                if target == uid:
                    self.send(pid, "❌ Себя нельзя!"); return
                ok, err = self.mute_user(pid, target)
                self.send(pid, f"🔇 {self.user_link(target)} замучен!" if ok else f"❌ {err}"); return

            if cmd.startswith('.размут '):
                target = self.get_target_user(msg, raw_text)
                if not target:
                    self.send(pid, "❌ .размут @user"); return
                ok, err = self.unmute_user(pid, target)
                self.send(pid, f"🔊 {self.user_link(target)} размучен!" if ok else f"❌ {err}"); return

            if cmd == '.замученные':
                if pid < 2000000000:
                    self.send(pid, "❌ В беседах!"); return
                ml = self.get_muted_list(pid)
                if not ml:
                    self.send(pid, "📭 Никто не замучен."); return
                self.send(pid, "🔇 Замученные:\n" + "\n".join(self.user_link(u2) for u2 in ml)); return

            # музыка
            if cmd == 'рек':
                self.send(pid, f"{self.user_link(uid)}, выбери действие:", keyboard=self.get_rek_keyboard(uid)); return
            if cmd.startswith('рек '):
                parts = clean_text.split()
                q = None; mood = None
                if len(parts) > 1:
                    q = " ".join(parts[1:])
                    if parts[-1].lower() in MOODS:
                        mood = parts[-1].lower()
                        q = " ".join(parts[1:-1]) or None
                self.send_music(pid, uid, q, mood, owner_id=uid); return
            if cmd == 'обновить микс':
                self.send(pid, "🔄 Обновляю...")
                self.send_music(pid, uid, None, None, owner_id=uid); return
            if cmd.startswith('текст '):
                q = clean_text[6:].strip()
                if '/' not in q:
                    self.send(pid, f"📝 текст артист / название"); return
                a, t = q.split('/', 1)
                a, t = a.strip(), t.strip()
                if not a or not t:
                    self.send(pid, "❌ текст артист / название"); return
                self.send(pid, "🔍 Ищу...")
                res, err = self.lyrics(a, t)
                self.send(pid, res if res else err); return

            # RP
            if cmd.startswith('рп '):
                rp_text = clean_text[3:].strip()
                all_rp = self.rp_all()
                if cmd == 'рп +рандом':
                    if not all_rp:
                        self.send(pid, "❌ Нет RP"); return
                    name = random.choice(list(all_rp.keys()))
                    try:
                        members = self.vk.method('messages.getConversationMembers', {'peer_id': pid})
                        target = random.choice([m['member_id'] for m in members['items'] if m['member_id'] > 0 and m['member_id'] != uid])
                    except:
                        target = uid
                    self.rp_do(pid, uid, name, all_rp[name], [target]); return
                if cmd == 'рп +список рп':
                    res = "📋 Список RP:\n\n" + "\n".join(f"{i}. {n} — {d['description']}" for i,(n,d) in enumerate(all_rp.items(), 1))
                    self.send(pid, res); return
                for name, data in all_rp.items():
                    if rp_text.lower() == name or rp_text.lower().startswith(name + ' '):
                        target = extract_id(rp_text)
                        if not target and msg.get('reply_message'):
                            target = msg['reply_message'].get('from_id')
                        if not target:
                            self.send(pid, "❌ Укажи пользователя"); return
                        self.history.setdefault(uid, []).append(f"{name} {self.user_name(target)}")
                        if uid != target:
                            key = f"{min(uid, target)}_{max(uid, target)}"
                            self.mutual[key] = self.mutual.get(key, 0) + 1
                        self.favorites_rp.setdefault(uid, {})
                        self.favorites_rp[uid][name] = self.favorites_rp[uid].get(name, 0) + 1
                        self.rp_do(pid, uid, name, data, [target]); return

            if cmd == '+топ рп':
                actions = self.rp_top()
                if actions:
                    res = "🏆 Топ RP:\n\n" + "\n".join(f"{a}: {c} раз" for a,c in sorted(actions.items(), key=lambda x: x[1], reverse=True)[:5])
                    self.send(pid, res)
                else:
                    self.send(pid, "📭 Нет данных")
                return

            # браки
            if cmd.startswith('+брак'):
                target = self.get_target_user(msg, clean_text)
                if not target:
                    self.send(pid, "❌ Укажи пользователя"); return
                if target == uid:
                    self.send(pid, "❌ Нельзя на себе"); return
                date = None
                if d := re.search(r'(\d{2}\.\d{2}\.\d{4})', clean_text):
                    try: date = datetime.strptime(d.group(1), '%d.%m.%Y')
                    except: pass
                ok, err = self.marriage_add(uid, target, date)
                if ok:
                    suffix = f" с {date.strftime('%d.%m.%Y')}" if date else ""
                    self.send(pid, f"💍 {self.user_link(uid)} + {self.user_link(target)} теперь в браке{suffix}!")
                else:
                    self.send(pid, err)
                return

            if cmd.startswith('-брак'):
                target = self.get_target_user(msg, clean_text)
                if target:
                    u2 = str(uid)
                    if u2 not in self.marriages or self.marriages[u2]["partner"] != target:
                        self.send(pid, f"❌ Ты не в браке с {self.user_link(target)}"); return
                ok, err = self.marriage_remove(uid)
                self.send(pid, "💔 Брак расторгнут" if ok else err); return

            if cmd == 'мой брак':
                status = self.marriage_status(uid)
                self.send(pid, status if status else "💔 Вы не в браке"); return

            if cmd == 'обновить детей':
                updated = self.update_all_children()
                self.send(pid, f"🔄 Обновлены {updated} детей!" if updated else "✅ Все актуальны!"); return

            if cmd == 'браки':
                if not self.marriages:
                    self.send(pid, "📭 Браков нет"); return
                res = "🤡Список парочек:\n\n"
                seen = set()
                for uid_s, d in self.marriages.items():
                    if uid_s in seen: continue
                    p = str(d["partner"]); uu, partner = int(uid_s), int(p)
                    children = self.get_children_in_marriage(uu, partner)
                    res += f"💍 {self.user_link(uu)} + {self.user_link(partner)} ({fmt_time(d['since'])})\n"
                    if children:
                        names = []
                        for c in children:
                            g = "👦" if c.get("gender", "male") == "male" else "👧"
                            names.append(f"{g} {c['name']} ({format_child_age(c['birthday'])})")
                        res += "   👶 " + ", ".join(names) + "\n"
                    res += "\n"
                    seen.add(uid_s); seen.add(p)
                self.send(pid, res); return

            # беременность
            if 'забеременеть от' in raw_text.lower():
                partner = None
                m = re.search(r'\[id(\d+)\|.*?\]', raw_text)
                if m: partner = int(m.group(1))
                if not partner: partner = extract_id(raw_text)
                if not partner:
                    sm = re.search(r'@([a-zA-Z0-9_]+)', raw_text)
                    if sm: partner = get_user_id_by_screen_name(sm.group(1))
                if not partner and msg.get('reply_message'):
                    partner = msg['reply_message'].get('from_id')
                if not partner:
                    nums = re.findall(r'\b\d{5,}\b', raw_text)
                    if nums: partner = int(nums[0])
                if not partner:
                    self.send(pid, "❌ Укажи партнера"); return
                if partner == uid:
                    self.send(pid, "❌ Нельзя от себя!"); return
                u1 = str(uid)
                if u1 not in self.marriages:
                    self.send(pid, "❌ Вы не в браке!"); return
                if self.marriages[u1]["partner"] != partner:
                    self.send(pid, f"❌ Вы в браке с {self.user_link(self.marriages[u1]['partner'])}"); return
                if self.get_child(uid, partner)[0]:
                    self.send(pid, "❌ Уже есть ребенок!"); return
                if uid in self.pregnancies:
                    self.send(pid, "❌ Уже есть беременность!"); return
                if partner in self.pregnancies:
                    self.send(pid, "❌ У партнера беременность!"); return
                self.pregnancies[uid] = {"partner": partner, "status": "waiting"}
                self.save_all()
                keyboard = {"inline": True, "buttons": [
                    [{"action": {"type": "callback", "label": "✅ Взять ответственность", "payload": {"preg": "yes", "user": uid}}}],
                    [{"action": {"type": "callback", "label": "❌ Уйти за хлебом", "payload": {"preg": "no", "user": uid}}}]
                ]}
                self.vk.method('messages.send', {
                    'peer_id': pid,
                    'message': f"🤰 {self.user_link(uid)} хочет ребенка от {self.user_link(partner)}!\n\n{self.user_link(partner)}, выбери:",
                    'keyboard': json.dumps(keyboard, ensure_ascii=False),
                    'random_id': random.randint(1, 10**9)
                })
                return

            if cmd.startswith('ребенок имя '):
                if uid not in self.pregnancies:
                    self.send(pid, "Нет беременности!"); return
                name = cmd[12:].strip()
                if not name:
                    self.send(pid, "Напиши имя"); return
                self.temp_names[uid] = name
                self.send(pid, f"Имя {name} сохранено! Теперь: ребенок пол мальчик/девочка"); return

            if cmd.startswith('ребенок пол '):
                if uid not in self.pregnancies:
                    self.send(pid, "Нет беременности!"); return
                gender = cmd[12:].strip().lower()
                if gender not in ["мальчик", "девочка"]:
                    self.send(pid, "Пол: мальчик или девочка"); return
                if uid not in self.temp_names:
                    self.send(pid, "Сначала: ребенок имя Саня"); return
                name = self.temp_names[uid]
                gender_en = "male" if gender == "мальчик" else "female"
                ok, result = self.create_child_from_pregnancy(uid, name, gender_en)
                if ok:
                    self.send(pid, f"✅ {result} ({gender})")
                    self.temp_names.pop(uid, None)
                    self.update_all_children()
                else:
                    self.send(pid, result)
                return

            if cmd == 'статус':
                self.send_child_status(uid, pid, edit=False); return
            if cmd.startswith('дем '):
                self.create_demotivator(pid, uid, cmd[4:].strip() or None, event); return
            if cmd == 'дети':
                self.send(pid, self.get_children_list()); return
            if cmd == 'помощь семья':
                self.send(pid, self.get_family_help()); return

            # стат
            if cmd == '+стат':
                s = self.get_user_stats(uid)
                self.send(pid, f"📊 Статистика {self.user_link(uid)}:\n\n📝 {s['text']}\n🖼️ {s['sticker']}\n🎤 {s['voice']}\n🎬 {s['video']}\n📷 {s['photo']}\n📄 {s['doc']}\n📦 {s['other']}\n📊 Всего: {s['total']}"); return
            for stat_cmd, field, label in [
                ('+топ смс','text','сообщениям'), ('+топ стикеры','sticker','стикерам'),
                ('+топ гс','voice','голосовым'), ('+топ видео','video','видео'),
                ('+топ фото','photo','фото'), ('+топ общение','total','общению'),
                ('топ','total','общению')]:
                if cmd == stat_cmd:
                    self.send(pid, self.format_top(self.get_top_by_type(field), field, label)); return

            # игры
            if cmd.startswith('!кости'):
                target = self.get_target_user(msg, clean_text)
                if not target:
                    self.send(pid, "❌ !кости @user"); return
                if target == uid:
                    self.send(pid, "❌ Нельзя с собой!"); return
                self.send(pid, self.start_dice_game(pid, uid, target)); return
            if cmd == 'бросок':
                if pid in self.dice_games and self.dice_games[pid].get("active", False):
                    self.send(pid, self.handle_dice_turn(pid, uid))
                else:
                    self.send(pid, "❌ Нет игры! !кости @user")
                return
            if cmd.startswith('!крестики') or cmd.startswith('!ttt'):
                target = self.get_target_user(msg, clean_text)
                if not target:
                    self.send(pid, "❌ !крестики @user"); return
                if target == uid:
                    self.send(pid, "❌ Нельзя с собой!"); return
                self.send(pid, self.start_ttt_game(pid, uid, target)); return

        except Exception as e:
            print(f"❌ Ошибка в handle: {e}")

    def run(self):
        print("🤖 RP Бот запущен!")
        print(f"📱 ID сообщества: {GROUP_ID}")
        while True:
            try:
                for event in self.longpoll.listen():
                    if event.type in (VkBotEventType.MESSAGE_NEW, VkBotEventType.MESSAGE_EVENT):
                        self.handle(event)
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                print("🔄 Переподключение через 5с...")
                time.sleep(5)
                self.init()