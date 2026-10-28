# Solitaire Klondike — Assistant de Résolution

Application web locale qui aide l'utilisateur à résoudre une partie de solitaire Klondike.
L'application ne remplace pas le jeu réel : elle recommande des coups que l'utilisateur exécute sur son propre jeu.

## 🎴 Fonctionnalités

- **Saisie initiale guidée** : sélection visuelle des 7 cartes visibles et des 24 cartes de la pioche
- **Moteur de règles complet** : Klondike standard avec pioche 1 par 1, retournements illimités
- **Solveur intelligent** : recherche en profondeur avec mémorisation d'états et heuristiques
- **Recommandations classées** : victoires prioritaires, puis révélations de cartes cachées, libérations de colonnes
- **Suivi de partie réelle** : confirmation des coups, identification des cartes révélées
- **Historique complet** : annulation/rétablissement, corrections
- **Limite de 200 secondes** de calcul actif (ne compte pas le temps utilisateur)
- **Navigation dans les solutions** : précédent/suivant/lecture automatique/pause

## 🔧 Prérequis

- **Python 3.10+** installé et accessible dans le PATH
- **Navigateur web** moderne (Chrome, Firefox, Edge)
- **Windows** (testé sur Windows 10/11)

## 🚀 Installation et lancement

### Option 1 : Script automatique (recommandé)

- **Sous Windows (Double-clic ou Invite de commandes CMD) :**
  ```cmd
  solitaire_setup_and_run.cmd
  ```

- **Sous PowerShell :**
  ```powershell
  .\solitaire_setup_and_run.ps1
  ```

Le script vérifie Python, installe les dépendances dans `.venv`, valide les tests, lance le serveur et ouvre le navigateur sur `http://localhost:5055`.

### Option 2 : Lancement direct en ligne de commande

- **Depuis PowerShell :**
  ```powershell
  .\.venv\Scripts\python.exe app.py
  ```

- **Depuis l'Invite de commandes (CMD) :**
  ```cmd
  .venv\Scripts\python.exe app.py
  ```

### Accès à l'application

Ouvrez votre navigateur à l'adresse : **http://localhost:5055**

Appuyez sur `Ctrl+C` dans le terminal pour arrêter le serveur.

## 📁 Structure du projet

```
solitaire-klondike/
├── app.py                  # Point d'entrée Flask (serveur web + API REST)
├── backend/
│   ├── __init__.py
│   ├── cards.py            # Représentation des cartes (Card, CardStack)
│   ├── game_state.py       # État du jeu (colonnes, fondations, pioche, défausse)
│   ├── rules.py            # Moteur de règles et validation des coups
│   ├── inventory.py        # Inventaire central des 52 cartes
│   ├── history.py          # Historique, annulation et restauration
│   └── solver.py           # Solveur (DFS + mémorisation + heuristiques)
├── frontend/
│   ├── index.html          # Interface web principale
│   ├── css/
│   │   └── style.css       # Feuille de style
│   ├── js/
│   │   └── app.js          # Logique JavaScript frontend
│   └── assets/             # Ressources visuelles
├── tests/
│   ├── __init__.py
│   ├── test_cards.py       # Tests cartes et représentation
│   ├── test_game_state.py  # Tests état du jeu
│   ├── test_rules.py       # Tests règles et validation
│   ├── test_inventory.py   # Tests inventaire
│   ├── test_history.py     # Tests historique et annulation
│   └── test_solver.py      # Tests solveur
├── requirements.txt        # Dépendances Python
├── solitaire_setup_and_run.cmd  # Script de lancement Windows
├── CAHIER_DES_CHARGES.md   # Spécification complète
└── README.md               # Ce fichier
```

## 🏗️ Architecture

### Backend (Python + Flask)

- **Flask** sert l'interface web et expose une API REST JSON
- Le moteur de règles (`rules.py`) valide chaque coup selon les règles du Klondike
- L'inventaire (`inventory.py`) garantit qu'aucune carte n'est en double
- L'historique (`history.py`) permet l'annulation et la correction
- Le solveur (`solver.py`) explore les séquences de coups en background

