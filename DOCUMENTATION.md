# 🎰 KZ CASINO BOT
## Documentation Complète v2.1
### Mise à jour: 26 Décembre 2025

---

# 📋 TABLE DES MATIÈRES

1. [Présentation](#-présentation)
2. [Économie du Casino](#-économie-du-casino)
3. [Commandes Joueurs](#-commandes-joueurs)
4. [Commandes Administrateur](#-commandes-administrateur)
5. [Jeux & Probabilités](#-jeux--probabilités)
6. [Système d'Activité](#-système-dactivité)
7. [Système de Niveaux (XP)](#-système-de-niveaux-xp)
8. [Boutique & Items](#-boutique--items)
9. [Système de Prêts](#-système-de-prêts)
10. [Paramètres Configurables](#-paramètres-configurables-odds)
11. [Statistiques & Prévisions](#-statistiques--prévisions)
12. [Installation](#-installation)

---

# 🎲 Présentation

**KZ Casino Bot** est un bot Discord de casino virtuel complet en français.

### Fonctionnalités principales
- 🎮 **6 jeux de hasard** : Coinflip, Slots, Roulette, Blackjack, Crash, Guess
- ⚔️ **3 modes PvP** : Duel, Pierre/Feuille/Ciseaux, Blackjack 1v1
- 💰 **Économie complète** : Daily, Weekly, Work, Transferts
- 📊 **Activité récompensée** : KZ gagnés en envoyant des messages et en restant en vocal
- ⭐ **Système de niveaux** : XP et progression
- 🛒 **Boutique** : Items, boosts, cosmétiques
- 🏦 **Prêts** : Système bancaire entre joueurs
- 👤 **Profils** : Personnalisables avec bannières et cadres
- 🔧 **Administration** : Contrôle total des paramètres

### Monnaie
- **KZ Coins** (monnaie virtuelle, conforme aux ToS Discord)
- Aucune valeur réelle

---

# 💰 Économie du Casino

## Paramètres par défaut

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| Solde de départ | **2,500 KZ** | À l'inscription |
| Mise minimum | **10 KZ** | Pour tous les jeux |
| Mise maximum | **1,000,000 KZ** | Pour tous les jeux |
| Taxe transfert | **2%** | Sur les transferts entre joueurs |

## Revenus passifs

| Source | Montant | Cooldown | Calcul/jour |
|--------|---------|----------|-------------|
| `/daily` | 500 KZ | 20h | ~600 KZ/jour |
| `/weekly` | 2,500 KZ | 7 jours | ~357 KZ/jour |
| `/work` | 80-220 KZ | 30 min | ~4,800 KZ/jour (max) |
| Messages | 100 KZ | /100 msgs | Variable |
| Vocal | 1,000 KZ | /heure | Variable |

### Revenus maximum théoriques (sans jouer)
- **Par jour** : ~5,750 KZ (daily + work x48)
- **Par semaine** : ~42,750 KZ (+ weekly)

---

# 🎮 Commandes Joueurs

## 💵 Économie de base

| Commande | Alias | Description | Syntaxe |
|----------|-------|-------------|---------|
| `/register` | - | Créer ton compte | `/register` |
| `/balance` | `/bal` | Voir ton solde | `/balance` |
| `/daily` | - | Bonus quotidien (+500 KZ) | `/daily` |
| `/weekly` | - | Bonus hebdo (+2,500 KZ) | `/weekly` |
| `/work` | - | Travailler (80-220 KZ) | `/work` |
| `/transfer` | `/pay` | Transférer des KZ | `/transfer @user 1000` |
| `/leaderboard` | `/lb`, `/top` | Classement | `/leaderboard` |
| `/cooldowns` | `/cd` | Voir tes cooldowns | `/cooldowns` |

## 🎰 Jeux Solo

| Commande | Alias | Description | Syntaxe |
|----------|-------|-------------|---------|
| `/coinflip` | `/cf` | Pile ou Face | `/coinflip 1000 pile` |
| `/slots` | `/sl` | Machine à sous | `/slots 500` |
| `/roulette` | `/rl` | Roulette | `/roulette 1000 rouge` |
| `/blackjack` | `/bj` | Blackjack interactif | `/blackjack 1000` |
| `/crash` | `/cr` | Crash (cash-out) | `/crash 500` |
| `/guess` | - | Deviner 1-100 | `/guess 100 50` |
| `/chest` | - | Coffre gratuit | `/chest` |

### Options de mise
```
Nombre exact : 100, 1000, 50000
All-in      : all, max, tout
```

### Options Roulette
```
Couleurs   : rouge, noir, vert (0)
Parité     : pair, impair
Moitiés    : 1-18, 19-36
Douzaines  : 1-12, 13-24, 25-36
Numéro     : 0 à 36
```

## ⚔️ Jeux PvP

| Commande | Description | Syntaxe |
|----------|-------------|---------|
| `/pvp` | Duel Attaque/Défense/All-in | `/pvp @user 1000` |
| `/rps1v1` | Pierre/Feuille/Ciseaux | `/rps1v1 @user 500` |
| `/blackjack1v1` | Blackjack en duel | `/blackjack1v1 @user 1000` |
| `/steal` | Tenter de voler | `/steal @user` |
| `/sabotage` | Saboter (bloquer + voler) | `/sabotage @user` |
| `/pvp_stats` | Tes stats PvP | `/pvp_stats` |
| `/botstats` | Stats contre le bot | `/botstats` |

## 🎁 Cadeaux

| Commande | Description | Syntaxe |
|----------|-------------|---------|
| `/gift coins` | Offrir des KZ | `/gift coins @user 1000` |
| `/gift item` | Offrir un item | `/gift item @user shield` |

## 👤 Profil

| Commande | Description | Syntaxe |
|----------|-------------|---------|
| `/profile` | Voir un profil | `/profile` ou `/profile @user` |
| `/p` | Alias profil | `/p` |
| `/profile set banner` | Définir bannière | `/profile set banner https://...` |
| `/profile set bio` | Définir bio | `/profile set bio Ma bio ici` |
| `/profile set color` | Définir couleur | `/profile set color #FF5733` |
| `/profile set reset` | Réinitialiser | `/profile set reset` |
| `/profile set removebanner` | Retirer bannière | `/profile set removebanner` |
| `/cosmetic framelist` | Voir tes cadres | `/cosmetic framelist` |
| `/cosmetic frameequip` | Équiper un cadre | `/cosmetic frameequip 1` |
| `/cosmetic frameremove` | Retirer cadre | `/cosmetic frameremove` |

## 🛒 Boutique

| Commande | Alias | Description | Syntaxe |
|----------|-------|-------------|---------|
| `/shop` | - | Ouvrir la boutique | `/shop` |
| `/inventory` | `/inv` | Ton inventaire | `/inventory` |
| `/buy` | - | Acheter un item | `/buy shield` |
| `/use` | - | Utiliser un item | `/use shield` |
| `/boosts` | - | Voir tes boosts | `/boosts` |

## 🏦 Prêts

| Commande | Description | Syntaxe |
|----------|-------------|---------|
| `/pret demander` | Demander un prêt | `/pret demander 5000` |
| `/pret proposer` | Proposer à un joueur | `/pret proposer @user 5000` |
| `/pret rembourser` | Rembourser | `/pret rembourser 1` |
| `/pret mes` | Voir tes prêts | `/pret mes` |
| `/pret actifs` | Prêts actifs | `/pret actifs` |
| `/pret attente` | Prêts en attente | `/pret attente` |
| `/pret historique` | Historique | `/pret historique` |
| `/pret annuler` | Annuler un prêt | `/pret annuler 1` |

## 📊 Activité

| Commande | Alias | Description | Syntaxe |
|----------|-------|-------------|---------|
| `/activite` | `/av` | Voir tes récompenses d'activité | `/activite` |

## 🎯 Prédictions

| Commande | Description | Syntaxe |
|----------|-------------|---------|
| `/prediction` | Faire une prédiction | `/prediction ...` |
| `/prediction_cancel` | Annuler | `/prediction_cancel` |
| `/predictions` | Voir tes prédictions | `/predictions` |

## ❓ Aide

| Commande | Description |
|----------|-------------|
| `/help` | Aide complète du bot |

---

# 🔧 Commandes Administrateur

## 💰 Gestion des joueurs

| Commande | Description | Syntaxe |
|----------|-------------|---------|
| `/give` | Donner des KZ | `/give @user 10000` |
| `/take` | Retirer des KZ | `/take @user 5000` |
| `/setbal` | Définir le solde | `/setbal @user 50000` |
| `/giveitem` | Donner un item | `/giveitem @user shield` |
| `/takeitem` | Retirer un item | `/takeitem @user shield` |
| `/givevip` | Donner du VIP | `/givevip @user 7` |
| `/giveimmunity` | Donner immunité | `/giveimmunity @user 24` |
| `/clearuser` | Reset complet | `/clearuser @user` |
| `/clearcoins` | Solde à 0 | `/clearcoins @user` |
| `/clearinv` | Vider inventaire | `/clearinv @user` |
| `/stat` | Stats d'un joueur | `/stat @user` |

## 👑 Gestion des admins

| Commande | Permission | Description | Syntaxe |
|----------|------------|-------------|---------|
| `/addadmin` | Admin | Ajouter admin | `/addadmin @user` |
| `/deladmin` | Owner | Retirer admin | `/deladmin @user` |
| `/listadmin` | Admin | Liste admins | `/listadmin` |
| `/wipeall` | Owner | Reset TOUT | `/wipeall` |

## ⭐ Gestion XP

| Commande | Description | Syntaxe |
|----------|-------------|---------|
| `/xp give` | Ajouter XP | `/xp give @user 1000` |
| `/xp remove` | Retirer XP | `/xp remove @user 500` |
| `/xp reset` | Reset XP + niveau | `/xp reset @user` |
| `/xp setlevel` | Définir niveau | `/xp setlevel @user 50` |
| `/xp info` | Voir XP joueur | `/xp info @user` |

## ⛔ Blacklist

| Commande | Description | Syntaxe |
|----------|-------------|---------|
| `/bl add` | Blacklist définitif | `/bl add @user Triche` |
| `/bl temp` | Blacklist temporaire | `/bl temp @user 24 Spam` |
| `/bl remove` | Retirer blacklist | `/bl remove @user` |
| `/bl list` | Voir la blacklist | `/bl list` |

## 📊 Paramètres /odds

| Commande | Description | Syntaxe |
|----------|-------------|---------|
| `/odds list` | Voir paramètres | `/odds list` |
| `/odds set` | Modifier | `/odds set coinflip_win_chance 0.45` |
| `/odds reset` | Reset un param | `/odds reset coinflip_win_chance` |
| `/odds reset all` | Reset TOUT | `/odds reset all` |
| `/odds help` | Aide | `/odds help` |
| `/odds gif_list` | Voir GIFs | `/odds gif_list` |
| `/odds gif_add` | Ajouter GIF | `/odds gif_add https://...` |
| `/odds gif_remove` | Supprimer GIF | `/odds gif_remove 1` |

## 📍 Gestion des salons

| Commande | Description | Syntaxe |
|----------|-------------|---------|
| `/channels allow` | Autoriser salon | `/channels allow #casino` |
| `/channels remove` | Retirer salon | `/channels remove #casino` |
| `/channels list` | Liste salons | `/channels list` |
| `/channels clear` | Reset whitelist | `/channels clear` |
| `/category allow` | Autoriser catégorie | `/category allow 123456789` |
| `/category remove` | Retirer catégorie | `/category remove 123456789` |
| `/category list` | Liste catégories | `/category list` |
| `/category clear` | Reset catégories | `/category clear` |
| `/permit add` | User autorisé partout | `/permit add @user` |
| `/permit remove` | Retirer permission | `/permit remove @user` |
| `/permit list` | Liste users | `/permit list` |

## 📋 Autres Admin

| Commande | Description | Syntaxe |
|----------|-------------|---------|
| `/panel` | Publier menu interactif | `/panel` |
| `/pret interet` | Définir taux intérêt | `/pret interet 15` |

---

# 🎯 Jeux & Probabilités

## 🪙 Coinflip

```
┌─────────────────────────────────────┐
│  COINFLIP - Pile ou Face            │
├─────────────────────────────────────┤
│  Probabilité de victoire : 48%      │
│  Payout victoire : x1.95            │
│  Avantage maison : 6.4%             │
└─────────────────────────────────────┘
```

**Exemple** : Mise 1,000 KZ
- ✅ Victoire (48%) : +950 KZ profit
- ❌ Défaite (52%) : -1,000 KZ

**EV (Expected Value)** : -64 KZ par mise de 1,000 KZ

---

## 🎰 Slots

```
┌─────────────────────────────────────┐
│  SLOTS - Machine à sous             │
├─────────────────────────────────────┤
│  Probabilité victoire : 35%         │
│                                     │
│  Distribution des gains :           │
│  • Paire (85% des wins) : x2.0      │
│  • Triple (13% des wins) : x5.0     │
│  • Jackpot 777 (2% des wins) : x10  │
│                                     │
│  Multiplicateur moyen : x2.55       │
│  Avantage maison : 10.75%           │
└─────────────────────────────────────┘
```

**Exemple** : Mise 1,000 KZ
- 🍒🍒🔔 Paire (29.75%) : +1,000 KZ
- 🍋🍋🍋 Triple (4.55%) : +4,000 KZ
- 7️⃣7️⃣7️⃣ Jackpot (0.7%) : +9,000 KZ
- ❌ Défaite (65%) : -1,000 KZ

---

## 🎡 Roulette

```
┌─────────────────────────────────────┐
│  ROULETTE                           │
├─────────────────────────────────────┤
│  Probabilité victoire : 45%         │
│  (forcée, peu importe le pari)      │
│                                     │
│  Payouts :                          │
│  • Rouge/Noir : x2                  │
│  • Pair/Impair : x2                 │
│  • 1-18 / 19-36 : x2                │
│  • Douzaines : x3                   │
│  • Numéro exact : x36               │
│  • Vert (0) : x14                   │
│                                     │
│  Avantage maison : 10%              │
└─────────────────────────────────────┘
```

---

## 🃏 Blackjack

```
┌─────────────────────────────────────┐
│  BLACKJACK                          │
├─────────────────────────────────────┤
│  Règles authentiques (vraies cartes)│
│                                     │
│  Croupier tire jusqu'à 17           │
│  Blackjack naturel : x2.5           │
│  Victoire normale : x1.95           │
│  Égalité : mise remboursée          │
│                                     │
│  Probabilité victoire : ~42-48%     │
│  (dépend de la stratégie)           │
│                                     │
│  Avantage maison : ~5-12%           │
└─────────────────────────────────────┘
```

**Actions disponibles** :
- 🎯 **Hit** : Tirer une carte
- ✋ **Stand** : Rester
- ⏬ **Double** : Doubler la mise (1 carte)
- 🏳️ **Surrender** : Abandonner (récupère 50%)

---

## 🚀 Crash

```
┌─────────────────────────────────────┐
│  CRASH                              │
├─────────────────────────────────────┤
│  Le multiplicateur monte...         │
│  Cash-out avant le crash !          │
│                                     │
│  Multiplicateur max : x20           │
│  Avantage maison : 5%               │
│                                     │
│  Plus tu attends = plus de gain     │
│  Mais plus de risque de crash !     │
└─────────────────────────────────────┘
```

---

## 🔢 Guess

```
┌─────────────────────────────────────┐
│  GUESS - Deviner un nombre (1-100)  │
├─────────────────────────────────────┤
│  Tirage aléatoire 1-100             │
│                                     │
│  • Exact (1%) : x50                 │
│  • ±1 (2%) : x10                    │
│  • ±2 (2%) : x5                     │
│  • ±3 à ±5 : Mise remboursée        │
│  • Autre : Perdu                    │
└─────────────────────────────────────┘
```

---

## 📊 Tableau récapitulatif

| Jeu | Win % | Payout | EV/mise | Avantage maison |
|-----|-------|--------|---------|-----------------|
| 🪙 Coinflip | 48% | x1.95 | **-6.4%** | ✅ |
| 🎰 Slots | 35% | x2.55 moy | **-10.75%** | ✅ |
| 🎡 Roulette | 45% | x2 | **-10%** | ✅ |
| 🃏 Blackjack | ~45% | x1.95 | **-12.25%** | ✅ |
| 🚀 Crash | Variable | Variable | **-5%** | ✅ |
| 🔢 Guess | 1-5% | x5-50 | **~-5%** | ✅ |

> **Tous les jeux ont un avantage pour la maison** = Casino équilibré

---

# 📊 Système d'Activité

## Comment ça marche

Tu gagnes des KZ automatiquement en :
- 💬 **Envoyant des messages** dans les salons autorisés
- 🎤 **Restant en vocal**

## Paramètres par défaut

### 💬 Messages
| Paramètre | Valeur |
|-----------|--------|
| Messages pour récompense | 100 |
| Récompense | 100 KZ |
| Anti-spam | 15 secondes entre chaque message comptabilisé |
| XP par message | 10 XP |

**→ Tous les 100 messages = +100 KZ + 1,000 XP**

### 🎤 Vocal
| Paramètre | Valeur |
|-----------|--------|
| Temps pour récompense | 1 heure |
| Récompense | 1,000 KZ |
| XP par minute | 4 XP |

**→ 1 heure en vocal = +1,000 KZ + 240 XP**

## Commande `/activite`

Affiche tes statistiques d'activité :
- Total de messages envoyés
- Temps total en vocal
- KZ gagnés en activité
- Progression vers la prochaine récompense
- Barre de progression visuelle

```
📊 Activité

💬 Messages
Total envoyés: 847
Récompenses obtenues: 8x (800 KZ)
Progression: 47/100
████░░░░░░ 47%
Restant: 53 messages → +100 KZ

🎤 Vocal
Temps total: 5h 23m
Récompenses obtenues: 5x (5,000 KZ)
Progression: 23m 15s/1h 0m
███░░░░░░░ 38%
Restant: 36m 45s → +1,000 KZ
🎙️ En vocal: 12m 30s

💰 Total gagné en activité
5,800 KZ
```

---

# ⭐ Système de Niveaux (XP)

## Gains d'XP

| Action | XP gagné |
|--------|----------|
| Message (activité) | +10 XP |
| Minute en vocal | +4 XP |
| Partie jouée | +25 XP |
| Victoire (jeu) | +25 XP bonus |
| Défaite (jeu) | +10 XP bonus |
| Partie PvP | +35 XP |
| Victoire PvP | +35 XP bonus |
| Défaite PvP | +15 XP bonus |

## Formule de niveau

La progression est **volontairement difficile** :
```
XP requis pour niveau N = 100 × N²
```

| Niveau | XP requis | XP total cumulé |
|--------|-----------|-----------------|
| 1 | 100 | 100 |
| 5 | 2,500 | 5,500 |
| 10 | 10,000 | 38,500 |
| 25 | 62,500 | 455,625 |
| 50 | 250,000 | 4,292,500 |
| 100 | 1,000,000 | 33,835,000 |

## Niveau maximum
- **100** (configurable via `XP_LEVEL_CAP`)

---

# 🛒 Boutique & Items

## Catégories

| Catégorie | Description |
|-----------|-------------|
| 🛡️ Protection | Boucliers, immunités |
| 👑 VIP | Avantages exclusifs |
| ⚡ Boost | Multiplicateurs temporaires |
| 🎨 Cosmetics | Cadres, titres |

## Items principaux

### 🛡️ Protection
| Item | Prix | Effet |
|------|------|-------|
| Shield | Variable | Protection contre le vol |
| Immunity | Variable | Immunité temporaire |

### 👑 VIP
| Item | Prix | Effet |
|------|------|-------|
| VIP Pass | Variable | Cooldown coffre réduit (72h → 24h) |

### ⚡ Boosts
| Item | Prix | Effet |
|------|------|-------|
| XP Boost | Variable | +50% XP pendant X heures |
| Luck Boost | Variable | +% chances de gain |

---

# 🏦 Système de Prêts

## Prêts Banque (validés par owner)

| Paramètre | Valeur |
|-----------|--------|
| Montant minimum | 100 KZ |
| Montant maximum | 50,000 KZ |
| Taux d'intérêt | 10% |
| Durée max | 14 jours |
| Durée par défaut | 7 jours |
| Prêts simultanés max | 3 |

### Fonctionnement
1. `/pret demander 5000` → Demande envoyée à l'owner
2. Owner valide ou refuse en DM
3. Si validé, tu reçois 5,000 KZ
4. Tu dois rembourser 5,500 KZ (5,000 + 10%)

## Prêts P2P (entre joueurs)

| Paramètre | Valeur |
|-----------|--------|
| Taux d'intérêt max | 30% |
| Durée max | 14 jours |

### Fonctionnement
1. `/pret proposer @user 5000` → Proposition envoyée
2. Le joueur accepte ou refuse
3. Si accepté, les KZ sont transférés
4. Remboursement avec intérêt

---

# ⚙️ Paramètres Configurables (/odds)

## 🪙 Coinflip

| Paramètre | Description | Min | Max | Défaut |
|-----------|-------------|-----|-----|--------|
| `coinflip_payout` | Multiplicateur | 1.0 | 3.0 | **1.95** |
| `coinflip_win_chance` | Probabilité victoire | 0.01 | 0.99 | **0.48** |

## 🎰 Slots

| Paramètre | Description | Min | Max | Défaut |
|-----------|-------------|-----|-----|--------|
| `slots_win_chance` | Probabilité victoire | 0.01 | 0.99 | **0.35** |
| `slots_pair_mult` | Mult paire | 1.0 | 10.0 | **2.0** |
| `slots_triple_mult` | Mult triple | 1.0 | 50.0 | **5.0** |
| `slots_jackpot_mult` | Mult jackpot 777 | 1.0 | 100.0 | **10.0** |

## 🎡 Roulette

| Paramètre | Description | Min | Max | Défaut |
|-----------|-------------|-----|-----|--------|
| `roulette_win_chance` | Probabilité victoire | 0.01 | 0.99 | **0.45** |
| `roulette_green_mult` | Mult vert (0) | 2 | 100 | **14** |

## 🔢 Guess

| Paramètre | Description | Min | Max | Défaut |
|-----------|-------------|-----|-----|--------|
| `guess_exact_mult` | Mult nombre exact | 1.0 | 500.0 | **50.0** |
| `guess_close1_mult` | Mult ±1 | 1.0 | 100.0 | **10.0** |
| `guess_close2_mult` | Mult ±2 | 1.0 | 50.0 | **5.0** |

## 🃏 Blackjack

| Paramètre | Description | Min | Max | Défaut |
|-----------|-------------|-----|-----|--------|
| `blackjack_payout` | Multiplicateur | 1.0 | 3.0 | **1.95** |

## 🚀 Crash

| Paramètre | Description | Min | Max | Défaut |
|-----------|-------------|-----|-----|--------|
| `crash_house_edge` | Avantage maison | 0.0 | 0.5 | **0.05** |
| `crash_max_mult` | Mult maximum | 1.01 | 100.0 | **20.0** |

## ⚔️ Vol & Sabotage

| Paramètre | Description | Min | Max | Défaut |
|-----------|-------------|-----|-----|--------|
| `steal_success_rate` | Chance de réussite | 0.0 | 1.0 | **0.25** |
| `steal_steal_pct` | % volé si succès | 0.01 | 0.50 | **0.10** |
| `steal_fail_penalty_pct` | Pénalité si échec | 0.0 | 0.50 | **0.05** |
| `steal_fail_penalty_min` | Pénalité min | 0 | 100000 | **10** |
| `steal_fail_penalty_max` | Pénalité max | 0 | 1000000 | **200** |
| `sabotage_success_rate` | Chance sabotage | 0.0 | 1.0 | **0.12** |
| `sabotage_steal_pct` | % volé sabotage | 0.01 | 1.0 | **0.15** |

## 💰 Économie

| Paramètre | Description | Min | Max | Défaut |
|-----------|-------------|-----|-----|--------|
| `daily_amount` | Bonus daily | 0 | 1000000 | **500** |
| `weekly_amount` | Bonus weekly | 0 | 10000000 | **2500** |
| `work_min` | Work minimum | 0 | 1000000 | **80** |
| `work_max` | Work maximum | 0 | 10000000 | **220** |
| `min_bet` | Mise minimum | 1 | 10000000 | **10** |
| `max_bet` | Mise maximum | 1 | 1000000000 | **1000000** |

## 🧑‍🤝‍🧑 PvP

| Paramètre | Description | Min | Max | Défaut |
|-----------|-------------|-----|-----|--------|
| `pvp_tax` | Taxe PvP | 0.0 | 0.9 | **0** |
| `rps_tax` | Taxe Pierre/Feuille/Ciseaux | 0.0 | 0.9 | **0** |
| `blackjack1v1_tax` | Taxe Blackjack 1v1 | 0.0 | 0.9 | **0** |
| `pvp_timeout` | Timeout défis (sec) | 10 | 600 | **60** |

## 🤖 Bot PvP

| Paramètre | Description | Min | Max | Défaut |
|-----------|-------------|-----|-----|--------|
| `bot_enabled` | Bot actif (0/1) | 0 | 1 | **1** |
| `bot_win_chance` | Chance du bot | 0.0 | 1.0 | **0.50** |
| `bot_loss_penalty` | Pénalité si perd vs bot | 0 | 1000000 | **0** |

## 🎞️ GIFs

| Paramètre | Description | Min | Max | Défaut |
|-----------|-------------|-----|-----|--------|
| `win_gifs_enabled` | GIFs victoire (0/1) | 0 | 1 | **1** |

---

# 📈 Statistiques & Prévisions

## 💸 Combien de temps pour atteindre 1 MILLION ?

### Méthode 1 : Revenus passifs uniquement (sans jouer)

| Source | Par jour | Par mois |
|--------|----------|----------|
| Daily | 600 KZ | 18,000 KZ |
| Weekly | 357 KZ | 10,710 KZ |
| Work (max) | 4,800 KZ | 144,000 KZ |
| Messages (500/jour) | 500 KZ | 15,000 KZ |
| Vocal (4h/jour) | 4,000 KZ | 120,000 KZ |
| **TOTAL** | **~10,257 KZ** | **~307,710 KZ** |

**Temps pour 1 Million** : ~3.3 mois (100 jours)

---

### Méthode 2 : Jeux avec mises fixes

⚠️ **IMPOSSIBLE** - L'EV négative garantit la faillite à long terme.

Simulation sur 10,000 joueurs avec mises de 1,000 KZ :
| Jeu | Atteint 1M | Faillite |
|-----|------------|----------|
| Coinflip | 0% | 100% |
| Slots | 0% | 100% |
| Roulette | 0% | 100% |
| Blackjack | 0% | 100% |

---

### Méthode 3 : Stratégie All-In (très risquée)

| Jeu | Chance d'atteindre 1M | Temps si chanceux |
|-----|----------------------|-------------------|
| 🪙 Coinflip | **0.57%** | ~1 minute |
| 🎡 Roulette | **0.39%** | ~1 minute |
| 🎰 Slots | **<0.1%** | ~1 minute |

**Calcul Coinflip All-In** (depuis 10,000 KZ) :
```
10,000 → 19,500 → 38,025 → 74,149 → 144,590 → 281,950 → 549,803 → 1,072,115
```
= **7 victoires d'affilée** nécessaires

Probabilité : `0.48^7 = 0.56%`

**99.5% des joueurs font faillite** avec cette stratégie !

---

### Méthode 4 : Combinaison optimale

**Stratégie recommandée** :
1. Collecter daily/weekly/work régulièrement
2. Rester en vocal pendant les sessions Discord
3. Envoyer des messages naturellement
4. Jouer occasionnellement avec des petites mises (divertissement)
5. Ne jamais all-in sur plus de 10% de son solde

**Temps estimé** : 2-4 mois avec activité régulière

---

## 📊 Tableau des chances

### Probabilité d'atteindre X KZ (depuis 10,000 KZ, all-in coinflip)

| Objectif | Wins nécessaires | Probabilité |
|----------|------------------|-------------|
| 20,000 KZ | 1 | 48% |
| 50,000 KZ | 3 | 11% |
| 100,000 KZ | 4 | 5.3% |
| 500,000 KZ | 6 | 1.2% |
| 1,000,000 KZ | 7 | 0.56% |
| 3,000,000 KZ | 9 | 0.13% |

---

## 🎰 EV par jeu (pour 100 KZ misés)

| Jeu | EV | Tu perds en moyenne |
|-----|-----|---------------------|
| 🪙 Coinflip | -6.4 KZ | 6.4 KZ |
| 🎰 Slots | -10.75 KZ | 10.75 KZ |
| 🎡 Roulette | -10 KZ | 10 KZ |
| 🃏 Blackjack | -12.25 KZ | 12.25 KZ |
| 🚀 Crash | -5 KZ | 5 KZ |

**Interprétation** : Sur 1,000 parties à 100 KZ, tu perdras en moyenne 6,400 à 12,250 KZ selon le jeu.

---

# 🛠️ Installation

## Prérequis

- Python 3.9+
- pip
- Un bot Discord créé sur le [Discord Developer Portal](https://discord.com/developers/applications)

## Installation

```bash
# Cloner ou extraire le ZIP
unzip KZ_CASINO_FINAL.zip
cd "KZ CASINO"

# Installer les dépendances
pip install -r requirements.txt

# Configurer
cp .env.example .env
nano .env  # Éditer avec ton token
```

## Configuration .env

```env
# OBLIGATOIRE
DISCORD_TOKEN=ton_token_discord_ici
OWNER_ID=ton_id_discord_ici

# OPTIONNEL (valeurs par défaut)
START_BALANCE=2500
MIN_BET=10
MAX_BET=1000000
DAILY_AMOUNT=500
WEEKLY_AMOUNT=2500
```

## Lancement

```bash
python main.py
```

## Synchronisation des commandes

Après le premier lancement, les commandes slash se synchronisent automatiquement.
Si nécessaire, redémarre le bot ou attends quelques minutes.

---

# 📝 Résumé

| Aspect | Valeur |
|--------|--------|
| Commandes totales | **108** |
| Jeux disponibles | 6 solo + 3 PvP |
| EV moyenne des jeux | -6% à -12% |
| Avantage maison | ✅ Oui (tous les jeux) |
| Temps pour 1M (passif) | ~3 mois |
| Temps pour 1M (jeux) | Quasi impossible |
| Stratégie gagnante | ❌ Aucune (comme un vrai casino) |

---

## ⚠️ Rappel important

**Ce bot utilise une monnaie virtuelle (KZ Coins) sans aucune valeur réelle.**

Le casino est conçu pour être équilibré comme un vrai casino :
- La maison gagne toujours sur le long terme
- Les jeux sont un divertissement, pas un moyen de s'enrichir
- Les revenus passifs (daily, work, activité) sont la vraie source de KZ

---

*Documentation générée le 26/12/2025*
*KZ Casino Bot v2.1*
*© 2025 - Tous droits réservés*
