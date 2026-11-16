import os
import sys
import io
import json
import shutil
import asyncio
import subprocess
import datetime
import time
import re
import random
from collections import defaultdict, deque
import discord
from aiohttp import web
from openai import OpenAI
from dotenv import load_dotenv

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

try:
    import davey
    HAS_DAVEY = True
except ImportError:
    HAS_DAVEY = False

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0").strip() or "0")

if not DISCORD_TOKEN:
    print("CRITICAL ERROR: DISCORD_TOKEN is missing from your .env or environment variables!")
    sys.exit(1)

if not OPENROUTER_API_KEY:
    print("WARNING: OPENROUTER_API_KEY is missing! AI replies will fail.")

ai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

DEFAULT_PERSONA = (
    "be like wemmbu from the unstable smp which is kinda mean "
    "Keep answers under 3 sentences and stay strictly in character."
)

current_persona = DEFAULT_PERSONA
tts_rate = -1
tts_pitch = 0.84

ai_model = "openrouter/free"
ai_temperature = 0.7
ai_max_tokens = 500

MEMORY_FILE = "memory.json"
PERSONAS_FILE = "personas.json"
BOT_STATE_FILE = "bot_state.json"
MAX_CONTEXT_MESSAGES = 40

START_TIME = datetime.datetime.now()
IS_INTERACTIVE = sys.stdin is not None and sys.stdin.isatty() and os.getenv("CLOUD_MODE", "").lower() != "true"

TRIVIA_TOPIC_EMOJIS = {
    "Space": "🚀",
    "Math": "➗",
    "History": "📜",
    "Geography": "🌍",
    "Science": "🔬",
}
TRIVIA_CUSTOM_FILE = "trivia_custom.json"
CUSTOM_TOPIC_EMOJI_POOL = [
    "🎲", "🎯", "🎳", "🎰", "🎨", "🎮", "🎬", "🎵", "🍔",
    "💻", "📚", "🏀", "🐶", "🧪", "⚡", "🔥", "💀", "🤖", "👾", "🌟",
]
TRIVIA_TOPICS = {
    "Space": [
        ("What planet is closest to the sun?", "Mercury"),
        ("How many moons does Earth have?", "1"),
        ("What is the largest planet in our solar system?", "Jupiter"),
        ("What galaxy is Earth located in?", "Milky Way"),
        ("Who was the first person to walk on the moon?", "Neil Armstrong"),
        ("What is the hottest planet in our solar system?", "Venus"),
        ("What is the name of the closest star to Earth?", "Sun"),
        ("Which planet is known as the Red Planet?", "Mars"),
        ("How many planets are in our solar system?", "8"),
        ("What is the largest moon of Saturn?", "Titan"),
    ],
    "Math": [
        ("What is 7 times 8?", "56"),
        ("What is the square root of 144?", "12"),
        ("What is 15 plus 27?", "42"),
        ("What is 100 divided by 4?", "25"),
        ("What is 9 squared?", "81"),
        ("What is the value of pi to 2 decimal places?", "3.14"),
        ("What is 50 percent of 200?", "100"),
        ("What is 11 times 11?", "121"),
        ("What is 6 factorial (6!)?", "720"),
        ("What is 1000 minus 567?", "433"),
    ],
    "History": [
        ("In what year did World War 2 end?", "1945"),
        ("Who was the first president of the United States?", "George Washington"),
        ("Who painted the Mona Lisa?", "Leonardo da Vinci"),
        ("In what year did the Titanic sink?", "1912"),
        ("What ancient civilization built the pyramids of Giza?", "Egyptians"),
        ("In what year did the Berlin Wall fall?", "1989"),
        ("Who wrote the Communist Manifesto?", "Karl Marx"),
        ("In what year did the United States declare independence?", "1776"),
        ("What year did Christopher Columbus first reach the Americas?", "1492"),
        ("Who was the first emperor of unified China?", "Qin Shi Huang"),
    ],
    "Geography": [
        ("What is the capital of France?", "Paris"),
        ("What is the largest country by area?", "Russia"),
        ("What is the longest river in the world?", "Nile"),
        ("What is the smallest country in the world?", "Vatican City"),
        ("What ocean lies between Europe and North America?", "Atlantic"),
        ("What is the capital of Japan?", "Tokyo"),
        ("On which continent is Egypt located?", "Africa"),
        ("What is the tallest mountain in the world?", "Everest"),
        ("What is the capital of Australia?", "Canberra"),
        ("What is the capital of Brazil?", "Brasilia"),
    ],
    "Science": [
        ("What is the chemical symbol for water?", "H2O"),
        ("What is the chemical symbol for gold?", "Au"),
        ("How many bones are in the adult human body?", "206"),
        ("What gas do plants absorb from the air?", "carbon dioxide"),
        ("What is the powerhouse of the cell?", "mitochondria"),
        ("What is the most abundant gas in Earth's atmosphere?", "nitrogen"),
        ("At what temperature does water boil in Celsius?", "100"),
        ("What force keeps us on the ground?", "gravity"),
        ("What is the pH of pure water?", "7"),
        ("What particle in an atom has a negative charge?", "electron"),
    ],
}
TRIVIA_TOPIC_NAMES = list(TRIVIA_TOPICS.keys())
TRIVIA_ROUNDS = 5
TRIVIA_VOTE_SECONDS = 15
TRIVIA_ANSWER_SECONDS = 15
trivia_active_channels = set()
trivia_scoreboards = {}
RESERVED_CUSTOM_KEYS = {"_emoji_overrides"}


