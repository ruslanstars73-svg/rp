import os

# ========== ТОКЕНЫ ==========
BOT_TOKEN = "vk1.a.DTZN636-NBwhymUhn5PhyRwxJaTWSkW5wnPM_LyZTeqswU1kbqHZQznSn1iI9j5QVlAE72BVWlRFLvBX1PTDeFlzflyK5pvGKZUZ8e2zX-2Se8bZ0EKz5hwGeAiJhFWLoSN-v8O1ekqjT322XbG1JFLav062DJQmtF1DSsHxePXpThYxSC6VgvCJa35lcEkbpsyUhLPFnrqlFIfMjkmUlA"
USER_TOKEN = "vk1.a.r3OSNtIm7ng8dBYvs-6rs8XYCbd3nR0H519_5XKICJ1RQhevguvwJC0Vxt465Fw9m_RNYuWttX4s02fZlkimM1mN4Mrhp3DetvEQ7UHp2KIDl5m3TG-C2Ria9-NSm0a-eAw9qFAOqWBmPBR9zf2QKBfTkkAxIF0jl12fqXcW0WjCOCaAj5V5aSJ-nOkt-LktaUvbi1g1aTilfPBBsvxicg"
GROUP_ID = 241029527

# ========== ФОТО РЕБЁНКА ==========
CHILD_PHOTO_MALE = "photo-241029527_457239062"
CHILD_PHOTO_FEMALE = "photo-241029527_457239064"

# ========== ПУТИ К ДАННЫМ ==========
DATA_DIR = "data"

RP_FILE         = os.path.join(DATA_DIR, "custom_rp.json")
STATS_FILE      = os.path.join(DATA_DIR, "stats.json")
MARRIAGE_FILE   = os.path.join(DATA_DIR, "marriages.json")
CHILDREN_FILE   = os.path.join(DATA_DIR, "children.json")
PREGNANCY_FILE  = os.path.join(DATA_DIR, "pregnancies.json")
CHAT_STATS_FILE = os.path.join(DATA_DIR, "chat_stats.json")
MUTED_FILE      = os.path.join(DATA_DIR, "muted.json")

# ========== GIGACHAT ==========
GIGACHAT_AUTH_KEY   = "MDE5ZjllNTgtZTU3OC03MTg5LWE5MmMtZGRjMDhlMzNjZTg2OjVmY2NjNjIwLTE2YTgtNDYxYS04NjMwLTVmOTgxNTE4ZDE4Nw=="
GIGACHAT_CLIENT_ID  = "019f9e58-e578-7189-a92c-ddc08e33ce86"

# ========== GENIUS ==========
GENIUS_TOKEN = "FrlouGVpHz8STK7OKfq5-wsbO-kAImD9LgaWcOiWfCHNP-5RF0Q4fUs079WbCWQU"

# ========== ЖАНРЫ / НАСТРОЕНИЯ ==========
GENRES = {"рок":"rock","поп":"pop","хип-хоп":"hiphop","рэп":"rap","электроника":"electronic","танцевальная":"dance","хаус":"house","техно":"techno","транс":"trance","джаз":"jazz","блюз":"blues","классика":"classical","метал":"metal","панк":"punk","регги":"reggae","кантри":"country","фолк":"folk","инди":"indie","альтернатива":"alternative","шансон":"chanson","поп-рок":"poprock","соул":"soul","фанк":"funk","диско":"disco","лаунж":"lounge","эмбиент":"ambient","dubstep":"dubstep","drum_and_bass":"drumandbass","hardstyle":"hardstyle","psytrance":"psytrance","к-поп":"kpop","инструментальная":"instrumental","саундтрек":"soundtrack"}

MOODS = {"веселое":"happy","грустное":"sad","романтичное":"romantic","энергичное":"energetic","спокойное":"calm","меланхоличное":"melancholy","агрессивное":"aggressive","расслабленное":"relax","ночное":"night","утреннее":"morning","драйвовое":"drive","задумчивое":"thoughtful","ностальгическое":"nostalgic","вдохновляющее":"inspirational","танцевальное":"dance","мечтательное":"dreamy","эпичное":"epic","космическое":"space","зимнее":"winter"}

# ========== ДЕФОЛТНЫЕ RP ==========
DEFAULT_RP = {
    "обнять": {"vk_photo_id": "457239029", "description": "🤗 нежно обнял(а)"},
    "поцеловать": {"vk_photo_id": "457239043", "description": "💋 страстно поцеловал(а)"},
    "укусить": {"vk_photo_id": "457239039", "description": "🦷 игриво укусил(а)"},
    "погладить": {"vk_photo_id": "457239045", "description": "🤚 нежно погладил(а)"},
    "пощекотать": {"vk_photo_id": "457239034", "description": "😄 пощекотал(а)"},
    "шлепнуть": {"vk_photo_id": "457239032", "description": "✋ шлепнул(а) по попе"},
    "облизнуть": {"vk_photo_id": "457239040", "description": "👅 облизнул(а) шею"},
    "прижать": {"vk_photo_id": "457239033", "description": "🔥 прижал(а) к стене"},
    "зарычать": {"vk_photo_id": "457239038", "description": "🐺 зарычал(а) в ухо"},
    "поцеловать_в_лоб": {"vk_photo_id": "457239042", "description": "👼 поцеловал(а) в лоб"},
    "обнять_со_спины": {"vk_photo_id": "457239044", "description": "🤗 обнял(а) со спины"},
    "взъерошить": {"vk_photo_id": "457239035", "description": "💇 взъерошил(а) волосы"},
    "поцеловать_руку": {"vk_photo_id": "457239037", "description": "🤵 поцеловал(а) руку"},
    "ущипнуть": {"vk_photo_id": "457239041", "description": "✌️ ущипнул(а) за попу"},
    "шепнуть": {"vk_photo_id": "457239036", "description": "🌙 шепнул(а) на ухо"},
    "трахнуть": {"vk_photo_id": "457239046", "description": "💥 жёстко трахнул(а)"},
    "отсосать": {"vk_photo_id": "457239047", "description": "🍆 страстно отсосал(а)"},
    "кончить": {"vk_photo_id": "457239048", "description": "💦 кончил(а) на"},
    "отлизать": {"vk_photo_id": "457239049", "description": "👅 нежно отлизал(а)"},
    "растлить": {"vk_photo_id": "457239050", "description": "😈 растлил(а)"},
    "изнасиловать": {"vk_photo_id": "457239051", "description": "🔞 изнасиловал(а)"},
    "снять_трусы": {"vk_photo_id": "457239052", "description": "🩲 снял(а) трусы с"},
    "погладить_член": {"vk_photo_id": "457239053", "description": "🍌 погладил(а) член"},
    "лизать_киску": {"vk_photo_id": "457239054", "description": "🐱 лизал(а) киску"},
    "войти": {"vk_photo_id": "457239055", "description": "🚪 вошёл(а) в"},
}