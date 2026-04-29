# Setup Guide for Calorie & Fitness Bot

## Prerequisites
- Python 3.13+
- Discord Bot Token
- USDA FoodData Central API Key

## Setup Instructions

### 1. Get Your API Keys

#### Discord Bot Token
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section and click "Add Bot"
4. Copy the token

#### USDA API Key
1. Go to [USDA FoodData Central](https://fdc.nal.usda.gov/api-key-signup.html)
2. Sign up for a free API key
3. Check your email for the key

### 2. Configure Environment Variables

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your keys:
   ```
   DISCORD_BOT_TOKEN=your_discord_bot_token_here
   USDA_API_KEY=your_usda_fdc_api_key_here
   ```

3. Make sure `.env` is in `.gitignore` (never commit API keys!)

### 3. Install Dependencies

```bash
pip install discord.py requests python-dotenv matplotlib
```

### 4. Run the Bot

```bash
python3 cal_bot.py
```

### 5. Invite Bot to Discord Server

1. In Developer Portal, go to OAuth2 > URL Generator
2. Select scopes: `bot`, `applications.commands`
3. Select permissions: `Send Messages`, `Read Messages/View Channels`
4. Copy the generated URL and open it to invite the bot

## Commands

### Nutrition Commands
- `/cal <food>` - Look up nutrition info from USDA database
- `/weekly` - View weekly workout summary

### Workout Logging
- `/log <exercise> <weight> <reps> <sets>` - Log a workout
- `/workouts` - View your recent workouts

### Statistics & Progress
- `/stats [exercise]` - View fitness statistics
- `/progress <exercise>` - View progress chart with graph
- `/strength_compare <exercise>` - Compare to strength standards
- `/streak` - View your workout streak

### Social Features
- `/badges` - View your achievement badges
- `/leaderboard [metric]` - Server leaderboard (workouts or volume)

## API Integration

The bot now uses the **USDA FoodData Central API** for food nutrition data:
- Supports 400,000+ foods in the USDA database
- Accurate macronutrient information
- Automatic updates when USDA data changes
- No hardcoded food list needed

Your API key is stored in `.env` and never exposed in the code.
