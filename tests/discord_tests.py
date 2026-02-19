from music import Music_Manager
import discord
import time
import asyncio
from settings.settings import get_all_settings, modify_setting, populate_settings_json
import tools
from message_history import load_message_history, create_message, save_new_message, clear_message_history

def load_message_history_test(client : discord.Client, music_manager : Music_Manager):
    try:
        load_message_history()  # Just test that it can load without error
        return create_test_return(success=True, message="Load Message History Test Passed")
    except Exception as e:
        return create_test_return(success=False, message=f"Load Message History Test Failed: {str(e)}")

def request_song_test(client : discord.Client, music_manager : Music_Manager):
    try:
        music_manager.request_song("Never Gonna Give You Up")
        time.sleep(0.1)  # Wait for the song to start playing
        if not client.voice_clients[0].is_playing():
            assert False, "Song did not start playing"
        return create_test_return(success=True, message="Request Song Test Passed")
    except Exception as e:
        return create_test_return(success=False, message=f"Request Song Test Failed: {str(e)}")
    
def auto_play_test(client : discord.Client, music_manager : Music_Manager):
    try:
        modify_setting("autoplay", True)  # Enable autoplay for testing
        music_manager.request_song("Never Gonna Give You Up")
        time.sleep(0.5)  # Wait for the song to start playing
        if not client.voice_clients[0].is_playing():
            assert False, "Song did not start playing"
        time.sleep(5)  # Wait for the song to finish and autoplay to start
        if not client.voice_clients[0].is_playing():
            assert False, "Autoplay did not start after song finished"
        modify_setting("autoplay", False)  # Disable autoplay after testing
        music_manager.skip_song()  # Skip the autoplay song to clean up
        return create_test_return(success=True, message="Autoplay Test Passed")
    except Exception as e:
        return create_test_return(success=False, message=f"Autoplay Test Failed: {str(e)}")

def skip_song_test(client : discord.Client, music_manager : Music_Manager):
    try:
        modify_setting("autoplay", False)  # Disable autoplay for testing
        if not client.voice_clients[0].is_playing():
            assert False, "Voice client is not playing"
        while client.voice_clients[0].is_playing():
            music_manager.skip_song()
            time.sleep(0.1)  # Wait for the song to skip
        music_manager.request_song("Never Gonna Give You Up")
        time.sleep(0.5)  # Wait for the song to start playing
        music_manager.skip_song()
        time.sleep(2)  # Wait for the song to skip
        if client.voice_clients[0].is_playing():
            assert False, "Song did not skip"
        return create_test_return(success=True, message="Skip Song Test Passed")
    except Exception as e:
        return create_test_return(success=False, message=f"Skip Song Test Failed: {str(e)}")

def pause_test(client : discord.Client, music_manager : Music_Manager):
    try:
        modify_setting("autoplay", False)  # Disable autoplay for testing
        music_manager.request_song("Never Gonna Give You Up")
        time.sleep(0.1)  # Wait for the song to start playing
        music_manager.pause()
        time.sleep(0.1)  # Wait for the song to pause
        if not client.voice_clients[0].is_paused():
            assert False, "Song did not pause"
        music_manager.resume()
        time.sleep(0.1)  # Wait for the song to resume
        if not client.voice_clients[0].is_playing():
            assert False, "Song did not resume"
        music_manager.skip_song()  # Skip the song to clean up
        return create_test_return(success=True, message="Pause/Resume Test Passed")
    except Exception as e:
        return create_test_return(success=False, message=f"Pause/Resume Test Failed: {str(e)}")

def ollama_tool_test(client : discord.Client, music_manager : Music_Manager):
    try:
        tools.init_tools(music_manager)
        tools.request_song_tool("Never Gonna Give You Up")
        time.sleep(0.5)  # Wait for the song to start playing
        if not client.voice_clients[0].is_playing():
            assert False, "Tool Play did not request the song correctly"
        music_manager.skip_song()  # Skip the song to clean up
        return create_test_return(success=True, message="Tool Play Test Passed")
    except Exception as e:
        return create_test_return(success=False, message=f"Tool Play Test Failed: {str(e)}")

def ollama_play_test(client : discord.Client, music_manager : Music_Manager):
    try:
        clear_message_history()  # Clear message history to ensure a clean test
        user_message = f"6split: Jarvis play Never Gonna Give You Up"
        message = create_message('user', user_message)
        save_new_message(message)
        tools.init_tools(music_manager)
        response = tools.chat_with_tools()
        time.sleep(0.5)  # Wait for the song to start playing
        if not client.voice_clients[0].is_playing():
            assert False, "Ollama tool did not request the song correctly"
        music_manager.skip_song()  # Skip the song to clean up
        return create_test_return(success=True, message="Ollama Tool Test Passed")
    except Exception as e:
        return create_test_return(success=False, message=f"Ollama Tool Test Failed: {str(e)}")

def create_test_return(success=True, message="Test Successful"):
    string = ""
    if success:
        string += ":white_check_mark: "
    else:
        string += ":red_square: "
    string += message
    return string

TESTS_TO_RUN = [
    load_message_history_test,
    request_song_test,
    skip_song_test,
    auto_play_test,
    pause_test,
    ollama_tool_test,
    ollama_play_test,
]

def run_tests(client : discord.Client, voice_channel : discord.VoiceChannel, music_manager : Music_Manager, debug_func=None):
    test_results = []
    for test in TESTS_TO_RUN:
        time.sleep(0.1)
        result = test(client, music_manager)
        if debug_func:
            debug_func(result)
        else:
            test_results.append(result)
    return test_results