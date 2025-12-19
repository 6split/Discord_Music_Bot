import discord

from sensitive_data.sensitive_data import get_application_id, get_application_token
from settings.settings import get_all_settings, modify_setting, populate_settings_json

#We can only connect to one voice channel, so it is fine to have a global variable here
current_voice_channel = None
#Create the discord client
client = discord.Client(intents=discord.Intents.all(), application_id=get_application_id())

@client.event
async def on_ready():
    populate_settings_json()
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message : discord.Message):
    
    #If it's our own message do not respond
    if message.author == client.user:
        return
    
    #Handle our ! "commands"
    if message.content.startswith("!"):
        if message.content.startswith("!settings"):
            current_settings = get_all_settings()
            await message.reply(f"Current Settings: {current_settings}")
            return
        
        if message.content == "!autoplay":
            current_settings = get_all_settings()
            current_autoplay = current_settings["autoplay"]
            modify_setting("autoplay", not current_autoplay)

            await message.reply("Autoplay now set to " + str(not current_autoplay))
            return
        
        #Handles all of our shut_down
        if message.content == "!shut_down":
            return

            
        

    return





#Run the discord client
print("Running Jarvis...")
client.run(get_application_token())