# 🚗 Car Dodger — Python Game Project (Tkinter + Pygame)

A polished Class 12 Computer Science project featuring a **Tkinter-based launcher** and a **Pygame-based arcade game**.
The project includes user accounts, car selection, settings, background music, leaderboards, and a complete game loop with scoring and collision mechanics.

---

## 📌 Features

### 🔹 **1. Tkinter Launcher**

* Login / Sign-up system
* Car selection (Garage)
* Settings: background music, volume control
* Help / Instructions
* Leaderboards (mode-wise scores)
* Dark themed UI
* Persistent user preferences (config.json)

### 🔹 **2. Pygame Car Dodger Game**

* Smooth lane-based movement
* Multiple difficulty modes: Casual, Heroic, Nightmare
* Enemy car spawning with increasing difficulty
* Score system (pass + close-pass points)
* Pause menu with Resume, Help, Leaderboard
* Animated UI components
* Clean, dark visual theme
* FPS-optimized loop

### 🔹 **3. Persistent Storage**

* SQLite database via a lightweight `db.py` module
* Stores:

  * User accounts
  * Passwords
  * Selected cars
  * High scores (per mode)
* JSON used for quick settings storage

---

## 📁 Project Structure

```
CarDodgerProject/
│
├── assets/
│   ├── bg_game.mp3
│   ├── bg_launcher.mp3
│   ├── enemy.png
│   ├── logo.ico
│   ├── player1.png
│   ├── player2.png
│   ├── player3.png
│   ├── player4.png
│   ├── player5.png
│   ├── road.png
│
├── car_game.db      # SQLite database 
├── config.json      # User settings (car, volume, bgm)
├── db.py            # SQLite helper functions
├── game.py          # Pygame arcade game
├── launcher.py      # Tkinter launcher UI
└── README.md
```

---

## 🛠 Tools & Technologies

* **Python 3.10+**
* **Tkinter** — launcher UI
* **Pygame** — game engine
* **Pillow (PIL)** — image processing
* **SQLite (via db.py)** — accounts + scores
* **JSON** — configuration file
* **Pathlib** — clean path handling

---

## 🚀 How to Run

### **1. Install dependencies**

```bash
pip install pygame pillow
```

(Tkinter and sqlite3 come pre-installed with Python.)

- Can skip (Taken care in launcher.py)

### **2. Run the launcher**

```bash
python launcher.py
```

### **3. From the launcher, you can:**

* Log in / create an account
* Choose a car
* Adjust music
* View leaderboards
* Start the game

---

## 🧠 Gameplay Controls

| Action      | Key    |
| ----------- | ------ |
| Move Left   | ← or A |
| Move Right  | → or D |
| Pause       | P      |
| Leaderboard | L      |
| Quit / Back | Esc    |

---

## 📊 Difficulty Modes

| Mode      | Speed Range | Spawn Rate | Max Enemies |
| --------- | ----------- | ---------- | ----------- |
| Casual    | Slow        | Low        | 5           |
| Heroic    | Medium      | Moderate   | 7           |
| Nightmare | Fast        | High       | 10          |

---

## 🗂 Database Structure

### **Users Table**

* id
* username
* password
* selected_car

### **Scores Table**

* id
* user_id
* score
* difficulty
* created_at

Leaderboards are generated **per mode** to avoid duplicates.

---

## 🏆 What This Project Demonstrates

* Event-driven programming
* GUI development (Tkinter)
* Game development (Pygame)
* Multimedia handling
* Persistent storage (SQLite + JSON)
* Modular software design
* Exception handling and user-friendly UI design

Perfect for CBSE Class 12 Computer Science practical/project submission.

---

## 📌 Author

**Omesh Goyal & Nischeyjeet Singh**
Class XII — Computer Science Project (2025–26)


