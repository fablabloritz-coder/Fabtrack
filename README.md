<p align="center">
  <img src="static/img/Fabtrack%20(clair).png" alt="FabTrack Logo" height="80">
</p>

<h1 align="center">FabTrack</h1>

<p align="center">
  <strong>Application de suivi des consommations du Fablab Loritz</strong><br>
  Flask · SQLite · Bootstrap 5.3 · Chart.js
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/flask-3.1-green?logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/bootstrap-5.3-purple?logo=bootstrap" alt="Bootstrap">
  <img src="https://img.shields.io/badge/license-MIT-orange" alt="License">
</p>

---

## 📋 Présentation

**FabTrack** est une application web locale permettant de suivre et analyser les consommations de matériaux et l'utilisation des machines d'un Fablab. Elle remplace un suivi par tableur Google Sheets par une interface moderne, rapide et entièrement autonome (aucune dépendance cloud).

### Fonctionnalités principales

| Module | Description |
|--------|-------------|
| **Saisie** | Formulaire rapide avec sélection visuelle du type d'activité, auto-complétion des champs |
| **Historique** | Tableau paginé avec filtres (date, type, machine, classe), modification et suppression inline |
| **Statistiques** | Tableaux de bord interactifs avec Chart.js (répartition, timeline, top machines/classes) |
| **Paramètres** | CRUD complet pour machines, matériaux, types d'activité, classes, référents, salles, préparateurs, images, champs personnalisés |
| **État machines** | Suivi de l'état des machines : Disponible / En réparation / Hors service |
| **Calculateur** | Calcul de surface (rectangle, cercle, triangle) avec presets papier A0-A5 et zones machines |
| **Import / Export** | Export CSV complet/filtré, gabarits d'import, import CSV en masse |

---

## 🖼️ Aperçu

L'interface utilise un thème **orange/ambre** avec Bootstrap 5.3 et supporte le **mode sombre**.

---

## 🚀 Installation

### Prérequis

- Python 3.10 ou supérieur
- pip

### Installation rapide (Windows)

Double-cliquez sur les scripts `.bat` fournis :

| Script | Rôle |
|--------|------|
| **`installer.bat`** | Crée le venv, installe les dépendances et prépare les dossiers |
| **`lancer.bat`** | Libère le port 5555 si occupé, lance le serveur et ouvre le navigateur |

### Installation manuelle

```bash
# Cloner le dépôt
git clone https://github.com/fablabloritz-coder/Fabtrack.git
cd Fabtrack

# Créer un environnement virtuel
python -m venv .venv

# Activer l'environnement
# Windows :
.venv\Scripts\activate
# macOS/Linux :
source .venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python app.py
```

L'application démarre sur **http://localhost:5555**

> La base de données SQLite (`fabtrack.db`) est créée automatiquement au premier lancement avec les données de référence pré-remplies.

---

## 🏗️ Architecture

```
Fabtrack/
├── app.py                  # Routes Flask et API REST
├── models.py               # Schéma SQLite, migrations, données de référence, démo
├── requirements.txt        # Dépendances Python
├── installer.bat           # Script d'installation Windows (venv + dépendances)
├── lancer.bat              # Script de lancement Windows (kill port + serveur)
├── fabtrack.db             # Base SQLite (générée automatiquement)
├── static/
│   ├── css/
│   │   ├── style.css       # Thème principal (orange/ambre)
│   │   └── dark-mode.css   # Surcharges mode sombre
│   ├── img/                # Logos et images matériaux
│   └── uploads/            # Images uploadées (entités)
└── templates/
    ├── base.html           # Layout avec navbar, dark mode, toasts
    ├── index.html          # Page de saisie
    ├── historique.html      # Historique paginé
    ├── statistiques.html    # Tableaux de bord
    ├── parametres.html      # Gestion des données de référence + champs perso
    ├── etat_machines.html   # État des machines (disponible / réparation / HS)
    ├── calculateur.html     # Calculateur de surface
    └── export.html          # Import / Export, démo, réinitialisation
```

---

## ⚙️ Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | Flask 3.1 (Python) |
| Base de données | SQLite 3 |
| Frontend | Bootstrap 5.3.2 + Bootstrap Icons 1.11.2 |
| Graphiques | Chart.js 4.4.7 |
| Polices | Inter (Google Fonts) |
| Serveur | Werkzeug (dev) — port 5555 |

Aucune dépendance npm, aucun build nécessaire. Toutes les librairies front sont chargées via CDN.

---

## 🛠️ Machines du Fablab Loritz

L'application est pré-configurée avec les 13 machines du Fablab :

| Machine | Type | Quantité |
|---------|------|----------|
| Creality CR10-S | Impression 3D | ×2 |
| Creality Ender 3 | Impression 3D | ×1 |
| Raise 3D Pro | Impression 3D | ×1 |
| Raise 3D Pro 2 | Impression 3D | ×1 |
| Raise 3D Pro 3 | Impression 3D | ×1 |
| Creabot D600 | Impression 3D | ×1 |
| Grande Strato | Découpe Laser | ×1 |
| Petite Strato | Découpe Laser | ×1 |
| JAMP 78 Moy | CNC / Fraisage | ×1 |
| Formech 300XQ | Thermoformage | ×1 |
| Kyocera | Impression Papier | ×1 |
| Epson Eco-tank | Impression Papier | ×1 |
| Traceur HP | Impression Papier | ×1 |

Chaque machine dispose d'une **fiche technique** : marque, zone de travail, puissance, description.

