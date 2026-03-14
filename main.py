import discord
import asyncio
from sensitive_data.credentials import get_discord_application_id, get_discord_application_token
from settings.settings import get_all_settings, modify_setting, populate_settings_json
from music import Music_Manager
from tests.discord_tests import run_tests
import tools
import threading
import time
from message_history import load_message_history, create_message, save_new_message
#We can only connect to one voice channel, so it is fine to have a global variable here
current_voice_channel = None
music_manager_instance = None
request_threads = []
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
    music_manager_instance.update_set_presence_function(set_presence_tool)

async def leave_voice_channel():
    global current_voice_channel, music_manager_instance
    if len(client.voice_clients) > 0 and client.voice_clients[0].is_connected():
        await client.voice_clients[0].disconnect()
    current_voice_channel = None
    music_manager_instance = None

async def set_presence(status : str):
    print(f"Setting presence to: {status}")
    await client.change_presence(activity=discord.CustomActivity(status))

def set_presence_tool(status):
    """Tool function to set the bot's presence status."""
    """Args:
        status (str): The status message to set for the bot's presence.
    Returns:
        str: A message indicating the new presence status.
    """
    asyncio.run_coroutine_threadsafe(set_presence(status), client.loop)
    return f"Set presence to: {status}"

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
        
        #Command for skipping the current song
        if message.content == "!ts":
            if music_manager_instance is not None:
                music_manager_instance.skip_song()
                await message.reply("Skipped current song.")
            else:
                await message.reply("Not connected to a voice channel.")
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
            tests_passed = 0
            total_tests = 0
            def debug_print(result):
                nonlocal tests_passed, total_tests
                print(result)
                if isinstance(result, str):
                    total_tests += 1
                    if result.startswith(":white_check_mark:"):
                        tests_passed += 1
                asyncio.run_coroutine_threadsafe(message.reply(result), client.loop)
            await join_voice_channel(voice_channel)
            run_tests(client, voice_channel, music_manager_instance, debug_func=debug_print)
            await leave_voice_channel()
            await asyncio.sleep(0.05)  # Wait for all test results to be sent before sending the final message
            await message.reply(f"Finished running tests. {tests_passed}/{total_tests} tests passed.")
            return

        #Handles shutting down
        if message.content == "!shut_down":
            await message.reply("Shutting down.")
            await client.close()
            quit()
            return
        
    if message.content.lower().__contains__("jarvis"):
        current_message = await message.reply("Processing...")

        #Save the user's message to our message history so that it can be used in the future for context in our conversations with the AI
        user_message = f"{message.author.name}: {message.content}"
        message = create_message('user', user_message)
        save_new_message(message)

        debug_queue = []
        def debug(message_to_print):
            for debug_coroutine in debug_queue:
                while not debug_coroutine.done():
                    time.sleep(0.1)
            debug_queue.clear()
            debug_coroutine = asyncio.run_coroutine_threadsafe(current_message.edit(content=message_to_print), client.loop)
            debug_queue.append(debug_coroutine)
        while len(request_threads) > 0:
            thread = request_threads[0]
            if not thread.is_alive():
                request_threads.pop(0)
        #Sets up our tools with the music manager and debug function so that they can be used in the chat_with_tools function
        tools.init_tools(music_manager_instance, debug_func=debug)
        thread = threading.Thread(target=tools.chat_with_tools)
        thread.start()
        request_threads.append(thread)
    return

#Run the discord client
print("Running Jarvis...")
client.run(get_discord_application_token())