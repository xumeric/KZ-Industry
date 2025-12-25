KZ Casino Bot — Version modulaire

Fichiers:
  - main.py
  - kz_casino_bot/
      config.py
      db.py
      utils.py
      checks.py
      shop_data.py
      cogs/
          economy.py
          games.py
          shop.py
          admin.py

Installation:
  pip install -U discord.py python-dotenv

.env (dans le même dossier que main.py):
  DISCORD_TOKEN=TON_TOKEN
  OWNER_ID=123456789012345678  (optionnel)
  DB_PATH=casino.db            (optionnel)

Lancer:
  python main.py

Notes:
  - Les réponses sont publiques.
  - Roulette est en mode texte: /roulette mise choix
