import discord
import asyncio
from sensitive_data.credentials import get_discord_application_id, get_discord_application_token
from settings.settings import get_all_settings, modify_setting, populate_settings_json
from music import Music_Manager
from tests.discord_tests import run_tests
#We can only connect to one voice channel, so it is fine to have a global variable here
current_voice_channel = None
music_manager_instance = None
#Create the discord client
client = discord.Client(intents=discord.Intents.all(), application_id=get_discord_application_id())

@client.event
async def on_ready():
    populate_settings_json()
    print('We have logged in as {0.user}'.format(client))

async def join_voice_channel(voice_channel : discord.VoiceChannel):
    global current_voice_channel, music_manager_instance
    if len(client.voice_clients) > 0 and client.voice_clients[0].is_connected():
        await client.voice_clients[0].disconnect()
    current_voice_channel = voice_channel
    voice = await voice_channel.connect()
    music_manager_instance = Music_Manager(voice)

async def leave_voice_channel():
    global current_voice_channel, music_manager_instance
    if len(client.voice_clients) > 0 and client.voice_clients[0].is_connected():
        await client.voice_clients[0].disconnect()
    current_voice_channel = None
    music_manager_instance = None

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
        
        if message.content == "!join":
            if message.author.voice and message.author.voice.channel:
                await join_voice_channel(message.author.voice.channel)
                await message.reply(f"Joined voice channel: {message.author.voice.channel.name}")
            else:
                await message.reply("You are not connected to a voice channel.")
            return
        
        if message.content == "!leave":
            await leave_voice_channel()
            await message.reply("Left voice channel.")
            return
        
        #Runs our test suite, replying with the results of each test
        if message.content == "!test":
            await message.reply("Running test suite...")
            potential_voice_channels = message.channel.guild.voice_channels
            print(f"Found {len(potential_voice_channels)} potential voice channels.")
            if len(potential_voice_channels) == 0:
                await message.reply("No voice channels found in this server.")
                return
            #Just connect to the first voice channel we find, since we can only be in one at a time
            voice_channel = potential_voice_channels[0]
            def debug_print(result):
                print(result)
                asyncio.run_coroutine_threadsafe(message.reply(result), client.loop)
            await join_voice_channel(voice_channel)
            run_tests(client, voice_channel, music_manager_instance, debug_func=debug_print)
            await leave_voice_channel()
            return

        #Handles shutting down
        if message.content == "!shut_down":
            await message.reply("Shutting down.")
            await client.close()
            quit()
            return
        
    return

#Run the discord client
print("Running Jarvis...")
client.run(get_discord_application_token())