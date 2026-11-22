## Fixes
# How to fix it
Fixes for the known issues listed in [updates.md](updates.md). Some of them I have to fix in a future update of `bot.py`, so there is nothing you can do yet.
## Saved files resetting on Render
Fixed in v1.4, but you have to turn it on. Create a **private** text channel, copy its ID, and add it in Render as the `STORAGE_CHANNEL_ID` variable (README step 7). The bot then keeps your data in that channel and loads it back after every redeploy.
## Storage doesn't seem to work
First type `!backup`. It tells you how many files it saved and the last error if there was one. Then check:
- The logs should say `Storage: backing up to channel ...` on startup. If they say `STORAGE_CHANNEL_ID not set`, the variable is missing or has a typo in Render
- If they say `could not read the backup channel`, the ID is wrong or the bot can't see that channel. Give the bot **View Channel**, **Read Message History**, **Send Messages** and **Attach Files** there
- Use the **channel** ID, not the server ID or your user ID
- Don't delete the bot's backup messages in the channel, they are your data. If you do, type `!backup` to save fresh copies
- A single file bigger than 8 MB isn't backed up, which only really happens with a huge `memory.json`
- Data is only restored for files that don't exist yet, so on your own PC (where the files already exist) your local files win
## Warnings aren't showing up
- Type `!warnchannel` with nothing after it. If it says **off**, set one with `!warnchannel here` in the channel you want
- Give the bot **View Channel**, **Send Messages**, **Embed Links** and **Mention Users** in the warnings channel. If the logs say `Warning send failed`, it's almost always a permission
- It only flags the phrase "fuck you" (also "fuck u" and stretched versions). "fuckyou" with no space and other insults aren't flagged
- It waits 10 seconds between warnings for the same person, so a second one right after the first won't show
- Messages from bots and DMs are ignored
## My flagged phrase isn't being caught
- Check it with `!flagged`. Make sure the phrase is listed and a warnings channel is set
- Phrases only match **whole words**, so a flagged "idiot" won't catch "idiotic", and "shut up" won't catch "shutup". Add each version you want as its own phrase
- Spelling tricks like "sh*t" or extra letters aren't caught for custom phrases, add those spellings as separate phrases
- Use `|` to separate the phrase from the reason, for example `!addflag shut up | Told someone to shut up`. A `|` inside the phrase itself isn't supported
## `!avatar` or `!nick` fails
- `!avatar` needs a **direct** link to the image file (it should end in .png, .jpg, .gif or .webp, and open as just the picture). Links to web pages won't work, and it has to be under 8 MB
- Discord only lets a bot change its avatar a couple of times per hour. If it says it was rejected, wait and try again
- `!nick` needs the **Change Nickname** permission for the bot, and nicknames are at most 32 characters
## `!export` says it couldn't DM me
Turn on **Allow direct messages from server members** in the server's privacy settings (or share any server with the bot), then try again. Exports always go to your DMs on purpose, never to a channel.
## `!reply` or `!react` can't find the message
They look in the channel you type them in. Either use them in the same channel as the message, or give the full message link (right click the message, Copy Message Link). For custom emojis, the bot has to be in the server that owns the emoji.
## `!whois` shows little about someone
The bot can't see members it hasn't been given access to without the privileged Members intent, so `!whois` looks people up by ID or mention. Use it in the server where you want to see their nickname, roles and join date. Outside it, you only get their account info.
## `!pause` doesn't stop everything
It only stops the AI replies (mentions and DMs). Public commands like `!snipe` and `!addq`, trivia, warnings and all owner commands keep working on purpose.
## ffmpeg missing (`!play` and `!vc` audio)
First run `!diag` and check the `FFmpeg Binary` line. If it says **MISSING**, Render's normal Python setup doesn't have it, so you have to deploy with Docker instead:
1. In your Github repository, create a new file called `Dockerfile` with this inside:
```
FROM python:3.12-slim
RUN apt-get update && apt-get install -y ffmpeg libopus0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```
2. Commit it.
3. In Render, set the **Language / Runtime** of your service to **Docker** (you may need to create a new Web Service for this) and redeploy.
4. Run `!diag` again, `FFmpeg Binary` should now show a path.

*(I haven't tested this exact Dockerfile on Render, so if it fails, check the build logs and tell me what it says.)*
## `!tts` not working
It only works when the bot is hosted on a Windows PC, so on Render there is no fix. Use `!play` instead.
## `!purge` says I don't have the Manage Messages permission
The bot needs the **Manage Messages** permission in that channel. Either re-invite it with the permission ticked (README step 2), or in Discord open the channel's settings, go to Permissions, and allow **Manage Messages** for the bot's role.
## `!purge` is slow on old messages
Discord only lets bots delete messages newer than 14 days in bulk. Older ones are deleted one by one, which can take a while and can hit rate limits (see step 12 in the README). Use smaller counts if this happens.
## `!ban`, `!kick` or `!timeout` says "I can't do that"
Two things cause this. The bot is missing the permission (**Ban Members**, **Kick Members** or **Moderate Members**), or the bot's role is not above the target's highest role. In Discord go to Server Settings, then Roles, and drag the bot's role above the roles of the people you want to moderate. Nobody can be timed out or kicked by a bot if they have a higher role, and **Administrator** members can never be timed out.
## `!timeout` says it can't read the duration
Use a number followed by `s`, `m`, `h`, `d` or `w`, with no spaces, for example `!timeout @user 10m spamming`. You can combine them like `1h30m`. The maximum is 28 days.
## The AI reply freezing the bot
Nothing to fix on your side, just wait a moment for the reply. I'll fix it in a future update of `bot.py`.
## Why is it slow?
There isn't just one reason, a few things can make the bot slow, and most of them come from the free hosting:
- **Render woke up.** Render spins down after 15 minutes of inactivity. UptimeRobot is supposed to keep it awake by pinging every 5 minutes, but if the monitor is paused or set up wrong, the first command after a while will be very slow while the bot starts back up. Check that your UptimeRobot monitor is **up** and uses the right primary URL.
- **The free server is small.** Render's free tier gives the bot very little CPU and memory, so heavier things like `!play` (yt-dlp has to look up the song first) take a few seconds, and sometimes longer.
- **The AI model is slow.** The default model is `openrouter/free`, and free models can be slow, busy or rate limited. Try a different one with `!model <name>` (pick one from [openrouter](https://openrouter.ai), paid models are usually faster).
- **The bot waits for the AI.** Right now the bot can freeze for a moment while it waits for OpenRouter, so other commands feel slow at the same time. This is one of the known issues and I'll fix it in a future update.
- **Rate limits.** If Discord or OpenRouter is slowing the bot down on purpose, see step 12 in the README, the only fix is to wait.
- **Old chat memory.** The bot saves its whole memory file every time someone talks to it, so over time it gets bigger. This helps only a little, but `!forgetall` wipes it if the bot has been running for a long time.

If you turned on the dashboard, `/panel` shows the bot's latency, so you can tell if it's the bot (high latency) or the AI model (normal latency but slow replies).
*(You can also use `!ping` to see the latency.)*
