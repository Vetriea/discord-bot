## Fixes
# How to fix it
Fixes for the known issues listed in [updates.md](updates.md). Some of them I have to fix in a future update of `bot.py`, so there is nothing you can do yet.
## Saved files resetting on Render
There is no easy free fix, Render's free tier just doesn't keep files between deploys. For now:
- Keep your `!addq` questions and personas written down somewhere (a notes app is fine) so you can add them again after a redeploy
- Don't redeploy or restart more than you need to

A real fix needs a Render **persistent disk** (paid) or a database, plus a change in `bot.py`. I'll look into it for a future update.
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
