# Telegram Aggregator

The aggregator code for a Telegram channel forwards posts from selected channels to a bot, which then forwards them to the target channel.

### Before launch:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirement.txt

# Create Telethon session
python services/auth.py

# start soft
python main.py
```


Create `.env` 
```Bash
cp .env.example .env
```

```python
BOT_TOKEN= # Your bot token from @BotFather 
API_HASH= # Your api keys from my.telegram.org
API_ID=

ADMIN_ID= # Your user id (check from @userinfobot)
BOT_USERNAME=@ 
```
The code is designed for continuous operation through `PM2`.

```bash
pm2 start main.py --name "Aggregator"
pm2 save
```

The database is created in `JSON` format:

```json
{
    "sources": [
        {
            "channel": "@tessfff3", 
            "end_date": "20.09.2026 16:01"
        }
    ],
    "target": [],
    "allowed_ids": [],
    "reply_mode": true,
    "ignore_words": [],
    "target_channel": "@test_agr"
}
```


> **Warning** This code is written without the use of AI.




