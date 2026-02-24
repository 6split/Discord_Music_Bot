import discord
import asyncio
import importlib.util
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


async def wait_for_voice_e2ee_ready(voice_client: discord.VoiceClient, timeout_seconds: float = 10.0):
    """Wait for Discord voice E2EE session negotiation to complete when supported by discord.py."""
    end_time = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < end_time:
        privacy_code = getattr(voice_client, "voice_privacy_code", None)
        if privacy_code:
            return privacy_code
        await asyncio.sleep(0.2)
    return None


def build_e2ee_status(voice_client: discord.VoiceClient = None):
    """Build concrete diagnostics for E2EE state in the current runtime."""
    diagnostics = {
        "discord_py_version": getattr(discord, "__version__", "unknown"),
        "davey_installed": importlib.util.find_spec("davey") is not None,
        "connected_to_voice": voice_client is not None and voice_client.is_connected(),
        "has_voice_privacy_code_property": voice_client is not None and hasattr(voice_client, "voice_privacy_code"),
        "voice_privacy_code": None,
        "e2ee_active": False,
    }

    if voice_client is not None and diagnostics["has_voice_privacy_code_property"]:
        diagnostics["voice_privacy_code"] = getattr(voice_client, "voice_privacy_code", None)
        diagnostics["e2ee_active"] = diagnostics["voice_privacy_code"] is not None

    return diagnostics

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
    privacy_code = await wait_for_voice_e2ee_ready(voice)
    if privacy_code is not None:
        print(f"Voice E2EE enabled. Privacy code: {privacy_code}")
    else:
        print("Voice E2EE unavailable (missing davey dependency, unsupported discord.py version, or negotiation timed out).")
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

        if message.content == "!privacy":
            if len(client.voice_clients) == 0 or not client.voice_clients[0].is_connected():
                await message.reply("Not connected to a voice channel.")
                return
            privacy_code = getattr(client.voice_clients[0], "voice_privacy_code", None)
            if privacy_code is None:
                await message.reply("No active voice E2EE session. Make sure you are on discord.py with DAVE support and the `davey` package installed.")
            else:
                await message.reply(f"Current voice privacy code: `{privacy_code}`")
            return
        


        if message.content == "!e2ee_status":
            active_voice_client = None
            if len(client.voice_clients) > 0 and client.voice_clients[0].is_connected():
                active_voice_client = client.voice_clients[0]

            diagnostics = build_e2ee_status(active_voice_client)
            await message.reply(
                "\n".join([
                    "E2EE diagnostics:",
                    f"- discord.py version: `{diagnostics['discord_py_version']}`",
                    f"- davey installed: `{diagnostics['davey_installed']}`",
                    f"- connected to voice: `{diagnostics['connected_to_voice']}`",
                    f"- voice_privacy_code property available: `{diagnostics['has_voice_privacy_code_property']}`",
                    f"- voice privacy code: `{diagnostics['voice_privacy_code']}`",
                    f"- e2ee active: `{diagnostics['e2ee_active']}`",
                ])
            )
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
