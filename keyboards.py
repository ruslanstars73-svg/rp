import json


class KeyboardMixin:
    def get_main_keyboard(self):
        return json.dumps({
            "one_time": False,
            "buttons": [
                [{"action": {"type": "text", "label": "💍 Браки"}, "color": "secondary"},
                 {"action": {"type": "text", "label": "🎲 Рп +рандом"}, "color": "secondary"}],
                [{"action": {"type": "text", "label": "📊 Статус"}, "color": "secondary"},
                 {"action": {"type": "text", "label": "🏆Топ"}, "color": "secondary"}]
            ]
        }, ensure_ascii=False)

    def get_rek_keyboard(self, owner_id):
        return json.dumps({
            "inline": True,
            "buttons": [
                [{"action": {"type": "callback", "label": "🔄 Обновить лист", "payload": {"action": "update_list", "owner": owner_id}}, "color": "secondary"}],
                [{"action": {"type": "callback", "label": "🔄 Обновить микс", "payload": {"action": "update_mix", "owner": owner_id}}, "color": "secondary"}]
            ]
        }, ensure_ascii=False)

    def get_music_keyboard(self, owner_id):
        return json.dumps({
            "inline": True,
            "buttons": [
                [{"action": {"type": "callback", "label": "🔄 Обновить лист", "payload": {"action": "update_list", "owner": owner_id}}, "color": "primary"}],
                [{"action": {"type": "callback", "label": "🔄 Обновить микс", "payload": {"action": "update_mix", "owner": owner_id}}, "color": "primary"}]
            ]
        }, ensure_ascii=False)

    def get_empty_keyboard(self):
        return json.dumps({"buttons": []}, ensure_ascii=False)

    def get_dice_keyboard(self):
        return json.dumps({
            "one_time": False,
            "buttons": [[{"action": {"type": "text", "label": "🎲 Бросок"}, "color": "positive"}]]
        }, ensure_ascii=False)

    def get_child_status_keyboard(self, user_id):
        return json.dumps({
            "inline": True,
            "buttons": [
                [
                    {"action": {"type": "callback", "label": "🍼 Покормить", "payload": {"action": "feed", "user": user_id}}},
                    {"action": {"type": "callback", "label": "🎮 Поиграть", "payload": {"action": "play", "user": user_id}}}
                ],
                [
                    {"action": {"type": "callback", "label": "😴 Уложить", "payload": {"action": "sleep", "user": user_id}}},
                    {"action": {"type": "callback", "label": "💊 Лечить", "payload": {"action": "treat", "user": user_id}}}
                ]
            ]
        }, ensure_ascii=False)

    def get_ttt_keyboard(self, board, game_id):
        buttons = []
        for i in range(3):
            row = []
            for j in range(3):
                idx = i * 3 + j
                cell = board[idx]
                if cell == "X":
                    label, color = "❌", "negative"
                elif cell == "O":
                    label, color = "⭕", "primary"
                else:
                    label, color = "▪️", "secondary"
                row.append({"action": {"type": "callback", "label": label, "payload": {"ttt": game_id, "pos": idx}}, "color": color})
            buttons.append(row)
        return json.dumps({"inline": True, "buttons": buttons}, ensure_ascii=False)