---

## 📊 Types d'activité

| Type | Icône | Unité par défaut |
|------|-------|------------------|
| Impression 3D | 🖨️ | Grammes (g) |
| Découpe Laser | ⚡ | Mètres carrés (m²) |
| CNC / Fraisage | ⚙️ | Mètres carrés (m²) |
| Impression Papier | 📄 | Feuilles |
| Thermoformage | 🔥 | Pièces |
| Bricolage | 🔧 | — |
| Broderie | 🧵 | — |

Les types sont entièrement personnalisables (ajout, modification, suppression) depuis la page Paramètres.

---

## 👥 Catégories de référents

Les référents ne sont plus limités aux professeurs :

- 👨‍🏫 **Professeur**
- 🔧 **Agent technique**
- 🏢 **Demande extérieure**
- 📋 **Administration**
- 📌 **Autre**

---

## 📈 Statistiques harmonisées

La statistique **« Surface découpe »** combine automatiquement les surfaces consommées en **Découpe Laser** et **CNC / Fraisage** pour une vue unifiée de la consommation de matériaux en plaques.

---

## 📐 Calculateur de surface

Page dédiée accessible depuis la navbar, permettant de :

- Calculer la surface de 3 formes : **rectangle**, **cercle**, **triangle**
- Travailler en **mm**, **cm** ou **m** avec conversion automatique
- Utiliser des **presets** papier (A0 à A5)
- Remplir rapidement avec les **zones de travail** des machines
- Conserver un **historique** des calculs (localStorage)
- Envoyer la surface calculée directement dans le **formulaire de saisie**

---

## 📥 Import / Export

### Export
- **CSV complet** : toutes les consommations
- **CSV filtré** : par période et type d'activité
- **Statistiques** : résumé chiffré

### Import
- **Gabarits CSV** téléchargeables pour 6 entités (machines, matériaux, classes, référents, salles, préparateurs)
- **Import CSV** en masse avec détection automatique du séparateur (`;`)
- Format compatible Excel (BOM UTF-8)

---

## 🧪 Base de démonstration

Depuis la page **Export** :

- **Générer une démo** : crée ~150 consommations fictives réalistes réparties sur 6 mois, avec des référents diversifiés (13 personnes de différentes catégories)
- **Réinitialiser** : supprime toutes les données et recrée les tables vierges avec les données de référence. Nécessite de taper `REINITIALISER` en majuscules pour confirmer.

---

## 🔌 API REST

Toutes les données sont accessibles via une API JSON :

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/reference` | Données de référence (machines, matériaux, etc.) |
| `GET` | `/api/consommations` | Liste paginée avec filtres |
| `POST` | `/api/consommations` | Créer une consommation |
| `PUT` | `/api/consommations/<id>` | Modifier une consommation |
| `DELETE` | `/api/consommations/<id>` | Supprimer une consommation |
| `GET` | `/api/stats/summary` | Résumé statistique |
| `GET` | `/api/stats/timeline` | Données timeline pour graphiques |
| `GET` | `/api/export/csv` | Télécharger CSV |
| `GET` | `/api/template/<entity>` | Télécharger gabarit CSV |
| `POST` | `/api/import/<entity>` | Importer un CSV |
| `POST` | `/api/<entity>/mass-delete` | Suppression de masse |
| `POST` | `/api/demo/generate` | Générer données démo |
| `POST` | `/api/reset` | Réinitialiser la base |

CRUD complet disponible pour : `types_activite`, `machines`, `materiaux`, `classes`, `referents`, `salles`, `preparateurs`.

### Endpoints ajoutés (Phase 4)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `PUT` | `/api/<entity>/<id>` | Modifier une entité existante |
| `GET` | `/api/<entity>/<id>/usage-count` | Nombre de saisies liées (sécurité suppression) |
| `POST` | `/api/<entity>/<id>/replace-and-delete` | Remplacer les dépendances puis supprimer |
| `POST` | `/api/upload-image` | Upload d'image pour une entité |
| `PUT` | `/api/machines/<id>/statut` | Changer le statut d'une machine |
| `GET/POST` | `/api/custom-fields` | CRUD champs personnalisés |
| `PUT/DELETE` | `/api/custom-fields/<id>` | Modifier / supprimer un champ personnalisé |
| `GET/POST` | `/api/custom-field-values/<type>/<id>` | Valeurs des champs personnalisés |

---

## 🔧 État des machines

Page dédiée accessible depuis la navbar, permettant de :

- Visualiser toutes les machines avec leur **statut** en temps réel
- Basculer entre 3 états : ✅ **Disponible** / 🔧 **En réparation** / ❌ **Hors service**
- Filtrer par type d'activité
- Les machines **indisponibles** sont automatiquement masquées dans le formulaire de saisie

---

## 🖼️ Images et champs personnalisés

- **Images** : chaque entité (machine, matériau, type d'activité, référent, préparateur) peut avoir une image uploadée localement
- **Champs personnalisés** : onglet dédié dans Paramètres pour ajouter des champs supplémentaires (texte, nombre, liste, date) à n'importe quelle entité
- **Suppression sécurisée** : vérification des dépendances avant suppression, avec option de remplacement

---

## 🌙 Mode sombre

Basculez entre mode clair et sombre via le bouton 🌙/☀️ dans la navbar. Le choix est sauvegardé dans le localStorage.

---

## 📝 Licence

MIT — Fablab Loritz © 2025
