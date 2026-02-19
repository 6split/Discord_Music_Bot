import json

def save_message_history(message_history, file_path='message_history.json'):
    """Saves the message history to a JSON file.

    Args:
        message_history (list): A list of message dictionaries.
        file_path (str): The path to the file where the history will be saved.
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(message_history, f, ensure_ascii=False, indent=4)

def load_message_history(file_path='message_history.json'):
    """Loads the message history from a JSON file.

    Args:
        file_path (str): The path to the file from which the history will be loaded.

    Returns:
        list: A list of message dictionaries.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        message_history = json.load(f)
    return message_history

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
    assert isinstance(message_history, list), "Expected message_history to be a list."
    message_history.append(message)
    save_message_history(message_history, file_path)

def create_message(role, content):
    """Creates a message dictionary.

    Args:
        role (str): The role of the message sender (e.g., 'user', 'assistant').
        content (str): The content of the message.

    Returns:
        dict: A dictionary representing the message.
    """
    return {"role": role, "content": content}

if __name__ == "__main__":
    # Example usage
    history = [
        create_message("user", "Hello!"),
        create_message("assistant", "Hi there! How can I help you?")
    ]
    save_message_history(history, 'message_history.json')

    new_message = create_message("user", "Can you tell me a joke?")
    save_new_message(new_message)

    loaded_history = load_message_history('message_history.json')
    print(loaded_history)