## Updates
# v1.0
Repository was released.
# v1.1
Added better commands for users, etc ! instead of !bot /.
- Commands now use a simple **!** prefix, for example `!trivia` instead of `!bot /trivia`
- This applies to all the commands, public and owner ones, like `!snipe`, `!trivia`, `!play` and `!say`
- The old `!bot /<command>` way still works as a fallback, so nothing breaks if you were already using it
- `!help` shows the full list of commands that you can use
- **How to update:** replace your `bot.py` with the new one (see step 11 in the README), no new variables or `requirements.txt` changes needed
# Known Issues
Things I know about and haven't fixed yet:
- On Render's free tier, saved files (`!addq` questions, saved personas, chat memory) can reset whenever the bot redeploys, including when you update `bot.py`
- `!play` and `!vc` audio need ffmpeg, which might not be installed on Render. Use `!diag` and check the `FFmpeg Binary` line to see
- `!tts` only works when the bot is hosted on a Windows PC
- `!purge`, `!ping`, `!uptime`, `!info`, `!snipestats`, `!snipewipe` and `!customq` are in the command list but don't do anything yet
- The AI reply can freeze the bot for a moment while waiting for OpenRouter
# How to fix it
Fixes for the known issues above. Some of them I have to fix in a future update of `bot.py`, so there is nothing you can do yet.
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
## Commands that don't do anything
Nothing to fix on your side, just don't use `!purge`, `!ping`, `!uptime`, `!info`, `!snipestats`, `!snipewipe` or `!customq` for now. I'll add them in a future update.
## The AI reply freezing the bot
Nothing to fix on your side, just wait a moment for the reply. I'll fix it in a future update of `bot.py`.
