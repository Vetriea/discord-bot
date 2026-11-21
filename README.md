## Render & Github Discord Bot

This is a project of a Discord Bot that I am doing, it is **still being updated** per when I get an idea, but it is complete.

## What is this?
This is a Discord Bot relying on Render for the cloud hosting and Github for Render to notice when a change has been committed.
## How do I use this?
The steps are simple,
## 1. The Setup
Create your bot application in the [Discord Developer Portal](https://discord.com/developers/applications).
Name it **however** you want, add any profile picture.
## 2. The Configuration
Go on the OAuth2 page in your application.
In OAuth2 URL generator, **tick the bot box.**
Then in bot permissions, **tick the administrator box.** But you should be responsible on what happens with your token.
Then copy the URL and go on the URL, authorize the application and make the choice to add it to a server that you want. *This can be repeated to add in multiple servers.*
Then go to the Bot page.
In Privileged Gateway Intents, check Message Content Intent, and save.
## 3. Using Github
Make a Github repository at [Github](https://github.com)
Go to File Manager then create two files, requirements.txt and bot.py.
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
## 4. Render
Go to [Render](https://render.com)
Sign up and then connect your github repository.
Go to ENV variables and add 4 variables.
```
OPENROUTER_API_KEY
DISCORD_TOKEN
DASHBOARD_PASSWORD (optional)
OWNER_ID
```
## 5. OpenRouter
Go to [openrouter](https://openrouter.com)
Sign in then create a key, make it have NO expiration and NO limit, create the key and copy it and pin it. ***You will never see it again.***
## 6. Back to Render
in OPENROUTER_API_KEY, input your key in the second box.
## 7. Back to Discord Developer Portals
Go to Bot page, press Reset Token and copy the token and pin it, and just like the openrouter key, ***You will never see it again.***
Then in Render, in the DISCORD_TOKEN variable, input the token in the second box.
## 8. In Discord
To get your Owner ID, go to your profile and then copy your user ID from there.
In Render, in OWNER_ID input your ID in the second box.
## 9. Deploying Render
Back in Render, deploy the project and wait till it finishes building, then in the terminal you should see something like a:
```
==> Uploading build...
==> Uploaded in 2.5s. Compression took 1.5s
==> Build successful 🎉
==> Deploying...
==> Setting WEB_CONCURRENCY=1 by default, based on available CPUs in the instance
==> Running 'python bot.py'
[2026-11-21 14:59:36] [INFO    ] discord.client: logging in using static token
[2026-11-21 14:59:37] [INFO    ] discord.gateway: Shard ID None has connected to Gateway (Session ID: 2a749d1867cf976a5c97cd3c6c86ffab).
==> Your service is live 🎉
==> 
==> ///////////////////////////////////////////////////////////
==> 
==> Available at your primary URL https://discord-bot-zhl2.onrender.com
==> 
==> ///////////////////////////////////////////////////////////
```
In the primary URL, copy it.
## 10. UptimeRobot
Go to [UptimeRobot](https://uptimerobot.com)
Sign up and then put the primary URL in the designated box.
## Why is step 10 a thing?
It's so because Render spins down after 15 minutes of inactivity, UptimeRobot fixes this by pinging the website every 5 minutes.
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
(editsnipe and snipe should be used responsibly, if a user doesn't want to opt in it, you should never use it, if it's a community where they are okay with it, go.)
```
## Notes
Never EVER commit your token in a file, ALWAYS. It is no longer my problem if you use this project IMPROPERLY.
Openrouter key is also your responsibility to use, if it's leaked, it's ggs.
## Goodbye?
This marks the end of the tutorial, if anything goes wrong, you can simply go back and know what went wrong.
**Goodbye.**

