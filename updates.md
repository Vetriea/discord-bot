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
Want to know how to fix them? Read [fixes.md](fixes.md).
