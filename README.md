## Render & Github Discord Bot

This is a project of a Discord Bot that I am doing, it is **still being updated** per when I get an idea, but it is complete.

# What is this?
This is a Discord Bot relying on Render for the cloud hosting and Github for Render to notice when a change has been committed.
# How do I use this?
The steps are simple,
## 1. The Setup
Create your bot application in the [Discord Developer Portal](https://discord.com/developers/applications).
Name it **however** you want, add any profile picture.
## 2. The Configuration
Go on the OAuth2 page in your application.
In OAuth2 URL generator, **tick the bot box.**
Then in bot permissions, **tick the administrator box.**
Then copy the URL and go on the URL, authorize the application and make the choice to add it to a server that you want. *This can be repeated to add in multiple servers.*
Then go to the Bot page.
In Privileged Gateway Intents, check Message Content Intent, and save.
## 3. Using Github
Make a Github repository at [Github](https://github.com)
Go to File Manager then create two files, requirements.txt and bot.**py**.
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
Go to ENV variables and add 4 variables
OPENROUTER_API_KEY

*to be finished*
