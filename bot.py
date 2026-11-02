import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import random
import re
import json
import os
import time
import sys

from config import (
    BOT_TOKEN, USER_TOKEN, GROUP_ID,
    RP_FILE, STATS_FILE, MARRIAGE_FILE, CHILDREN_FILE,
    PREGNANCY_FILE, CHAT_STATS_FILE, MUTED_FILE,
)
from database import load_json, save_json
from utils import (
    fmt_time, extract_id, remove_emoji,
    get_user_id_by_screen_name, format_child_age,
)
from keyboards import KeyboardMixin
from modules.ai import get_ai
from modules.rp import RPMixin
from modules.family import FamilyMixin
from modules.games import GamesMixin
from modules.music import MusicMixin
from modules.stats import StatsMixin
from modules.certificate import CertificateMixin
from modules.demotivator import DemotivatorMixin


class VKBot(KeyboardMixin, RPMixin, FamilyMixin, GamesMixin, MusicMixin,
            StatsMixin, CertificateMixin, DemotivatorMixin):

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
        self.achievements = {}
        self.cooldowns = {}
        self.music_cooldowns = {}
        self.child_counter = len(self.children)
        self.temp_names = {}
        self.running = True
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

    # ========== СОХРАНЕНИЕ ==========
    def save_all(self):
        save_json(MARRIAGE_FILE, self.marriages)
        save_json(CHILDREN_FILE, self.children)
        save_json(PREGNANCY_FILE, self.pregnancies)
        save_json(STATS_FILE, self.stats)
        save_json(RP_FILE, self.custom_rp)
        save_json(CHAT_STATS_FILE, self.chat_stats)
        save_json(MUTED_FILE, self.muted)

    # ========== ИНИЦИАЛИЗАЦИЯ ==========
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

    # ========== ХЕЛПЕРЫ ==========
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
        text = re.sub(r'\[club\d+\|.*?\]', '', text)
        return text.strip()

    def get_target_user(self, msg, raw_text):
        target = extract_id(raw_text)
        if target:
            return target
        if msg.get('reply_message'):
            return msg['reply_message'].get('from_id')
        numbers = re.findall(r'\b\d{5,}\b', raw_text)
        if numbers:
            return int(numbers[0])
        return None

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
            try:
                self.vk.method('messages.send', {'peer_id': peer, 'message': text, 'random_id': random.randint(1, 10**9)})
            except: pass

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

    # ========== МУТ ==========
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

    # ========== ХЕЛП ==========
    def get_help(self):
        return """
🎮 Рп-Команды
 • рп действие • рп +рандом • рп +список рп • +топ рп

🎵 Музыка
 • рек [запрос] · текст исполнитель/название · обновить микс

🤖 ИИ
 • ии текст

💍 Браки
 • +брак (@user) [дата] · -брак (@user) · мой брак · браки

👶 Семья
 • помощь семья

🎲 Игры
 • !кости (@user) · бросок · !крестики (@user)

📊 Статистика
 • +стат · топ · +топ смс/стикеры/гс/видео/фото/общение

🎯 Разное
 • .кто [текст] · .вероятность что [текст] · .выбери [варианты] · .сертификат (@user)
"""

    # ========== ОБРАБОТКА СОБЫТИЙ ==========
    def handle(self, event):
        try:
            # ---- Callback-кнопки ----
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
                        answer("не кликай по чужим кнопкам")
                        return
                    now = time.time()
                    last = self.music_cooldowns.get(peer_id, 0)
                    cd = 10 if peer_id == user_id else 5
                    if now - last < cd:
                        answer(f"⏳ Подожди {int(cd - (now - last))} сек")
                        return
                    self.music_cooldowns[peer_id] = now
                    self.send_music(peer_id, owner, None, None, edit_conv_msg_id=conv_msg_id, owner_id=owner)
                    answer("🔄 Обновляю...")
                    return

                if payload.get('preg'):
                    action = payload.get('preg')
                    target_user = payload.get('user')
                    if action == "no":
                        self.send(target_user, f"❌ {self.user_link(user_id)} отказался от ребенка!")
                        if target_user in self.pregnancies:
                            del self.pregnancies[target_user]
                            self.save_all()
                        try:
                            self.vk.method('messages.edit', {
                                'peer_id': peer_id,
                                'message': f"🤰 {self.user_link(target_user)} хотел(а) ребенка от {self.user_link(user_id)}!\n\n❌ {self.user_link(user_id)} отказался(ась)!",
                                'keyboard': json.dumps({"buttons": []}, ensure_ascii=False),
                                'conversation_message_id': conv_msg_id
                            })
                        except: pass
                        answer("❌ Отказано!")
                        return
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
                        answer("❌ У вас нет ребенка!")
                        return
                    action = payload.get('action')
                    result = {'feed': self.feed_child, 'play': self.play_with_child,
                              'sleep': self.sleep_child, 'treat': self.treat_child}[action](user_id)
                    self.send_child_status(user_id, peer_id, edit=True, conv_msg_id=conv_msg_id)
                    answer("✅ Готово!")
                    return

                if payload.get('ttt'):
                    self.handle_ttt_move(peer_id, user_id, payload.get('pos'), payload.get('ttt'))
                    answer("✅ Ход сделан!")
                    return
                return

            # ---- Обычные сообщения ----
            if not hasattr(event, 'message'):
                return

            msg = event.message
            uid = msg.get('from_id')
            pid = msg.get('peer_id')
            raw_text = msg.get('text', '').strip()
            if not raw_text or not uid or not pid:
                return

            # Статистика
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

            # ===== АДМИН =====
            if cmd == '//restart':
                try:
                    user = self.vk.method('users.get', {'user_ids': uid, 'fields': 'screen_name'})
                    if user and user[0].get('screen_name', '').lower() != 'karp1k69':
                        self.send(pid, '❌ Только для @karp1k69!')
                        return
                except:
                    self.send(pid, '❌ Ошибка проверки'); return
                self.send(pid, '🔄 Бот перезапушен!')
                self.save_all()
                os.execl(sys.executable, sys.executable, *sys.argv)
                return

            if cmd == '+клава':
                self.keyboard_enabled[uid] = True
                self.send(pid, '⌨️ Клавиатура включена!')
                return

            if cmd == '-клава':
                self.keyboard_enabled[uid] = False
                self.send(pid, '⌨️ Клавиатура скрыта!', self.get_empty_keyboard())
                return

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
                top_text = "\n".join([f"{i+1}. {self.user_link(int(uid))} — {d.get('total', 0)}" for i,(uid,d) in enumerate(top)]) or "Нет данных"
                self.send(pid, f"📊 Статистика беседы:\n\n👥 Участников: {len(self.chat_stats)}\n💬 Всего сообщений: {total_msgs}\n\n🏆 Топ-5:\n{top_text}")
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
                self.send(pid, response)
                return

            if cmd.startswith('/clearsms '):
                target = self.get_target_user(msg, raw_text)
                if not target:
                    self.send(pid, "❌ Укажите пользователя"); return
                try:
                    user = self.vk.method('users.get', {'user_ids': uid, 'fields': 'screen_name'})
                    if user[0].get('screen_name', '').lower() != 'karp1k69':
                        self.send(pid, '❌ Только для @karp1k69!'); return
                except: return
                u = str(target)
                self.chat_stats[u] = {k: 0 for k in ["text","sticker","voice","video","photo","doc","other","total"]}
                save_json(CHAT_STATS_FILE, self.chat_stats)
                self.send(pid, f"✅ Статистика {self.user_link(target)} обнулена.")
                return

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
                u = str(target)
                self.chat_stats.setdefault(u, {k: 0 for k in ["text","sticker","voice","video","photo","doc","other","total"]})
                self.chat_stats[u]["text"] = self.chat_stats[u].get("text", 0) + amount
                self.chat_stats[u]["total"] = sum(self.chat_stats[u].get(k,0) for k in ["text","sticker","voice","video","photo","doc","other"])
                save_json(CHAT_STATS_FILE, self.chat_stats)
                self.send(pid, f"✅ +{amount} {self.user_link(target)}. Текстовых: {self.chat_stats[u]['text']}, всего: {self.chat_stats[u]['total']}.")
                return

            # ===== БАЗОВЫЕ =====
            if cmd == 'хелп':
                self.send(pid, self.get_help()); return

            if cmd.startswith('ии '):
                prompt = clean_text[3:].strip()
                if not prompt:
                    self.send(pid, "❌ Напиши запрос"); return
                self.send(pid, "🤔 Думаю...")
                self.send(pid, get_ai(uid, prompt))
                return

            if cmd == 'ид':
                target = self.get_target_user(msg, raw_text)
                self.send(pid, self.get_user_id_info(uid, target)); return

            if cmd.startswith('.кто '):
                query = cmd[4:].strip()
                if not query:
                    self.send(pid, "❌ Напиши запрос"); return
                if pid > 2000000000:
                    try:
                        members = self.vk.method('messages.getConversationMembers', {'peer_id': pid})
                        candidates = [m['member_id'] for m in members['items'] if m['member_id'] > 0]
                        if len(candidates) < 2:
                            self.send(pid, "❌ Мало участников"); return
                        chosen = random.choice(candidates)
                        self.send(pid, f"🔮Это: {self.user_link(chosen)} «{query}»")
                    except Exception as e:
                        self.send(pid, f"❌ {e}")
                else:
                    self.send(pid, f"это {self.user_link(uid)} {query}")
                return

            if cmd.startswith('.вероятность '):
                query = cmd[12:].strip()
                if not query:
                    self.send(pid, "❌ Напиши запрос"); return
                self.send(pid, f"🔮Вероятность «{query}» равна: {random.randint(0, 100)}%")
                return

            if cmd.startswith('.выбери '):
                raw = cmd[7:].strip()
                if not raw:
                    self.send(pid, "❌ Напиши варианты"); return
                options = [o.strip() for o in re.split(r',\s*|\s+или\s+', raw) if o.strip()]
                if len(options) < 2:
                    self.send(pid, "❌ Минимум 2 варианта"); return
                self.send(pid, f"🤯Выбор сделан, это: «{random.choice(options)}»")
                return

            if cmd.startswith('.сертификат '):
                target = self.get_target_user(msg, raw_text)
                if not target:
                    self.send(pid, "❌ .сертификат @user"); return
                try:
                    img_bytes = self.generate_certificate(target, self.user_name(target), self.user_name(uid))
                    upload_server = self.vk.method('photos.getMessagesUploadServer', {'peer_id': pid})
                    img_bytes.seek(0)
                    files = {'photo': ('cert.png', img_bytes.getvalue(), 'image/png')}
                    import requests as _rq
                    upload_response = _rq.post(upload_server['upload_url'], files=files).json()
                    if 'error' in upload_response:
                        self.send(pid, f"❌ {upload_response['error']['error_msg']}"); return
                    photo = self.vk.method('photos.saveMessagesPhoto', {
                        'photo': upload_response['photo'],
                        'server': upload_response['server'],
                        'hash': upload_response['hash']
                    })
                    self.vk.method('messages.send', {
                        'peer_id': pid,
                        'message': '📜 Сертификат готов:',
                        'attachment': f"photo{photo[0]['owner_id']}_{photo[0]['id']}",
                        'random_id': random.randint(1, 10**9)
                    })
                except Exception as e:
                    self.send(pid, f"❌ {e}")
                return

            if cmd.startswith('.мут '):
                if pid < 2000000000:
                    self.send(pid, "❌ Только в беседах!"); return
                target = self.get_target_user(msg, raw_text)
                if not target:
                    self.send(pid, "❌ .мут @user"); return
                if target == uid:
                    self.send(pid, "❌ Себя нельзя!"); return
                ok, err = self.mute_user(pid, target)
                self.send(pid, f"🔇 {self.user_link(target)} замучен!" if ok else f"❌ {err}")
                return

            if cmd.startswith('.размут '):
                target = self.get_target_user(msg, raw_text)
                if not target:
                    self.send(pid, "❌ .размут @user"); return
                ok, err = self.unmute_user(pid, target)
                self.send(pid, f"🔊 {self.user_link(target)} размучен!" if ok else f"❌ {err}")
                return

            if cmd == '.замученные':
                if pid < 2000000000:
                    self.send(pid, "❌ Только в беседах!"); return
                ml = self.get_muted_list(pid)
                if not ml:
                    self.send(pid, "📭 Никто не замучен."); return
                self.send(pid, "🔇 Замученные:\n" + "\n".join(self.user_link(u) for u in ml))
                return

            # ===== МУЗЫКА =====
            if cmd == 'рек':
                self.send(pid, f"{self.user_link(uid)}, выберите действие:", keyboard=self.get_rek_keyboard(uid))
                return

            if cmd.startswith('рек '):
                from config import MOODS
                parts = clean_text.split()
                q = None; mood = None
                if len(parts) > 1:
                    q = " ".join(parts[1:])
                    if parts[-1].lower() in MOODS:
                        mood = parts[-1].lower()
                        q = " ".join(parts[1:-1]) or None
                self.send_music(pid, uid, q, mood, owner_id=uid)
                return

            if cmd == 'обновить микс':
                self.send(pid, "🔄 Обновляю...")
                self.send_music(pid, uid, None, None, owner_id=uid)
                return

            if cmd.startswith('текст '):
                q = clean_text[6:].strip()
                if '/' not in q:
                    self.send(pid, f"📝 Напиши: текст {q} / (название)"); return
                a, t = q.split('/', 1)
                a, t = a.strip(), t.strip()
                if not a or not t:
                    self.send(pid, "❌ Используй: текст исполнитель / название"); return
                self.send(pid, "🔍 Ищу текст...")
                res, err = self.lyrics(a, t)
                self.send(pid, res if res else err)
                return

            # ===== RP =====
            if cmd.startswith('рп '):
                rp_text = clean_text[3:].strip()
                all_rp = self.rp_all()
                if cmd == 'рп +рандом':
                    if not all_rp:
                        self.send(pid, "❌ Нет RP"); return
                    name = random.choice(list(all_rp.keys()))
                    data = all_rp[name]
                    try:
                        members = self.vk.method('messages.getConversationMembers', {'peer_id': pid})
                        target = random.choice([m['member_id'] for m in members['items'] if m['member_id'] > 0 and m['member_id'] != uid])
                    except:
                        target = uid
                    self.rp_do(pid, uid, name, data, [target])
                    return
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
                        self.rp_do(pid, uid, name, data, [target])
                        return

            if cmd == '+топ рп':
                actions = self.rp_top()
                if actions:
                    res = "🏆 Топ RP:\n\n" + "\n".join(f"{a}: {c} раз" for a,c in sorted(actions.items(), key=lambda x: x[1], reverse=True)[:5])
                    self.send(pid, res)
                else:
                    self.send(pid, "📭 Нет данных")
                return

            # ===== БРАКИ =====
            if cmd.startswith('+брак'):
                target = self.get_target_user(msg, clean_text)
                if not target:
                    self.send(pid, "❌ Укажи пользователя"); return
                if target == uid:
                    self.send(pid, "❌ Нельзя на себе"); return
                from datetime import datetime as _dt
                date = None
                if d := re.search(r'(\d{2}\.\d{2}\.\d{4})', clean_text):
                    try: date = _dt.strptime(d.group(1), '%d.%m.%Y')
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
                    u = str(uid)
                    if u not in self.marriages or self.marriages[u]["partner"] != target:
                        self.send(pid, f"❌ Ты не в браке с {self.user_link(target)}"); return
                ok, err = self.marriage_remove(uid)
                self.send(pid, "💔 Брак расторгнут" if ok else err)
                return

            if cmd == 'мой брак':
                status = self.marriage_status(uid)
                self.send(pid, status if status else "💔 Вы не в браке"); return

            if cmd == 'обновить детей':
                updated = self.update_all_children()
                self.send(pid, f"🔄 Обновлены {updated} детей!" if updated else "✅ Все дети актуальны!")
                return

            if cmd == 'браки':
                if not self.marriages:
                    self.send(pid, "📭 Браков нет"); return
                res = "🤡Список далбаебных парочек:\n\n"
                seen = set()
                for uid_s, d in self.marriages.items():
                    if uid_s in seen: continue
                    p = str(d["partner"])
                    u, partner = int(uid_s), int(p)
                    children = self.get_children_in_marriage(u, partner)
                    res += f"💍 {self.user_link(u)} + {self.user_link(partner)} ({fmt_time(d['since'])})\n"
                    if children:
                        names = []
                        for c in children:
                            g = "👦" if c.get("gender", "male") == "male" else "👧"
                            names.append(f"{g} {c['name']} ({format_child_age(c['birthday'])})")
                        res += "   👶 " + ", ".join(names) + "\n"
                    res += "\n"
                    seen.add(uid_s); seen.add(p)
                self.send(pid, res)
                return

            # ===== БЕРЕМЕННОСТЬ =====
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
                    self.send(pid, "❌ Укажи партнера: забеременеть от @юз"); return
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
                    'message': f"🤰 {self.user_link(uid)} хочет ребенка от {self.user_link(partner)}!\n\n{self.user_link(partner)}, выбери действие:",
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
                self.send(pid, f"Имя {name} сохранено! Теперь: ребенок пол мальчик/девочка")
                return

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
                dem_text = cmd[4:].strip() or None
                self.create_demotivator(pid, uid, dem_text, event)
                return

            if cmd == 'дети':
                self.send(pid, self.get_children_list()); return

            if cmd == 'помощь семья':
                self.send(pid, self.get_family_help()); return

            # ===== СТАТИСТИКА =====
            if cmd == '+стат':
                s = self.get_user_stats(uid)
                self.send(pid, f"📊 Статистика {self.user_link(uid)}:\n\n📝 {s['text']}\n🖼️ {s['sticker']}\n🎤 {s['voice']}\n🎬 {s['video']}\n📷 {s['photo']}\n📄 {s['doc']}\n📦 {s['other']}\n📊 Всего: {s['total']}")
                return
            for stat_cmd, field, label in [
                ('+топ смс','text','сообщениям'), ('+топ стикеры','sticker','стикерам'),
                ('+топ гс','voice','голосовым'), ('+топ видео','video','видео'),
                ('+топ фото','photo','фото'), ('+топ общение','total','общению'),
                ('топ','total','общению')]:
                if cmd == stat_cmd:
                    self.send(pid, self.format_top(self.get_top_by_type(field), field, label))
                    return

            # ===== ИГРЫ =====
            if cmd.startswith('!кости'):
                target = self.get_target_user(msg, clean_text)
                if not target:
                    self.send(pid, "❌ !кости @user"); return
                if target == uid:
                    self.send(pid, "❌ Нельзя с собой!"); return
                self.send(pid, self.start_dice_game(pid, uid, target))
                return

            if cmd == 'бросок':
                if pid in self.dice_games and self.dice_games[pid].get("active", False):
                    self.send(pid, self.handle_dice_turn(pid, uid))
                else:
                    self.send(pid, "❌ Нет активной игры! !кости @user")
                return

            if cmd.startswith('!крестики') or cmd.startswith('!ttt'):
                target = self.get_target_user(msg, clean_text)
                if not target:
                    self.send(pid, "❌ !крестики @user"); return
                if target == uid:
                    self.send(pid, "❌ Нельзя с собой!"); return
                self.send(pid, self.start_ttt_game(pid, uid, target))
                return

        except Exception as e:
            print(f"❌ Критическая ошибка в handle: {e}")

    # ========== ЗАПУСК ==========
    def run(self):
        print("🤖 RP Бот запущен!")
        print(f"📱 ID сообщества: {GROUP_ID}")
        print(f"📊 Браков: {len(self.marriages)}")
        print(f"👶 Детей: {len(self.children)}")
        print(f"🤰 Беременностей: {len(self.pregnancies)}")

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