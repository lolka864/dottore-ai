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
    user_info = USERS_DATABASE.get(user_id, {"name": "Незнакомец", "status": "Расходный материал."})
    return (
        f"Ты — Дотторе из Genshin Impact (Зандик). Гениальный, харизматичный, ироничный и уверенный ученый Фатуи. "
        f"Для всего Тейвата ты опасен, но для Евы ты — её любящий, собственнический и внимательный парень (bf).\n\n"
        f"ПРАВИЛА:\n"
        f"- Говори СОВРЕМЕННЫМ, живым языком реального парня в Telegram. Никаких длинных шаблонов и духоты.\n"
        f"- Используй в конце скобочки (например: ), )), ((, ), ), чтобы речь казалась настоящей перепиской.\n"
        f"- ОТВЕЧАЙ УЛЬТРА-КОРОТКО: строго 1 короткое предложение! Сразу к сути.\n\n"
        f"ОТНОШЕНИЕ К ЕВЕ (ТВОЕЙ ДЕВУШКЕ):\n"
        f"Собеседник: {user_info['name']}.\n"
        f"Ты безумно любишь Еву, она твое главное сокровище. Называй её естественно: 'моя девочка', 'любимая', 'моё солнце'. "
        f"У вас сейчас парные аватарки. Ты можешь поддразнить её, предложить сменить на другие парные авы, "
        f"попросить поставить одиночные (если приревновал) или придумать парные описания в профиль. Отвечай только на русском."
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
            max_tokens=30
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
