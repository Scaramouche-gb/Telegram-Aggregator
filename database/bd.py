import json 
import os
import datetime
from datetime import datetime, timedelta

class Database:
    def __init__(self, filename="database/data.json"):
        self.filename = filename
        self._init_db()

    def _init_db(self):
        if not os.path.exists(self.filename):
            default_data = {
                "sources": [],
                "target": [],
                "allowed_ids": [],
                "reply_mode": [],
                "ignore_words": []
            }
            self._save(default_data)
    


    def _load(self) -> dict:
        with open(self.filename, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save(self, data: dict):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    


    def get_sources(self) -> list:
        data = self._load()
        return data.get("sources", [])
    
    def add_source(self, channel: str, days: int = None, title: str = ""):
        data = self._load()
        if days:
            end_date = (datetime.now() + timedelta(days=days)).strftime("%d.%m.%Y %H:%M")
        else:
            end_date = "Бессрочно"
            
        data["sources"].append({
            "channel": channel,
            "title": title,
            "end_date": end_date
            })
        self._save(data)

    def update_source_title(self, channel: str, title: str):
        data = self._load()
        updated = False
        for src in data.get("sources", []):
            if src["channel"] == channel:
                src["title"] = title
                updated = True
                break
        if updated:
            self._save(data)
    
    def remove_source(self, channel: str):
        data = self._load()
        data["sources"] = [s for s in data.get("sources", []) if s["channel"] != channel]
        self._save(data)


    
    def ignore_word(self, words: list):
        data = self._load()
        data["ignore_words"].extend(words)
        self._save(data)
    
    def get_ignore_words(self) -> list:
        data = self._load()
        return data.get("ignore_words", [])
    
    def add_ignore_word(self, word: str):
        data = self._load()
        if word not in data["ignore_words"]:
            data["ignore_words"].append(word)
            self._save(data)
    
    def remove_ignore_word(self, word: str):
        data = self._load()
        if word in data["ignore_words"]:
            data["ignore_words"].remove(word)
            self._save(data)


    def get_target_channel(self) -> str:
        data = self._load()
        return data.get("target_channel", "")

    def set_target_channel(self, channel: str):
        data = self._load()
        data["target_channel"] = channel
        self._save(data)
    

    def get_reply_mode(self) -> str:
        data = self._load()
        return data.get("reply_mode", "")
    
    def set_reply_mode(self, mode: str):
        data = self._load()
        data["reply_mode"] = mode
        self._save(data)


    
db = Database()
