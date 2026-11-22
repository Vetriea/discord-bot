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
# v1.2
Fixed the commands that were listed but didn't do anything.

**What happened:** `!ping`, `!uptime`, `!info`, `!purge`, `!snipestats`, `!snipewipe` and `!customq` were in `!help`, the owner command list and the dashboard, but the bot had no code behind them, so they did nothing. This update adds that code.

**What changed:**
- `!ping` shows the bot's latency in milliseconds
- `!uptime` shows how long the bot has been running
- `!info` shows a summary: bot name and ID, servers, members, latency, uptime, AI model settings, persona preview and voice connections
- `!purge <count>` deletes the last N messages in the current channel (max 1000). It keeps your command message so the bot can still reply, and it tells you if it's missing the Manage Messages permission
- `!snipestats` shows how many deleted/edited messages are stored, the busiest channels and the current snipe alert settings
- `!snipewipe` clears all stored snipe data and tells you how many messages it removed
- `!customq` lists every custom trivia question with its answer, grouped by topic
- The console `/help` text now includes the new commands
- The dashboard buttons (Bot Info, Stats, Wipe All, List All) should now work too, since they use the same handlers
- Removed these commands from Known Issues and from [fixes.md](fixes.md)
- **How to update:** replace your `bot.py` with the new one (see step 11 in the README), no new variables or `requirements.txt` changes needed
# v1.2.1
Small fix for `!purge`.

**What happened:** `!purge <count>` deleted one message fewer than you asked for. For example, `!purge 5` only deleted 4. The bot skips your command message so it can reply to it, but that message was still counted toward the limit.

**What changed:**
- `!purge <count>` now deletes the full number of messages you ask for, not counting your command message
- Nothing else changed
- **How to update:** replace your `bot.py` with the new one (see step 11 in the README), no new variables or `requirements.txt` changes needed
# v1.3
Added moderation commands (owner only).
- `!ban <@user|id> [reason]` bans a user, even if they are not in the server anymore
- `!unban <user id> [reason]` unbans a user
- `!kick <@user|id> [reason]` kicks a member
- `!timeout <@user|id> <duration> [reason]` times a member out, duration like `30s`, `10m`, `2h`, `1d`, `1w` or `1h30m` (Discord's max is 28 days)
- `!untimeout <@user|id>` removes a timeout
- They work on the server of the channel you use them in (or the one picked with `!ch` in the console)
- The bot refuses to moderate itself, you (the owner) or the server owner, and says so if its role is too low or it's missing a permission
- Actions show up in the server's Audit Log with the reason you gave
- If you gave the bot **Administrator** you don't need to change anything. If you picked permissions by hand, add **Ban Members**, **Kick Members** and **Moderate Members** (README step 2), and make sure the bot's role is above the roles of the people you moderate
- **How to update:** replace your `bot.py` with the new one (see step 11 in the README), no new variables or `requirements.txt` changes needed
# Known Issues
Things I know about and haven't fixed yet:
- On Render's free tier, saved files (`!addq` questions, saved personas, chat memory) can reset whenever the bot redeploys, including when you update `bot.py`
- `!play` and `!vc` audio need ffmpeg, which might not be installed on Render. Use `!diag` and check the `FFmpeg Binary` line to see
- `!tts` only works when the bot is hosted on a Windows PC
- The AI reply can freeze the bot for a moment while waiting for OpenRouter
Want to know how to fix them? Read [fixes.md](fixes.md).
