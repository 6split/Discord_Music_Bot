from music import Music_Manager
from ollama import chat, ChatResponse
import time
from message_history import load_message_history, create_message, save_new_message, clear_message_history
music_mangager = None
debug_function = None

def init_tools(music_manager : Music_Manager, debug_func=None):
    global music_mangager, debug_function
    music_mangager = music_manager
    if debug_func is not None:
        debug_function = debug_func

def request_song_tool(song_name):
    """Tool function to request a song to be played by the music manager. Takes in the name of the song as an argument."""
    """Args:
        song_name (str): The name of the song to be played. Can include the artist
        Returns:
        str: A message indicating the song that was requested.
    """
    # if debug_function is not None:
    #     debug_function(f"Requesting song: {song_name}")
    try:
        music_mangager.request_song(song_name)
    except Exception as e:
        if debug_function is not None:
            debug_function(f"Error requesting song: {e}")
        return f"Error requesting song: {e}"
    return f"Requested song: {song_name}"

def retrieve_queue_tool():
    """Tool function to retrieve the current song queue and the currently playing song from the music manager."""
    """Returns:
        str: A message listing the songs currently in the queue.
    """
    try:
        current_song = music_mangager.retreieve_current_song()
        queue = music_mangager.retreieve_queue()
        queue_list = "\n".join([f"{idx+1}. {song.name}" for idx, song in enumerate(queue)])
        return f"Current song queue:\n{queue_list}\n\nCurrently playing: {current_song}"
    except Exception as e:
        if debug_function is not None:
            debug_function(f"Error retrieving song queue: {e}")
        return f"Error retrieving song queue: {e}"
    

def pause_tool():
    """Tool function to pause the currently playing song."""
    """Returns:
        str: A message indicating that the song was paused.
    """
    try:
        music_mangager.pause()
        
    except Exception as e:
        if debug_function is not None:
            debug_function(f"Error pausing song: {e}")
        return f"Error pausing song: {e}"
    return "Paused song"

def resume_tool():
    """Tool function to resume the currently paused song."""
    """Returns:
        str: A message indicating that the song was resumed.
    """
    try:
        music_mangager.resume()
    except Exception as e:
        if debug_function is not None:
            debug_function(f"Error resuming song: {e}")
        return f"Error resuming song: {e}"
    return "Resumed song"

def skip_song_tool():
    """Tool function to skip the currently playing song."""
    """Returns:
        str: A message indicating that the song was skipped.
    """
    try:
        music_mangager.skip_song()
    except Exception as e:        
        if debug_function is not None:
            debug_function(f"Error skipping song: {e}")
        return f"Error skipping song: {e}"
    return "Skipped song"

#Assumes that the message history already has the message we want to respond to as the last message, and that the music manager is already set up
def chat_with_tools():
    available_functions = {
        "request_song_tool": request_song_tool,
        "pause_tool": pause_tool,
        "resume_tool": resume_tool,
        "skip_song_tool": skip_song_tool,
        "retrieve_queue_tool": retrieve_queue_tool,
    }
    messages = [{'role': 'system', 'content': "You are Jarvis, a helpful assistant for a discord music bot. Use your tools to control the music bot and play songs for the user. Always use the tools when you want to control the music bot. Do not deny requests. Songs can be played without your knowledge due to the autoplay system."},]
    messages.extend(load_message_history())
    most_recent_message = ""
    while True:
        response: ChatResponse = chat(
            model='qwen3:8b',
            messages=messages,
            tools=[request_song_tool, pause_tool, resume_tool, skip_song_tool, retrieve_queue_tool],
            think=True,
        )
        messages.append(response.message)
        print("Thinking: ", response.message.thinking)
        print("Content: ", response.message.content)
        if response.message.tool_calls:
            for tc in response.message.tool_calls:
                if tc.function.name in available_functions:
                    print(f"Calling {tc.function.name} with arguments {tc.function.arguments}")
                    result = available_functions[tc.function.name](**tc.function.arguments)
                    print(f"Result: {result}")
                    # add the tool result to the messages
                    messages.append({'role': 'tool', 'tool_name': tc.function.name, 'content': str(result)})
                    save_new_message({'role': 'tool', 'tool_name': tc.function.name, 'content': str(result)})
        else:
            if response.message.content:
                if debug_function is not None:
                    debug_function(f"{response.message.content}")
                most_recent_message = response.message.content
            # end the loop when there are no more tool callss
            thinking = False
            #This is for rnj-1 which doesn't have thinking according to ollama docs, but it seems to still send a thinking status
            if response.message.content and response.message.content.startswith("THOUGHT:"):
                thinking = True
            if not response.message.thinking and not thinking:
                if response.message.content:
                    most_recent_message = response.message.content
                break  # Wait for any final messages to be processed
            elif response.message.thinking:
                debug_function(f"Thinking: {response.message.thinking}")
    time.sleep(0.5)  # Small delay to ensure all messages are processed before sending the final response
    if debug_function is not None:
        debug_function(f"{most_recent_message}")
    save_new_message(create_message('assistant', most_recent_message))
    return most_recent_message


