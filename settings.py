import json
from pathlib import Path

from environs import Env

BASE_DIR = Path(__file__).resolve().parent

env = Env()
env.read_env(str(BASE_DIR / '.env'))
cameras_json = env('CAMERAS')
print(f'JSON: {cameras_json}')

with open(cameras_json) as f:
    cameras = json.load(f)
print(f'Configured {len(cameras)} cameras')

save_path = env('SAVE_PATH')
ai_model = env('AI_MODEL')
proto_txt = env('PROTO_TXT')
min_confidence = env.float('CONFIDENCE')
