# Discord Calorie & Fitness Bot 



## Commands

### `/cal`
Look up calorie information for a food.
- **Parameters:**
  - `food` (required): The food name (e.g., 'chicken breast', 'apple')
- **Example:** `/cal chicken breast`

### `/log`
Log a gym workout with weight, reps, and sets.
- **Parameters:**
  - `exercise` (required): Exercise name (e.g., 'bench press')
  - `weight` (required): Weight in pounds (numeric)
  - `reps` (required): Number of repetitions (whole number)
  - `sets` (required): Number of sets (whole number)
- **Example:** `/log exercise:bench press weight:185 reps:8 sets:4`

### `/workouts`
View your recent workouts (last 10).
- **Parameters:** None
- **Shows:** Your 5 most recent exercises with weight, reps, sets, and timestamps

### `/stats`
View your fitness statistics.
- **Parameters:**
  - `exercise` (optional): Specific exercise to view (e.g., 'bench press')
- **Shows:**
  - Without exercise: Max weight and avg reps for all exercises
  - With exercise: Max weight, avg reps, times done, and total volume

## Data Storage

All workouts are saved to `workouts.json` and persist between bot restarts.
Each user's data is tracked separately by Discord user ID.

## Available Foods (for /cal)

Currently supports: apple, banana, orange, chicken breast, egg, milk, rice, bread, pasta, broccoli, carrot, salmon, steak, yogurt, almonds, peanut butter, pizza, burger, oatmeal

## Getting Started

1. Run the bot: `python3 cal_bot.py`
2. In Discord, type `/` to see the slash command menu
3. Commands will show parameter input fields as you type
4. All parameters are clearly labeled with descriptions
