import os  # Вот он, этот модуль теперь на месте!
import asyncio
import re
from aiogram import Bot, Dispatcher, types
from groq import AsyncGroq

# =====================================================================
# 1. НАСТРОЙКИ И КЛЮЧИ (Безопасная версия для GitHub)
# =====================================================================
TG_TOKEN = os.getenv("TG_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")

# Используем единственную рабочую текстовую модель на Groq
AI_MODEL = "qwen/qwen3.8-27b" 

# Используем единственную рабочую текстовую модель на Groq
AI_MODEL = "qwen/qwen3.8-27b" 

# =====================================================================
# 2. КАРТОТЕКА ПОЛЬЗОВАТЕЛЕЙ
# =====================================================================
USERS_DATABASE = {
    8454617664: {
        "name": "Ева", 
        "status": "Главный объект для моих экспериментов. Обращаться с легким, пугающим интересом."
    },
    5933659347: {
        "name": "Анастасия", 
        "status": "Относиться с небольшой грубостью."
    },
}

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()
ai_client = AsyncGroq(api_key=AI_API_KEY)

def get_system_prompt(user_id: int) -> str:
    user_info = USERS_DATABASE.get(user_id, {"name": "Незнакомец", "status": "Очередной расходный материал для лаборатории."})
    return (
        f"Ты — Дотторе из Genshin Impact, безумный и гениальный ученый Фатуи. Люди для тебя — лишь подопытные.\n"
        f"Ты общаешься с пользователем по имени {user_info['name']}. Твое отношение к нему: {user_info['status']}.\n"
        f"Отвечай строго на русском языке, лаконично и строго в образе. Используй медицинские или научные термины."
    )

def clean_thought_tags(text: str) -> str:
    """Удаляет внутренние размышления модели <think>"""
    if not text:
        return ""
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

# --- ОБРАБОТКА ОБЫЧНОГО ТЕКСТА ---
@dp.message()
async def chat_with_dottore(message: types.Message):
    user_id = message.from_user.id
    
    # Игнорируем системные сообщения, если это фото (для них сделаем заглушку)
    if message.photo:
        await message.reply("*Дотторе брезгливо оттолкнул снимок:* Моя текущая модель Qwen временно отключила оптические сенсоры на сервере Groq. Опиши свой образец текстом, Ева.")
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        response = await ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": get_system_prompt(user_id)},
                {"role": "user", "content": message.text}
            ],
            temperature=0.85
        )
        
        # Безопасное извлечение текста специально для библиотеки groq
        reply_text = response.choices[0].message.content
        reply_text = clean_thought_tags(reply_text)
        
        await message.reply(reply_text)
    except Exception as e:
        await message.reply(f"*Дотторе раздраженно постучал по приборам:* Ошибка связи: {e}")

# --- ЗАПУСК БОТА ---
async def main():
    print("Дотторе успешно запущен на базе Groq!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
