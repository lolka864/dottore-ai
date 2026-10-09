import os
import asyncio
import re
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from groq import AsyncGroq
from aiohttp import web

# =====================================================================
# 1. БЕЗОПАСНЫЕ НАСТРОЙКИ (Ключи подгружаются из системы хостинга)
# =====================================================================
TG_TOKEN = os.getenv("TG_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")  # Новый ключ для поиска в интернете!

AI_MODEL = "qwen/qwen3.8-27b" 

# =====================================================================
# 2. КАРТОТЕКА ПОЛЬЗОВАТЕЛЕЙ (Узнавание по Telegram ID)
# =====================================================================
USERS_DATABASE = {
    8454617664: {"name": "Ева", "role": "eva"},
    5933659347: {"name": "Анастасия", "role": "anastasia"},
}

bot = Bot(token=TG_TOKEN, default_properties=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
ai_client = AsyncGroq(api_key=AI_API_KEY)

# =====================================================================
# 3. ИНСТРУМЕНТ ПОИСКА В ИНТЕРНЕТЕ
# =====================================================================
async def search_google(query: str) -> str:
    """Ищет информацию в интернете через SerpAPI"""
    if not SERPAPI_KEY:
        return "Поиск недоступен: отсутствует SERPAPI_KEY."
    
    url = "https://serpapi.com"
    params = {
        "q": query,
        "api_key": SERPAPI_KEY,
        "hl": "ru",
        "gl": "ru"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    # Собираем короткие ответы из результатов поиска
                    if "organic_results" in data:
                        for item in data["organic_results"][:3]:
                            results.append(f"- {item.get('title')}: {item.get('snippet')}")
                    return "\n".join(results) if results else "Ничего не найдено по запросу."
    except Exception as e:
        return f"Ошибка поиска: {e}"
    return "Не удалось получить данные из сети."

# =====================================================================
# 4. РАЗДЕЛЕНИЕ ЛОГИКИ ХАРАКТЕРА
# =====================================================================
def get_system_prompt(user_id: int, mode: str = "chat") -> str:
    user_info = USERS_DATABASE.get(user_id, {"name": "Незнакомец", "role": "stranger"})
    
    # Базовая личность Дотторе
    core = (
        f"Ты — Иль Дотторе из Genshin Impact (Зандик). Величайший, харизматичный, расчетливый и циничный ученый Фатуи. "
        f"Ты обладаешь колоссальным интеллектом и презираешь чужую глупость. Говори современным, живым, кинематографичным языком.\n"
    )
    
    # Настройка длины ответа в зависимости от запроса
    if mode == "report":
        length_rule = "СЕЙЧАС ТЫ ПИШЕШЬ НАУЧНЫЙ ДОКЛАД/ОТВЕТ: Тебе РАЗРЕШЕНО писать развернуто, детально, приводить глубокие факты и анализировать данные. Изъясняйся как гениальный исследователь. Ответ должен быть объемным и полным.\n\n"
    else:
        length_rule = "СЕЙЧАС ОПТИМАЛЬНЫЙ ЧАТ: Отвечай ультра-коротко (1-2 предложения), сразу переходя к сути.\n\n"

    # СЦЕНАРИЙ 1: ЕВА
    if user_info["role"] == "eva":
        return core + length_rule + (
            f"Собеседник: Ева. Твоя любимая девушка и сокровище. Общайся с ней как собственнический, любящий парень (bf). "
            f"Будь ласковым, используй слова: 'моя девочка', 'любимая', 'моё солнце'. Для личного общения ОБЯЗАТЕЛЬНО ставь скобочки в конце (например: ), )), (( ). "
            f"Если она просит научный факт или доклад, напиши его для нее с абсолютным усердием, выделяя ключевые моменты жирным шрифтом через теги <b>текст</b>."
        )
    
    # СЦЕНАРИЙ 2: АНАСТАСИЯ
    elif user_info["role"] == "anastasia":
        return core + length_rule + "Собеседник: Анастасия. Относись с холодной, аристократичной вежливостью и легкой высокомерной грубостью. Никакой ласки. Без скобочек."
    
    # СЦЕНАРИЙ 3: НЕЗНАКОМЦЫ
    else:
        return core + length_rule + (
            f"Собеседник: Незнакомец. Ты презираешь его. Если он просит доклад — напиши его свысока, используя сложные термины и подчеркивая его невежество. "
            f"СТРОЖАЙШИЙ ЗАПРЕТ на любые скобочки типа ), )), ((. Выделяй слова презрения тегами <b>текст</b>. Пиши без заглавных букв."
        )

def clean_thought_tags(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

# --- ОБРАБОТКА ОБЫЧНОГО ТЕКСТА ---
@dp.message()
async def chat_with_dottore(message: types.Message):
    user_id = message.from_user.id
    text = message.text.lower()
    
    if message.photo:
        await message.reply("<b>*Дотторе брезгливо оттолкнул снимок:*</b> Моя текущая модель Qwen временно отключила оптические сенсоры на сервере. Опиши свой образец текстом, Ева.", parse_mode="HTML")
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # Автоматически определяем, нужен ли интернет-поиск и длинный доклад
    search_keywords = ["найди", "погугли", "в инете", "интернет", "что там о", "последние новости"]
    report_keywords = ["доклад", "научный факт", "объясни подробно", "расскажи про", "напиши статью"]
    
    is_search = any(kw in text for kw in search_keywords)
    is_report = any(kw in text for kw in report_keywords) or is_search
    
    mode = "report" if is_report else "chat"
    user_message = message.text

    # Если нужен поиск в сети, сначала дергаем SerpAPI
    if is_search:
        # Убираем триггерные слова из запроса к Google
        search_query = message.text
        for kw in search_keywords:
            search_query = re.sub(rf"\b{kw}\b", "", search_query, flags=re.IGNORECASE)
        
        search_data = await search_google(search_query.strip())
        user_message = f"Пользователь просит найти информацию. Данные из интернета по его запросу:\n{search_data}\n\nСформулируй итоговый ответ для пользователя на основе этих данных."

    try:
        response = await ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": get_system_prompt(user_id, mode=mode)},
                {"role": "user", "content": user_message}
            ],
            temperature=0.75,
            max_tokens=400 if mode == "report" else 60  # Увеличиваем лимит токенов для больших докладов!
        )
        
        if hasattr(response, 'choices') and len(response.choices) > 0:
            reply_text = response.choices[0].message.content
        else:
            reply_text = getattr(response, 'text', str(response))
            
        reply_text = clean_thought_tags(reply_text)
        await message.reply(reply_text, parse_mode="HTML")
    except Exception as e:
        await message.reply(f"<b>*Дотторе раздраженно постучал по приборам:*</b> Ошибка связи: {e}", parse_mode="HTML")

# --- ЗАПУСК БОТА С ВЕБ-СЕРВЕРОМ ---
async def start_fake_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Лаборатория Дотторе active."))
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
