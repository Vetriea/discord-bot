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
# v1.4
Your saved data now survives redeploys.

**What happened:** On Render's free tier the bot's files are wiped on every redeploy, so `!addq` questions, saved personas, chat memory and the bot's saved state kept resetting.

**What changed:**
- The bot can now back up `memory.json`, `personas.json`, `trivia_custom.json` and `bot_state.json` to a private Discord channel, and load them back when it starts
- It is optional and off by default, turn it on by adding the `STORAGE_CHANNEL_ID` variable (see [README](README.md), step 7)
- Backups happen a few seconds after something changes, and once more when Render stops the bot for a redeploy
- Each file is stored as a single message that gets updated in place, so the channel stays tidy (one message per file)
- A local file is never overwritten by a backup, and a damaged backup is ignored instead of loaded
- New owner command `!backup` saves everything to the storage channel right now and tells you if something went wrong
- If you don't set `STORAGE_CHANNEL_ID`, nothing changes from before
- **Make the storage channel private.** Chat memory is stored in it
- **How to update:** replace your `bot.py` with the new one (see step 11 in the README), then add `STORAGE_CHANNEL_ID` in Render if you want persistence. No `requirements.txt` changes needed
# v1.4.1
Added a warning for "fuck you".

**What changed:**
- The bot now flags messages that say "fuck you" and pings the person in a warnings channel
- The warning is a message that mentions the user, plus a card with the **reason**, the channel it was said in, a link to the message and what they said
- It catches different capitals, extra spaces, stretched letters ("FUUUCK YOUUU"), "fuck u", and hidden zero-width characters. It does not flag things like "what the fuck" or "fuck yourself"
- It only posts the warning. It doesn't delete the message or punish anyone
- It ignores bots and DMs, and won't warn the same person more than once every 10 seconds, so a spammer can't flood the warnings channel
- New owner command `!warnchannel <here|#channel|id|clear>` sets where warnings go. Typing `!warnchannel` alone shows the current one
- It's off until you set a warnings channel, and the setting is saved with your other data
- The README command list now also includes the moderation commands (`!ban`, `!unban`, `!kick`, `!timeout`, `!untimeout`) and `!backup`
- **How to update:** replace your `bot.py` with the new one (see step 11 in the README), then type `!warnchannel here` in the channel you want. No new variables or `requirements.txt` changes needed
# v1.4.2
You can now add your own flagged phrases.
- New owner command `!addflag <phrase> | [reason]` flags a phrase. Example: `!addflag shut up | Told someone to shut up`. Without a reason it uses "Said a flagged phrase"
- `!removeflag <phrase>` stops flagging a phrase
- `!flagged` lists the built-in and custom phrases, their reasons and the current warnings channel
- Custom phrases ignore capitals and extra spaces, and only match whole words ("shut up" won't flag "shutup", "idiot" won't flag "idiotic")
- Special characters are matched as typed, so nothing you add can break the bot
- Phrases are saved with your other data, so they survive redeploys if you set up storage
- Up to 200 custom phrases. The built-in "fuck you" flag can't be removed
- When you (the owner) run a command like `!addflag <phrase>`, the bot won't warn you for the phrase you typed in it
- **How to update:** replace your `bot.py` with the new one (see step 11 in the README). No new variables or `requirements.txt` changes needed
# Known Issues
Things I know about and haven't fixed yet:
- `!play` and `!vc` audio need ffmpeg, which might not be installed on Render. Use `!diag` and check the `FFmpeg Binary` line to see
- `!tts` only works when the bot is hosted on a Windows PC
- The AI reply can freeze the bot for a moment while waiting for OpenRouter
Want to know how to fix them? Read [fixes.md](fixes.md).
