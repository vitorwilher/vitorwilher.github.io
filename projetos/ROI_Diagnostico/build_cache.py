from dotenv import load_dotenv
load_dotenv()

from data.loader import load_all

print("Populando cache...")
load_all(force=True)
print("Cache criado com sucesso!")
