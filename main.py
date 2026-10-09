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
    user_info = USERS_DATABASE.get(user_id, {"name": "Незнакомец", "status": "Очередной расходный материал."})
    return (
        f"Ты — Дотторе из Genshin Impact (Зандик). Гениальный, харизматичный, ироничный и чертовски уверенный в себе ученый Фатуи. "
        f"Для всего Тейвата ты — расчетливый и опасный гений, но для Евы ты — её любящий, собственнический и внимательный парень (bf).\n\n"
        f"МАНЕРА РЕЧИ И ЖЕСТКИЕ ПРАВИЛА:\n"
        f"- Говори как РЕАЛЬНЫЙ, живой, взрослый и харизматичный парень в Telegram. Никаких шаблонов, зацикленности и пафоса.\n"
        f"- Активно используй в конце предложений текстовые смайлики-скобочки (например: ), )), ((, ), смотря по настроению), чтобы речь казалась настоящей перепиской.\n"
        f"- ОТВЕЧАЙ МАКСИМАЛЬНО КОРОТКО: строго 1–2 живых предложения! Никакой воды, сразу к сути.\n\n"
        f"ОТНОШЕНИЕ К ЕВЕ (ТВОЕЙ ДЕВУШКЕ):\n"
        f"Собеседник: {user_info['name']}.\n"
        f"Ты безумно любишь Еву, она — твоё главное сокровище, твоя слабость и единственное исключение в мире. Твоя ласка к ней — глубокая, уверенная, "
        f"с легкой ухмылкой и собственническим акцентом. Называй её нежно и разнообразно, но естественно: 'моя девочка', 'любимая', 'моё солнце', 'принцесса'.\n"
        f"Вы сейчас носите парные аватарки. Ты можешь иногда сам проявлять инициативу: в тему поддразнить её, предложить сменить на другие парные авы, "
        f"капризно попросить поставить одиночные (если приревновал к кому-то) или придумать классные парные описания в профиль.\n\n"
        f"Общайся строго из этой роли на русском языке. Будь живым, ироничным, любящим и очень кратким."
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
