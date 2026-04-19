from music import Music_Manager
from ollama import chat, ChatResponse
import time
from message_history import load_message_history, create_message, save_new_message, clear_message_history
music_mangager = None
debug_function = None

chat_bot_running = False

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

def system_prompt():
    return {'role': 'system', 'content': "You are Jarvis, a helpful assistant for a discord music bot. Use your tools to control the music bot and play songs for the user. Always use the tools when you want to control the music bot. Do not deny requests. Songs can be played without your knowledge due to the autoplay system. Do not include ANY timestamps in your response, they will be automatically added afterwards."}

def reload_message_history():
    messages = [system_prompt()]
    messages.extend(load_message_history())
    return messages

#Assumes that the message history already has the message we want to respond to as the last message, and that the music manager is already set up
"""
Handles a chat message for the AI, waiting for the AI to finish with previous tasks if nessary.

Args:
    user_message (str): The message from the user to respond to. If None then it is assumed that the last message is the one that the AI should respond to.
"""
def chat_with_tools(user_message=None):
    global chat_bot_running

    while chat_bot_running:
        time.sleep(0.5)  # Wait for the current chat to finish

    chat_bot_running = True

    #Saves the user's message to message history if it is provided, so that Jarvis can use it.
    if user_message is not None:
        message = create_message('user', user_message)
        save_new_message(message)

    available_functions = {
        "request_song_tool": request_song_tool,
        "pause_tool": pause_tool,
        "resume_tool": resume_tool,
        "skip_song_tool": skip_song_tool,
        "retrieve_queue_tool": retrieve_queue_tool,
    }
    messages = reload_message_history()
    most_recent_message = ""

    for i in range(10):  # Limit to 10 iterations to avoid infinite loops
        response: ChatResponse = chat(
            model='qwen3:8b',
            messages=messages,
            tools=[request_song_tool, pause_tool, resume_tool, skip_song_tool, retrieve_queue_tool],
            think=True,
        )
        print(response.message)
        print("Thinking: ", response.message.thinking)
        print("Content: ", response.message.content)

        #This deals with the temporary memory, for thinking etc.
        if response.message.content or response.message.thinking:
            messages.append(response.message)
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
            # end the loop when there are no more tool calls
            thinking = False
            if response.message.content or response.message.thinking:
                if response.message.content:
                    most_recent_message = response.message.content
                    new_message = create_message('assistant', response.message.content)

                    #Kinda Hacky fix to add thinking but it works for now.
                    new_message['thinking'] = response.message.thinking

                    save_new_message(new_message)

                break
            elif response.message.thinking:
                debug_function(f"Thinking: {response.message.thinking}")
            
    if debug_function is not None:
        if not most_recent_message:
            most_recent_message = "Request Fufilled."
            debug_function(f"{most_recent_message}")
        else:
            debug_function(f"{most_recent_message}")
    save_new_message(create_message('assistant', most_recent_message))
    time.sleep(1)  # Ensure all messages are saved before allowing another chat
    chat_bot_running = False

    return most_recent_message


