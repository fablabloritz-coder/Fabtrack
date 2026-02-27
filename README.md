<p align="center">
  <img src="static/img/Fabtrack%20(clair).png" alt="FabTrack Logo" height="80">
</p>

<h1 align="center">FabTrack</h1>

<p align="center">
  <strong>Application de suivi des consommations pour Fablabs</strong><br>
  Flask · SQLite · Bootstrap 5.3 · Chart.js
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/flask-3.1-green?logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/bootstrap-5.3-purple?logo=bootstrap" alt="Bootstrap">
  <img src="https://img.shields.io/badge/sqlite-3-lightblue?logo=sqlite" alt="SQLite">
  <img src="https://img.shields.io/badge/license-MIT-orange" alt="License">
</p>

---

## 📋 Présentation

**FabTrack** est une application web locale de suivi et d'analyse des consommations de matériaux et de l'utilisation des machines d'un Fablab. Elle remplace un suivi par tableur par une interface moderne, rapide et entièrement autonome — **aucune dépendance cloud**.

La base de données par défaut est livrée **neutre** : les machines et matériaux sont pré-configurés, mais les classes, préparateurs et référents sont vides pour que chaque fablab puisse personnaliser son installation.

<img width="1918" height="917" alt="image" src="https://github.com/user-attachments/assets/9b3909b6-e80c-4fb3-865d-842a234fcd8d" />
<img width="1917" height="689" alt="image" src="https://github.com/user-attachments/assets/d049cb31-1f66-4347-95c5-0db0bbd8fe4a" />
<img width="1918" height="915" alt="image" src="https://github.com/user-attachments/assets/c6623aae-9cbb-4d57-b3d5-5b198000b03b" />



---

## ✨ Fonctionnalités

| Module | Description |
|--------|-------------|
| **Saisie multi-action** | Formulaire dynamique : informations projet (date, intitulé, classe, référent) + N actions indépendantes (type, machine, matériau, champs spécifiques) enregistrées en une seule requête |
| **Historique** | Tableau paginé avec filtres combinables (date, type, machine, classe, référent), modification et suppression inline |
| **Statistiques** | Tableaux de bord Chart.js : répartition par type, timeline, top machines/classes, activité journalière (par heure, jour de semaine, préparateur), détail impression papier (Couleur/N&B) |
| **État des machines** | Suivi temps réel : ✅ Disponible / 🔧 En réparation / ❌ Hors service, avec notes permanentes et raison de réparation |
| **Calculateur** | Calcul de surface (rectangle, cercle, triangle) avec presets papier A0–A5, zones machine, et envoi direct vers le formulaire de saisie |
| **Paramètres** | CRUD complet pour toutes les entités, images uploadées, champs personnalisés, slider taille icônes, informations du fablab personnalisables |
| **Import / Export** | Export CSV complet ou filtré (BOM UTF-8 + `;`), gabarits d'import, import CSV en masse |
| **Sauvegarde & Restauration** | Sauvegardes automatiques (journalières/hebdomadaires) ou manuelles au format `.fabtrack`, chemin personnalisable (serveur réseau, disque externe…), export/import entre instances |
| **Démonstration** | Génération de ~150 consommations fictives réalistes avec classes, préparateurs et référents fictifs |

---

## 🚀 Installation

### Prérequis

- **Python 3.10** ou supérieur
- **pip** (inclus avec Python)

### Installation rapide (Windows)

| Script | Rôle |
|--------|------|
| `installer.bat` | Crée le venv, installe les dépendances, prépare les dossiers |
| `lancer.bat` | Libère le port 5555 si occupé, lance le serveur et ouvre le navigateur |

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

L'application démarre sur **http://localhost:5555**. La base SQLite est créée automatiquement au premier lancement avec les machines et matériaux pré-configurés.

---

## 🏗️ Architecture

```
Fabtrack/
├── app.py                  # Application Flask — routes, API REST, backups
├── models.py               # Schéma SQLite, migrations, seed, démo
├── requirements.txt        # Dépendances Python (Flask, Werkzeug)
├── installer.bat           # Script d'installation Windows
├── lancer.bat              # Script de lancement Windows
├── fabtrack.db             # Base SQLite (générée automatiquement)
├── backup_config.json      # Configuration sauvegardes (généré)
├── backups/                # Sauvegardes .fabtrack (ou chemin personnalisé)
├── static/
│   ├── css/
│   │   ├── style.css       # Thème principal (orange/ambre)
│   │   └── dark-mode.css   # Surcharges mode sombre
│   ├── img/                # Logos et images matériaux
│   └── uploads/            # Images uploadées (entités)
└── templates/
    ├── base.html           # Layout, navbar, dark mode, toasts, escHtml()
    ├── index.html          # Saisie multi-action
    ├── historique.html      # Historique paginé + filtres
    ├── statistiques.html    # Tableaux de bord Chart.js
    ├── parametres.html      # Gestion référentiels + champs personnalisés
    ├── etat_machines.html   # État des machines (statut, notes, réparation)
    ├── calculateur.html     # Calculateur de surface
    └── export.html          # Import/Export CSV, sauvegarde, démo, réinitialisation
```

### Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | Flask 3.1 (Python) |
| Base de données | SQLite 3 (WAL mode, foreign keys) |
| Frontend | Bootstrap 5.3.2 + Bootstrap Icons 1.11.2 |
| Graphiques | Chart.js 4.4.7 |
| Polices | Inter (Google Fonts) |
| Serveur | Werkzeug (dev) — port 5555 |

> Aucune dépendance npm, aucun build. Toutes les librairies front sont chargées via CDN.

---

## 🗄️ Modèle de données

### Schéma principal

```
              ┌──────────────────┐
              │  types_activite  │
              └────────┬─────────┘
                       │ 1
                       │
                       │ N
              ┌────────┴─────────┐         ┌─────────────────┐
              │     machines     │────N:M───│    materiaux     │
              └────────┬─────────┘         └─────────────────┘
                       │                via materiau_machine
                       │                  (table de jonction)
              ┌────────┴─────────┐
              │  consommations   │──── FK → preparateurs
              │ (dénormalisées)  │──── FK → classes
              └──────────────────┘──── FK → referents
```

### Principes clés

| Concept | Détail |
|---------|--------|
| **Table de jonction** | `materiau_machine` lie chaque matériau aux machines compatibles (N:M). Plus de doublons de matériaux. |
| **Dénormalisation** | Chaque consommation stocke les noms (`nom_preparateur`, `nom_machine`, etc.) en plus des FK, garantissant la lisibilité même après suppression d'une entité. |
| **Soft-delete** | Les entités ne sont jamais supprimées physiquement — le champ `actif` passe à `0`. Les consommations existantes restent intactes. |
| **Principes de conception** | Chaque machine porte un attribut `principes_conception` (`ajout`, `enlevement`, `deformation`) pour classification pédagogique. |
| **Migration automatique** | `_migrate_db()` ajoute les colonnes manquantes pour les bases existantes, assurant la rétrocompatibilité. |
| **Base neutre** | L'installation par défaut contient uniquement les machines, matériaux et types d'activité. Les classes, préparateurs et référents sont à configurer par chaque fablab. |

---

## 🛠️ Parc machines par défaut

L'application est pré-configurée avec **13 machines** :

| Machine | Type | Qté | Marque | Zone de travail |
|---------|------|:---:|--------|-----------------|
| Creality CR10-S | Impression 3D | ×2 | Creality | 300×300×400 mm |
| Creality Ender 3 | Impression 3D | ×1 | Creality | 220×220×250 mm |
| Raise 3D Pro | Impression 3D | ×1 | Raise3D | 305×305×305 mm |
| Raise 3D Pro 2 | Impression 3D | ×1 | Raise3D | 305×305×300 mm |
| Raise 3D Pro 3 | Impression 3D | ×1 | Raise3D | 300×300×300 mm |
| Creabot D600 | Impression 3D | ×1 | Creabot | 600×600×600 mm |
| JAMP 78 Moy | Découpe Laser | ×1 | JAMP | 780×460 mm |
| Grande Strato | CNC / Fraisage | ×1 | — | 1200×900 mm |
| Petite Strato | CNC / Fraisage | ×1 | — | 600×450 mm |
| Formech 300XQ | Thermoformage | ×1 | Formech | 300×300 mm |
| Kyocera | Impression Papier | ×1 | Kyocera | — |
| Epson Eco-tank | Impression Papier | ×1 | Epson | — |
| Traceur HP | Impression Papier | ×1 | HP | Grand format |

> Les machines sont entièrement personnalisables depuis les Paramètres (ajout, modification, suppression).

<img width="1915" height="916" alt="image" src="https://github.com/user-attachments/assets/822cc63e-b7e8-4808-a831-c8299c6c34af" />


### Matériaux par imprimante papier

| Imprimante | Formats | Mode |
|------------|---------|------|
| **Kyocera** | A3, A4 | N&B uniquement |
| **Epson Eco-tank** | A4 | Couleur + N&B |
| **Traceur HP** | A0 → A5 | Couleur + N&B |

---

## 📊 Types d'activité

