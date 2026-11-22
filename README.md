# Render & Github Discord Bot

This is a project of a Discord Bot that I am doing, it is **still being updated** per when I get an idea, but it is complete.

It's a Discord bot with trivia, snipe/editsnipe, AI personas (through OpenRouter), and voice channel music playback.

## What is this?
This is a Discord Bot relying on Render for the cloud hosting and Github for Render to notice when a change has been committed.

## How do I use this?
The steps are simple,

## On mobile?
You can do all of this on your phone too, everything is a website so a mobile browser is enough.
- Turn on **Desktop site** in your browser (Chrome: the ⋮ menu, Safari: the aA button), the Discord Developer Portal and Render are buggy in the mobile layout.
- Use the Github **website** instead of the app, the app can't really add new files. Use **Add file → Create new file**.
- When copying bot.py, long-press, select all, copy, and scroll to make sure the whole file got selected before pasting.
- Paste your OpenRouter key and Discord token into a notes app **right away**, you only see them once and switching tabs can reload the page.
- Turn on Developer Mode in User Settings → Advanced in the Discord app so you can copy your user ID.
- Copy your values first and then paste them into Render, typing a long token by hand is a bad idea.

## 1. The Setup
Create your bot application in the [Discord Developer Portal](https://discord.com/developers/applications).
Name it **however** you want.
To add a profile picture, go to the Bot page and upload it there (the picture on the General Information page is only the app icon, it won't show as the bot's profile picture).

## 2. The Configuration
Go on the OAuth2 page in your application.
In OAuth2 URL generator, **tick the bot box.**
Then in bot permissions, **tick the administrator box.** But you should be responsible on what happens with your token.
*(Tip: if you'd rather not give full admin, the permissions the bot actually needs are Send Messages, Read Message History, Manage Messages (for `!purge`), Connect and Speak (for voice), and Ban Members, Kick Members and Moderate Members (for `!ban`, `!unban`, `!kick`, `!timeout` and `!untimeout`).)*
Then copy the URL and go on the URL, authorize the application and make the choice to add it to a server that you want. *This can be repeated to add in multiple servers.*
Then go to the Bot page.
In Privileged Gateway Intents, check Message Content Intent, and save.

## 3. OpenRouter
Go to [openrouter](https://openrouter.ai)
Sign in then create a key, make it have NO expiration and NO limit, create the key and copy it and pin it (save it somewhere safe). ***You will never see it again.***
*(Tip: setting a credit limit on the key is optional, but it caps the damage if the key ever leaks.)*

## 4. Your Discord Token
Go back to the Bot page in the Discord Developer Portal, press Reset Token and copy the token and pin it (save it somewhere safe), and just like the openrouter key, ***You will never see it again.***

## 5. Your Owner ID
To get your Owner ID, go to your profile in Discord and then copy your user ID from there.
*(If you don't see the copy option, turn on Developer Mode in Discord Settings → Advanced.)*

## 6. Using Github
Make a Github repository at [Github](https://github.com)
Click **Add file → Create new file**, then create two files, requirements.txt and bot.py.
In requirements.txt, make sure that it has this on the txt file.
```
discord.py[voice]
davey
openai
python-dotenv
aiohttp
yt-dlp
```
In bot.py, check the file that is on my repository itself, and paste it all there.
***MAKE SURE TO COMMIT CHANGES!***

*(I know this step is the boring part, a lot of copying and pasting, but don't give up now! Once this is done, the hardest part is over and the rest is just filling in boxes. You're almost there, keep going! 💪)*

## 7. Render
Go to [Render](https://render.com)
Sign up and then connect your github repository.
Make it a **Web Service**, and set the **Start Command** to:
```
python bot.py
```
(The Build Command should be `pip install -r requirements.txt`, Render usually fills this in by itself.)
Go to ENV variables and add these variables (plus the optional `STORAGE_CHANNEL_ID` explained below).
```
OPENROUTER_API_KEY
DISCORD_TOKEN
DASHBOARD_PASSWORD (optional)
OWNER_ID
```
In OPENROUTER_API_KEY, input your OpenRouter key in the second box.
In DISCORD_TOKEN, input your Discord token in the second box.
In OWNER_ID, input your ID in the second box.

### Keeping your saved data (recommended)
On Render's free tier the bot's files get wiped on every redeploy, so your `!addq` questions, saved personas and chat memory would disappear. To stop that, the bot can back them up to a private Discord channel and load them back when it starts.
1. In your Discord server, create a new text channel (for example `bot-storage`) and make it **private**, so only you and the bot can see it. Your chat memory is saved there, so never let anyone else in.
2. Make sure the bot can see the channel and has **View Channel**, **Send Messages** and **Attach Files** in it.
3. Right click the channel, press **Copy Channel ID** (turn on Developer Mode like in step 5 if you don't see it).
4. In Render, add one more ENV variable called `STORAGE_CHANNEL_ID` and paste the ID.
5. Redeploy. In the logs you should see `Storage: backing up to channel ...`. Type `!backup` to force a save and check the channel, you should see one file per data type.

Skip it and everything still works, your data just resets on redeploy like before.

## 8. Deploying Render
Back in Render, deploy the project and wait till it finishes building, then in the terminal you should see something like a:
```
==> Uploading build...
==> Uploaded in 2.5s. Compression took 1.5s
==> Build successful 🎉
==> Deploying...
==> Setting WEB_CONCURRENCY=1 by default, based on available CPUs in the instance
==> Running 'python bot.py'
[2026-11-21 14:59:36] [INFO    ] discord.client: logging in using static token
[2026-11-21 14:59:37] [INFO    ] discord.gateway: Shard ID None has connected to Gateway (Session ID: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx).
==> Your service is live 🎉
==> 
==> ///////////////////////////////////////////////////////////
==> 
==> Available at your primary URL https://your-app-name.onrender.com
==> 
==> ///////////////////////////////////////////////////////////
```
In the primary URL, copy it.

## 9. UptimeRobot
Go to [UptimeRobot](https://uptimerobot.com)
Sign up, create a new monitor (type: HTTP(s)), and put the primary URL in the designated box.

## Why is step 9 a thing?
It's so because Render spins down after 15 minutes of inactivity, UptimeRobot fixes this by pinging the website every 5 minutes.

## 10. Making Another Bot
Want a second bot? Just repeat the steps again, but with a few things separate for each bot:
- A **new** Discord application (steps 1, 2 and 4), every bot needs its own token. **Never** run two bots on the same token.
- A **new** Github repository with its own requirements.txt and bot.py (step 6).
- A **new** Render Web Service for that repository, with its own start command and variables (step 7).
- A **new** UptimeRobot monitor with the new bot's primary URL (step 9).

You can reuse the **same** OpenRouter key and Owner ID for every bot, so steps 3 and 5 can be skipped.
*(Render's free tier has a monthly hours limit that is shared between your services, so check their current limits if you plan on running more than one bot 24/7.)*

## 11. Updating Your Bot
What if I update bot.py? Don't worry, updating is way easier than the first setup.
### How do I know if there is an update?
The fastest way is to let Github tell you:
1. Go to my repository and press the **Watch** button at the top.
2. Press **Custom**, tick **Releases**, then press **Apply**.

Now every time I publish a new release (like **V1.1**), Github will notify you by itself, so you don't have to keep checking. You can also look at the **Releases** section on the right side of my repository to see the latest version anytime.
Then check [updates.md](updates.md) on my repository to see what changed.

### How do I update it?
If there is an update, do this:
1. Open `bot.py` on my repository and copy **all** of it.
2. Go to **your** Github repository, open `bot.py`, and press the pencil icon to edit it.
3. Select everything, delete it, and paste the new version in.
4. Press **Commit changes**.

That's it. Render notices the commit by itself and redeploys the bot, so just wait for the build to finish and your bot will come back online with the update. It will be offline for a short moment while it redeploys.
If I changed `requirements.txt` too, do the same thing with that file.
Your variables (token, keys, Owner ID) stay the same, you don't have to enter them again unless I say so in updates.md.
*(If Render doesn't redeploy by itself, check that **Auto-Deploy** is on in your service settings, or press **Manual Deploy** in Render.)*
*(On mobile? Use Desktop site mode like before.)*

## 12. What If My Bot Gets Rate Limited?
Sometimes Discord (or OpenRouter) will tell your bot to slow down because it's doing too much too fast. You might see the bot reply late, not reply at all, or see `429` or `rate limited` in your Render logs.
**The honest answer is that you can't really do anything about it.** Rate limits are set by Discord and OpenRouter, not by me or by the bot, so the only real fix is to **wait**. Most of the time it clears up by itself in a few seconds or minutes, and the bot keeps working like normal afterwards.
Here is what you can do to make it happen less:
- Don't spam commands, especially `!purge`, `!say`, `!dm` and `!play`
- Don't redeploy or restart the bot over and over, logging in too many times in a row can get you limited
- If the AI replies stop working, your OpenRouter key might have hit its limit, so check your usage on [openrouter](https://openrouter.ai)

If it lasts a long time, check the logs in Render to see what it says, then wait a bit and try again.
*(Sometimes it's the hosting itself being limited, since Render shares servers with other people. Restarting later can sometimes help, but it isn't guaranteed.)*

## The Result
After doing all of this, your bot should now be running 24/7 with the commands you'll need.

## The Commands
```
Public commands (anyone can use):
!addq Topic | Question | Answer — add a trivia question
!qstats — custom question counts
!qlist Topic — DM you questions in a topic
!emoji Topic 👑 — set a topic emoji
!snipe [N] — show the Nth recent deleted message
!editsnipe [N] — show the Nth recent edited message
!photo [#channel] — forward an attached/replied image
!help — this message

Owner commands (you can use these):
!trivia [channel] — start trivia • !triviastop — abort
!status <online|idle|dnd|invisible> • !activity playing <text>
!persona <prompt> • !resetpersona • !savepersona <name> • !loadpersona <name>
!snipealert <channel|here|clear> • !snipealert edits on|off
!snipestats • !snipewipe • !customq
!clear • !purge <count> • !forget • !forgetall
!list • !diag • !info • !ping • !uptime
!say <#channel> <msg> • !dm <uid> <msg>
!model <name> • !vc <name> • !play <query> • !stop • !leave
(also: !bot /<command> still works as a fallback)
```
(editsnipe and snipe should be used responsibly, if a user doesn't want to opt in it, you should never use it, if it's a community where they are okay with it, go.)

## Notes
Never EVER commit your token in a file, NEVER. It is no longer my problem if you use this project IMPROPERLY.
Openrouter key is also your responsibility to use, if it's leaked, it's ggs.

## Goodbye?
This marks the end of the tutorial, if anything goes wrong, you can simply go back and know what went wrong.

**Goodbye.**
