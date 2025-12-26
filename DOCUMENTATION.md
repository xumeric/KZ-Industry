# 🎰 KZ CASINO BOT - Documentation v2.0
## Mise à jour: 26/12/2025

---

# 📋 SOMMAIRE

1. Présentation
2. Paramètres par défaut  
3. Commandes Joueurs
4. Commandes Admin
5. Probabilités & Mathématiques
6. Temps pour 1 Million
7. Paramètres /odds
8. Installation

---

# 🎲 PRÉSENTATION

Bot Discord de casino virtuel complet en français.

**Fonctionnalités:**
- 6 jeux solo: Coinflip, Slots, Roulette, Blackjack, Crash, Guess
- 3 jeux PvP: Duel, RPS, Blackjack 1v1
- Économie: Daily, Weekly, Work, Transferts
- Récompenses d'activité: Messages + Vocal
- Boutique, Profils, Prêts, Stats

**Monnaie:** KZ Coins (virtuelle)

---

# ⚙️ PARAMÈTRES PAR DÉFAUT

## Économie
| Paramètre | Valeur |
|-----------|--------|
| Solde départ | 2,500 KZ |
| Mise min | 10 KZ |
| Mise max | 1,000,000 KZ |
| Taxe transfert | 2% |

## Cooldowns
| Commande | Gain | Cooldown |
|----------|------|----------|
| /daily | +500 KZ | 20h |
| /weekly | +2,500 KZ | 7 jours |
| /work | +80-220 KZ | 30 min |
| /chest | Variable | 72h (24h VIP) |
| /steal | 10% cible | 12h |
| /sabotage | 15% (max 8K) | 6h |

## Activité
| Type | Objectif | Gain |
|------|----------|------|
| Messages | 100 msgs | +100 KZ |
| Vocal | 1 heure | +1,000 KZ |

## Probabilités jeux
| Jeu | Win % | EV |
|-----|-------|-----|
| Coinflip | 48% | -6.4% |
| Slots | 35% | -10.75% |
| Roulette | 45% | -10% |
| Blackjack | ~45% | -12.25% |
| Crash | Variable | ~-5% |

---

# 🎮 COMMANDES JOUEURS

## 💰 Économie

| Commande | Description | Exemple |
|----------|-------------|---------|
| `/register` | Créer compte | `/register` |
| `/balance` `/bal` | Voir solde | `/bal` |
| `/daily` | Bonus quotidien | `/daily` |
| `/weekly` | Bonus hebdo | `/weekly` |
| `/work` | Travailler | `/work` |
| `/transfer` `/pay` | Transférer KZ | `/pay @user 1000` |
| `/leaderboard` `/lb` `/top` | Classement | `/lb` |
| `/cooldowns` `/cd` | Voir cooldowns | `/cd` |
| `/gift coins` | Offrir KZ | `/gift coins @user 500` |
| `/gift item` | Offrir item | `/gift item @user item` |

---

## 🎰 Jeux Solo

### Options de mise
- Nombre: `100`, `1000`, `50000`
- All-in: `all`, `max`, `tout`

---

### 🪙 Coinflip
```
/coinflip <mise> <pile|face>
/cf 1000 pile
/cf all face
```
| Param | Valeur |
|-------|--------|
| Win % | 48% |
| Payout | x1.95 |
| EV | -6.4% |

---

### 🎰 Slots
```
/slots <mise>
/sl 500
/sl all
```
| Résultat | Chance | Mult |
|----------|--------|------|
| Paire | 29.75% | x2 |
| Triple | 4.55% | x5 |
| Jackpot 777 | 0.7% | x10 |
| Défaite | 65% | x0 |

---

### 🎡 Roulette
```
/roulette <mise> <choix>
/rl 1000 rouge
/rl 500 17
```
| Pari | Syntaxe | Mult |
|------|---------|------|
| Rouge | rouge, red | x2 |
| Noir | noir, black | x2 |
| Vert | vert, green, 0 | x14 |
| Pair | pair, even | x2 |
| Impair | impair, odd | x2 |
| 1-18 | 1-18, low | x2 |
| 19-36 | 19-36, high | x2 |
| Douzaine | 1-12, 13-24, 25-36 | x3 |
| Numéro | 0 à 36 | x36 |

---

### 🃏 Blackjack
```
/blackjack <mise>
/bj 1000
/bj all
```
**Boutons:** Hit, Stand, Double

| Résultat | Payout |
|----------|--------|
| Blackjack naturel | x2.5 |
| Victoire | x1.95 |
| Égalité | x1 |
| Défaite | x0 |

---

### 🚀 Crash
```
/crash <mise>
/cr 500
```
Cash-out avant le crash !
- House Edge: 5%
- Mult max: x20

---

### 🔢 Guess
```
/guess <mise> <nombre 1-100>
/guess 100 50
```
| Résultat | Mult |
|----------|------|
| Exact | x50 |
| ±1 | x10 |
| ±2 | x5 |
| ±3 à ±5 | x1 |
| Autre | x0 |

---