### Frontend (HTML/CSS/JavaScript vanilla)

- Interface responsive, rendu visuel des cartes avec symboles Unicode
- Communication asynchrone avec le backend via `fetch()`
- Sélecteur visuel de 52 cartes pour la configuration et les révélations

### API REST

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/init` | POST | Initialiser une partie |
| `/api/state` | GET | État courant |
| `/api/move` | POST | Exécuter un coup |
| `/api/draw` | POST | Piocher une carte |
| `/api/reset-stock` | POST | Retourner la défausse |
| `/api/reveal` | POST | Identifier une carte révélée |
| `/api/solve` | POST | Lancer la recherche |
| `/api/solver-status` | GET | Progression du solveur |
| `/api/stop-solver` | POST | Arrêter la recherche |
| `/api/results` | GET | Résultats du solveur |
| `/api/confirm-move` | POST | Confirmer un coup recommandé |
| `/api/undo` | POST | Annuler le dernier coup |
| `/api/redo` | POST | Rétablir |
| `/api/history` | GET | Historique des actions |
| `/api/available-cards` | GET | Cartes non assignées |

## 🧠 Algorithme de résolution

Le solveur utilise une **recherche en profondeur (DFS) avec mémorisation d'états** :

1. **Mémorisation** : chaque état du jeu est hashé pour éviter de revisiter des configurations identiques
2. **Heuristiques de classement** (pas des probabilités) :
   - Cartes aux fondations : priorité maximale
   - Révélation de cartes cachées
   - Libération de colonnes
   - Accessibilité des cartes utiles
3. **Ordonnancement des coups** : fondations > révélations > libérations > pioche
4. **Budget** : 200 secondes de calcul actif, arrêt propre avec conservation des résultats partiels
5. **Multi-solutions** : recherche de plusieurs séquences gagnantes distinctes

### Limites connues

- Le solveur ne peut pas résoudre complètement une partie lorsque des cartes cachées dans les colonnes ont une identité inconnue (il s'arrête au point de révélation)
- La recherche exhaustive de l'espace des états est impossible pour la plupart des distributions (l'espace est trop grand)
- Un dépassement du délai de 200 secondes ne signifie **pas** que la partie est impossible
- Les scores heuristiques ne sont **pas** des probabilités de victoire

## 📋 Règles du Klondike implémentées

- 7 colonnes (1 à 7 cartes), seule la carte du dessus est visible initialement
- Déplacements par alternance rouge/noir et ordre décroissant
- Seul un roi (ou une séquence commençant par un roi) peut occuper une colonne vide
- Fondations : As → Roi par couleur, irréversible
- Pioche : 1 carte à la fois, retournements illimités
- Retournement de la défausse : l'ordre est inversé (le dessus de la défausse devient le dessous de la nouvelle pioche)

## 🧪 Tests

Exécuter les tests :

```cmd
.venv\Scripts\activate.bat
python -m pytest tests/ -v --tb=short
```

Avec couverture :

```cmd
python -m pytest tests/ -v --cov=backend --cov-report=term-missing
```

## ⚙️ Dépendances

| Package | Version | Rôle |
|---------|---------|------|
| Flask | 3.1.1 | Serveur web et API |
| flask-cors | 5.0.1 | Gestion CORS |
| pytest | 8.3.4 | Tests automatisés |
| pytest-cov | 6.0.0 | Couverture de tests |

Aucun service cloud payant n'est requis. L'application fonctionne entièrement en local.

## 📝 Évolutions futures possibles

- Saisie d'une partie déjà commencée
- Variantes (Klondike 3 cartes, Spider, FreeCell)
- Déploiement en ligne
- Sauvegarde/chargement de parties
- Amélioration du solveur (algorithmes Monte Carlo, A*)
