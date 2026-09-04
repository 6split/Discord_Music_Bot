import discord
import asyncio
from sensitive_data.credentials import get_discord_application_id, get_discord_application_token
from settings.settings import get_all_settings, modify_setting, populate_settings_json
from music import Music_Manager
from tests.discord_tests import run_tests
import tools
import threading
import time
from custom_songs import is_song_command
from music_history import get_top_songs
from message_history import load_message_history, create_message, save_new_message
#We can only connect to one voice channel, so it is fine to have a global variable here
current_voice_channel = None
music_manager_instance = None
request_threads = []
#Create the discord client
client = discord.Client(intents=discord.Intents.all(), application_id=get_discord_application_id())
jarvis_messages = [] #Saves messages that we have to edit with the most recent response from the AI.

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

        #Handle custom song commands
        if is_song_command(message.content):
            if music_manager_instance is not None:
                music_manager_instance.custom_command(message.content)
                await message.reply(f"Added song for command '{message.content}' to the queue.")
            else:
                await message.reply("Not connected to a voice channel.")
            return

        if message.content.startswith("!settings"):
            current_settings = get_all_settings()
            await message.reply(f"Current Settings: {current_settings}")
            return
        
        #For modifying settings we can just use the setting name
        toggle_settings = []
        non_toggle_settings = []
        for setting_name in get_all_settings().keys():
            if isinstance(get_all_settings()[setting_name], bool):
                toggle_settings.append(setting_name)
            else:
                non_toggle_settings.append(setting_name)
        is_toggle_command = any(message.content.startswith(f"!{setting_name}") for setting_name in toggle_settings)
        is_non_toggle_command = any(message.content.startswith(f"!{setting_name}") for setting_name in non_toggle_settings)
        if is_toggle_command:
            try:
                setting_name = message.content[1:]  # Remove the "!" prefix
                current_settings = get_all_settings()
                current_value = current_settings[setting_name]
                modify_setting(setting_name, not current_value)

                await message.reply(f"{setting_name} now set to {not current_value}")
            except Exception as e:
                await message.reply(f"Error modifying setting: {e}")
            return
        
        if is_non_toggle_command:
            try:
                setting_name = message.content.split(" ")[0][1:]  # Remove the "!" prefix
                new_value = message.content.split(" ", 1)[1]  # Get the value after the space
                modify_setting(setting_name, new_value)

                await message.reply(f"{setting_name} now set to {new_value}")
            except Exception as e:
                await message.reply(f"Error modifying setting: {e}")
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

        #Command for showing the most played songs, e.g. "!top_song" or "!top_song 10"
        if message.content.startswith("!top_song"):
            parts = message.content.split()
            if parts[0] != "!top_song" or (len(parts) > 1 and not parts[1].isdigit()):
                await message.reply("Usage: !top_song [number]")
                return
            num_songs = int(parts[1]) if len(parts) > 1 else 5
            if num_songs < 1:
                await message.reply("Please provide a number of 1 or greater.")
                return
            top_songs = get_top_songs(num_songs)
            if len(top_songs) == 0:
                await message.reply("No songs have been played yet.")
                return
            song_lines = []
            for rank, entry in enumerate(top_songs, start=1):
                song_name = entry['queries'][0] if entry.get('queries') else entry['file_path']
                song_name = song_name[:120]  #Keep long song names from blowing up the message
                song_lines.append(f"{rank}. {song_name} - {entry.get('plays', 0)} plays")
            reply_text = f"Top {len(top_songs)} most played song(s):\n" + "\n".join(song_lines)
            #Trim the list if it would exceed Discord's message length limit
            while len(reply_text) > 1990 and len(song_lines) > 1:
                song_lines.pop()
                reply_text = f"Top {len(song_lines)} most played songs (out of {len(top_songs)}):\n" + "\n".join(song_lines)
            await message.reply(reply_text)
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
            await asyncio.to_thread(run_tests, client, voice_channel, music_manager_instance, debug_func=debug_print)
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

        #Our current message requests
        jarvis_messages.append(current_message)
        

        debug_queue = []
        def debug(message_to_print):
            current_thread_count = 0
            #Trim down jarvis_messages so we have the most up to date message to edit.
            threads_to_remove = []
            for thread in request_threads:
                if not thread.is_alive():
                    threads_to_remove.append(thread)
                else:
                    current_thread_count += 1
            for thread in threads_to_remove:
                request_threads.remove(thread)

            while len(jarvis_messages) > current_thread_count:
                jarvis_messages.pop(0)

            message_to_edit = jarvis_messages[0] if len(jarvis_messages) > 0 else current_message
            if len(jarvis_messages) == 0:
                print("There is no jarvis message to edit, using the current message instead.")

            for debug_coroutine in debug_queue:
                while not debug_coroutine.done():
                    time.sleep(0.1)
                if debug_coroutine.done():
                    debug_queue.remove(debug_coroutine)

            debug_coroutine = asyncio.run_coroutine_threadsafe(message_to_edit.edit(content=message_to_print), client.loop)
            debug_queue.append(debug_coroutine)

        #Sets up our tools with the music manager and debug function so that they can be used in the chat_with_tools function
        tools.init_tools(music_manager_instance, debug_func=debug)
        #Save the user's message to our message history so that it can be used in the future for context in our conversations with the AI
        user_message = f"{message.author.name}: {message.content}"
        thread = threading.Thread(target=tools.chat_with_tools, args=(user_message,), daemon=True)
        thread.start()
        request_threads.append(thread)
        
    return

#Run the discord client
print("Running Jarvis...")
client.run(get_discord_application_token())