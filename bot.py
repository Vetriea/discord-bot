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
import signal
import urllib.request
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
        return
    name = os.path.basename(path)
    if STORAGE_CHANNEL_ID and name in BACKUP_FILES:
        dirty_backups.add(name)


# ---------------------------------------------------------------------------
# Persistent storage: backs up the JSON data files to a private Discord channel
# so they survive Render redeploys. Turned on by setting STORAGE_CHANNEL_ID.
# ---------------------------------------------------------------------------
STORAGE_CHANNEL_ID = int(os.getenv("STORAGE_CHANNEL_ID", "0").strip() or "0")
BACKUP_FILES = {MEMORY_FILE, PERSONAS_FILE, BOT_STATE_FILE, TRIVIA_CUSTOM_FILE}
BACKUP_MAX_BYTES = 8 * 1024 * 1024
DISCORD_API = "https://discord.com/api/v10"
backup_message_ids = {}
dirty_backups = set()
last_backup_error = ""


def _discord_http_get(url, raw=False):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bot {DISCORD_TOKEN}",
        "User-Agent": "DiscordBot (https://github.com/Vetriea/discord-bot, 1.0)",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    return data if raw else json.loads(data.decode("utf-8"))


def restore_from_discord():
    """Runs once at startup, before the data files are loaded.
    Downloads each missing data file from the storage channel."""
    if not STORAGE_CHANNEL_ID:
        return
    try:
        me = _discord_http_get(f"{DISCORD_API}/users/@me")
        msgs = _discord_http_get(f"{DISCORD_API}/channels/{STORAGE_CHANNEL_ID}/messages?limit=100")
    except Exception as e:
        print(f"Storage: could not read the backup channel ({e}). Check STORAGE_CHANNEL_ID and that the bot can see that channel.")
        return
    seen = set()
    restored = []
    for m in msgs:  # newest first
        if m.get("author", {}).get("id") != me.get("id"):
            continue
        for att in m.get("attachments", []):
            name = att.get("filename")
            if name not in BACKUP_FILES or name in seen:
                continue
            seen.add(name)
            backup_message_ids[name] = int(m["id"])
            if os.path.isfile(name):
                continue  # a local copy exists, don't overwrite it
            try:
                data = _discord_http_get(att["url"], raw=True)
                json.loads(data.decode("utf-8"))  # make sure it's valid before using it
                with open(name, "wb") as f:
                    f.write(data)
                restored.append(name)
            except Exception as e:
                print(f"Storage: could not restore {name}: {e}")
    if restored:
        print(f"Storage: restored {', '.join(sorted(restored))} from Discord.")
    else:
        print("Storage: connected, nothing to restore.")


restore_from_discord()


def _backup_file_obj(name):
    with open(name, "rb") as f:
        data = f.read()
    if len(data) > BACKUP_MAX_BYTES:
        raise ValueError(f"{name} is {len(data) // 1024} KB, too big to back up (limit {BACKUP_MAX_BYTES // 1024} KB)")
    return discord.File(io.BytesIO(data), filename=name)


async def backup_dirty_files():
    """Uploads every changed data file to the storage channel. Returns how many were saved."""
    global last_backup_error
    if not STORAGE_CHANNEL_ID or not dirty_backups:
        return 0
    channel = bot.get_channel(STORAGE_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(STORAGE_CHANNEL_ID)
        except Exception as e:
            last_backup_error = f"cannot open storage channel: {e}"
            print(f"Storage: {last_backup_error}")
            return 0
    saved = 0
    for name in list(dirty_backups):
        dirty_backups.discard(name)
        try:
            if not os.path.isfile(name):
                continue
            msg_id = backup_message_ids.get(name)
            if msg_id:
                try:
                    msg = await channel.fetch_message(msg_id)
                    await msg.edit(attachments=[_backup_file_obj(name)])
                    saved += 1
                    continue
                except discord.NotFound:
                    pass
            sent = await channel.send(content=f"Backup: {name}", file=_backup_file_obj(name))
            backup_message_ids[name] = sent.id
            saved += 1
        except Exception as e:
            last_backup_error = f"{name}: {e}"
            print(f"Storage: backup of {name} failed: {e}")
            if not isinstance(e, ValueError):
                dirty_backups.add(name)  # try again next round
    if saved:
        last_backup_error = ""
    return saved


async def backup_loop():
    await bot.wait_until_ready()
    for name in BACKUP_FILES:  # first run: back up anything that has no copy yet
        if os.path.isfile(name) and name not in backup_message_ids:
            dirty_backups.add(name)
    while True:
        await asyncio.sleep(10)
        if dirty_backups:
            await backup_dirty_files()


async def flush_and_close():
    """On a shutdown signal (Render redeploy) save everything, then stop."""
    try:
        await asyncio.wait_for(backup_dirty_files(), timeout=15)
    except Exception as e:
        print(f"Storage: final backup failed: {e}")
    await bot.close()


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


DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "").strip()
web_current_channel = None  # persistent channel for web dashboard commands


def check_auth(request):
    """Check if the request has a valid auth token."""
    if not DASHBOARD_PASSWORD:
        return False
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:] == DASHBOARD_PASSWORD
    return False


def get_web_current_channel():
    """Get or initialize the web dashboard's current channel."""
    global web_current_channel
    if web_current_channel is not None:
        return web_current_channel
    writable = [
        ch for ch in bot.get_all_channels()
        if isinstance(ch, discord.TextChannel) and ch.permissions_for(ch.guild.me).send_messages
    ]
    if writable:
        web_current_channel = writable[0]
    return web_current_channel


async def handle_root(request):
    return web.Response(text="Bot is online 24/7!")


async def handle_panel(request):
    if not DASHBOARD_PASSWORD:
        return web.Response(text="Dashboard disabled. Set DASHBOARD_PASSWORD env var to enable.", status=403)
    return web.Response(text=DASHBOARD_HTML, content_type="text/html")


