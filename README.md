# The Enemy Remembers

An open arena survival shooter with a bright, print-inspired arcade look. Move with WASD or the arrow keys, aim with the mouse, and fire energy shots at incoming hunters. The pack watches a rolling sample of your movement and can recognize favored directions, stillness, and sustained circles. Once it has a read, enemies lead your route and dodge shots that are actually headed toward them. Switching to a different pattern briefly weakens their prediction and is called out on screen.

## Difficulty

Choose Easy, Medium, or Hard from the title screen. Click a difficulty card or press 1, 2, or 3, then click Start or press Space. After getting caught, choose a different difficulty on the game-over screen before starting your next run. Easy gives you four hits and a slower, smaller pack. Medium is the standard challenge. Hard starts with a fast, frequent wave and quickly adds tougher hunters, larger groups, and dodgers. Best times are tracked separately for each difficulty.

## Run it

Install Python 3.10 or newer, then create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python game.py
```

On macOS or Linux, activate the environment with `source .venv/bin/activate` instead.

## Controls

- Move: WASD or arrow keys
- Aim: mouse
- Shoot: hold left mouse button or Space
- Pause/resume: Escape or P
- Change difficulty on title/game-over screen: click a card or press 1, 2, or 3
- Start/replay: Space or click the start button
- Quit from the title screen: Escape

The HUD shows survival time, best run for the selected difficulty, kills, wave, health, and enemy learning progress. Best times are stored locally in `best_run.json` and are excluded from Git.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
