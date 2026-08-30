import os
from dotenv import load_dotenv
import google.genai as genai

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key)

# Imtiaz loyihaning barcha Python fayllarini o'qi
project_code = {}

for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', '.git', 'venv']]

    for file in files:
        if file.endswith('.py'):
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    project_code[file_path] = content
            except:
                pass

project_structure = "\n\n".join([
    f"=== {path} ===\n{code}"
    for path, code in project_code.items()
])

print("⏳ N+1 Query muammolarini topib, fix qilinyapti...\n")

response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents=f"""Django loyihasida **N+1 Query** muammolarini topib tuzat:

1. **N+1 Query muammalarini topish** - qaysi joyda bor?
2. **Sababi** - nima uchun sodir bo'layapti?
3. **Fix kod** - `select_related()` yoki `prefetch_related()` bilan tuzatirilgan kod
4. **Performance** - qancha tez bo'ladi?

LOYIHA KODI:
{project_structure}

**Javob format:**
- Muamma 1: [file nomi] - [qaysi joyda]
  - Fix kod: [to'liq kod]

- Muamma 2: [file nomi] - [qaysi joyda]
  - Fix kod: [to'liq kod]"""
)

print(response.text)