async def handle_login(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON"})
    pw = data.get("password", "")
    if pw == DASHBOARD_PASSWORD:
        return web.json_response({"ok": True})
    return web.json_response({"ok": False, "error": "Wrong password"})


async def handle_api_command(request):
    if not check_auth(request):
        return web.json_response({"ok": False, "error": "Unauthorized"}, status=401)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON"})
    cmd = data.get("command", "").strip()
    if not cmd:
        return web.json_response({"ok": False, "error": "No command provided"})
    current_ch = get_web_current_channel()
    if current_ch is None:
        return web.json_response({"ok": False, "error": "No writable channel available"})
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        new_ch = await execute_admin_command(cmd, current_ch)
        if new_ch is not None:
            global web_current_channel
            web_current_channel = new_ch
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        sys.stdout = old_stdout
    output = buf.getvalue().strip()
    return web.json_response({"ok": True, "output": output[:4000]})


async def handle_api_status(request):
    if not check_auth(request):
        return web.json_response({"ok": False}, status=401)
    uptime = format_uptime((datetime.datetime.now() - START_TIME).total_seconds())
    total_members = sum(g.member_count or 0 for g in bot.guilds)
    status = bot_state.get("status", "online")
    activity_data = bot_state.get("activity", {})
    activity_str = "—"
    if activity_data and activity_data.get("type") != "clear":
        activity_str = f"{activity_data.get('type', '').title()} {activity_data.get('name', '')}"
    current_ch = get_web_current_channel()
    return web.json_response({
        "ok": True,
        "online": True,
        "uptime": uptime,
        "latency": round(bot.latency * 1000, 1),
        "servers": len(bot.guilds),
        "members": total_members,
        "status": status,
        "activity": activity_str,
        "current_channel": f"#{current_ch.name}" if current_ch else "none",
    })


async def handle_api_channels(request):
    """Return list of text channels for the dropdown."""
    if not check_auth(request):
        return web.json_response({"ok": False}, status=401)
    channels = []
    for ch in bot.get_all_channels():
        if isinstance(ch, discord.TextChannel) and ch.permissions_for(ch.guild.me).send_messages:
            channels.append({
                "id": str(ch.id),  # MUST be string — JS loses precision on 18-digit numbers
                "name": ch.name,
                "guild": ch.guild.name,
            })
    return web.json_response({"ok": True, "channels": channels})


async def handle_api_send(request):
    """Send a message as the bot to a channel."""
    if not check_auth(request):
        return web.json_response({"ok": False, "error": "Unauthorized"}, status=401)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON"})
    message = data.get("message", "").strip()
    channel_str = data.get("channel", "").strip()
    if not message:
        return web.json_response({"ok": False, "error": "No message"})
    if len(message) > 2000:
        return web.json_response({"ok": False, "error": "Message too long (max 2000 chars)"})
    # Resolve target channel
    target = None
    if channel_str:
        if channel_str.isdigit():
            target = bot.get_channel(int(channel_str))
        else:
            target = discord.utils.find(
                lambda c: isinstance(c, discord.TextChannel) and c.name.lower() == channel_str.lstrip("#").lower(),
                bot.get_all_channels()
            )
    else:
        target = get_web_current_channel()
    if not target or not isinstance(target, discord.TextChannel):
        return web.json_response({"ok": False, "error": "No valid channel. Set one first or pass channel field."})
    if not target.permissions_for(target.guild.me).send_messages:
        return web.json_response({"ok": False, "error": f"Bot lacks Send Messages permission in #{target.name}"})
    try:
        await target.send(message)
        # Save to chat memory as assistant message
        chat_memory.setdefault(str(target.id), []).append({"role": "assistant", "content": message})
        save_json_file(MEMORY_FILE, chat_memory)
        return web.json_response({"ok": True, "channel": f"#{target.name}", "guild": target.guild.name})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})


async def handle_api_messages(request):
    """Fetch recent messages from a channel."""
    if not check_auth(request):
        return web.json_response({"ok": False}, status=401)
    channel_str = request.query.get("channel", "")
    try:
        limit = int(request.query.get("limit", "15"))
    except ValueError:
        limit = 15
    if limit < 1 or limit > 50:
        limit = 15
    # Resolve channel
    target = None
    if channel_str:
        if channel_str.isdigit():
            target = bot.get_channel(int(channel_str))
        else:
            target = discord.utils.find(
                lambda c: isinstance(c, discord.TextChannel) and c.name.lower() == channel_str.lstrip("#").lower(),
                bot.get_all_channels()
            )
    else:
        target = get_web_current_channel()
    if not target or not isinstance(target, discord.TextChannel):
        return web.json_response({"ok": False, "error": "No channel"})
    try:
        msgs = []
        async for msg in target.history(limit=limit):
            content = msg.content
            if not content:
                if msg.embeds:
                    content = "[embed]"
                elif msg.attachments:
                    content = f"[attachment: {msg.attachments[0].filename}]"
                else:
                    content = "(empty)"
            msgs.append({
                "id": msg.id,
                "author": msg.author.display_name,
                "author_id": msg.author.id,
                "content": content[:800],
                "timestamp": msg.created_at.strftime("%H:%M:%S"),
                "bot": msg.author.bot,
                "avatar": str(msg.author.display_avatar.url) if msg.author.display_avatar else None,
            })
        msgs.reverse()  # oldest first, like a chat log
        return web.json_response({"ok": True, "messages": msgs, "channel": f"#{target.name}", "guild": target.guild.name})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})