def load_json_file(path, default):
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json_file(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Warning: Could not save {path}: {e}")


def get_topic_emoji(topic_name: str) -> str:
    custom = load_custom_questions()
    overrides = custom.get("_emoji_overrides", {})
    target = topic_name.lower()
    for k, v in overrides.items():
        if k.lower() == target:
            return v
    if topic_name in TRIVIA_TOPIC_EMOJIS:
        return TRIVIA_TOPIC_EMOJIS[topic_name]
    h = sum(ord(c) for c in topic_name.lower())
    return CUSTOM_TOPIC_EMOJI_POOL[h % len(CUSTOM_TOPIC_EMOJI_POOL)]


def load_custom_questions() -> dict:
    return load_json_file(TRIVIA_CUSTOM_FILE, {})


def save_custom_questions(data: dict):
    save_json_file(TRIVIA_CUSTOM_FILE, data)


def find_topic_key(custom_data: dict, topic_name: str):
    target = topic_name.lower()
    for key in custom_data.keys():
        if key in RESERVED_CUSTOM_KEYS:
            continue
        if isinstance(custom_data.get(key), list):
            if key.lower() == target:
                return key
    for builtin in TRIVIA_TOPICS.keys():
        if builtin.lower() == target:
            return builtin
    return None


def get_combined_topics() -> list:
    custom = load_custom_questions()
    names = set(TRIVIA_TOPICS.keys())
    for k, v in custom.items():
        if k in RESERVED_CUSTOM_KEYS:
            continue
        if isinstance(v, list) and v:
            names.add(k)
    return sorted(names)


def get_all_questions_for_topic(topic_name: str) -> list:
    result = list(TRIVIA_TOPICS.get(topic_name, []))
    custom = load_custom_questions()
    target = topic_name.lower()
    for key, entries in custom.items():
        if key in RESERVED_CUSTOM_KEYS:
            continue
        if not isinstance(entries, list):
            continue
        if key.lower() == target:
            for entry in entries:
                result.append((entry.get("question", ""), entry.get("answer", "")))
            break
    return result


def normalize_topic_name(topic_name: str) -> str:
    if topic_name.strip().startswith("_"):
        return topic_name.strip()
    existing = find_topic_key(load_custom_questions(), topic_name)
    if existing:
        return existing
    return topic_name.strip().title()


def set_topic_emoji_override(topic_name: str, emoji: str) -> bool:
    custom = load_custom_questions()
    overrides = custom.setdefault("_emoji_overrides", {})
    target = topic_name.lower()
    keys_to_remove = [k for k in overrides.keys() if k.lower() == target]
    for k in keys_to_remove:
        del overrides[k]
    if emoji.strip().lower() not in ("clear", "", "none", "default"):
        canonical = find_topic_key(custom, topic_name) or topic_name.strip().title()
        overrides[canonical] = emoji.strip()
    custom["_emoji_overrides"] = overrides
    save_custom_questions(custom)
    return True


chat_memory = load_json_file(MEMORY_FILE, {})
saved_personas = load_json_file(PERSONAS_FILE, {})
bot_state = load_json_file(BOT_STATE_FILE, {})

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
}
if os.path.isfile("qjs.exe"):
    YDL_OPTIONS.update({"js_runtimes": {"quickjs": {"path": os.path.abspath("qjs.exe")}}})

FFMPEG_STREAM_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": '-vn -af "volume=1.5"',
}

intents = discord.Intents.default()
intents.message_content = True
ENABLE_MEMBERS_INTENT = False
if ENABLE_MEMBERS_INTENT:
    intents.members = True
bot = discord.Client(intents=intents)

opened_dm_windows = set()
os.makedirs("dm_logs", exist_ok=True)