### 📦 Chest
```
/chest
```
Coffre gratuit (72h cooldown, 24h VIP)

---

### 🦝 Steal
```
/steal @user
```
| Param | Valeur |
|-------|--------|
| Succès | 25% |
| Gain | 10% cible |
| Échec | -5% toi |
| Cooldown | 12h |

---

### 💣 Sabotage
```
/sabotage @user
```
| Param | Valeur |
|-------|--------|
| Coût | 100 KZ |
| Succès | 12% |
| Gain | 15% (max 8K) |
| Blocage | 60s |
| Cooldown | 6h |

---

## ⚔️ Jeux PvP

| Commande | Description |
|----------|-------------|
| `/pvp @user 1000` | Duel Attaque/Défense/All-in |
| `/rps1v1 @user 500` | Pierre/Feuille/Ciseaux |
| `/blackjack1v1 @user 1000` | Blackjack duel |
| `/pvp_stats` | Stats PvP |
| `/botstats` | Stats vs bot |

---

## 👤 Profil

| Commande | Description |
|----------|-------------|
| `/profile` `/p` | Voir profil |
| `/profile set banner <url>` | Définir bannière |
| `/profile set bio <texte>` | Définir bio |
| `/profile set color <couleur>` | Définir couleur |
| `/profile set reset` | Reset profil |
| `/profile set removebanner` | Retirer bannière |
| `/cosmetic framelist` | Voir cadres |
| `/cosmetic frameequip <id>` | Équiper cadre |
| `/cosmetic frameremove` | Retirer cadre |

---

## 🛒 Boutique

| Commande | Description |
|----------|-------------|
| `/shop` | Ouvrir boutique |
| `/inventory` `/inv` | Voir inventaire |
| `/buy <item>` | Acheter item |
| `/use <item>` | Utiliser item |
| `/boosts` | Boosts actifs |

---

## 🏦 Prêts

| Commande | Description |
|----------|-------------|
| `/pret demander <montant>` | Demander prêt banque |
| `/pret proposer @user <montant> <intérêt>` | Proposer prêt joueur |
| `/pret rembourser <slot>` | Rembourser prêt |
| `/pret mes` | Tous tes prêts |
| `/pret actifs` | Prêts actifs |
| `/pret attente` | Prêts en attente |
| `/pret historique` | Historique |
| `/pret annuler <slot>` | Annuler prêt |

Params: 100-50K KZ, 10% intérêt, 14j max, 3 slots

---

## 📊 Activité

### `/activite` ou `/av`
Voir tes récompenses d'activité.

**Affiche:**
- 💬 Messages: total, progression, restant
- 🎤 Vocal: temps, progression, restant  
- 💰 Total KZ gagné

| Type | Objectif | Gain |
|------|----------|------|
| Messages | 100 | +100 KZ |
| Vocal | 1h | +1,000 KZ |

---

## 🎯 Prédictions

| Commande | Description |
|----------|-------------|
| `/prediction` | Créer prédiction |
| `/prediction_cancel` | Annuler |
| `/predictions` | Voir prédictions |

---

## ❓ Aide
```
/help
```

---

# 🔧 COMMANDES ADMIN

## Gestion joueurs
| Commande | Description |
|----------|-------------|
| `/give @user 1000` | Donner KZ |
| `/take @user 500` | Retirer KZ |
| `/setbal @user 10000` | Définir solde |
| `/giveitem @user item` | Donner item |
| `/takeitem @user item` | Retirer item |
| `/givevip @user 7` | Donner VIP (jours) |
| `/giveimmunity @user 24` | Donner immunité (heures) |
| `/clearuser @user` | Reset complet |
| `/clearcoins @user` | Solde à 0 |
| `/clearinv @user` | Vider inventaire |
| `/stat @user` | Stats joueur |

## Gestion admins
| Commande | Description | Permission |
|----------|-------------|------------|
| `/addadmin @user` | Ajouter admin | Admin |
| `/deladmin @user` | Retirer admin | Owner |
| `/listadmin` | Liste admins | Admin |
| `/wipeall` | Reset TOUT | Owner |

## Gestion XP
| Commande | Description |
|----------|-------------|
| `/xp give @user 500` | Ajouter XP |
| `/xp remove @user 200` | Retirer XP |
| `/xp reset @user` | Reset XP |
| `/xp setlevel @user 10` | Définir niveau |
| `/xp info @user` | Voir XP |

## Blacklist
| Commande | Description |
|----------|-------------|
| `/bl add @user raison` | Ban définitif |
| `/bl temp @user 24 raison` | Ban temporaire |
| `/bl remove @user` | Retirer ban |
| `/bl list` | Voir blacklist |

## Paramètres /odds
| Commande | Description |
|----------|-------------|
| `/odds list` | Voir paramètres |
| `/odds set param valeur` | Modifier |
| `/odds reset param` | Reset un |
| `/odds reset all` | Reset tout |
| `/odds help` | Aide |
| `/odds gif_list` | Voir GIFs |
| `/odds gif_add url` | Ajouter GIF |
| `/odds gif_remove id` | Supprimer GIF |