async def start_keepalive_server():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/panel", handle_panel)
    app.router.add_post("/api/login", handle_login)
    app.router.add_post("/api/command", handle_api_command)
    app.router.add_get("/api/status", handle_api_status)
    app.router.add_get("/api/channels", handle_api_channels)
    app.router.add_post("/api/send", handle_api_send)
    app.router.add_get("/api/messages", handle_api_messages)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server listening on port {port}")
    if DASHBOARD_PASSWORD:
        print(f"Dashboard: http://localhost:{port}/panel (or your Render URL)")
    else:
        print("Dashboard disabled (set DASHBOARD_PASSWORD env var to enable)")


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bot Control Panel</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0d1117;color:#e6edf3;min-height:100vh}
.login{display:flex;justify-content:center;align-items:center;min-height:100vh;padding:1rem}
.login-box{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:2rem;width:100%;max-width:360px}
.login-box h1{font-size:1.4rem;margin-bottom:1.5rem;text-align:center}
.login-box input{width:100%;padding:0.75rem;border-radius:8px;border:1px solid #30363d;background:#0d1117;color:#e6edf3;font-size:1rem;margin-bottom:0.75rem}
.login-box button{width:100%;padding:0.75rem;border-radius:8px;border:none;background:#238636;color:white;font-size:1rem;cursor:pointer}
.login-box button:hover{background:#2ea043}
.err{color:#f85149;font-size:0.85rem;margin-top:0.5rem;text-align:center}
.dash{display:none}
.hdr{background:#161b22;padding:0.75rem 1rem;border-bottom:1px solid #30363d;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:10}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:#3fb950;margin-right:0.5rem}
.tabs{display:flex;background:#161b22;border-bottom:1px solid #30363d;overflow-x:auto;position:sticky;top:57px;z-index:9}
.tab{padding:0.75rem 1.25rem;cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap;font-size:0.9rem}
.tab.act{border-bottom:2px solid #f78166;background:#0d1117}
.tab:hover{background:#0d1117}
.main{padding:1rem;max-width:900px;margin:0 auto}
.card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:1.25rem;margin-bottom:1rem}
.card h2{font-size:1rem;margin-bottom:0.75rem;color:#f78166}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:0.75rem}
.stat{background:#0d1117;padding:0.75rem;border-radius:8px;text-align:center}
.stat v{font-size:1.3rem;font-weight:bold;display:block}
.stat l{font-size:0.75rem;opacity:0.6}
.btn{padding:0.5rem 1rem;border-radius:8px;border:1px solid #30363d;background:#21262d;color:#e6edf3;cursor:pointer;font-size:0.85rem}
.btn:hover{background:#30363d}
.btn-g{background:#238636;border-color:#238636;color:white}
.btn-g:hover{background:#2ea043}
.btn-r{background:#da3633;border-color:#da3633;color:white}
.btn-r:hover{background:#f85149}
input,select,textarea{padding:0.5rem;border-radius:8px;border:1px solid #30363d;background:#0d1117;color:#e6edf3;font-size:0.85rem;width:100%;font-family:inherit}
textarea{resize:vertical}
label{font-size:0.8rem;opacity:0.7;display:block;margin-bottom:0.25rem}
.row{display:flex;gap:0.5rem;align-items:flex-end;margin-bottom:0.5rem;flex-wrap:wrap}
.row>*{flex:1}
.row>.btn{flex:0 0 auto}
.out{background:#0d1117;border:1px solid #30363d;padding:0.75rem;border-radius:8px;font-family:'SF Mono',Monaco,monospace;font-size:0.8rem;white-space:pre-wrap;margin-top:0.5rem;max-height:250px;overflow-y:auto;word-break:break-word}
.hide{display:none}
.info{font-size:0.8rem;opacity:0.6;margin-bottom:0.5rem}
@media(max-width:600px){.main{padding:0.75rem}.grid{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<div class="login" id="login">
<div class="login-box">
<h1>🤖 Bot Panel</h1>
<input type="password" id="pw" placeholder="Password" onkeydown="if(event.key==='Enter')login()">
<button onclick="login()">Login</button>
<div class="err" id="err"></div>
</div>
</div>
<div class="dash" id="dash">
<div class="hdr">
<div><span class="dot"></span><strong>Bot Control Panel</strong></div>
<button class="btn" onclick="logout()">Logout</button>
</div>
<div class="tabs">
<div class="tab act" onclick="tab('overview',this)">📊 Overview</div>
<div class="tab" onclick="tab('trivia',this)">🎯 Trivia</div>
<div class="tab" onclick="tab('snipe',this)">🔫 Snipe</div>
<div class="tab" onclick="tab('ai',this)">🤖 AI</div>
<div class="tab" onclick="tab('chat',this);loadCh();loadMsgs()">💬 Chat</div>
<div class="tab" onclick="tab('cmd',this)">💻 Console</div>
</div>
<div class="main">
<div id="t-overview">
<div class="card"><h2>Status</h2><div class="grid" id="stats"></div></div>
<div class="card">
<h2>Presence</h2>
<div class="row">
<div><label>Status</label><select id="st"><option>online</option><option>idle</option><option>dnd</option><option>invisible</option></select></div>
<div><label>Activity Type</label><select id="at"><option value="clear">Clear</option><option>playing</option><option>listening</option><option>watching</option></select></div>
<div><label>Activity Text</label><input id="ax" placeholder="e.g. Minecraft"></div>
<button class="btn btn-g" onclick="setPresence()">Apply</button>
</div>
</div>
<div class="card">
<h2>Quick Actions</h2>
<div class="row">
<button class="btn" onclick="cmd('diag')">Diagnostics</button>
<button class="btn" onclick="cmd('list')">List Channels</button>
<button class="btn" onclick="cmd('info')">Bot Info</button>
<button class="btn btn-r" onclick="if(confirm('Restart bot?'))cmd('shutdown')">Restart</button>
</div>
<div class="out" id="o-quick"></div>
</div>
</div>
<div id="t-trivia" class="hide">
<div class="card">
<h2>Start Trivia</h2>
<div class="info">Enter a channel name/ID, or leave blank for current channel.</div>
<div class="row"><input id="tc" placeholder="channel name or ID"><button class="btn btn-g" onclick="cmd('trivia '+(document.getElementById('tc').value||''))">Start</button><button class="btn btn-r" onclick="cmd('triviastop')">Stop</button></div>
</div>
<div class="card">
<h2>Custom Questions</h2>
<div class="row"><button class="btn" onclick="cmd('customq')">List All</button><button class="btn" onclick="cmd('qstats')">Stats</button></div>
<div class="out" id="o-trivia"></div>
</div>
<div class="card">
<h2>Add Question</h2>
<div class="info">Format: Topic | Question | Answer</div>
<div class="row"><input id="aq" placeholder="Cruel King | What castle does he live in? | Blackrock Castle"><button class="btn btn-g" onclick="cmd('say customq_add_helper')">Add via Discord</button></div>
<div class="info">Note: Use <code>!addq Topic | Question | Answer</code> in Discord chat to add questions.</div>
</div>
</div>
<div id="t-snipe" class="hide">
<div class="card">
<h2>Snipe Alert Config</h2>
<div class="info">Forward all deleted messages to a channel.</div>
<div class="row"><input id="sc" placeholder="channel name or ID"><button class="btn btn-g" onclick="cmd('snipealert '+(document.getElementById('sc').value||''))">Set</button><button class="btn btn-r" onclick="cmd('snipealert clear')">Clear</button></div>
<div class="row"><button class="btn" onclick="cmd('snipealert edits on')">Edits ON</button><button class="btn" onclick="cmd('snipealert edits off')">Edits OFF</button></div>
</div>
<div class="card">
<h2>Snipe Data</h2>
<div class="row"><button class="btn" onclick="cmd('snipestats')">Stats</button><button class="btn btn-r" onclick="if(confirm('Wipe ALL snipe data?'))cmd('snipewipe')">Wipe All</button></div>
<div class="out" id="o-snipe"></div>
</div>
</div>
<div id="t-ai" class="hide">
<div class="card">
<h2>Persona</h2>
<textarea id="pt" rows="3" placeholder="Enter persona prompt..."></textarea>
<div class="row" style="margin-top:0.5rem"><button class="btn btn-g" onclick="cmd('persona '+(document.getElementById('pt').value||''))">Set</button><button class="btn" onclick="cmd('resetpersona')">Reset</button><button class="btn" onclick="cmd('personas')">List Saved</button></div>
</div>
<div class="card">
<h2>Model & Memory</h2>
<div class="row"><button class="btn" onclick="cmd('memory')">View Memory</button><button class="btn" onclick="cmd('info')">Bot Info</button><button class="btn btn-r" onclick="if(confirm('Wipe ALL memory?'))cmd('forgetall')">Wipe Memory</button></div>
<div class="out" id="o-ai"></div>
</div>
</div>
<div id="t-chat" class="hide">
<div class="card">
<h2>📢 Active Channel</h2>
<div class="info" id="cur-ch">Current: —</div>
</div>
<div class="card">
<h2>📋 Switch Channel</h2>
<div class="info">Click a channel to make it active:</div>
<div id="ch-list" style="max-height:280px;overflow-y:auto;"></div>
<button class="btn" style="margin-top:0.5rem" onclick="loadCh()">Refresh List</button>
</div>
<div class="card">
<h2>✉️ Send Message as Bot</h2>
<textarea id="msg" rows="3" placeholder="Type a message to send as the bot..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendMsg()}"></textarea>
<div class="row" style="margin-top:0.5rem">
<button class="btn btn-g" onclick="sendMsg()">Send</button>
<button class="btn" onclick="document.getElementById('msg').value=''">Clear</button>
</div>
<div class="out" id="o-send"></div>
</div>
<div class="card">
<h2>📜 Recent Messages</h2>
<div class="row">
<button class="btn" onclick="loadMsgs()">Refresh</button>
<div class="info" id="msg-ch" style="flex:2;text-align:right"></div>
</div>
<div id="msgs" style="margin-top:0.5rem;"></div>
</div>
</div>
<div id="t-cmd" class="hide">
<div class="card">
<h2>Raw Command</h2>
<div class="info">Type any command as if using the console (without the / prefix).</div>
<div class="row"><input id="rc" placeholder="e.g. status dnd" onkeydown="if(event.key==='Enter')raw()"><button class="btn btn-g" onclick="raw()">Run</button></div>
<div class="out" id="o-cmd"></div>
</div>
</div>
</div>
</div>
<script>
let tk=localStorage.getItem('bp')||'';
function api(p,m='GET',b){const o={method:m,headers:{'Authorization':'Bearer '+tk}};if(b){o.headers['Content-Type']='application/json';o.body=JSON.stringify(b)}return fetch(p,o).then(r=>r.json())}
function login(){const p=document.getElementById('pw').value;fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:p})}).then(r=>r.json()).then(d=>{if(d.ok){tk=p;localStorage.setItem('bp',p);show()}else{document.getElementById('err').textContent='Wrong password'}})}
function logout(){localStorage.removeItem('bp');tk='';location.reload()}
function show(){document.getElementById('login').style.display='none';document.getElementById('dash').style.display='block';refresh()}
function tab(n,e){document.querySelectorAll('.tab').forEach(t=>t.classList.remove('act'));e.classList.add('act');document.querySelectorAll('[id^="t-"]').forEach(d=>d.classList.add('hide'));document.getElementById('t-'+n).classList.remove('hide')}
function cmd(c){api('/api/command','POST',{command:c}).then(d=>{const el=document.querySelector('.out:not(.hide)')||document.getElementById('o-quick');el.textContent=d.output||'(no output)'})}
function raw(){const c=document.getElementById('rc').value;if(!c)return;api('/api/command','POST',{command:c}).then(d=>{document.getElementById('o-cmd').textContent=d.output||'(no output)'})}
function setPresence(){const s=document.getElementById('st').value,t=document.getElementById('at').value,x=document.getElementById('ax').value;api('/api/command','POST',{command:'status '+s}).then(()=>{if(t!=='clear'&&x)return api('/api/command','POST',{command:t+' '+x});return{ok:true}}).then(()=>{document.getElementById('o-quick').textContent='Presence updated!';refresh()})}
function refresh(){api('/api/status').then(d=>{if(!d.ok)return;document.getElementById('stats').innerHTML=`<div class="stat"><v>${d.uptime}</v><l>Uptime</l></div><div class="stat"><v>${d.latency}ms</v><l>Latency</l></div><div class="stat"><v>${d.servers}</v><l>Servers</l></div><div class="stat"><v>${d.members}</v><l>Members</l></div><div class="stat"><v style="font-size:0.9rem">${d.status}</v><l>Status</l></div><div class="stat"><v style="font-size:0.8rem">${d.activity}</v><l>Activity</l></div><div class="stat" style="grid-column:1/-1"><v style="font-size:0.85rem">${d.current_channel}</v><l>Active Channel</l></div>`;document.getElementById('cur-ch').textContent='Current: '+(d.current_channel||'—')})}
function loadCh(){api('/api/channels').then(d=>{if(!d.ok)return;const l=document.getElementById('ch-list');l.innerHTML=d.channels.map(c=>`<button class="btn" style="display:block;width:100%;text-align:left;margin-bottom:0.25rem;font-size:0.85rem" onclick="setCh('${c.id}')">#${c.name}<span style="opacity:0.5"> · ${c.guild}</span></button>`).join('')||'<div class="info">No channels found.</div>'})}
function setCh(id){api('/api/command','POST',{command:'ch '+id}).then(d=>{document.getElementById('o-send').textContent=d.output||'Switched';refresh();loadMsgs()})}
function sendMsg(){const m=document.getElementById('msg').value;if(!m.trim())return;api('/api/send','POST',{message:m}).then(d=>{if(d.ok){document.getElementById('o-send').textContent='✅ Sent to '+d.channel+' ('+d.guild+')';document.getElementById('msg').value='';loadMsgs()}else{document.getElementById('o-send').textContent='❌ '+d.error}})}
function loadMsgs(){api('/api/messages?limit=20').then(d=>{if(!d.ok){document.getElementById('msgs').innerHTML='<div class="info">'+(d.error||'No channel')+'</div>';return}document.getElementById('msg-ch').textContent=d.channel+' · '+d.guild;document.getElementById('msgs').innerHTML=d.messages.map(m=>`<div style="padding:0.5rem 0;border-bottom:1px solid #30363d;"><span style="font-size:0.7rem;opacity:0.5">${m.timestamp}</span> <strong style="color:${m.bot?'#f78166':'#58a6ff'}">${m.author}:</strong> <span style="word-break:break-word">${m.content}</span></div>`).join('')||'<div class="info">No messages yet.</div>'})}
if(tk){api('/api/status').then(d=>{if(d.ok)show()})}
setInterval(()=>{if(tk)refresh()},30000);
</script>
</body>
</html>"""





def run_startup_diagnostics():
    print("\n--- SYSTEM DIAGNOSTICS ---")
    print(f"Mode              : {'Interactive PC Console' if IS_INTERACTIVE else 'Headless Cloud (Render/Server)'}")
    print(f"Owner ID          : {OWNER_ID if OWNER_ID else 'Not set (set OWNER_ID in env for !bot commands)'}")
    print(f"Dashboard         : {'ENABLED — visit /panel' if DASHBOARD_PASSWORD else 'DISABLED (set DASHBOARD_PASSWORD env var)'}")
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


KNOWN_DISCORD_COMMANDS = {"!addq", "!qstats", "!qlist", "!emoji", "!snipe", "!editsnipe", "!photo", "!help"}

# Admin commands that the owner can invoke directly via "!<command>" (no "!bot" wrapper needed).
# These map to the same handlers as the console /commands.
ADMIN_DISCORD_COMMANDS = {
    "trivia", "triviastop", "status", "activity", "persona", "resetpersona",
    "savepersona", "loadpersona", "personas", "model", "forget", "forgetall",
    "clear", "snipealert", "snipestats", "snipewipe", "customq", "diag",
    "list", "ch", "say", "vc", "tts", "pitch", "play", "stop", "leave",
    "dm", "shutdown", "restart", "pause", "resume", "nick", "avatar",
    "temperature", "maxtokens", "info", "ping", "uptime", "servers",
    "members", "whois", "channelinfo", "serverinfo", "memory", "export",
    "purge", "say", "reply", "react", "embed", "spam", "poll", "timer",
    "reload", "backup", "ban", "unban", "kick", "timeout", "untimeout",
}


active_command_message = None


async def run_admin_from_discord(cmd_body: str, message: discord.Message):
    """Run an admin command from Discord, capture stdout, and reply with it."""
    global active_command_message
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    active_command_message = message
    try:
        await execute_admin_command(cmd_body, message.channel)
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        sys.stdout = old_stdout
        active_command_message = None
    output = buf.getvalue().strip()
    if output:
        # Split into chunks of 1900 chars (code block wrapper takes some)
        for i in range(0, len(output), 1900):
            await message.reply(f"```text\n{output[i:i+1900]}\n```")
    else:
        await message.add_reaction("✅")


async def cmd_help_discord(message: discord.Message):
    """Show all available Discord commands."""
    is_owner = OWNER_ID and message.author.id == OWNER_ID
    lines = ["📖 **Public commands** (anyone can use):"]
    lines.append("  `!addq Topic | Question | Answer` — add a trivia question")
    lines.append("  `!qstats` — custom question counts")
    lines.append("  `!qlist Topic` — DM you questions in a topic")
    lines.append("  `!emoji Topic 👑` — set a topic emoji")
    lines.append("  `!snipe [N]` — show the Nth recent deleted message")
    lines.append("  `!editsnipe [N]` — show the Nth recent edited message")
    lines.append("  `!photo [#channel]` — forward an attached/replied image")
    lines.append("  `!help` — this message")
    if is_owner:
        lines.append("")
        lines.append("🔐 **Owner commands** (you can use these):")
        lines.append("  `!trivia [channel]` — start trivia  •  `!triviastop` — abort")
        lines.append("  `!status <online|idle|dnd|invisible>`  •  `!activity playing <text>`")
        lines.append("  `!persona <prompt>`  •  `!resetpersona`  •  `!savepersona <name>`  •  `!loadpersona <name>`")
        lines.append("  `!snipealert <channel|here|clear>`  •  `!snipealert edits on|off`")
        lines.append("  `!snipestats`  •  `!snipewipe`  •  `!customq`")
        lines.append("  `!clear`  •  `!purge <count>`  •  `!forget`  •  `!forgetall`")
        lines.append("  `!list`  •  `!diag`  •  `!info`  •  `!ping`  •  `!uptime`")
        lines.append("  `!ban <user> [reason]`  •  `!unban <user id> [reason]`  •  `!kick <user> [reason]`")
        lines.append("  `!timeout <user> <10m|2h|1d> [reason]`  •  `!untimeout <user>`")
        lines.append("  `!backup`  (save your data to the storage channel now)")
        lines.append("  `!say <#channel> <msg>`  •  `!dm <uid> <msg>`")
        lines.append("  `!model <name>`  •  `!vc <name>`  •  `!play <query>`  •  `!stop`  •  `!leave`")
        lines.append("  *(also: `!bot /<command>` still works as a fallback)*")
    else:
        lines.append("")
        lines.append("🔐 Admin commands are owner-only. Set `OWNER_ID` to enable them.")
    embed = discord.Embed(
        title="Commands",
        description="\n".join(lines),
        color=discord.Color.blurple(),
    )
    await message.reply(embed=embed)


async def handle_discord_command(message: discord.Message) -> bool:
    """Check for Discord-side commands (! prefix). Returns True if handled."""
    if not message.content or not message.content.startswith("!"):
        return False
    parts = message.content.split()
    first_word = parts[0].lower() if parts else ""

    # === Public commands (anyone can use) ===
    if first_word in KNOWN_DISCORD_COMMANDS:
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
        elif first_word == "!photo":
            await cmd_photo(message)
        elif first_word == "!help":
            await cmd_help_discord(message)
        return True

    # === Legacy "!bot <command>" wrapper (owner only) ===
    if first_word == "!bot":
        if not OWNER_ID or message.author.id != OWNER_ID:
            return False  # not owner — let it fall through (won't trigger AI since no mention)
        if len(parts) < 2:
            await message.reply("Usage: `!bot <command>` or just `!<command>` directly (e.g. `!trivia`).")
            return True
        cmd_body = message.content[5:].strip()  # strip "!bot "
        await run_admin_from_discord(cmd_body, message)
        return True

    # === Direct admin commands: "!trivia", "!status dnd", etc. (owner only) ===
    admin_cmd_name = first_word.lstrip("!").lower()
    if admin_cmd_name in ADMIN_DISCORD_COMMANDS:
        if not OWNER_ID:
            return False  # OWNER_ID not configured — don't intercept
        if message.author.id != OWNER_ID:
            return False  # not owner — silently ignore (don't reply, don't trigger AI)
        # Strip the leading "!" and pass to the admin dispatcher
        cmd_body = message.content[1:].strip()  # e.g. "trivia" or "status dnd"
        await run_admin_from_discord(cmd_body, message)
        return True

    return False


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


async def cmd_photo(message: discord.Message):
    """Forward an image to a channel. Usage:
    - Attach an image + type `!photo`             -> re-posts in same channel
    - Attach an image + type `!photo #general`    -> sends to #general
    - Reply to a message with an image + `!photo` -> forwards that image
    - Type `!photo <url> [#channel]`              -> sends URL image as embed
    """
    parts = message.content.split()
    # Default target = current channel
    target_channel = message.channel
    target_arg = None
    if len(parts) >= 2:
        target_arg = parts[1].strip().lstrip("#")

    # Resolve target channel
    if target_arg:
        if target_arg.isdigit():
            found = bot.get_channel(int(target_arg))
            if found and isinstance(found, discord.TextChannel):
                target_channel = found
            else:
                await message.reply(f"Couldn't find a text channel with ID `{target_arg}`.")
                return
        else:
            found = discord.utils.find(
                lambda c: isinstance(c, discord.TextChannel) and c.name.lower() == target_arg.lower(),
                bot.get_all_channels()
            )
            if found:
                target_channel = found
            else:
                await message.reply(f"Couldn't find a channel named `#{target_arg}`. Try `/list` or use a channel ID.")
                return

    # Check permissions
    if not target_channel.permissions_for(target_channel.guild.me).send_messages:
        await message.reply(f"Bot lacks **Send Messages** permission in #{target_channel.name}.")
        return
    needs_files = True
    if not target_channel.permissions_for(target_channel.guild.me).attach_files:
        needs_files = False

    # === Source 1: attachment on this message ===
    image_attachment = None
    if message.attachments:
        for att in message.attachments:
            ct = getattr(att, "content_type", None) or ""
            if ct.startswith("image/") or any(att.filename.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
                image_attachment = att
                break
        if not image_attachment:
            # No image-typed attachment; fall back to first attachment
            image_attachment = message.attachments[0]

    # === Source 2: replied-to message with an attachment ===
    if not image_attachment and message.reference:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            if ref_msg.attachments:
                for att in ref_msg.attachments:
                    ct = getattr(att, "content_type", None) or ""
                    if ct.startswith("image/") or any(att.filename.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
                        image_attachment = att
                        break
                if not image_attachment:
                    image_attachment = ref_msg.attachments[0]
        except Exception as e:
            print(f"Photo: couldn't fetch replied message: {e}")

    # === Source 3: URL in the message content ===
    if not image_attachment:
        # Look for a URL anywhere in the content (could be the 2nd arg if 1st was a channel)
        url_match = re.search(r"https?://\S+\.(?:png|jpg|jpeg|gif|webp|bmp)(?:\?\S*)?", message.content, re.IGNORECASE)
        if not url_match:
            # Broader URL match (for CDN links without file extension)
            url_match = re.search(r"https?://\S+", message.content)
        if url_match:
            url = url_match.group()
            # Don't treat the channel arg as a URL
            if target_arg and url.rstrip(",.") == target_arg:
                url_match = None
            if url_match:
                if not target_channel.permissions_for(target_channel.guild.me).embed_links:
                    await message.reply(f"Bot lacks **Embed Links** permission in #{target_channel.name} — can't post URL images.")
                    return
                try:
                    embed = discord.Embed(color=discord.Color.blurple())
                    embed.set_image(url=url)
                    await target_channel.send(embed=embed)
                    if target_channel.id != message.channel.id:
                        await message.reply(f"📸 Sent image URL to #{target_channel.name}")
                    return
                except Exception as e:
                    await message.reply(f"Failed to send URL image: {e}")
                    return

    if not image_attachment:
        await message.reply(
            "📸 **Usage:**\n"
            "• Attach an image + type `!photo` to re-post it here\n"
            "• Attach an image + type `!photo #channel` to send it there\n"
            "• Reply to a message with an image + type `!photo [channel]`\n"
            "• Type `!photo <image_url> [channel]` to send a URL image"
        )
        return

    if not needs_files:
        await message.reply(f"Bot lacks **Attach Files** permission in #{target_channel.name}.")
        return

    # Download the attachment and re-send it
    try:
        image_data = await image_attachment.read()
        file_obj = discord.File(io.BytesIO(image_data), filename=image_attachment.filename)
        await target_channel.send(file=file_obj)
        if target_channel.id != message.channel.id:
            await message.reply(f"📸 Sent `{image_attachment.filename}` to #{target_channel.name}")
        else:
            try:
                await message.delete()
            except Exception:
                pass
    except Exception as e:
        await message.reply(f"Failed to send image: {e}")


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


MAX_TIMEOUT = datetime.timedelta(days=28)


def parse_user_id(token: str):
    """Turn '<@123>', '<@!123>' or '123' into an int user ID, else None."""
    m = re.fullmatch(r"<@!?(\d{15,25})>|(\d{15,25})", token.strip())
    if not m:
        return None
    return int(m.group(1) or m.group(2))


def parse_duration(token: str):
    """Turn '30s', '10m', '2h', '1d', '1w' (or combos like '1h30m') into a timedelta, else None."""
    token = token.strip().lower()
    if not re.fullmatch(r"(\d+[smhdw])+", token):
        return None
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    total = sum(int(n) * units[u] for n, u in re.findall(r"(\d+)([smhdw])", token))
    return datetime.timedelta(seconds=total) if total > 0 else None


def mod_target_error(user_id: int, guild: discord.Guild):
    """Return an error string if this user must not be moderated, else None."""
    if user_id == bot.user.id:
        return "I won't do that to myself."
    if OWNER_ID and user_id == OWNER_ID:
        return "That's the bot owner, refusing."
    if user_id == guild.owner_id:
        return "That's the server owner, Discord doesn't allow that."
    return None


async def execute_mod_command(name: str, args: str, current_channel):
    """Handle ban / unban / kick / timeout / untimeout. Prints the result."""
    guild = getattr(current_channel, "guild", None)
    if guild is None:
        print("Moderation commands only work in a server channel. Use !ch <channel> to pick one.")
        return
    usage = {
        "ban": "Usage: !ban <@user|id> [reason]",
        "unban": "Usage: !unban <user id> [reason]",
        "kick": "Usage: !kick <@user|id> [reason]",
        "timeout": "Usage: !timeout <@user|id> <duration like 10m, 2h, 1d> [reason]  (max 28d)",
        "untimeout": "Usage: !untimeout <@user|id>",
    }
    parts = args.split(None, 1)
    if not parts:
        print(usage[name])
        return
    user_id = parse_user_id(parts[0])
    if user_id is None:
        print(f"Couldn't read a user from '{parts[0]}'. Use a mention or a numeric user ID.")
        print(usage[name])
        return
    rest = parts[1].strip() if len(parts) > 1 else ""
    audit = f"{name} by bot owner"

    if name != "unban":
        err = mod_target_error(user_id, guild)
        if err:
            print(err)
            return

    try:
        if name == "ban":
            reason = rest or None
            await guild.ban(discord.Object(id=user_id), reason=(f"{audit}: {reason}" if reason else audit), delete_message_seconds=0)
            print(f"Banned {user_id} from {guild.name}." + (f" Reason: {reason}" if reason else ""))

        elif name == "unban":
            await guild.unban(discord.Object(id=user_id), reason=(f"{audit}: {rest}" if rest else audit))
            print(f"Unbanned {user_id} in {guild.name}.")

        elif name == "kick":
            member = await guild.fetch_member(user_id)
            await member.kick(reason=(f"{audit}: {rest}" if rest else audit))
            print(f"Kicked {member} from {guild.name}." + (f" Reason: {rest}" if rest else ""))

        elif name == "timeout":
            dur_parts = rest.split(None, 1)
            if not dur_parts:
                print(usage[name])
                return
            duration = parse_duration(dur_parts[0])
            if duration is None:
                print(f"Couldn't read the duration '{dur_parts[0]}'. Use something like 30s, 10m, 2h, 1d.")
                return
            if duration > MAX_TIMEOUT:
                print("Discord's maximum timeout is 28 days.")
                return
            reason = dur_parts[1].strip() if len(dur_parts) > 1 else ""
            member = await guild.fetch_member(user_id)
            await member.timeout(duration, reason=(f"{audit}: {reason}" if reason else audit))
            print(f"Timed out {member} for {format_elapsed(duration)}." + (f" Reason: {reason}" if reason else ""))

        elif name == "untimeout":
            member = await guild.fetch_member(user_id)
            await member.timeout(None, reason=audit)
            print(f"Removed the timeout from {member}.")

    except discord.NotFound:
        if name == "unban":
            print(f"{user_id} isn't banned in {guild.name} (or doesn't exist).")
        elif name == "ban":
            print(f"No Discord user with ID {user_id}.")
        else:
            print(f"{user_id} isn't a member of {guild.name}.")
    except discord.Forbidden:
        print("I can't do that. Check that I have the right permission (Ban Members / Kick Members / Moderate Members) "
              "and that my role is above that user's highest role in Server Settings -> Roles.")
    except discord.HTTPException as e:
        print(f"Discord rejected that: {e}")


async def execute_admin_command(raw_cmd: str, current_channel):
    global current_persona, tts_pitch, chat_memory, saved_personas, ai_model, ai_temperature, ai_max_tokens
    text = raw_cmd.strip()
    if not text.startswith("/"):
        text = "/" + text

    if text == "/help":
        print("Commands: /list, /ch, /say, /photo, /vc, /tts, /pitch, /play, /stop, /leave, /dm, /status, /activity, /persona, /resetpersona, /savepersona, /loadpersona, /personas, /model, /forget, /forgetall, /clear, /trivia, /triviastop, /snipealert, /diag, /ping, /uptime, /info, /purge, /snipestats, /snipewipe, /customq, /ban, /unban, /kick, /timeout, /untimeout, /backup")
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

    for _mod in ("untimeout", "unban", "timeout", "ban", "kick"):
        if text == f"/{_mod}" or text.startswith(f"/{_mod} "):
            await execute_mod_command(_mod, text[len(_mod) + 1:].strip(), current_channel)
            return current_channel

    if text == "/backup":
        if not STORAGE_CHANNEL_ID:
            print("Storage is off. Set STORAGE_CHANNEL_ID (see README) to keep your data across redeploys.")
            return current_channel
        for name in BACKUP_FILES:
            if os.path.isfile(name):
                dirty_backups.add(name)
        saved = await backup_dirty_files()
        print(f"Backed up {saved} file(s) to channel {STORAGE_CHANNEL_ID}.")
        if last_backup_error:
            print(f"Last error: {last_backup_error}")
        return current_channel

    if text == "/ping":
        print(f"Pong! Latency: {round(bot.latency * 1000)}ms")
        return current_channel

    if text == "/uptime":
        print(f"Uptime: {format_uptime((datetime.datetime.now() - START_TIME).total_seconds())}")
        return current_channel

    if text == "/info":
        total_members = sum(g.member_count or 0 for g in bot.guilds)
        persona_preview = current_persona if len(current_persona) <= 120 else current_persona[:117] + "..."
        print(f"Bot: {bot.user} (ID: {bot.user.id})")
        print(f"Servers: {len(bot.guilds)}  |  Members: {total_members}")
        print(f"Latency: {round(bot.latency * 1000)}ms")
        print(f"Uptime: {format_uptime((datetime.datetime.now() - START_TIME).total_seconds())}")
        print(f"AI model: {ai_model}  |  Temp: {ai_temperature}  |  Max tokens: {ai_max_tokens}")
        print(f"Persona: {persona_preview}")
        print(f"Voice connections: {len(bot.voice_clients)}")
        return current_channel

    if text == "/purge" or text.startswith("/purge "):
        arg = text[6:].strip()
        if not arg.isdigit() or int(arg) < 1:
            print("Usage: !purge <count>  (a number from 1 to 1000)")
            return current_channel
        count = min(int(arg), 1000)
        keep_id = active_command_message.id if active_command_message else None
        try:
            deleted = await current_channel.purge(limit=count + (1 if keep_id else 0), check=lambda m: m.id != keep_id)
            print(f"Purged {len(deleted)} message(s) from #{current_channel.name}.")
        except discord.Forbidden:
            print("I don't have the Manage Messages permission in this channel.")
        except discord.HTTPException as e:
            print(f"Purge failed: {e}")
        except AttributeError:
            print("Purge only works in server text channels.")
        return current_channel

    if text == "/snipestats":
        del_total = sum(len(d) for d in sniped_deletes.values())
        edit_total = sum(len(d) for d in sniped_edits.values())
        print(f"Stored deleted messages: {del_total} across {len([c for c, d in sniped_deletes.items() if d])} channel(s)")
        print(f"Stored edited messages: {edit_total} across {len([c for c, d in sniped_edits.items() if d])} channel(s)")
        print(f"Max per channel: {SNIPE_MAX_PER_CHANNEL}")
        alert = f"<#{snipe_alert_channel_id}>" if snipe_alert_channel_id else "off"
        print(f"Snipe alerts: {alert}  |  Edit alerts: {'on' if snipe_alert_edits else 'off'}")
        busiest = sorted(
            ((cid, len(sniped_deletes.get(cid, [])) + len(sniped_edits.get(cid, []))) for cid in set(sniped_deletes) | set(sniped_edits)),
            key=lambda kv: kv[1], reverse=True,
        )[:5]
        for cid, n in busiest:
            ch = bot.get_channel(cid)
            print(f"  - #{ch.name if ch else cid}: {n} stored")
        return current_channel

    if text == "/snipewipe":
        del_total = sum(len(d) for d in sniped_deletes.values())
        edit_total = sum(len(d) for d in sniped_edits.values())
        sniped_deletes.clear()
        sniped_edits.clear()
        print(f"Wiped {del_total} deleted and {edit_total} edited message(s) from snipe storage.")
        return current_channel

    if text == "/customq":
        custom = load_custom_questions()
        topics = {k: v for k, v in custom.items() if k not in RESERVED_CUSTOM_KEYS and isinstance(v, list) and v}
        if not topics:
            print("No custom questions yet. Add one with !addq Topic | Question | Answer")
            return current_channel
        total = 0
        for topic in sorted(topics):
            entries = topics[topic]
            total += len(entries)
            print(f"{topic} ({len(entries)}):")
            for i, entry in enumerate(entries, 1):
                print(f"  {i}. {entry.get('question', '')}  ->  {entry.get('answer', '')}")
        print(f"Total custom questions: {total}")
        return current_channel

    if text == "/diag":
        run_startup_diagnostics()
        return current_channel

    if text == "/shutdown" or text == "/restart":
        print("Shutting down gracefully... Bot will go offline.")
        # Schedule the shutdown on the event loop so this function can return first
        asyncio.create_task(bot.close())
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
    if STORAGE_CHANNEL_ID:
        bot.loop.create_task(backup_loop())
        try:
            bot.loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.ensure_future(flush_and_close()))
        except (NotImplementedError, RuntimeError, ValueError):
            pass
        print(f"Storage: backing up to channel {STORAGE_CHANNEL_ID}")
    else:
        print("Storage: STORAGE_CHANNEL_ID not set, data resets on redeploy")
    bot.loop.create_task(start_keepalive_server())
    if IS_INTERACTIVE:
        bot.loop.create_task(manual_console_sender())


@bot.event
async def on_message(message):
    if message.author == bot.user:
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
