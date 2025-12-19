import json

def populate_settings_json():
    """
    Initializes settings.json with the default settings

    """
    settings = {
        "current_model" : "azure",
        "advanced_memory" : True,
        "autoplay" : False,
    }
    f =  open("settings/settings.json", "w")
    json.dump(settings, f)
    f.close()

def get_all_settings():
    f =  open("settings/settings.json", "r")
    settings = json.load(f)
    f.close()
    return settings

def modify_setting(setting_name : str, setting_value):
    current_settings = get_all_settings()
    current_settings[setting_name] = setting_value
    f =  open("settings/settings.json", "w")
    json.dump(current_settings, f)
    f.close()

if __name__ == "__main__":
    populate_settings_json()
    print(get_all_settings())