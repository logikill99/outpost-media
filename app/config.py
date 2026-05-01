import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-before-deploy")
    SQLALCHEMY_DATABASE_URI = "sqlite:///outpost.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me")
    CTF_FLAG_PREFIX = "FLAG{"
    MAX_MESSAGES_HISTORY = 50
    CHAT_CHANNELS = ["pitwall", "ctf"]
    CTF_FLAGS = {
        "welcome-paddock":    os.environ.get("CTF_FLAG_WELCOME",  ""),
        "pit-wall-intercept": os.environ.get("CTF_FLAG_PITWALL",  ""),
        "steg-lap":           os.environ.get("CTF_FLAG_STEG",     ""),
        "caesars-pit-stop":   os.environ.get("CTF_FLAG_CAESAR",   ""),
        "black-box":          os.environ.get("CTF_FLAG_BLACKBOX", ""),
        "final-lap":          os.environ.get("CTF_FLAG_FINALLAP", ""),
    }