## Gestion salons
| Commande | Description |
|----------|-------------|
| `/channels allow` | Autoriser salon |
| `/channels remove` | Retirer salon |
| `/channels list` | Liste salons |
| `/channels clear` | Vider liste |
| `/category allow` | Autoriser catégorie |
| `/category remove` | Retirer catégorie |
| `/category list` | Liste catégories |
| `/permit add @user` | Autoriser user partout |
| `/permit remove @user` | Retirer autorisation |
| `/permit list` | Liste autorisés |

## Autres
| Commande | Description |
|----------|-------------|
| `/panel` | Menu interactif public |
| `/pret interet 15` | Taux intérêt banque |

---

# 📈 PROBABILITÉS & MATHS

## Expected Value (EV)
```
EV = P(win) × Gain - P(lose) × Mise
```

| Jeu | Win % | Payout | EV | Perte/1000 KZ |
|-----|-------|--------|-----|---------------|
| Coinflip | 48% | x1.95 | -6.4% | -64 KZ |
| Slots | 35% | x2.55 | -10.75% | -107 KZ |
| Roulette | 45% | x2 | -10% | -100 KZ |
| Blackjack | 45% | x1.95 | -12.25% | -122 KZ |
| Crash | Var | Var | ~-5% | ~-50 KZ |

**→ La maison gagne toujours !**

---

# ⏱️ TEMPS POUR 1 MILLION

## Depuis 10,000 KZ

### Mises fixes: IMPOSSIBLE
- Probabilité: 0%
- Faillite garantie

### Stratégie All-In
| Jeu | Chance | Temps |
|-----|--------|-------|
| Coinflip | 0.57% | ~1 min |
| Roulette | 0.39% | ~1 min |

**⚠️ 99.5% font faillite !**

### Calcul All-In Coinflip
```
10K → 19.5K → 38K → 74K → 144K → 282K → 550K → 1.07M
```
7 wins d'affilée = 0.56% de chance

---

## Revenus passifs /jour
| Source | Gain |
|--------|------|
| Daily | 500 KZ |
| Weekly | 357 KZ/jour |
| Work (10x) | 1,500 KZ |
| Messages | 200 KZ |
| Vocal (2h) | 2,000 KZ |
| **TOTAL** | **~4,500 KZ** |

**Temps pour 1M: ~222 jours (7 mois)**

---

# 🎛️ PARAMÈTRES /odds

## Jeux
| Param | Min | Max | Défaut |
|-------|-----|-----|--------|
| coinflip_win_chance | 0.01 | 0.99 | 0.48 |
| coinflip_payout | 1.0 | 3.0 | 1.95 |
| slots_win_chance | 0.01 | 0.99 | 0.35 |
| slots_pair_mult | 1.0 | 10.0 | 2.0 |
| slots_triple_mult | 1.0 | 50.0 | 5.0 |
| slots_jackpot_mult | 1.0 | 100.0 | 10.0 |
| roulette_win_chance | 0.01 | 0.99 | 0.45 |
| roulette_green_mult | 2 | 100 | 14 |
| blackjack_payout | 1.0 | 3.0 | 1.95 |
| crash_house_edge | 0.01 | 0.20 | 0.05 |
| crash_max_mult | 10 | 1000 | 20 |
| guess_exact_mult | 10 | 100 | 50 |
| guess_close1_mult | 2 | 50 | 10 |
| guess_close2_mult | 1.5 | 25 | 5 |

## Économie
| Param | Min | Max | Défaut |
|-------|-----|-----|--------|
| daily_amount | 100 | 10000 | 500 |
| weekly_amount | 500 | 50000 | 2500 |
| work_min | 10 | 1000 | 80 |
| work_max | 50 | 5000 | 220 |
| min_bet | 1 | 1000 | 10 |
| max_bet | 1000 | 10000000 | 1000000 |

## Vol
| Param | Min | Max | Défaut |
|-------|-----|-----|--------|
| steal_success_rate | 0.1 | 0.9 | 0.25 |
| steal_steal_pct | 0.05 | 0.5 | 0.10 |
| steal_fail_penalty_pct | 0.01 | 0.3 | 0.05 |

---

# 🛠️ INSTALLATION

## Prérequis
- Python 3.9+
- discord.py 2.0+

## Installation
```bash
cd "KZ CASINO"
pip install -r requirements.txt
cp .env.example .env
nano .env
```

## .env
```env
DISCORD_TOKEN=ton_token
OWNER_ID=ton_id
```

## Lancement
```bash
python main.py
```

---

# 📊 RÉSUMÉ

| Stat | Valeur |
|------|--------|
| Commandes | 100+ |
| Jeux solo | 6 |
| Jeux PvP | 3 |
| EV moyenne | -6% à -12% |
| Chance 1M | <1% |
| Revenus passifs | ~4,500 KZ/jour |
| Temps 1M passif | ~7 mois |

**La maison gagne toujours !** 🎰

---

*KZ Casino Bot v2.0 - 26/12/2025*