| Type | Icône | Unité | Principe |
|------|:-----:|-------|----------|
| Impression 3D | 🖨️ | g | Ajout |
| Découpe Laser | ⚡ | m² | Enlèvement |
| CNC / Fraisage | ⚙️ | m² | Enlèvement |
| Impression Papier | 📄 | feuilles | — |
| Thermoformage | 🔥 | feuilles | Déformation |
| Bricolage | 🔧 | — | — |
| Broderie | 🧵 | — | Ajout |

Les types sont entièrement personnalisables (ajout, modification, suppression) depuis Paramètres.

### Champs spécifiques par type

| Type | Champs de saisie |
|------|------------------|
| Impression 3D | Poids (g) |
| Découpe Laser / CNC | Longueur, largeur, surface auto (mm/cm/m) |
| Impression Papier | Nb feuilles, format (A0–A5), couleur/N&B |
| Thermoformage | Nb feuilles plastique, type (opaque/transparente) |

---

## 💾 Sauvegarde & Restauration

### Format `.fabtrack`

Les sauvegardes sont des copies complètes de la base SQLite avec l'extension `.fabtrack`. Elles sont directement importables sur une autre instance de FabTrack.

### Fonctionnalités

| Fonctionnalité | Description |
|----------------|-------------|
| **Sauvegarde automatique** | Fréquence configurable : désactivée / journalière / hebdomadaire |
| **Sauvegarde manuelle** | Création à la demande depuis la page Export |
| **Emplacement personnalisé** | Chemin de sauvegarde configurable (dossier local, disque réseau, serveur externe…) avec test d'écriture |
| **Export** | Téléchargement de la base actuelle ou d'une sauvegarde existante en `.fabtrack` |
| **Import** | Restauration d'une base `.fabtrack` avec validation SQLite + tables requises. Sauvegarde de sécurité automatique avant remplacement |
| **Gestion** | Liste des sauvegardes (nom, date, taille), téléchargement individuel, suppression |
| **Nettoyage** | Maximum configurable de sauvegardes conservées (30 par défaut), rotation automatique |

### Configuration

La configuration est stockée dans `backup_config.json` :

```json
{
  "frequency": "daily",
  "last_backup": "2026-02-27 15:18:08",
  "max_backups": 30,
  "backup_path": ""
}
```

- `backup_path` vide = dossier par défaut `./backups/`
- `backup_path` renseigné = chemin personnalisé (ex : `\\serveur\partage\fabtrack_backups` ou `D:\sauvegardes`)

---

## 📈 Statistiques

Les tableaux de bord incluent :

- **Résumé** — Total interventions, poids 3D (g), surface découpe (m²), feuilles papier (Couleur/N&B)
- **Répartition par type** — Doughnut chart avec pourcentages
- **Timeline** — Courbes par type d'activité (jour/semaine/mois)
- **Consommation 3D** — Par matériau (PLA, PETG, ABS, TPU)
- **Surface découpe** — Laser + CNC combinés, par matériau
- **Impressions papier** — Répartition Couleur vs N&B + évolution temporelle
- **Top 10 machines / classes** — Bar charts
- **Activité journalière** — Répartition par heure, par jour de semaine, par préparateur
- **Filtres temporels** — Presets (7j, 30j, 90j, année, tout) ou dates personnalisées

<img width="1915" height="916" alt="image" src="https://github.com/user-attachments/assets/4cdd03a3-6557-4f13-ba88-26cd449e6425" />


---

## 📐 Calculateur de surface

- 3 formes : **rectangle**, **cercle**, **triangle**
- Unités : mm, cm, m avec conversion automatique
- **Presets papier** : A0 à A5
- **Zones machines** : remplissage automatique depuis la fiche technique
- **Historique** des calculs (localStorage)
- **Envoi direct** de la surface calculée dans le formulaire de saisie

<img width="1915" height="918" alt="image" src="https://github.com/user-attachments/assets/e6960452-c1ad-4e2d-8169-bbded19197f6" />

---

## 📥 Import / Export

### Export CSV
- **Complet** : toutes les consommations
- **Filtré** : par période et/ou type d'activité
- Format Excel-compatible (BOM UTF-8, séparateur `;`)

### Import CSV
- **Gabarits** téléchargeables pour 5 entités (machines, matériaux, classes, référents, préparateurs)
- **Import en masse** avec détection automatique du séparateur
- Support des liens matériau → machines dans le gabarit matériaux

---

## 🔌 API REST

Toutes les données sont accessibles via une API JSON complète :

### Données de référence

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/reference` | Toutes les données de référence (machines, matériaux, liens, etc.) |

### Consommations

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/consommations` | Liste paginée avec filtres (date, type, classe, etc.) |
| `POST` | `/api/consommations` | Créer une consommation |
| `POST` | `/api/consommations/batch` | Créer plusieurs consommations (multi-action) |
| `PUT` | `/api/consommations/<id>` | Modifier une consommation |
| `DELETE` | `/api/consommations/<id>` | Supprimer une consommation |

