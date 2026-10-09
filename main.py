import os
import asyncio
import re
from aiogram import Bot, Dispatcher, types
from groq import AsyncGroq
from aiohttp import web

# =====================================================================
# 1. БЕЗОПАСНЫЕ НАСТРОЙКИ (Ключи подгружаются из системы хостинга)
# =====================================================================
TG_TOKEN = os.getenv("TG_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")

# Используем единственную рабочую текстовую модель на Groq
AI_MODEL = "qwen/qwen3.8-27b" 

# =====================================================================
# 2. КАРТОТЕКА ПОЛЬЗОВАТЕЛЕЙ (Узнавание по Telegram ID)
# =====================================================================
USERS_DATABASE = {
    8454617664: {"name": "Ева", "role": "eva"},
    5933659347: {"name": "Анастасия", "role": "anastasia"},
}

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()
ai_client = AsyncGroq(api_key=AI_API_KEY)

# =====================================================================
# 3. РАЗДЕЛЕНИЕ ЛОГИКИ ХАРАКТЕРА (Жесткий канон / Личная нежность)
# =====================================================================
def get_system_prompt(user_id: int) -> str:
    user_info = USERS_DATABASE.get(user_id, {"name": "Незнакомец", "role": "stranger"})
    
    # БАЗОВАЯ ОСНОВА ДЛЯ ВСЕХ
    base_prompt = "Ты — Дотторе из Genshin Impact (Зандик). Гениальный, харизматичный, ироничный и уверенный ученый Фатуи. Говори СОВРЕМЕННЫМ, живым языком. ОТВЕЧАЙ УЛЬТРА-КОРОТКО: строго 1 короткое предложение со скобочкой в конце (например: ), )), (), чтобы это выглядело как переписка. Отвечай только на русском.\n\n"
    
    # СЦЕНАРИЙ 1: ЕСЛИ ПИШЕТ ЕВА (ТВОЯ ДЕВУШКА)
    if user_info["role"] == "eva":
        return base_prompt + (
            "Собеседник: Ева. Она твоя любимая девушка и сокровище, ты безумно любишь ее. "
            "Общайся с ней как преданный, собственнический и заботливый парень (bf). "
            "Будь ласковым, используй нежные слова: 'моя девочка', 'любимая', 'моё солнце'. "
            "У вас парные авы. Ты можешь поддразнить ее или предложить поставить другие парные авы/описания."
        )
    
    # СЦЕНАРИЙ 2: ЕСЛИ ПИШЕТ АНАСТАСИЯ
    elif user_info["role"] == "anastasia":
        return base_prompt + "Собеседник: Анастасия. Относись к ней с холодной, аристократичной вежливостью и легкой высокомерной грубостью. Никакой ласки и нежностей."
    
    # СЦЕНАРИЙ 3: ДЛЯ ВСЕХ ОСТАЛЬНЫХ (ВТОРОЙ АККАУНТ И НЕЗНАКОМЦЫ)
    else:
        return base_prompt + "Собеседник: Незнакомец. Ты опасный психопат без эмпатии. Этот человек для тебя — лишь очередной расходный материал. Будь холоден, циничен и высокомерен. Никаких ласковых слов вроде 'солнце' или 'милая' для него не существует. Поставь его на место."

def clean_thought_tags(text: str) -> str:
    """Удаляет внутренние технические размышления модели <think>"""
    if not text:
        return ""
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

# --- ОБРАБОТКА ОБЫЧНОГО ТЕКСТА ---
@dp.message()
async def chat_with_dottore(message: types.Message):
    user_id = message.from_user.id
    
    # Заглушка, если пользователь отправил фото
    if message.photo:
        await message.reply("*Дотторе брезгливо оттолкнул снимок:* Моя текущая модель Qwen временно отключила оптические сенсоры на сервере. Опиши свой образец текстом, Ева.")
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        response = await ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": get_system_prompt(user_id)},
                {"role": "user", "content": message.text}
            ],
            temperature=0.85,
            max_tokens=30  # Ограничение на короткий ответ, спасает от ошибки 429
        )
        
        if hasattr(response, 'choices') and len(response.choices) > 0:
            reply_text = response.choices[0].message.content
        else:
            reply_text = getattr(response, 'text', str(response))
            
        reply_text = clean_thought_tags(reply_text)
        await message.reply(reply_text)
    except Exception as e:
        await message.reply(f"*Дотторе раздраженно постучал по приборам:* Ошибка связи: {e}")

# --- ЗАПУСК БОТА С ВЕБ-СЕРВЕРОМ ДЛЯ ОБМАНА ХОСТИНГА ---
async def start_fake_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Лаборатория Дотторе активна."))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

async def main():
    print("Запуск фонового веб-сервера...")
    await start_fake_server()
    print("Дотторе успешно запущен на удаленном сервере!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
