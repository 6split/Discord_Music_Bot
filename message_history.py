import json
from datetime import datetime

def save_message_history(message_history, file_path='message_history.json'):
    """Saves the message history to a JSON file.

    Args:
        message_history (list): A list of message dictionaries.
        file_path (str): The path to the file where the history will be saved.
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(message_history, f, ensure_ascii=False, indent=4)

def load_message_history(file_path='message_history.json'):
    """Loads the message history from a JSON file. If the file does not exist, creates an empty list.

    Args:
        file_path (str): The path to the file from which the history will be loaded.

    Returns:
        list: A list of message dictionaries.
    """
    import os
    if not os.path.exists(file_path):
        save_message_history([], file_path)
    with open(file_path, 'r', encoding='utf-8') as f:
        message_history = json.load(f)
    return message_history

def create_message(role, content):
    """Creates a message dictionary.

    Args:
        role (str): The role of the message sender (e.g., 'user', 'assistant').
        content (str): The content of the message.

    Returns:
        dict: A dictionary representing the message.
    """
    now = datetime.now()
    formatted = now.strftime("%m/%d/%Y %H:%M:%S")
    #Removed timestamp due to bot loving to copy it regardless of what I put in the system prompt.
    return {"role": role, "content": f"{content}"}

def compress_message_history(file_path='message_history.json', model='qwen3:8b'):
    """Compresses the message history using an Ollama model.

    Args:
        file_path (str): The path to the JSON file containing the history.
        model (str): The name of the Ollama model to use for compression.
    """
    import ollama
    history = load_message_history(file_path)
    if not history:
        return

    # Construct a prompt context
    content_block = "".join([f"{m['role']}: {m['content']}\n" for m in history])
    prompt = f"The following is a long conversation history. Summarize it concisely while preserving all key facts and user intent, but output the result as a structured list of messages (e.g., \"user\" or \"assistant\"). Use only the necessary information.\n\n{content_block}"

    response = ollama.generate(model=model, prompt=prompt)
    # In some cases, the model might return extra text; we'd ideally parse it
    # but for now we take the result as the new history representation.
    # Since compression is a structural rewrite of logs, we save this back.
    new_history = []
    # This logic assumes the LLM output can be mapped or simply saved as one summary message
    new_history.append({"role": "assistant", "content": response['response']})

    save_message_history(new_history, file_path)

def clear_message_history(file_path='message_history.json'):
    """Clears the message history by saving an empty list to the JSON file.

    Args:
        file_path (str): The path to the file where the history will be cleared.
    """
    save_message_history([], file_path)

def save_new_message(message, file_path='message_history.json'):
    """Appends a new message to the message history JSON file.

    Args:
        message (dict): A dictionary representing the new message.
        file_path (str): The path to the file where the history is saved.
    """

    message_history = load_message_history(file_path)
    if message['role'] == 'user': #If it's a user message we can compress the history before the message is added.
        if len(message_history) > 15:
            print("Compressing message history...")
            compress_message_history(file_path, model='qwen3:8b')
            message_history = load_message_history(file_path) #Reload the history
    assert isinstance(message_history, list), "Expected message_history to be a list."
    message_history.append(message)
    save_message_history(message_history, file_path)

if __name__ == "__main__":
    # Example usage
    # history = [
    #     create_message("user", "Hello!"),
    #     create_message("assistant", "Hi there! How can I help you?")
    # ]
    # save_message_history(history, 'message_history.json')

    # new_message = create_message("user", "Can you tell me a joke?")
    # save_new_message(new_message)

    # loaded_history = load_message_history('message_history.json')
    # print(loaded_history)
    compress_message_history('message_history.json', model='qwen3:8b')