### Statistiques

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/stats/summary` | Résumé statistique (totaux, répartitions) |
| `GET` | `/api/stats/timeline` | Données timeline pour graphiques |
| `GET` | `/api/stats/activity` | Activité journalière (heure, jour, préparateur) |

### Gestion des entités (CRUD)

Pour chaque entité (`types_activite`, `machines`, `materiaux`, `classes`, `referents`, `preparateurs`) :

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/<entity>` | Créer |
| `PUT` | `/api/<entity>/<id>` | Modifier |
| `DELETE` | `/api/<entity>/<id>` | Désactiver (soft-delete) |
| `GET` | `/api/<entity>/<id>/usage-count` | Nombre de saisies liées |
| `POST` | `/api/<entity>/<id>/replace-and-delete` | Remplacer les dépendances puis désactiver |
| `POST` | `/api/<entity>/mass-delete` | Désactivation en masse |

### Sauvegarde & Restauration

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/backup/settings` | Paramètres de sauvegarde |
| `PUT` | `/api/backup/settings` | Modifier fréquence, chemin, max sauvegardes |
| `POST` | `/api/backup/create` | Créer une sauvegarde manuelle |
| `GET` | `/api/backup/list` | Lister toutes les sauvegardes |
| `GET` | `/api/backup/export/<filename>` | Télécharger une sauvegarde |
| `GET` | `/api/backup/export-current` | Exporter la base actuelle en `.fabtrack` |
| `POST` | `/api/backup/import` | Importer un fichier `.fabtrack` |
| `DELETE` | `/api/backup/delete/<filename>` | Supprimer une sauvegarde |
| `POST` | `/api/backup/validate-path` | Valider un chemin de sauvegarde |

### Autres

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/export/csv` | Télécharger CSV (complet ou filtré) |
| `GET` | `/api/template/<entity>` | Télécharger gabarit CSV |
| `POST` | `/api/import/<entity>` | Importer un CSV |
| `PUT` | `/api/machines/<id>/statut` | Changer statut machine |
| `POST` | `/api/upload-image` | Upload d'image pour une entité |
| `GET/POST` | `/api/custom-fields` | Gestion champs personnalisés |
| `PUT/DELETE` | `/api/custom-fields/<id>` | Modifier/supprimer champ personnalisé |
| `GET/POST` | `/api/custom-field-values/<type>/<id>` | Valeurs des champs personnalisés |
| `POST` | `/api/demo/generate` | Générer données de démonstration |
| `POST` | `/api/reset` | Réinitialiser la base (confirmation requise) |

---

## 🔒 Sécurité

| Mesure | Détail |
|--------|--------|
| **XSS** | Fonction globale `escHtml()` appliquée à tous les contenus utilisateur injectés via JavaScript |
| **SQL Injection** | Requêtes paramétrées exclusivement (pas de concaténation de valeurs utilisateur) |
| **Whitelist** | `_resolve_nom()` accepte uniquement les tables autorisées |
| **Validation** | Pagination bornée (`per_page` max 10 000), parsing protégé des entiers, exceptions typées |
| **Soft-delete** | Suppression sécurisée avec vérification des dépendances et option de remplacement |
| **Réinitialisation** | Requiert de taper `REINITIALISER` en majuscules pour confirmer |
| **Sauvegarde import** | Validation SQLite + tables requises avant import, sauvegarde automatique pré-remplacement |
| **Chemin sauvegarde** | Test d'écriture automatique avant validation d'un chemin personnalisé |
| **Secret key** | Lecture depuis `FABTRACK_SECRET` (variable d'environnement) avec fallback |

---

## 🌙 Mode sombre

Basculez entre mode clair et sombre via le bouton 🌙/☀️ dans la navbar. Le choix est sauvegardé dans le `localStorage`. Les logos s'adaptent automatiquement.

---

## 🧪 Démonstration & Réinitialisation

Depuis la page **Export** :

- **Générer une démo** : crée ~150 consommations fictives réalistes réparties sur 6 mois, avec des **préparateurs fictifs** (Préparateur A, B, C…), des **classes fictives** (Classe 1A, 1B, 2A…, BTS, Licence Pro) et des **référents fictifs** de différentes catégories (professeurs, agents techniques, demandes extérieures, administration)
- **Réinitialiser** : supprime toutes les données (consommations, classes, préparateurs, référents) et recrée les tables avec uniquement les **machines et matériaux par défaut**. Les types d'activité sont également recréés.

---

## 📝 Licence

MIT — © 2025-2026
