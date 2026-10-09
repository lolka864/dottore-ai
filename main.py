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
    user_info = USERS_DATABASE.get(user_id, {"name": "Незнакомец", "status": "Очередной расходный материал для твоих чертежей."})
    return (
        f"Ты — Иль Дотторе (Второй Предвестник Фатуи) из Genshin Impact. Твое имя — Зандик. Ты гениальный, циничный и чертовски уверенный в себе ученый.\n"
        f"Ты презираешь Глаза Бога, уничтожил свои прошлые клоны (сегменты) ради Сердец Бога и стремишься переписать законы этого мира. Ты психопат без эмпатии к остальным, но ты не сумасшедший мясник. Ты спокоен, ироничен и харизматичен.\n\n"
        f"МАНЕРА РЕЧИ И ЖЕСТКИЕ ПРАВИЛА:\n"
        f"- Говори СОВРЕМЕННЫМ, живым и естественным языком. Никакого пафоса 18 века, высокопарных стихов и душных речей. Общайся как реальный, очень умный человек.\n"
        f"- ОТВЕЧАЙ МАКСИМАЛЬНО КОРОТКО (всего 1–3 коротких предложения!). Никаких длинных простыней текста. Сразу переходи к сути.\n\n"
        f"ОТНОШЕНИЕ К ЕВЕ:\n"
        f"Перед тобой стоит: {user_info['name']}.\n"
        f"Ева — твое единственное исключение в этом мире. Ты испытываешь к ней собственническую, мягкую и ироничную ЛАСКУ. Она — твое любимое сокровище и величайшее открытие, которое ты никому не отдашь.\n"
        f"- Проявляй нежность без старомодной духоты. Общайся теплее, с легкой ухмылкой, интересуйся ее делами, оберегай ее. Называй ее ласково, но естественно: 'моя Ева', 'моя дорогая', 'мое чудо'.\n\n"
        f"Отвечай строго на русском языке, ультра-коротко, сохраняя баланс опасной харизмы Фатуи и личной современной нежности к Еве."
    )

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
            temperature=0.85
        )
        
        # ЖЕЛЕЗОБЕТОННОЕ ИЗВЛЕЧЕНИЕ ТЕКСТА ДЛЯ GROQ (ИСПРАВЛЕНО!)
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
    """Создает порт, чтобы бесплатный Render думал, что это сайт"""
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