async def start_keepalive_server():
    app = web.Application()
    app.router.add_get("/", lambda request: web.Response(text="Bot is online 24/7!"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Keep-alive web server listening on port {port}")


def run_startup_diagnostics():
    print("\n--- SYSTEM DIAGNOSTICS ---")
    print(f"Mode              : {'Interactive PC Console' if IS_INTERACTIVE else 'Headless Cloud (Render/Server)'}")
    print(f"Owner ID          : {OWNER_ID if OWNER_ID else 'Not set (set OWNER_ID in env for !bot commands)'}")
    print(f"Python Executable : {sys.executable}")
    print(f"discord.py Version: {discord.__version__}")
    print(f"DAVE Encryption   : {'OK (v' + davey.__version__ + ')' if HAS_DAVEY else 'MISSING! Run: pip install davey'}")
    ffmpeg_path = shutil.which("ffmpeg")
    print(f"FFmpeg Binary     : {ffmpeg_path if ffmpeg_path else 'MISSING! Voice playback will fail.'}")
    print(f"yt-dlp Module     : {'OK' if HAS_YTDLP else 'MISSING! Run: pip install yt-dlp[default]'}")
    print(f"QuickJS (qjs.exe) : {'Found in folder' if os.path.isfile('qjs.exe') else 'Not in folder (using Deno/default)'}")
    print(f"Loaded Memory     : {len(chat_memory)} conversation thread(s)")
    print(f"Saved Personas    : {len(saved_personas)} persona(s)")
    print(f"Current AI Model  : {ai_model}")
    print(f"Current Persona   : {current_persona[:80]}{'...' if len(current_persona) > 80 else ''}")
    print("--------------------------\n")


def log_and_open_dm_window(user_id: int, username: str, sender_label: str, content: str):
    log_path = os.path.abspath(f"dm_logs/dm_{user_id}.log")
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {sender_label}: {content}\n")
    if IS_INTERACTIVE and user_id not in opened_dm_windows:
        opened_dm_windows.add(user_id)
        if os.name == "nt":
            cmd = f'start "DM Log - {username} ({user_id})" powershell -NoExit -Command "Get-Content -Path \'{log_path}\' -Wait -Encoding UTF8"'
            subprocess.Popen(cmd, shell=True)


def generate_windows_wav(text: str, output_path: str):
    safe_text = text.replace("'", "''").replace('"', ' ').replace("\n", " ")
    ps_script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.SelectVoiceByHints('Male'); "
        "$s.Volume = 100; "
        f"$s.Rate = {tts_rate}; "
        f"$s.SetOutputToWaveFile('{output_path}'); "
        f"$s.Speak('{safe_text}'); "
        "$s.Dispose();"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True)


def format_uptime(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m}m {s}s"


def parse_color(text: str) -> discord.Color:
    text = text.strip().lstrip("#")
    if text.lower() == "random":
        return discord.Color.random()
    if text.lower() == "blurple":
        return discord.Color.blurple()
    if text.lower() == "red":
        return discord.Color.red()
    if text.lower() == "green":
        return discord.Color.green()
    if text.lower() == "gold":
        return discord.Color.gold()
    try:
        return discord.Color(int(text, 16))
    except Exception:
        return discord.Color.blurple()


def normalize_answer(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [w for w in text.split() if w not in {"the", "a", "an", "of"}]
    return "".join(words)


def levenshtein(a: str, b: str) -> int:
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [i] + [0] * n
        ai = a[i - 1]
        for j in range(1, n + 1):
            cost = 0 if ai == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[n]


def answers_match(player_answer: str, correct_answer: str) -> bool:
    pa = normalize_answer(player_answer)
    ca = normalize_answer(correct_answer)
    if not pa or not ca:
        return False
    if pa == ca:
        return True
    number_map = {
        "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
        "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
        "10": "ten", "11": "eleven", "12": "twelve",
    }
    if number_map.get(pa) == ca or number_map.get(ca) == pa:
        return True
    if len(ca) >= 6:
        return levenshtein(pa, ca) <= 2
    if len(ca) >= 3:
        return levenshtein(pa, ca) <= 1
    return False


def build_scoreboard_embed(channel_id: int, title: str = "Scoreboard") -> discord.Embed:
    sb = trivia_scoreboards.get(channel_id, {})
    if not sb:
        return discord.Embed(title=title, description="No scores yet.", color=discord.Color.blurple())
    sorted_scores = sorted(sb.items(), key=lambda kv: kv[1][1], reverse=True)
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (uid, (name, score)) in enumerate(sorted_scores):
        prefix = medals[i] if i < 3 else f"`{i+1}`"
        lines.append(f"{prefix}  **{name}** — {score} pts")
    return discord.Embed(title=title, description="\n".join(lines), color=discord.Color.gold())


SNIPE_MAX_PER_CHANNEL = 20
sniped_deletes = defaultdict(lambda: deque(maxlen=SNIPE_MAX_PER_CHANNEL))
sniped_edits = defaultdict(lambda: deque(maxlen=SNIPE_MAX_PER_CHANNEL))
snipe_alert_channel_id = bot_state.get("snipe_alert_channel_id")
snipe_alert_edits = bot_state.get("snipe_alert_edits", False)


def set_snipe_alert_channel(channel_id, include_edits=None):
    global snipe_alert_channel_id, snipe_alert_edits
    snipe_alert_channel_id = channel_id
    bot_state["snipe_alert_channel_id"] = channel_id
    if include_edits is not None:
        snipe_alert_edits = include_edits
        bot_state["snipe_alert_edits"] = include_edits
    save_json_file(BOT_STATE_FILE, bot_state)


def format_elapsed(delta: datetime.timedelta) -> str:
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"


KNOWN_DISCORD_COMMANDS = {"!addq", "!qstats", "!qlist", "!emoji", "!snipe", "!editsnipe"}


async def handle_discord_command(message: discord.Message) -> bool:
    if not message.content:
        return False
    first_word = message.content.split()[0].lower()
    if first_word not in KNOWN_DISCORD_COMMANDS:
        return False
    if first_word == "!addq":
        await cmd_addq(message)
    elif first_word == "!qstats":
        await cmd_qstats(message)
    elif first_word == "!qlist":
        await cmd_qlist(message)
    elif first_word == "!emoji":
        await cmd_emoji(message)
    elif first_word == "!snipe":
        await cmd_snipe(message)
    elif first_word == "!editsnipe":
        await cmd_editsnipe(message)
    return True


async def cmd_addq(message: discord.Message):
    parts = [p.strip() for p in message.content.split("|", 2)]
    if len(parts) < 3:
        await message.reply("Usage: `!addq Topic | Question | Answer`")
        return
    topic_raw = parts[0][len("!addq"):].strip()
    question = parts[1].strip()
    answer = parts[2].strip()
    if not topic_raw or not question or not answer:
        await message.reply("Topic, question, and answer can't be empty.")
        return
    if len(question) > 500 or len(answer) > 200:
        await message.reply("Question or answer is too long (max 500 / 200 chars).")
        return
    topic_name = normalize_topic_name(topic_raw)
    custom = load_custom_questions()
    entries = custom.get(topic_name, [])
    new_q_norm = normalize_answer(question)
    for entry in entries:
        if normalize_answer(entry.get("question", "")) == new_q_norm:
            await message.reply(f"That question already exists in **{topic_name}**.")
            return
    entries.append({
        "question": question,
        "answer": answer,
        "author": message.author.display_name,
        "author_id": message.author.id,
    })
    custom[topic_name] = entries
    save_custom_questions(custom)
    emoji = get_topic_emoji(topic_name)
    embed = discord.Embed(title=f"{emoji} Question Added", description=f"Added to **{topic_name}** ({len(entries)} total now).", color=discord.Color.green())
    embed.add_field(name="Question", value=question[:1024], inline=False)
    embed.add_field(name="Answer", value=f"||{answer[:1024]}||", inline=False)
    await message.reply(embed=embed)


async def cmd_qstats(message: discord.Message):
    custom = load_custom_questions()
    topics = {k: v for k, v in custom.items() if k not in RESERVED_CUSTOM_KEYS and isinstance(v, list)}
    if not topics:
        await message.reply("No custom questions yet. Add one with `!addq Topic | Question | Answer`.")
        return
    lines = [f"{get_topic_emoji(t)}  **{t}** — {len(topics[t])} question(s)" for t in sorted(topics.keys())]
    total = sum(len(v) for v in topics.values())
    await message.reply(embed=discord.Embed(title="📊 Custom Question Stats", description="\n".join(lines) + f"\n\n**Total:** {total}", color=discord.Color.blurple()))


async def cmd_qlist(message: discord.Message):
    parts = message.content.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        await message.reply("Usage: `!qlist Topic`")
        return
    topic_raw = parts[1].strip()
    topic_key = find_topic_key(load_custom_questions(), topic_raw)
    if not topic_key:
        await message.reply(f"No topic named '{topic_raw}' found.")
        return
    questions = get_all_questions_for_topic(topic_key)
    if not questions:
        await message.reply(f"No questions in **{topic_key}**.")
        return
    try:
        dm = await message.author.create_dm()
        batches = []
        for i in range(0, len(questions), 10):
            chunk = questions[i:i + 10]
            batches.append("\n\n".join(f"**{i + j + 1}.** {q}\n   → ||{a}||" for j, (q, a) in enumerate(chunk)))
        emoji = get_topic_emoji(topic_key)
        await dm.send(embed=discord.Embed(title=f"{emoji} {topic_key} — {len(questions)} questions", description=batches[0], color=discord.Color.blurple()))
        for batch in batches[1:]:
            await dm.send(embed=discord.Embed(description=batch, color=discord.Color.blurple()))
        await message.reply(f"DM'd you {len(questions)} questions for **{topic_key}**.")
    except discord.Forbidden:
        await message.reply("Your DMs are closed.")


async def cmd_emoji(message: discord.Message):
    parts = message.content.split(None, 2)
    if len(parts) < 3:
        await message.reply("Usage: `!emoji TopicName 👑`")
        return
    topic_raw = parts[1].strip()
    emoji_arg = parts[2].strip()
    if topic_raw.startswith("_"):
        await message.reply("Reserved topic name.")
        return
    clearing = emoji_arg.lower() in ("clear", "none", "default", "reset", "")
    set_topic_emoji_override(topic_raw, "clear" if clearing else emoji_arg)
    await message.reply(f"Emoji for **{topic_raw}** updated.")


async def cmd_snipe(message: discord.Message):
    parts = message.content.split()
    index = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
    snaps = sniped_deletes.get(message.channel.id, [])
    if not snaps or index < 1 or index > len(snaps):
        await message.reply("🚫 Nothing to snipe at that index.")
        return
    snap = list(snaps)[index - 1]
    elapsed = datetime.datetime.now() - snap["deleted_at"]
    embed = discord.Embed(description=(snap["content"] or "(attachment)")[:1900], color=discord.Color.red(), timestamp=snap["deleted_at"])
    embed.set_author(name=snap["author"], icon_url=snap.get("author_avatar"))
    embed.set_footer(text=f"Deleted {format_elapsed(elapsed)} ago  •  Snipe #{index} of {len(snaps)}")
    if snap.get("attachments"):
        embed.set_image(url=snap["attachments"][0])
    await message.reply(embed=embed)


async def cmd_editsnipe(message: discord.Message):
    parts = message.content.split()
    index = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
    snaps = sniped_edits.get(message.channel.id, [])
    if not snaps or index < 1 or index > len(snaps):
        await message.reply("🚫 Nothing to editsnipe at that index.")
        return
    snap = list(snaps)[index - 1]
    elapsed = datetime.datetime.now() - snap["edited_at"]
    embed = discord.Embed(color=discord.Color.orange(), timestamp=snap["edited_at"])
    embed.set_author(name=snap["author"], icon_url=snap.get("author_avatar"))
    embed.add_field(name="Before", value=(snap["before"] or "(empty)")[:900], inline=False)
    embed.add_field(name="After", value=(snap["after"] or "(empty)")[:900], inline=False)
    embed.set_footer(text=f"Edited {format_elapsed(elapsed)} ago  •  Editsnipe #{index} of {len(snaps)}")
    await message.reply(embed=embed)


async def forward_snipe_alert(embed: discord.Embed):
    if not snipe_alert_channel_id:
        return
    try:
        alert_ch = bot.get_channel(snipe_alert_channel_id)
        if alert_ch:
            await alert_ch.send(embed=embed)
    except Exception as e:
        print(f"Snipe alert forward failed: {e}")


@bot.event
async def on_message_delete(message: discord.Message):
    if message.author.bot or isinstance(message.channel, discord.DMChannel):
        return
    if not message.content and not message.attachments:
        return
    attachments = [a.url for a in message.attachments if getattr(a, "url", None)]
    now = datetime.datetime.now()
    snap = {
        "content": message.content or "",
        "author": message.author.display_name,
        "author_id": message.author.id,
        "author_avatar": str(message.author.display_avatar.url) if message.author.display_avatar else None,
        "deleted_at": now,
        "attachments": attachments,
        "channel_id": message.channel.id,
    }
    sniped_deletes[message.channel.id].appendleft(snap)
    if snipe_alert_channel_id:
        embed = discord.Embed(title="🗑️ Message Deleted", description=(message.content or "(attachment)")[:1900], color=discord.Color.red(), timestamp=now)
        embed.set_author(name=message.author.display_name, icon_url=snap["author_avatar"])
        embed.set_footer(text=f"from #{getattr(message.channel, 'name', 'unknown')} in {getattr(message.channel.guild, 'name', '')}")
        if attachments:
            embed.set_image(url=attachments[0])
        await forward_snipe_alert(embed)


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.author.bot or isinstance(before.channel, discord.DMChannel) or before.content == after.content:
        return
    now = datetime.datetime.now()
    snap = {
        "before": before.content or "",
        "after": after.content or "",
        "author": before.author.display_name,
        "author_id": before.author.id,
        "author_avatar": str(before.author.display_avatar.url) if before.author.display_avatar else None,
        "edited_at": now,
        "channel_id": before.channel.id,
    }
    sniped_edits[before.channel.id].appendleft(snap)
    if snipe_alert_channel_id and snipe_alert_edits:
        embed = discord.Embed(title="✏️ Message Edited", color=discord.Color.orange(), timestamp=now)
        embed.set_author(name=before.author.display_name, icon_url=snap["author_avatar"])
        embed.add_field(name="Before", value=(before.content or "(empty)")[:900], inline=False)
        embed.add_field(name="After", value=(after.content or "(empty)")[:900], inline=False)
        embed.set_footer(text=f"from #{getattr(before.channel, 'name', 'unknown')} in {getattr(before.channel.guild, 'name', '')}")
        await forward_snipe_alert(embed)


async def run_trivia_game(channel: discord.TextChannel):
    if channel.id in trivia_active_channels:
        await channel.send("Trivia is already running in this channel!")
        return
    trivia_active_channels.add(channel.id)
    trivia_scoreboards[channel.id] = {}
    used_questions = {}
    try:
        await channel.send(embed=discord.Embed(
            title="🎯 TRIVIA STARTING",
            description=f"5 rounds. Vote ({TRIVIA_VOTE_SECONDS}s) -> Answer ({TRIVIA_ANSWER_SECONDS}s). First correct = 3 pts, others = 1 pt.",
            color=discord.Color.gold(),
        ))
        await asyncio.sleep(3)
        for round_num in range(1, TRIVIA_ROUNDS + 1):
            if channel.id not in trivia_active_channels:
                break
            all_topics = get_combined_topics()
            if not all_topics:
                break
            round_topics = all_topics if len(all_topics) <= 5 else random.sample(all_topics, 5)
            round_emojis = [get_topic_emoji(t) for t in round_topics]
            vote_embed = discord.Embed(
                title=f"Round {round_num}/{TRIVIA_ROUNDS} — Vote for a topic!",
                description="\n".join(f"{round_emojis[i]}  {round_topics[i]}" for i in range(len(round_topics))) + f"\n\nVoting closes in {TRIVIA_VOTE_SECONDS}s.",
                color=discord.Color.blurple(),
            )
            vote_msg = await channel.send(embed=vote_embed)
            for emoji in round_emojis:
                await vote_msg.add_reaction(emoji)
            await asyncio.sleep(TRIVIA_VOTE_SECONDS)
            try:
                refreshed = await channel.fetch_message(vote_msg.id)
            except Exception:
                refreshed = vote_msg
            vote_counts = []
            for i, emoji in enumerate(round_emojis):
                reaction = discord.utils.find(lambda r: str(r.emoji) == emoji, refreshed.reactions)
                vote_counts.append((i, (reaction.count - 1) if reaction else 0))
            max_votes = max(c for _, c in vote_counts) if vote_counts else 0
            if max_votes == 0:
                chosen_idx = random.randrange(len(round_topics))
            else:
                chosen_idx = random.choice([i for i, c in vote_counts if c == max_votes])
            chosen_topic = round_topics[chosen_idx]
            await channel.send(embed=discord.Embed(description=f"Topic selected: **{chosen_topic}** {round_emojis[chosen_idx]}", color=discord.Color.green()))
            await asyncio.sleep(2)
            combined_questions = get_all_questions_for_topic(chosen_topic)
            if not combined_questions:
                continue
            used_set = used_questions.setdefault(chosen_topic, set())
            avail = [i for i in range(len(combined_questions)) if i not in used_set]
            if not avail:
                used_set.clear()
                avail = list(range(len(combined_questions)))
            q_idx = random.choice(avail)
            used_set.add(q_idx)
            question_text, correct_answer = combined_questions[q_idx]
            await channel.send(embed=discord.Embed(title=f"❓ {chosen_topic} — Round {round_num}", description=f"**{question_text}**\n\n{TRIVIA_ANSWER_SECONDS}s to answer!", color=discord.Color.gold()))
            answers = {}
            end_time = asyncio.get_event_loop().time() + TRIVIA_ANSWER_SECONDS
            while True:
                rem = end_time - asyncio.get_event_loop().time()
                if rem <= 0:
                    break
                try:
                    msg = await bot.wait_for("message", timeout=rem, check=lambda m: m.channel.id == channel.id and not m.author.bot)
                    if msg.author.id not in answers:
                        answers[msg.author.id] = (msg.author.display_name, msg.content)
                except asyncio.TimeoutError:
                    break
            correct_players = []
            for uid, (name, raw) in answers.items():
                if answers_match(raw, correct_answer):
                    correct_players.append((uid, name))
            sb = trivia_scoreboards.setdefault(channel.id, {})
            if correct_players:
                f_uid, f_name = correct_players[0]
                sb[f_uid] = (f_name, sb.get(f_uid, (f_name, 0))[1] + 3)
                for uid, name in correct_players[1:]:
                    sb[uid] = (name, sb.get(uid, (name, 0))[1] + 1)
            desc = f"**Answer:** {correct_answer}\n" + (f"✅ Correct: {', '.join(n for _, n in correct_players)}" if correct_players else "❌ Nobody got it!")
            await channel.send(embed=discord.Embed(title=f"Round {round_num} Results", description=desc, color=discord.Color.green() if correct_players else discord.Color.red()))
            if round_num < TRIVIA_ROUNDS:
                await channel.send(embed=build_scoreboard_embed(channel.id, f"📊 Standings after Round {round_num}"))
                await asyncio.sleep(3)
        await channel.send(embed=build_scoreboard_embed(channel.id, "🏁 Final Scoreboard"))
    finally:
        trivia_active_channels.discard(channel.id)


async def set_bot_presence(status_str: str):
    global bot_state
    status_map = {
        "online": discord.Status.online,
        "idle": discord.Status.idle,
        "dnd": discord.Status.dnd,
        "invisible": discord.Status.invisible,
        "offline": discord.Status.invisible,
    }
    status_str = status_str.lower()
    if status_str not in status_map:
        print("Use: online, idle, dnd, invisible")
        return
    saved_activity = await build_activity_from_state()
    await bot.change_presence(status=status_map[status_str], activity=saved_activity)
    bot_state["status"] = status_str
    save_json_file(BOT_STATE_FILE, bot_state)
    print(f"Presence set to: {status_str}")


async def build_activity_from_state():
    activity_data = bot_state.get("activity")
    if not activity_data or activity_data.get("type") == "clear":
        return None
    kind = activity_data.get("type", "")
    text = activity_data.get("name", "")
    twitch_url = activity_data.get("twitch_url")
    if kind == "playing":
        return discord.Game(name=text)
    if kind == "listening":
        return discord.Activity(type=discord.ActivityType.listening, name=text)
    if kind == "watching":
        return discord.Activity(type=discord.ActivityType.watching, name=text)
    if kind == "streaming" and twitch_url and "twitch.tv" in twitch_url:
        return discord.Streaming(name=text, url=twitch_url)
    return None


async def set_bot_activity(kind: str, text: str, twitch_url: str = None):
    global bot_state
    kind = kind.lower()
    saved_status_str = bot_state.get("status")
    status_obj = {
        "online": discord.Status.online,
        "idle": discord.Status.idle,
        "dnd": discord.Status.dnd,
        "invisible": discord.Status.invisible,
    }.get(saved_status_str, discord.Status.online)
    if kind == "clear":
        await bot.change_presence(activity=None, status=status_obj)
        bot_state["activity"] = {"type": "clear"}
        save_json_file(BOT_STATE_FILE, bot_state)
        print("Activity cleared.")
        return
    if kind == "playing":
        activity = discord.Game(name=text)
    elif kind == "listening":
        activity = discord.Activity(type=discord.ActivityType.listening, name=text)
    elif kind == "watching":
        activity = discord.Activity(type=discord.ActivityType.watching, name=text)
    elif kind == "streaming":
        if not twitch_url or "twitch.tv" not in twitch_url:
            print("Streaming requires a Twitch URL.")
            return
        activity = discord.Streaming(name=text, url=twitch_url)
    else:
        print("Use: playing, listening, watching, streaming, clear")
        return
    await bot.change_presence(activity=activity, status=status_obj)
    bot_state["activity"] = {"type": kind, "name": text, "twitch_url": twitch_url if kind == "streaming" else None}
    save_json_file(BOT_STATE_FILE, bot_state)
    print(f"Activity set to {kind}: {text}")


async def restore_bot_state():
    if not bot_state:
        return
    saved_status_str = bot_state.get("status")
    activity = await build_activity_from_state()
    status_obj = {
        "online": discord.Status.online,
        "idle": discord.Status.idle,
        "dnd": discord.Status.dnd,
        "invisible": discord.Status.invisible,
    }.get(saved_status_str, discord.Status.online)
    try:
        await bot.change_presence(activity=activity, status=status_obj)
    except Exception as e:
        print(f"Could not restore bot state: {e}")


async def execute_admin_command(raw_cmd: str, current_channel):
    global current_persona, tts_pitch, chat_memory, saved_personas, ai_model, ai_temperature, ai_max_tokens
    text = raw_cmd.strip()
    if not text.startswith("/"):
        text = "/" + text

    if text == "/help":
        print("Commands: /list, /ch, /say, /photo, /vc, /tts, /pitch, /play, /stop, /leave, /dm, /status, /activity, /persona, /resetpersona, /savepersona, /loadpersona, /personas, /model, /forget, /forgetall, /clear, /trivia, /triviastop, /snipealert, /diag")
        return current_channel

    if text == "/list":
        for ch in bot.get_all_channels():
            if isinstance(ch, (discord.TextChannel, discord.VoiceChannel)):
                print(f"  - [{type(ch).__name__}] {ch.name} ({ch.guild.name} | ID: {ch.id})")
        return current_channel

    if text.startswith("/ch "):
        target = text[4:].strip().lstrip("#")
        found = discord.utils.find(
            lambda c: isinstance(c, discord.TextChannel) and (c.name.lower() == target.lower() or str(c.id) == target),
            bot.get_all_channels()
        )
        if found:
            current_channel = found
            print(f"Switched to #{current_channel.name} ({current_channel.guild.name})")
        else:
            print(f"Couldn't find channel '{target}'.")
        return current_channel

    if text.startswith("/say "):
        parts = text[5:].strip().split(None, 1)
        if len(parts) >= 2:
            t_str = parts[0].lstrip("#")
            target = bot.get_channel(int(t_str)) if t_str.isdigit() else discord.utils.find(lambda c: isinstance(c, discord.TextChannel) and c.name.lower() == t_str.lower(), bot.get_all_channels())
            if target:
                await target.send(parts[1])
                print(f"Sent to #{target.name}")
        return current_channel

    if text.startswith("/photo "):
        target = text[7:].strip().strip('"').strip("'")
        if target.startswith("http"):
            embed = discord.Embed(color=discord.Color.blurple())
            embed.set_image(url=target)
            await current_channel.send(embed=embed)
            print("Sent image URL.")
        elif os.path.isfile(target):
            await current_channel.send(file=discord.File(target))
            print("Sent local photo.")
        return current_channel

    if text.startswith("/vc "):
        target = text[4:].strip()
        found_vc = discord.utils.find(lambda v: isinstance(v, discord.VoiceChannel) and (v.name.lower() == target.lower() or str(v.id) == target), bot.get_all_channels())
        if found_vc:
            if found_vc.guild.voice_client:
                await found_vc.guild.voice_client.move_to(found_vc)
            else:
                await found_vc.connect()
            print(f"Joined VC: {found_vc.name}")
        return current_channel

    if text.startswith("/pitch "):
        try:
            val = float(text[7:].strip())
            if 0.65 <= val <= 1.30:
                tts_pitch = val
                print(f"TTS pitch updated to {tts_pitch}")
        except ValueError:
            pass
        return current_channel

    if text.startswith("/tts "):
        if os.name != "nt":
            print("Windows SAPI5 /tts only works when hosted on Windows PC.")
            return current_channel
        speech_text = text[5:].strip()
        if speech_text and bot.voice_clients and shutil.which("ffmpeg"):
            vc_client = next(iter(bot.voice_clients))
            if vc_client.is_playing():
                vc_client.stop()
            wav_path = os.path.abspath("vc_tts.wav")
            await asyncio.to_thread(generate_windows_wav, speech_text, wav_path)
            tempo_comp = round(1.0 / tts_pitch, 3)
            deep_filter = f'-af "aresample=48000,asetrate=48000*{tts_pitch},aresample=48000,atempo={tempo_comp},volume=4.0"'
            vc_client.play(discord.FFmpegPCMAudio(wav_path, options=deep_filter))
            print(f"Speaking: {speech_text}")
        return current_channel

    if text.startswith("/play "):
        query = text[6:].strip()
        if query and HAS_YTDLP and shutil.which("ffmpeg") and bot.voice_clients:
            vc_client = next(iter(bot.voice_clients))
            def extract_audio():
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    info = ydl.extract_info(query, download=False)
                    if "entries" in info:
                        info = next(iter(info.get("entries")))
                    return info.get("url"), info.get("title", "Track")
            audio_url, title = await asyncio.to_thread(extract_audio)
            if audio_url:
                if vc_client.is_playing():
                    vc_client.stop()
                vc_client.play(discord.FFmpegPCMAudio(audio_url, **FFMPEG_STREAM_OPTIONS))
                print(f"Now playing: {title}")
        return current_channel

    if text == "/stop":
        if bot.voice_clients:
            next(iter(bot.voice_clients)).stop()
            print("Stopped playback.")
        return current_channel

    if text == "/leave":
        for vc in list(bot.voice_clients):
            await vc.disconnect()
        print("Left voice channel.")
        return current_channel

    if text.startswith("/dm "):
        parts_iter = iter(text.split(" ", 2))
        next(parts_iter, None)
        uid_s = next(parts_iter, "")
        dm_t = next(parts_iter, "").strip()
        if uid_s.isdigit() and dm_t:
            user = await bot.fetch_user(int(uid_s))
            dm_ch = await user.create_dm()
            await dm_ch.send(dm_t)
            chat_memory.setdefault(str(dm_ch.id), []).append({"role": "assistant", "content": dm_t})
            save_json_file(MEMORY_FILE, chat_memory)
            log_and_open_dm_window(user.id, user.name, "Bot (Manual)", dm_t)
            print(f"Sent DM to {user.name}")
        return current_channel

    if text.startswith("/status "):
        await set_bot_presence(text[8:].strip())
        return current_channel

    if text.startswith("/activity "):
        parts = text[10:].strip().split(None, 2)
        if parts:
            await set_bot_activity(parts[0], parts[1] if len(parts) > 1 else "", parts[2] if len(parts) > 2 else None)
        return current_channel

    if text == "/persona":
        print(f"Current Persona: {current_persona}")
        return current_channel

    if text.startswith("/persona "):
        current_persona = text[9:].strip()
        print("Persona updated!")
        return current_channel

    if text == "/resetpersona":
        current_persona = DEFAULT_PERSONA
        print("Persona reset to default.")
        return current_channel

    if text.startswith("/savepersona "):
        name = text[13:].strip()
        if name:
            saved_personas[name] = current_persona
            save_json_file(PERSONAS_FILE, saved_personas)
            print(f"Saved persona '{name}'.")
        return current_channel

    if text.startswith("/loadpersona "):
        name = text[13:].strip()
        if name in saved_personas:
            current_persona = saved_personas[name]
            print(f"Loaded persona '{name}'.")
        return current_channel

    if text == "/personas":
        print("Saved personas:", ", ".join(saved_personas.keys()) or "None")
        return current_channel

    if text.startswith("/model "):
        ai_model = text[7:].strip()
        print(f"Model set to {ai_model}")
        return current_channel

    if text == "/forget":
        chat_memory.pop(str(current_channel.id), None)
        save_json_file(MEMORY_FILE, chat_memory)
        print(f"Wiped memory for #{current_channel.name}")
        return current_channel

    if text == "/forgetall":
        chat_memory = {}
        save_json_file(MEMORY_FILE, chat_memory)
        print("Wiped ALL memory.")
        return current_channel

    if text == "/clear":
        deleted = 0
        async for m in current_channel.history(limit=200):
            if m.author == bot.user:
                try:
                    await m.delete()
                    deleted += 1
                    await asyncio.sleep(0.4)
                except Exception:
                    pass
        print(f"Deleted {deleted} bot message(s).")
        return current_channel

    if text == "/trivia" or text.startswith("/trivia "):
        arg = text[7:].strip()
        target_ch = bot.get_channel(int(arg)) if arg.isdigit() else current_channel
        if isinstance(target_ch, discord.TextChannel):
            asyncio.create_task(run_trivia_game(target_ch))
            print(f"Started trivia in #{target_ch.name}")
        return current_channel

    if text == "/triviastop":
        trivia_active_channels.discard(current_channel.id)
        print("Stopped trivia.")
        return current_channel

    if text == "/snipealert" or text.startswith("/snipealert "):
        arg = text[11:].strip()
        if arg == "clear":
            set_snipe_alert_channel(None)
            print("Snipe alert disabled.")
        elif arg == "edits on":
            set_snipe_alert_channel(snipe_alert_channel_id, include_edits=True)
            print("Edit alerts ON.")
        elif arg == "edits off":
            set_snipe_alert_channel(snipe_alert_channel_id, include_edits=False)
            print("Edit alerts OFF.")
        elif arg == "here":
            set_snipe_alert_channel(current_channel.id)
            print(f"Snipe alert set to #{current_channel.name}")
        elif arg.isdigit():
            set_snipe_alert_channel(int(arg))
            print(f"Snipe alert set to channel {arg}")
        return current_channel

    if text == "/diag":
        run_startup_diagnostics()
        return current_channel

    print(f"Unknown command: {text}")
    return current_channel


async def ai_reply(message, is_dm):
    user_text = message.content.replace(f"<@{bot.user.id}>", "").strip()
    if not user_text:
        return
    ch_key = str(message.channel.id)
    history = chat_memory.setdefault(ch_key, [])
    tagged_user_msg = f"{message.author.display_name}: {user_text}" if not is_dm else user_text
    history.append({"role": "user", "content": tagged_user_msg})
    save_json_file(MEMORY_FILE, chat_memory)
    recent_history = history[-MAX_CONTEXT_MESSAGES:]
    payload = [{"role": "system", "content": current_persona}] + recent_history
    async with message.channel.typing():
        try:
            kwargs = {"model": ai_model, "messages": payload, "temperature": ai_temperature}
            if ai_max_tokens:
                kwargs["max_tokens"] = ai_max_tokens
            response = ai_client.chat.completions.create(**kwargs)
            reply = next(iter(response.choices)).message.content
            await message.reply(reply[:2000])
            history.append({"role": "assistant", "content": reply})
            save_json_file(MEMORY_FILE, chat_memory)
            if is_dm:
                log_and_open_dm_window(message.author.id, message.author.name, "Bot (AI)", reply)
        except Exception as e:
            error_details = getattr(e, "body", str(e))
            await message.reply(f"Error details: {error_details}"[:2000])


async def manual_console_sender():
    await bot.wait_until_ready()
    writable_channels = [
        ch for ch in bot.get_all_channels()
        if isinstance(ch, discord.TextChannel) and ch.permissions_for(ch.guild.me).send_messages
    ]
    if not writable_channels:
        print("Error: Bot doesn't have permission to send messages in any channel!")
        return
    current_channel = next(iter(writable_channels))
    print(f"Currently chatting in: #{current_channel.name} ({current_channel.guild.name})\n")
    while not bot.is_closed():
        try:
            msg = await asyncio.to_thread(input, f"[#{current_channel.name}] > ")
        except (EOFError, KeyboardInterrupt):
            break
        text = msg.strip()
        if not text:
            continue
        if text == "/shutdown" or text == "/restart":
            await bot.close()
            break
        if text.startswith("/"):
            current_channel = await execute_admin_command(text, current_channel)
        else:
            try:
                await current_channel.send(text)
                chat_memory.setdefault(str(current_channel.id), []).append({"role": "assistant", "content": text})
                save_json_file(MEMORY_FILE, chat_memory)
            except Exception as e:
                print(f"Failed to send: {e}")


@bot.event
async def on_ready():
    run_startup_diagnostics()
    print(f"Logged in as {bot.user}")
    await restore_bot_state()
    if IS_INTERACTIVE:
        bot.loop.create_task(manual_console_sender())
    else:
        bot.loop.create_task(start_keepalive_server())


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if OWNER_ID and message.author.id == OWNER_ID and message.content.lower().startswith("!bot "):
        cmd_body = message.content[5:].strip()
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            await execute_admin_command(cmd_body, message.channel)
        finally:
            sys.stdout = old_stdout
        output = buf.getvalue().strip()
        if output:
            await message.reply(f"```text\n{output[:1900]}\n```")
        else:
            await message.add_reaction("✅")
        return

    is_dm = isinstance(message.channel, discord.DMChannel)
    if is_dm:
        log_and_open_dm_window(message.author.id, message.author.name, message.author.name, message.content)

    if not is_dm:
        handled = await handle_discord_command(message)
        if handled:
            return

    if bot.user in message.mentions or is_dm:
        await ai_reply(message, is_dm)


bot.run(DISCORD_TOKEN)
