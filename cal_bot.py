"""
Discord Calorie & Fitness Bot
------------------------------
Usage: 
  .cal <food name>              - Look up calories
  .log <exercise> <weight> <reps> <sets>  - Log a workout
  .workouts [@user]             - View workout history
  .stats [@user]                - View fitness stats

Setup:
1. pip install discord.py requests python-dotenv
2. Create a bot at https://discord.com/developers/applications
3. Copy your bot token into a .env file (see .env.example)
4. Invite bot to your server with "Send Messages" permission
5. Run: python cal_bot.py
"""

import discord
from discord import app_commands
import requests
import os
import sys
import json
from datetime import datetime, timedelta
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import base64
from dotenv import load_dotenv

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
USDA_API_KEY = os.getenv("USDA_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WORKOUTS_FILE = "workouts.json"

if not BOT_TOKEN:
    print("❌ DISCORD_BOT_TOKEN is not set.")
    print("   Create a .env file with: DISCORD_BOT_TOKEN=your_token_here")
    sys.exit(1)

# ── Workout tracking ────────────────────────────────────────────────────────
def load_workouts():
    """Load workouts from JSON file."""
    if os.path.exists(WORKOUTS_FILE):
        try:
            with open(WORKOUTS_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_workouts(workouts):
    """Save workouts to JSON file."""
    with open(WORKOUTS_FILE, "w") as f:
        json.dump(workouts, f, indent=2)

def log_workout(user_id: str, exercise: str, weight: float, reps: int, sets: int, guild_id: str = None) -> bool:
    """Log a workout for a user."""
    try:
        workouts = load_workouts()
        if user_id not in workouts:
            workouts[user_id] = []

        workout_entry = {
            "date": datetime.now().isoformat(),
            "exercise": exercise.title(),
            "weight": weight,
            "reps": reps,
            "sets": sets,
            "total_volume": weight * reps * sets,  # weight × reps × sets
            "guild_id": guild_id,
        }
        workouts[user_id].append(workout_entry)
        save_workouts(workouts)
        return True
    except:
        return False

def get_user_workouts(user_id: str, limit: int = 10) -> list:
    """Get recent workouts for a user."""
    workouts = load_workouts()
    user_workouts = workouts.get(user_id, [])
    return sorted(user_workouts, key=lambda x: x["date"], reverse=True)[:limit]

def get_exercise_stats(user_id: str, exercise: str) -> dict:
    """Get stats for a specific exercise."""
    workouts = load_workouts()
    user_workouts = workouts.get(user_id, [])
    exercise_logs = [w for w in user_workouts if w["exercise"].lower() == exercise.lower()]
    
    if not exercise_logs:
        return None
    
    max_weight = max(w["weight"] for w in exercise_logs)
    avg_reps = sum(w["reps"] for w in exercise_logs) / len(exercise_logs)
    total_volume = sum(w["total_volume"] for w in exercise_logs)
    
    return {
        "exercise": exercise.title(),
        "count": len(exercise_logs),
        "max_weight": max_weight,
        "avg_reps": avg_reps,
        "total_volume": total_volume,
        "last_date": max(exercise_logs, key=lambda x: x["date"])["date"]
    }

# ── USDA FoodData Central API Integration ───────────────────────────────────
async def search_calories(food_name: str) -> discord.Embed | None:
    """
    Search USDA FoodData Central for food nutrition info.
    Requires USDA_API_KEY environment variable.
    """
    if not USDA_API_KEY:
        return discord.Embed(
            title="❌ API Key Missing",
            description="USDA_API_KEY not configured. Add it to .env file",
            color=0xFF0000
        )
    
    url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    params = {
        "query": food_name,
        "pageSize": 5,
        "api_key": USDA_API_KEY
    }
    
    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return discord.Embed(
            title="❌ API Error",
            description=f"Error searching food data: {str(e)}",
            color=0xFF0000
        )
    
    foods = data.get("foods", [])
    
    # Find first food with calorie data
    for food in foods:
        food_nutrients = food.get("foodNutrients", [])
        
        # Extract nutrition info
        calories_100g = None
        protein = None
        carbs = None
        fat = None
        
        for nutrient in food_nutrients:
            nutrient_name = nutrient.get("nutrientName", "").lower()
            value = nutrient.get("value")
            unit = nutrient.get("unitName", "").lower()
            
            if "energy" in nutrient_name and "kcal" in unit and value:
                calories_100g = value
            elif "protein" in nutrient_name and "g" in unit and value:
                protein = value
            elif "carbohydrate" in nutrient_name and "g" in unit and value:
                carbs = value
            elif "fat, total" in nutrient_name and "g" in unit and value:
                fat = value
        
        if calories_100g is None:
            continue
        
        name = food.get("description", food_name.title())
        brand = food.get("brandName", "")
        
        # Build embed
        embed = discord.Embed(
            title=f"🍽️ {name}",
            color=0xFF6B35,
        )
        embed.set_footer(text="via USDA FoodData Central")
        
        embed.add_field(
            name="Calories per 100g",
            value=f"**{round(calories_100g)} kcal**",
            inline=True,
        )
        
        # Add macros if available
        macros = []
        if protein:
            macros.append(f"Protein: {round(protein, 1)}g")
        if carbs:
            macros.append(f"Carbs: {round(carbs, 1)}g")
        if fat:
            macros.append(f"Fat: {round(fat, 1)}g")
        
        if macros:
            embed.add_field(
                name="Macros (per 100g)",
                value=" · ".join(macros),
                inline=False,
            )
        
        return embed
    
    return None  # No food found with calorie data


# ── Strength Standards (by bodyweight) ──────────────────────────────────────
STRENGTH_STANDARDS = {
    "bench press": {150: 135, 170: 185, 190: 225, 210: 275},
    "squat": {150: 185, 170: 275, 190: 315, 210: 365},
    "deadlift": {150: 225, 170: 315, 190: 405, 210: 495},
    "overhead press": {150: 85, 170: 115, 190: 135, 210: 165},
    "bent row": {150: 135, 170: 185, 190: 225, 210: 275},
}

# ── Achievement Definitions ─────────────────────────────────────────────────
ACHIEVEMENTS = {
    "first_workout": {"name": "🚀 First Step", "desc": "Log your first workout"},
    "streak_5": {"name": "🔥 On Fire", "desc": "5-day workout streak"},
    "streak_10": {"name": "🌟 Unstoppable", "desc": "10-day workout streak"},
    "streak_30": {"name": "💎 Dedicated", "desc": "30-day workout streak"},
    "total_10": {"name": "💪 Consistency", "desc": "10 total workouts"},
    "total_50": {"name": "👑 Champion", "desc": "50 total workouts"},
    "total_100": {"name": "🏋️ Beast Mode", "desc": "100 total workouts"},
    "personal_record": {"name": "🎯 New PR", "desc": "Set a personal record"},
}

# ── Advanced Features ───────────────────────────────────────────────────────
def get_user_profile(user_id: str) -> dict:
    """Get or create user profile with streaks and achievements."""
    workouts = load_workouts()
    if user_id not in workouts:
        return {"workouts": [], "profile": {}}
    
    data = workouts[user_id] if isinstance(workouts[user_id], dict) else {"workouts": workouts.get(user_id, []), "profile": {}}
    
    if "profile" not in data:
        data["profile"] = {}
    
    return data

def calculate_streak(user_id: str) -> tuple:
    """Calculate current and max streak. Returns (current_streak, max_streak)."""
    profile = get_user_profile(user_id)
    workouts = profile.get("workouts", profile) if isinstance(profile, dict) else profile
    
    if not workouts or not isinstance(workouts, list):
        return (0, 0)
    
    workout_dates = sorted([datetime.fromisoformat(w["date"]).date() for w in workouts if isinstance(w, dict)])
    
    if not workout_dates:
        return (0, 0)
    
    max_streak = 1
    temp_streak = 1

    for i in range(1, len(workout_dates)):
        diff = (workout_dates[i] - workout_dates[i-1]).days
        if diff == 1:
            temp_streak += 1
        elif diff == 0:
            continue
        else:
            max_streak = max(max_streak, temp_streak)
            temp_streak = 1

    max_streak = max(max_streak, temp_streak)

    # current_streak is the most recent contiguous segment, if still active
    days_since_last = (datetime.now().date() - workout_dates[-1]).days
    current_streak = temp_streak if days_since_last <= 1 else 0

    return (current_streak, max_streak)

def get_user_achievements(user_id: str) -> list:
    """Get list of unlocked achievements for user."""
    profile = get_user_profile(user_id)
    workouts_list = profile.get("workouts", []) if isinstance(profile, dict) else profile
    if isinstance(workouts_list, dict) and "workouts" in workouts_list:
        workouts_list = workouts_list["workouts"]
    
    achievements = []
    
    # First workout
    if len(workouts_list) > 0:
        achievements.append("first_workout")
    
    # Streaks
    current_streak, max_streak = calculate_streak(user_id)
    if max_streak >= 5:
        achievements.append("streak_5")
    if max_streak >= 10:
        achievements.append("streak_10")
    if max_streak >= 30:
        achievements.append("streak_30")
    
    # Total workouts
    if len(workouts_list) >= 10:
        achievements.append("total_10")
    if len(workouts_list) >= 50:
        achievements.append("total_50")
    if len(workouts_list) >= 100:
        achievements.append("total_100")
    
    return list(set(achievements))

def get_server_leaderboard(guild_id: str, metric: str = "workouts") -> list:
    """Get leaderboard for a server. metric: 'workouts' or 'volume'"""
    workouts = load_workouts()
    leaderboard = []

    for user_id, data in workouts.items():
        workouts_list = data if isinstance(data, list) else data.get("workouts", [])

        # Filter to only this guild's workouts
        guild_workouts = [w for w in workouts_list if isinstance(w, dict) and w.get("guild_id") == guild_id]

        if not guild_workouts:
            continue

        if metric == "workouts":
            score = len(guild_workouts)
        else:  # volume
            score = sum(w.get("total_volume", 0) for w in guild_workouts)

        leaderboard.append({"user_id": user_id, "score": score})

    return sorted(leaderboard, key=lambda x: x["score"], reverse=True)[:10]

def generate_progress_chart(user_id: str, exercise: str) -> io.BytesIO:
    """Generate a matplotlib chart of exercise progress."""
    workouts = load_workouts()
    user_data = workouts.get(user_id, [])
    
    if isinstance(user_data, dict):
        user_data = user_data.get("workouts", [])
    
    exercise_logs = sorted(
        [w for w in user_data if isinstance(w, dict) and w.get("exercise", "").lower() == exercise.lower()],
        key=lambda x: x["date"]
    )
    
    if not exercise_logs:
        return None
    
    dates = [datetime.fromisoformat(w["date"]) for w in exercise_logs]
    weights = [w["weight"] for w in exercise_logs]
    
    plt.figure(figsize=(10, 6))
    plt.plot(dates, weights, marker='o', linestyle='-', linewidth=2, markersize=6, color='#FF6B35')
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Weight (lbs)', fontsize=12)
    plt.title(f'{exercise.title()} Progress', fontsize=14, fontweight='bold')
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close()
    
    return buf

# ── Discord client ───────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


# ── Calorie database (common foods) ─────────────────────────────────────────
CALORIE_DATABASE = {
    "apple": {"calories": 52, "protein": 0.3, "carbs": 14, "fat": 0.2},
    "banana": {"calories": 89, "protein": 1.1, "carbs": 23, "fat": 0.3},
    "orange": {"calories": 47, "protein": 0.9, "carbs": 12, "fat": 0.3},
    "chicken breast": {"calories": 165, "protein": 31, "carbs": 0, "fat": 3.6},
    "chicken": {"calories": 165, "protein": 31, "carbs": 0, "fat": 3.6},
    "egg": {"calories": 155, "protein": 13, "carbs": 1.1, "fat": 11},
    "milk": {"calories": 61, "protein": 3.2, "carbs": 4.8, "fat": 3.3},
    "rice": {"calories": 130, "protein": 2.7, "carbs": 28, "fat": 0.3},
    "bread": {"calories": 265, "protein": 9, "carbs": 49, "fat": 3.3},
    "pasta": {"calories": 131, "protein": 5, "carbs": 25, "fat": 1.1},
    "broccoli": {"calories": 34, "protein": 2.8, "carbs": 7, "fat": 0.4},
    "carrot": {"calories": 41, "protein": 0.9, "carbs": 10, "fat": 0.2},
    "salmon": {"calories": 208, "protein": 20, "carbs": 0, "fat": 13},
    "steak": {"calories": 271, "protein": 26, "carbs": 0, "fat": 17},
    "yogurt": {"calories": 59, "protein": 10, "carbs": 3.3, "fat": 0.4},
    "almonds": {"calories": 579, "protein": 21, "carbs": 22, "fat": 50},
    "peanut butter": {"calories": 588, "protein": 25, "carbs": 20, "fat": 50},
    "pizza": {"calories": 285, "protein": 12, "carbs": 36, "fat": 10},
    "burger": {"calories": 354, "protein": 15, "carbs": 35, "fat": 17},
    "oatmeal": {"calories": 389, "protein": 17, "carbs": 66, "fat": 7},
}



# ── Events ───────────────────────────────────────────────────────────────────
@client.event
async def on_ready():
    try:
        synced = await tree.sync()
        print(f"✅ Logged in as {client.user} — Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")


# ── Slash Commands ───────────────────────────────────────────────────────────

@tree.command(name="cal", description="Look up calorie info for a food")
@app_commands.describe(food="The food name (e.g., 'chicken breast', 'apple')")
async def cal_command(interaction: discord.Interaction, food: str):
    """Search for calorie information."""
    await interaction.response.defer()
    
    embed = await search_calories(food)
    
    if embed:
        await interaction.followup.send(embed=embed)
    else:
        # Fallback to local database
        local = CALORIE_DATABASE.get(food.lower())
        if local:
            fallback_embed = discord.Embed(title=f"🍽️ {food.title()}", color=0xFF6B35)
            fallback_embed.add_field(name="Calories per 100g", value=f"**{local['calories']} kcal**", inline=True)
            macros = [f"Protein: {local['protein']}g", f"Carbs: {local['carbs']}g", f"Fat: {local['fat']}g"]
            fallback_embed.add_field(name="Macros (per 100g)", value=" · ".join(macros), inline=False)
            fallback_embed.set_footer(text="via local database")
            await interaction.followup.send(embed=fallback_embed)
        else:
            await interaction.followup.send(f"😕 Couldn't find calorie info for **{food}**.")


@tree.command(name="log", description="Log a gym workout")
@app_commands.describe(
    exercise="Exercise name (e.g., 'bench press')",
    weight="Weight in pounds",
    reps="Number of repetitions",
    sets="Number of sets"
)
async def log_command(
    interaction: discord.Interaction,
    exercise: str,
    weight: float,
    reps: int,
    sets: int
):
    """Log a workout with weight, reps, and sets."""
    user_id = str(interaction.user.id)
    
    try:
        if weight <= 0 or reps <= 0 or sets <= 0:
            await interaction.response.send_message("❌ Weight, reps, and sets must be positive numbers!", ephemeral=True)
            return
        
        success = log_workout(user_id, exercise, weight, reps, sets, guild_id=str(interaction.guild.id) if interaction.guild else None)
        
        if success:
            total_volume = weight * reps * sets
            embed = discord.Embed(
                title="💪 Workout Logged!",
                color=0x00FF00,
                description=f"**{exercise.title()}**"
            )
            embed.add_field(name="Weight", value=f"{weight} lbs", inline=True)
            embed.add_field(name="Reps × Sets", value=f"{reps} × {sets}", inline=True)
            embed.add_field(name="Total Volume", value=f"{total_volume} lbs", inline=True)
            embed.set_footer(text=f"Logged at {datetime.now().strftime('%I:%M %p')}")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Error saving workout. Try again.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


@tree.command(name="workouts", description="View your recent workouts")
async def workouts_command(interaction: discord.Interaction):
    """Display recent workouts."""
    user_id = str(interaction.user.id)
    user_workouts = get_user_workouts(user_id, limit=10)
    
    if not user_workouts:
        await interaction.response.send_message("📋 No workouts logged yet. Start with `/log`!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"💪 {interaction.user.name}'s Workouts",
        color=0x3498DB,
    )
    
    # Group by exercise
    by_exercise = defaultdict(list)
    for workout in user_workouts:
        by_exercise[workout["exercise"]].append(workout)
    
    for exercise, logs in list(by_exercise.items())[:5]:
        latest = logs[0]
        weight = latest["weight"]
        reps = latest["reps"]
        sets = latest["sets"]
        date = datetime.fromisoformat(latest["date"]).strftime("%m/%d %I:%M %p")
        
        embed.add_field(
            name=f"{exercise}",
            value=f"{weight} lbs × {reps}×{sets}\n_{date}_",
            inline=True
        )
    
    embed.set_footer(text=f"Total workouts logged: {len(user_workouts)}")
    await interaction.response.send_message(embed=embed)


@tree.command(name="stats", description="View your fitness statistics")
@app_commands.describe(exercise="Specific exercise to view (optional)")
async def stats_command(interaction: discord.Interaction, exercise: str = None):
    """View exercise statistics."""
    user_id = str(interaction.user.id)
    
    if exercise:
        # Show stats for specific exercise
        stats = get_exercise_stats(user_id, exercise)
        
        if not stats:
            await interaction.response.send_message(f"❌ No data for **{exercise}**", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"📊 {stats['exercise']} Stats",
            color=0xFF6B35,
        )
        embed.add_field(name="Max Weight", value=f"{stats['max_weight']} lbs", inline=True)
        embed.add_field(name="Avg Reps", value=f"{stats['avg_reps']:.1f}", inline=True)
        embed.add_field(name="Times Done", value=f"{stats['count']}", inline=True)
        embed.add_field(name="Total Volume", value=f"{stats['total_volume']:,.0f} lbs", inline=False)
        embed.set_footer(text=f"Last: {datetime.fromisoformat(stats['last_date']).strftime('%m/%d %I:%M %p')}")
        
        await interaction.response.send_message(embed=embed)
    else:
        # Show all exercise stats
        workouts = load_workouts()
        user_workouts = workouts.get(user_id, [])
        
        if not user_workouts:
            await interaction.response.send_message("📊 No workouts logged yet!", ephemeral=True)
            return
        
        # Group by exercise
        exercises = set(w["exercise"].lower() for w in user_workouts)
        embed = discord.Embed(
            title=f"📊 {interaction.user.name}'s Stats",
            color=0xFF6B35,
        )
        
        for exercise_name in sorted(exercises):
            stats = get_exercise_stats(user_id, exercise_name)
            if stats:
                embed.add_field(
                    name=f"{stats['exercise']} ({stats['count']} times)",
                    value=f"Max: {stats['max_weight']} lbs | Avg Reps: {stats['avg_reps']:.1f}",
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed)


# ── NEW COMMANDS: Progress, Weekly, Strength, Streak, Badges, Leaderboard ────

@tree.command(name="progress", description="View progress chart for an exercise")
@app_commands.describe(exercise="Exercise name (e.g., 'bench press')")
async def progress_command(interaction: discord.Interaction, exercise: str):
    """Display progress chart for specified exercise."""
    user_id = str(interaction.user.id)
    await interaction.response.defer()
    
    chart = generate_progress_chart(user_id, exercise)
    
    if not chart:
        await interaction.followup.send(f"❌ No data for **{exercise}**. Log some workouts first!", ephemeral=True)
        return
    
    file = discord.File(chart, filename=f"{exercise}_progress.png")
    embed = discord.Embed(
        title=f"📈 {exercise.title()} Progress",
        color=0xFF6B35,
        description="Your weight progression over time"
    )
    await interaction.followup.send(file=file, embed=embed)


@tree.command(name="weekly", description="View your weekly workout summary")
async def weekly_command(interaction: discord.Interaction):
    """Display last 7 days of workouts."""
    user_id = str(interaction.user.id)
    
    workouts = load_workouts()
    user_data = workouts.get(user_id, [])
    
    if isinstance(user_data, dict):
        user_data = user_data.get("workouts", [])
    
    seven_days_ago = datetime.now() - timedelta(days=7)
    week_workouts = [w for w in user_data if isinstance(w, dict) and datetime.fromisoformat(w["date"]) > seven_days_ago]
    
    if not week_workouts:
        await interaction.response.send_message("📋 No workouts this week", ephemeral=True)
        return
    
    total_volume = sum(w.get("total_volume", 0) for w in week_workouts)
    total_sets = sum(w.get("sets", 0) for w in week_workouts)
    
    by_exercise = defaultdict(list)
    for w in week_workouts:
        by_exercise[w["exercise"]].append(w)
    
    embed = discord.Embed(
        title=f"📅 Weekly Report",
        color=0x3498DB,
        description=f"Last 7 days"
    )
    embed.add_field(name="Total Workouts", value=str(len(week_workouts)), inline=True)
    embed.add_field(name="Total Volume", value=f"{total_volume:,.0f} lbs", inline=True)
    embed.add_field(name="Total Sets", value=str(total_sets), inline=True)
    
    embed.add_field(name="Top Exercises", value="\n".join([f"**{ex}**: {len(logs)}x" for ex, logs in list(by_exercise.items())[:5]]), inline=False)
    
    await interaction.response.send_message(embed=embed)


@tree.command(name="strength_compare", description="Compare your strength to standards")
@app_commands.describe(exercise="Exercise to compare (e.g., 'bench press')")
async def strength_compare_command(interaction: discord.Interaction, exercise: str):
    """Compare user's max weight to strength standards."""
    user_id = str(interaction.user.id)
    
    stats = get_exercise_stats(user_id, exercise)
    
    if not stats:
        await interaction.response.send_message(f"❌ No data for **{exercise}**", ephemeral=True)
        return
    
    exercise_lower = exercise.lower()
    standards = STRENGTH_STANDARDS.get(exercise_lower)
    
    embed = discord.Embed(
        title=f"💪 Strength Comparison: {stats['exercise']}",
        color=0xFF6B35,
    )
    embed.add_field(name="Your Max", value=f"{stats['max_weight']} lbs", inline=True)
    
    if standards:
        embed.add_field(name="Standard (170 lbs)", value=f"{standards.get(170, 'N/A')} lbs", inline=True)
        
        user_max = stats['max_weight']
        std_val = standards.get(170, 1)
        percentage = (user_max / std_val * 100) if std_val > 0 else 0
        embed.add_field(name="vs Standard", value=f"{percentage:.0f}%", inline=True)
    else:
        embed.add_field(name="Standard", value="Not available", inline=True)
        embed.add_field(name="Note", value="Add your bodyweight for accurate comparison", inline=True)
    
    embed.add_field(name="Times Performed", value=stats['count'], inline=False)
    
    await interaction.response.send_message(embed=embed)


@tree.command(name="streak", description="View your workout streak")
async def streak_command(interaction: discord.Interaction):
    """Display current and max workout streak."""
    user_id = str(interaction.user.id)
    
    current, max_streak = calculate_streak(user_id)
    
    embed = discord.Embed(
        title="🔥 Workout Streak",
        color=0x00FF00 if current > 0 else 0xFF6B35,
    )
    embed.add_field(name="Current Streak", value=f"{current} days", inline=True)
    embed.add_field(name="Max Streak", value=f"{max_streak} days", inline=True)
    
    if current > 0:
        embed.add_field(name="Status", value="✅ Keep it up!", inline=False)
    else:
        embed.add_field(name="Status", value="Log a workout to start your streak!", inline=False)
    
    await interaction.response.send_message(embed=embed)


@tree.command(name="badges", description="View your achievement badges")
async def badges_command(interaction: discord.Interaction):
    """Display unlocked achievements."""
    user_id = str(interaction.user.id)
    
    achievements = get_user_achievements(user_id)
    
    embed = discord.Embed(
        title="🏆 Your Achievements",
        color=0xFFD700,
    )
    
    if not achievements:
        embed.description = "Log workouts to unlock achievements!"
    else:
        for ach_id in achievements:
            if ach_id in ACHIEVEMENTS:
                ach = ACHIEVEMENTS[ach_id]
                embed.add_field(name=ach["name"], value=ach["desc"], inline=False)
    
    await interaction.response.send_message(embed=embed)


@tree.command(name="leaderboard", description="View server leaderboard")
@app_commands.describe(metric="What to rank by: 'workouts' or 'volume'")
async def leaderboard_command(interaction: discord.Interaction, metric: str = "workouts"):
    """Display server leaderboard."""
    if metric.lower() not in ["workouts", "volume"]:
        await interaction.response.send_message("❌ Metric must be 'workouts' or 'volume'", ephemeral=True)
        return
    
    leaderboard = get_server_leaderboard(str(interaction.guild.id), metric.lower())
    
    if not leaderboard:
        await interaction.response.send_message("📊 No workout data yet!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"🏋️ Leaderboard - Top by {metric.title()}",
        color=0x3498DB,
    )
    
    for i, entry in enumerate(leaderboard, 1):
        try:
            user = await interaction.client.fetch_user(int(entry["user_id"]))
            user_name = user.name
        except:
            user_name = f"User {entry['user_id']}"
        
        if metric.lower() == "workouts":
            score_text = f"{entry['score']} workouts"
        else:
            score_text = f"{entry['score']:,.0f} lbs total"
        
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
        embed.add_field(name=f"{medal} {user_name}", value=score_text, inline=False)
    
    await interaction.response.send_message(embed=embed)


# ── OpenRouter Food Image Analysis ──────────────────────────────────────────
async def analyze_food_image(image_url: str, content_type: str) -> discord.Embed:
    if not OPENROUTER_API_KEY:
        return discord.Embed(
            title="❌ API Key Missing",
            description="OPENROUTER_API_KEY not configured. Add it to your .env file",
            color=0xFF0000
        )

    try:
        img_response = requests.get(image_url, timeout=10)
        img_response.raise_for_status()
        img_b64 = base64.b64encode(img_response.content).decode("utf-8")

        prompt = (
            "Analyze this food image and provide:\n"
            "1. Food item(s) identified\n"
            "2. Estimated serving size\n"
            "3. Estimated calories\n"
            "4. Estimated macros: protein (g), carbs (g), fat (g)\n\n"
            "Be concise. If multiple items are visible, list the main ones.\n"
            "Format your response exactly like this:\n"
            "**Food:** [name]\n"
            "**Serving:** [size]\n"
            "**Calories:** [number] kcal\n"
            "**Protein:** [g]g | **Carbs:** [g]g | **Fat:** [g]g\n\n"
            "Note: These are estimates based on visual analysis."
        )

        payload = {
            "model": "google/gemini-2.0-flash-exp:free",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{img_b64}"}}
                    ]
                }
            ]
        }

        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]

        embed = discord.Embed(
            title="📸 Food Scan Results",
            description=text,
            color=0xFF6B35
        )
        embed.set_footer(text="Estimates via OpenRouter AI · Results may vary")
        return embed

    except Exception as e:
        return discord.Embed(
            title="❌ Scan Error",
            description=f"Could not analyze image: {str(e)}",
            color=0xFF0000
        )


@tree.command(name="scan", description="Scan a food photo to estimate calories and macros")
@app_commands.describe(image="Upload a photo of your food")
async def scan_command(interaction: discord.Interaction, image: discord.Attachment):
    if not image.content_type or not image.content_type.startswith("image/"):
        await interaction.response.send_message("❌ Please upload an image file.", ephemeral=True)
        return

    await interaction.response.defer()
    embed = await analyze_food_image(image.url, image.content_type)
    await interaction.followup.send(embed=embed)


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    client.run(BOT_TOKEN)
