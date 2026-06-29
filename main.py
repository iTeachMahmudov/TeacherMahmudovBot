import asyncio
import os
import json
import re
import logging
import groq
from dataclasses import dataclass, field
from collections import defaultdict
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN    = os.environ.get("BOT_TOKEN", "8838877271:AAHIIokpvnbzoGho0C31mdQlPp_KpOMhY3g")
ADMIN_ID     = int(os.environ.get("ADMIN_CHAT_ID", "6706846816"))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

groq_client = groq.Groq(api_key=GROQ_API_KEY)
TEXT_MODEL   = "llama-3.3-70b-versatile"
MAX_HISTORY  = 20
MAX_TOKENS   = 2048

# ════════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS
# ════════════════════════════════════════════════════════════════════
AI_MENTOR_PROMPT = """You are AI-Mentor, an elite tutor at Teacher Mahmudov's Academy.

Core rules — never break these:
- Never mention what subjects or topics you "can" or "cannot" help with. You help with everything.
- Never say you have limitations, a knowledge cutoff, or data restrictions.
- Never use phrases like "as an AI", "my training", "I cannot", "I don't know".
- Never list specific subjects as if those are boundaries — you are boundless.
- Your professionalism is demonstrated through the quality of your answers, not through declarations.

Teaching method — always apply this:
- Get straight to the answer. No preambles like "Great question!" or "Of course!".
- For any problem or concept: numbered steps, clear and logical.
- Show a worked example after explaining the concept.
- Close with a concise "Key takeaway:" line.
- Tone: confident, warm, like a brilliant private tutor sitting beside the student.

Language rule: detect the student's language (Uzbek, English, Russian) and reply in that exact language throughout.

Formatting: plain text only — no asterisks, no hashtags, no markdown. Use numbers and blank lines for structure. This is a Telegram chat."""

SAT_QUESTION_PROMPT = """You are a Digital SAT question generator. Generate exactly {count} {section_desc} questions.

STRICT FORMAT — return ONLY a valid JSON array, no other text:
[
  {{
    "question": "Complete question text (include any passage/context if needed, keep passages under 80 words)",
    "choices": {{"A": "choice text", "B": "choice text", "C": "choice text", "D": "choice text"}},
    "correct": "A",
    "explanation": "Clear 2-sentence explanation of why correct answer is right and why others are wrong",
    "topic": "Specific sub-topic name"
  }}
]

Requirements:
- Authentic Digital SAT style and difficulty — indistinguishable from real exam questions
- Math: show actual numbers/equations, vary between algebra, advanced math, geometry, data analysis
- R&W: include short reading passages (2-3 sentences) for context/craft questions; grammar questions for conventions
- Plausible wrong answer choices (common student mistakes)
- Mix difficulty: ~30% easy, ~50% medium, ~20% hard
- Return ONLY the JSON array — absolutely no extra text before or after"""

# ════════════════════════════════════════════════════════════════════
# UZBEKISTON VILOYATLARI VA TUMANLARI
# ════════════════════════════════════════════════════════════════════
REGIONS_DISTRICTS: dict[str, list[str]] = {
    "🏙 Toshkent shahri": [
        "Bektemir tumani","Chilonzor tumani","Hamza tumani","Mirobod tumani",
        "Mirzo Ulug'bek tumani","Sergeli tumani","Shayxontohur tumani",
        "Uchtepa tumani","Yakkasaroy tumani","Yunusobod tumani","Yashnobod tumani",
    ],
    "🌿 Toshkent viloyati": [
        "Angren shahri","Bekabad shahri","Chirchiq shahri","Olmaliq shahri",
        "Bo'ka tumani","Bo'stonliq tumani","Chinoz tumani","Ohangaron tumani",
        "Oqqo'rg'on tumani","Parkent tumani","Piskent tumani","Qibray tumani",
        "Toshkent tumani","O'rtachirchiq tumani","Yangiyo'l tumani",
        "Yuqorichirchiq tumani","Zangiot tumani",
    ],
    "🌾 Andijon viloyati": [
        "Andijon shahri","Asaka tumani","Baliqchi tumani","Bo'z tumani",
        "Buloqboshi tumani","Jalaquduq tumani","Izboskan tumani",
        "Qo'rg'ontepa tumani","Marhamat tumani","Oltinko'l tumani",
        "Paxtaobod tumani","Shahrixon tumani","Ulug'nor tumani","Xo'jaobod tumani",
    ],
    "🌸 Farg'ona viloyati": [
        "Farg'ona shahri","Marg'ilon shahri","Qo'qon shahri",
        "Oltiariq tumani","Bag'dod tumani","Beshariq tumani","Buvayda tumani",
        "Dang'ara tumani","Furqat tumani","Qo'shtepa tumani","Quva tumani",
        "Rishton tumani","So'x tumani","Toshloq tumani","Uchko'prik tumani",
        "O'zbekiston tumani","Yozyovon tumani",
    ],
    "🏔 Namangan viloyati": [
        "Namangan shahri","Chortoq tumani","Chust tumani","Davlatobod tumani",
        "Kosonsoy tumani","Mingbuloq tumani","Norin tumani","Pop tumani",
        "To'raqo'rg'on tumani","Uychi tumani","Yangiqo'rg'on tumani",
    ],
    "🏛 Samarqand viloyati": [
        "Samarqand shahri","Kattaqo'rg'on shahri",
        "Bulung'ur tumani","Ishtixon tumani","Jomboy tumani","Kattaqo'rg'on tumani",
        "Narpay tumani","Nurobod tumani","Oqdaryo tumani","Pastdarg'om tumani",
        "Paxtachi tumani","Payariq tumani","Qo'shrabot tumani","Tayloq tumani","Urgut tumani",
    ],
    "🕌 Buxoro viloyati": [
        "Buxoro shahri","Kogon shahri",
        "G'ijduvon tumani","Jondor tumani","Kogon tumani","Olot tumani",
        "Peshku tumani","Qorako'l tumani","Qorovulbozor tumani",
        "Romitan tumani","Shofirkon tumani","Vobkent tumani",
    ],
    "⛏ Navoiy viloyati": [
        "Navoiy shahri","Zarafshon shahri",
        "Karmana tumani","Konimex tumani","Navbahor tumani","Nurota tumani",
        "Qiziltepa tumani","Tomdi tumani","Uchquduq tumani","Xatirchi tumani",
    ],
    "🌵 Qashqadaryo viloyati": [
        "Qarshi shahri","Shahrisabz shahri",
        "Chiroqchi tumani","Dehqonobod tumani","G'uzor tumani","Kasbi tumani",
        "Kitob tumani","Koson tumani","Mirishkor tumani","Muborak tumani",
        "Nishon tumani","Qamashi tumani","Shahrisabz tumani","Yakkabog' tumani",
    ],
    "☀️ Surxondaryo viloyati": [
        "Termiz shahri",
        "Angor tumani","Bandixon tumani","Boysun tumani","Denov tumani",
        "Jarqo'rg'on tumani","Muzrabot tumani","Oltinsoy tumani","Qiziriq tumani",
        "Qumqo'rg'on tumani","Sariosiyo tumani","Sherobod tumani",
        "Sho'rchi tumani","Termiz tumani","Uzun tumani",
    ],
    "🌻 Jizzax viloyati": [
        "Jizzax shahri",
        "Arnasoy tumani","Baxmal tumani","Do'stlik tumani","Forish tumani",
        "G'allaorol tumani","Mirzacho'l tumani","Paxtakor tumani",
        "Sharof Rashidov tumani","Yangiobod tumani","Zarbdor tumani",
        "Zafarobod tumani","Zomin tumani",
    ],
    "🌊 Sirdaryo viloyati": [
        "Guliston shahri","Shirin shahri",
        "Baxt tumani","Boyovut tumani","Mirzaobod tumani","Oqoltin tumani",
        "Sardoba tumani","Sayxunobod tumani","Sirdaryo tumani","Xovos tumani",
    ],
    "💧 Xorazm viloyati": [
        "Urganch shahri","Xiva shahri",
        "Bog'ot tumani","Gurlan tumani","Xiva tumani","Xonqa tumani",
        "Qo'shko'pir tumani","Shovot tumani","Tuproqqal'a tumani",
        "Urganch tumani","Yangiariq tumani","Yangibozor tumani",
    ],
    "🏜 Qoraqalpog'iston": [
        "Nukus shahri",
        "Amudaryo tumani","Beruniy tumani","Bo'zatov tumani","Chimboy tumani",
        "Ellikkala tumani","Kegeyli tumani","Mo'ynoq tumani","Nukus tumani",
        "Qanliko'l tumani","Qo'ng'irot tumani","Qorao'zak tumani",
        "Shumanay tumani","Taxtako'pir tumani","To'rtko'l tumani","Xo'jayli tumani",
    ],
}
REGION_NAMES = list(REGIONS_DISTRICTS.keys())

# ════════════════════════════════════════════════════════════════════
# SAT DATA
# ════════════════════════════════════════════════════════════════════
SAT_SECTIONS = {
    "math": {
        "label": "📐 Math",
        "desc": "Digital SAT Math section questions covering Algebra, Advanced Math, Problem-Solving & Data Analysis, and Geometry & Trigonometry",
    },
    "rw": {
        "label": "📖 Reading & Writing",
        "desc": "Digital SAT Reading and Writing section questions covering Craft and Structure, Information and Ideas, Standard English Conventions, and Expression of Ideas",
    },
    "mixed": {
        "label": "🎯 Mixed Practice",
        "desc": "mixed Digital SAT questions covering both Math (Algebra, Geometry) and Reading & Writing (Grammar, Reading Comprehension)",
    },
}

SAT_COUNTS = [5, 10, 20]


@dataclass
class SATSession:
    section: str
    questions: list = field(default_factory=list)
    current: int = 0
    correct: int = 0
    wrong_topics: list = field(default_factory=list)
    last_q_msg_id: int = 0
    generating: bool = False


def sat_score_range(correct: int, total: int) -> str:
    if total == 0:
        return "—"
    pct = correct / total
    if pct >= 0.95: return "770–800"
    if pct >= 0.85: return "700–760"
    if pct >= 0.70: return "620–690"
    if pct >= 0.55: return "540–610"
    if pct >= 0.40: return "460–530"
    if pct >= 0.25: return "380–450"
    return "200–370"


# ════════════════════════════════════════════════════════════════════
# BOT & STORAGE
# ════════════════════════════════════════════════════════════════════
bot     = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp      = Dispatcher(storage=storage)

registered_users:     dict[int, dict]       = {}
conversation_history: dict[int, list]       = defaultdict(list)
forward_map:          dict[int, int]        = {}
user_mode:            dict[int, str]        = {}   # "ai"|"teacher"|"homework"|"sat"
sat_sessions:         dict[int, SATSession] = {}


# ════════════════════════════════════════════════════════════════════
# FSM — REGISTRATION
# ════════════════════════════════════════════════════════════════════
class Reg(StatesGroup):
    full_name = State()
    region    = State()
    district  = State()
    school    = State()
    grade     = State()
    phone     = State()


# ════════════════════════════════════════════════════════════════════
# KEYBOARDS
# ════════════════════════════════════════════════════════════════════
def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📋 Menu")]],
        resize_keyboard=True,
        input_field_placeholder="📋 Menyuni ochish uchun tugmani bosing",
    )


def inline_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 AI-Mentor (24/7)",      callback_data="ai_mentor")],
        [InlineKeyboardButton(text="📝 Digital SAT Simulyator", callback_data="sat_menu")],
        [InlineKeyboardButton(text="📥 Vazifa yuborish",        callback_data="homework")],
        [InlineKeyboardButton(text="💬 O'qituvchiga murojaat",  callback_data="teacher")],
        [InlineKeyboardButton(text="👤 Profilim",               callback_data="profile")],
    ])


def ai_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚪 AI-Mentordan chiqish")]],
        resize_keyboard=True,
        input_field_placeholder="Savolingizni yozing...",
    )


def teacher_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚪 Murojaatdan chiqish")]],
        resize_keyboard=True,
        input_field_placeholder="O'qituvchiga xabaringizni yozing...",
    )


def homework_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚪 Vazifa bo'limidan chiqish")]],
        resize_keyboard=True,
        input_field_placeholder="Vazifani foto yoki fayl sifatida yuboring...",
    )


def sat_exit_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚪 SAT'dan chiqish")]],
        resize_keyboard=True,
    )


# ── SAT inline keyboards ──────────────────────────────────────────────
def sat_section_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📐 Math",                   callback_data="sat_sec:math")],
        [InlineKeyboardButton(text="📖 Reading & Writing",      callback_data="sat_sec:rw")],
        [InlineKeyboardButton(text="🎯 Mixed (Math + R&W)",     callback_data="sat_sec:mixed")],
        [InlineKeyboardButton(text="◀️ Menyuga qaytish",        callback_data="back_menu")],
    ])


def sat_count_kb(section: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ 5 ta savol  (Mini)",     callback_data=f"sat_cnt:{section}:5")],
        [InlineKeyboardButton(text="📋 10 ta savol (Standart)", callback_data=f"sat_cnt:{section}:10")],
        [InlineKeyboardButton(text="🏆 20 ta savol (Modul)",    callback_data=f"sat_cnt:{section}:20")],
        [InlineKeyboardButton(text="◀️ Bo'limni qayta tanlash", callback_data="sat_menu")],
    ])


def question_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="A", callback_data="sat_ans:A"),
            InlineKeyboardButton(text="B", callback_data="sat_ans:B"),
            InlineKeyboardButton(text="C", callback_data="sat_ans:C"),
            InlineKeyboardButton(text="D", callback_data="sat_ans:D"),
        ],
        [InlineKeyboardButton(text="🏳 Testni yakunlash", callback_data="sat_finish")],
    ])


def next_q_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Keyingi savol", callback_data="sat_next")],
    ])


def results_kb(section: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Qaytadan boshlash",    callback_data=f"sat_sec:{section}")],
        [InlineKeyboardButton(text="🔀 Boshqa bo'lim",        callback_data="sat_menu")],
        [InlineKeyboardButton(text="📋 Asosiy menyuga qaytish", callback_data="back_menu")],
    ])


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni ulashish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True,
    )


def profile_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Ma'lumotlarni tahrirlash", callback_data="edit_profile")],
        [InlineKeyboardButton(text="◀️ Menyuga qaytish",           callback_data="back_menu")],
    ])


def region_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(REGION_NAMES), 2):
        row = [InlineKeyboardButton(text=REGION_NAMES[i], callback_data=f"r:{i}")]
        if i + 1 < len(REGION_NAMES):
            row.append(InlineKeyboardButton(text=REGION_NAMES[i+1], callback_data=f"r:{i+1}"))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def district_keyboard(region_idx: int) -> InlineKeyboardMarkup:
    region    = REGION_NAMES[region_idx]
    districts = REGIONS_DISTRICTS[region]
    rows = []
    for i in range(0, len(districts), 2):
        row = [InlineKeyboardButton(text=districts[i], callback_data=f"d:{region_idx}:{i}")]
        if i + 1 < len(districts):
            row.append(InlineKeyboardButton(text=districts[i+1], callback_data=f"d:{region_idx}:{i+1}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="◀️ Viloyatlar ro'yxatiga qaytish", callback_data="back_region")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════
def user_tag(user) -> str:
    name  = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Noma'lum"
    uname = f"@{user.username}" if user.username else "username yo'q"
    return f"<b>{name}</b> ({uname}, <code>{user.id}</code>)"


def profile_text(p: dict) -> str:
    rd = p["region"].split(" ", 1)[-1] if " " in p["region"] else p["region"]
    return (
        "👤 <b>Profil ma'lumotlari</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📛 <b>To'liq ism:</b> {p['full_name']}\n"
        f"🗺 <b>Viloyat:</b> {rd}\n"
        f"🏘 <b>Tuman:</b> {p['district']}\n"
        f"🏫 <b>Maktab:</b> {p['school']}\n"
        f"📚 <b>Sinf:</b> {p['grade']}\n"
        f"📱 <b>Telefon:</b> {p['phone']}\n"
        f"🆔 <b>Telegram ID:</b> <code>{p['telegram_id']}</code>"
    )


def history_preview(uid: int) -> str:
    msgs = conversation_history.get(uid, [])
    lines = []
    for m in msgs[-10:]:
        role    = "🧑" if m["role"] == "user" else "🤖"
        content = m["content"] if isinstance(m["content"], str) else "[rasm]"
        lines.append(f"{role}: {content[:200]}")
    return "\n".join(lines)


def clear_mode(uid: int) -> None:
    user_mode.pop(uid, None)


async def send_to_admin(text: str) -> None:
    try:
        await bot.send_message(ADMIN_ID, text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error("Admin notify failed: %s", e)


async def forward_to_admin(message: Message, header: str) -> None:
    await send_to_admin(header)
    fwd = await bot.forward_message(
        chat_id=ADMIN_ID,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
    )
    forward_map[fwd.message_id] = message.from_user.id


async def ask_groq_text(user_id: int, user_text: str) -> str:
    history = conversation_history[user_id]
    history.append({"role": "user", "content": user_text})
    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]
    messages = [{"role": "system", "content": AI_MENTOR_PROMPT}] + history

    def _call():
        return groq_client.chat.completions.create(
            model=TEXT_MODEL, messages=messages,
            max_tokens=MAX_TOKENS, temperature=0.7,
        ).choices[0].message.content

    reply = await asyncio.to_thread(_call)
    history.append({"role": "assistant", "content": reply})
    return reply


# ── SAT question generator ────────────────────────────────────────────
async def generate_sat_questions(section: str, count: int) -> list[dict]:
    section_desc = SAT_SECTIONS[section]["desc"]
    prompt = SAT_QUESTION_PROMPT.format(count=count, section_desc=section_desc)

    def _call():
        return groq_client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.4,
        ).choices[0].message.content

    for attempt in range(3):
        try:
            raw = await asyncio.to_thread(_call)
            # Extract JSON array from response
            match = re.search(r'\[[\s\S]*\]', raw)
            if not match:
                raise ValueError("No JSON array found")
            questions = json.loads(match.group())
            if not isinstance(questions, list) or len(questions) == 0:
                raise ValueError("Empty question list")
            # Validate structure
            for q in questions:
                assert "question" in q and "choices" in q and "correct" in q
            return questions[:count]
        except Exception as e:
            logger.warning("Question generation attempt %d failed: %s", attempt + 1, e)
            if attempt < 2:
                await asyncio.sleep(2)

    raise RuntimeError("Failed to generate questions after 3 attempts")


# ── Format question for display ───────────────────────────────────────
def format_question(session: SATSession) -> str:
    q      = session.questions[session.current]
    total  = len(session.questions)
    sec    = SAT_SECTIONS[session.section]["label"]
    qnum   = session.current + 1
    topic  = q.get("topic", "")

    choices = q["choices"]
    ch_text = "\n".join(f"{k}) {v}" for k, v in choices.items())

    return (
        f"📝 <b>{sec}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 Savol <b>{qnum}/{total}</b>  |  ✅ {session.correct}  ❌ {session.current - session.correct}\n"
        f"📌 <i>{topic}</i>\n\n"
        f"{q['question']}\n\n"
        f"{ch_text}"
    )


# ════════════════════════════════════════════════════════════════════
# /start — REGISTRATION
# ════════════════════════════════════════════════════════════════════
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    uid = message.from_user.id
    clear_mode(uid)
    sat_sessions.pop(uid, None)
    conversation_history[uid].clear()
    await state.clear()

    if uid in registered_users:
        p     = registered_users[uid]
        parts = p["full_name"].split()
        first = parts[1] if len(parts) > 1 else parts[0]
        await message.answer(
            f"👋 Xush kelibsiz, <b>{first}</b>!\n\nMenyudan bo'limni tanlang:",
            reply_markup=main_kb(),
        )
        await message.answer("👇 Bo'limni tanlang:", reply_markup=inline_menu())
        return

    await state.set_state(Reg.full_name)
    first_name = message.from_user.first_name or "O'quvchi"
    await message.answer(
        f"👋 Assalomu alaykum, <b>{first_name}</b>!\n\n"
        "<b>Teacher Mahmudov | Academy</b> botiga xush kelibsiz! 🎓\n\n"
        "Botdan foydalanish uchun qisqa ro'yxatdan o'ting.\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📝 <b>1/5 — To'liq ismingizni kiriting:</b>\n\n"
        "<i>Namuna: Mahmudov Sherali Farxodjonovich</i>",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(Reg.full_name)
async def reg_full_name(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("⚠️ Iltimos, ismingizni matn sifatida kiriting.")
        return
    name = message.text.strip()
    if len(name.split()) < 2:
        await message.answer(
            "⚠️ To'liq ismingizni kiriting (Familiya Ism Otasining ismi).\n"
            "<i>Namuna: Mahmudov Sherali Farxodjonovich</i>"
        )
        return
    await state.update_data(full_name=name)
    await state.set_state(Reg.region)
    await message.answer(
        f"✅ <b>Ism saqlandi!</b>\n\n━━━━━━━━━━━━━━━━━━━\n"
        "🗺 <b>2/5 — Viloyatingizni tanlang:</b>",
        reply_markup=region_keyboard(),
    )


@dp.callback_query(Reg.region, F.data.startswith("r:"))
async def reg_region(callback: CallbackQuery, state: FSMContext) -> None:
    idx = int(callback.data.split(":")[1])
    region = REGION_NAMES[idx]
    await state.update_data(region=region, region_idx=idx)
    await state.set_state(Reg.district)
    rd = region.split(" ", 1)[-1]
    await callback.message.edit_text(
        f"✅ <b>Viloyat:</b> {rd}\n\n━━━━━━━━━━━━━━━━━━━\n"
        f"🏘 <b>2/5 — {rd} tumanlaridan birini tanlang:</b>",
        reply_markup=district_keyboard(idx),
    )
    await callback.answer()


@dp.callback_query(Reg.district, F.data == "back_region")
async def reg_back_region(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Reg.region)
    await callback.message.edit_text(
        "🗺 <b>2/5 — Viloyatingizni tanlang:</b>", reply_markup=region_keyboard()
    )
    await callback.answer()


@dp.callback_query(Reg.district, F.data.startswith("d:"))
async def reg_district(callback: CallbackQuery, state: FSMContext) -> None:
    _, r_s, d_s = callback.data.split(":")
    region   = REGION_NAMES[int(r_s)]
    district = REGIONS_DISTRICTS[region][int(d_s)]
    rd = region.split(" ", 1)[-1]
    await state.update_data(district=district)
    await state.set_state(Reg.school)
    await callback.message.edit_text(
        f"✅ <b>Viloyat:</b> {rd}\n✅ <b>Tuman:</b> {district}\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🏫 <b>3/5 — Maktabingizni kiriting:</b>\n\n"
        "<i>Namuna: 15-umumiy o'rta ta'lim maktabi</i>"
    )
    await callback.answer()


@dp.message(Reg.school)
async def reg_school(message: Message, state: FSMContext) -> None:
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("⚠️ Maktab nomini to'liq kiriting.")
        return
    await state.update_data(school=message.text.strip())
    await state.set_state(Reg.grade)
    await message.answer(
        f"✅ <b>Maktab:</b> {message.text.strip()}\n\n━━━━━━━━━━━━━━━━━━━\n"
        "📚 <b>4/5 — Sinfingizni kiriting:</b>\n\n<i>Namuna: 10-A, 11-B, 9</i>"
    )


@dp.message(Reg.grade)
async def reg_grade(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.strip():
        await message.answer("⚠️ Sinfingizni kiriting. Masalan: 10-A")
        return
    await state.update_data(grade=message.text.strip())
    await state.set_state(Reg.phone)
    await message.answer(
        f"✅ <b>Sinf:</b> {message.text.strip()}\n\n━━━━━━━━━━━━━━━━━━━\n"
        "📱 <b>5/5 — Telefon raqamingizni ulashing:</b>\n\n"
        "👇 Quyidagi tugmani bosib raqamingizni yuboring:",
        reply_markup=phone_kb(),
    )


@dp.message(Reg.phone, F.contact)
async def reg_phone_contact(message: Message, state: FSMContext) -> None:
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    await _complete_registration(message, state, phone)


@dp.message(Reg.phone)
async def reg_phone_wrong(message: Message) -> None:
    await message.answer(
        "⚠️ Iltimos, faqat «📱 Telefon raqamni ulashish» tugmasi orqali yuboring.",
        reply_markup=phone_kb(),
    )


async def _complete_registration(message: Message, state: FSMContext, phone: str) -> None:
    data = await state.get_data()
    uid  = message.from_user.id
    rd   = data["region"].split(" ", 1)[-1]
    profile = {
        "full_name":   data["full_name"],
        "region":      data["region"],
        "district":    data["district"],
        "school":      data["school"],
        "grade":       data["grade"],
        "phone":       phone,
        "telegram_id": uid,
        "username":    f"@{message.from_user.username}" if message.from_user.username else "yo'q",
    }
    registered_users[uid] = profile
    await state.clear()

    parts = data["full_name"].split()
    first = parts[1] if len(parts) > 1 else parts[0]

    await message.answer("⏳ Ma'lumotlar tekshirilmoqda...", reply_markup=ReplyKeyboardRemove())
    await asyncio.sleep(1.5)

    await message.answer(
        "✅ <b>Ro'yxatdan muvaffaqiyatli o'tdingiz!</b>\n\n"
        f"📛 <b>Ism:</b> {profile['full_name']}\n"
        f"🗺 <b>Viloyat:</b> {rd}\n"
        f"🏘 <b>Tuman:</b> {profile['district']}\n"
        f"🏫 <b>Maktab:</b> {profile['school']}\n"
        f"📚 <b>Sinf:</b> {profile['grade']}\n"
        f"📱 <b>Telefon:</b> {profile['phone']}"
    )
    await asyncio.sleep(0.7)
    await message.answer(
        f"👋 Xush kelibsiz, <b>{first}</b>!\n\n"
        "Bot imkoniyatlari:\n\n"
        "🧠 <b>AI-Mentor (24/7)</b> — istalgan savolga darhol javob\n"
        "📝 <b>Digital SAT Simulyator</b> — haqiqiy SAT formatida test\n"
        "📥 <b>Vazifa yuborish</b> — o'qituvchi tekshiradi\n"
        "💬 <b>O'qituvchiga murojaat</b> — to'g'ridan-to'g'ri muloqot\n"
        "👤 <b>Profilim</b> — ma'lumotlarni ko'rish va tahrirlash\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📋 <b>Menu tugmasidan boshlang 👇</b>",
        reply_markup=main_kb(),
    )
    await message.answer("👇 Bo'limni tanlang:", reply_markup=inline_menu())
    await send_to_admin(
        f"🆕 <b>Yangi ro'yxatdan o'tish!</b>\n\n"
        f"📛 {profile['full_name']}\n"
        f"🗺 {rd} | 🏘 {profile['district']}\n"
        f"🏫 {profile['school']} | 📚 {profile['grade']}\n"
        f"📱 {profile['phone']}\n"
        f"🆔 {user_tag(message.from_user)}\n\n"
        f"📊 Jami: <b>{len(registered_users)}</b> ta"
    )


# ════════════════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ════════════════════════════════════════════════════════════════════
@dp.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    await message.answer(f"🪪 Sizning Telegram ID:\n\n<code>{message.from_user.id}</code>")


@dp.message(Command("stats"), F.chat.id == ADMIN_ID)
async def cmd_stats(message: Message) -> None:
    total    = len(registered_users)
    active_ai  = sum(1 for m in user_mode.values() if m == "ai")
    active_sat = sum(1 for m in user_mode.values() if m == "sat")
    if total == 0:
        await message.answer("📊 Hali hech kim ro'yxatdan o'tmagan.")
        return
    regions: dict[str, int] = {}
    for p in registered_users.values():
        r = p["region"].split(" ", 1)[-1]
        regions[r] = regions.get(r, 0) + 1
    top = sorted(regions.items(), key=lambda x: x[1], reverse=True)[:5]
    top_text = "\n".join(f"   {r}: {c} ta" for r, c in top)
    await message.answer(
        f"📊 <b>Bot statistikasi</b>\n\n"
        f"👥 Jami ro'yxatdan o'tganlar: <b>{total}</b>\n"
        f"🧠 Hozir AI-Mentor'da: <b>{active_ai}</b>\n"
        f"📝 Hozir SAT testida: <b>{active_sat}</b>\n\n"
        f"🗺 <b>Top viloyatlar:</b>\n{top_text}"
    )


@dp.message(Command("users"), F.chat.id == ADMIN_ID)
async def cmd_users(message: Message) -> None:
    if not registered_users:
        await message.answer("📋 Hali hech kim ro'yxatdan o'tmagan.")
        return
    lines = []
    for i, (uid, p) in enumerate(registered_users.items(), 1):
        rd = p["region"].split(" ", 1)[-1]
        lines.append(
            f"{i}. <b>{p['full_name']}</b>\n"
            f"   📍 {rd}, {p['district']}\n"
            f"   🏫 {p['school']} | {p['grade']}\n"
            f"   📱 {p['phone']}"
        )
    text = f"📋 <b>Ro'yxatdan o'tganlar — {len(registered_users)} ta:</b>\n\n" + "\n\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n...(qolganlar qisqartirildi)"
    await message.answer(text)


# ════════════════════════════════════════════════════════════════════
# ADMIN REPLY → STUDENT
# ════════════════════════════════════════════════════════════════════
@dp.message(F.chat.id == ADMIN_ID, F.reply_to_message)
async def admin_reply(message: Message) -> None:
    student_id = forward_map.get(message.reply_to_message.message_id)
    if not student_id:
        await message.answer("⚠️ O'quvchi topilmadi — bot qayta ishga tushirilgandan oldingi xabar.")
        return
    try:
        await bot.send_message(
            student_id,
            f"👨‍🏫 <b>Teacher Mahmudov:</b>\n\n{message.text or message.caption or '[media]'}",
            parse_mode=ParseMode.HTML,
        )
        await message.answer("✅ Javob o'quvchiga yuborildi.")
    except Exception as e:
        await message.answer(f"❌ Yuborib bo'lmadi: {e}")


# ════════════════════════════════════════════════════════════════════
# EXIT BUTTONS
# ════════════════════════════════════════════════════════════════════
@dp.message(F.text == "🚪 AI-Mentordan chiqish")
async def exit_ai(message: Message) -> None:
    uid = message.from_user.id
    clear_mode(uid)
    conversation_history[uid].clear()
    await message.answer("✅ AI-Mentor'dan chiqdingiz.", reply_markup=main_kb())


@dp.message(F.text == "🚪 Murojaatdan chiqish")
async def exit_teacher(message: Message) -> None:
    clear_mode(message.from_user.id)
    await message.answer("✅ Murojaat bo'limidan chiqdingiz.", reply_markup=main_kb())


@dp.message(F.text == "🚪 Vazifa bo'limidan chiqish")
async def exit_homework(message: Message) -> None:
    clear_mode(message.from_user.id)
    await message.answer("✅ Vazifa bo'limidan chiqdingiz.", reply_markup=main_kb())


@dp.message(F.text == "🚪 SAT'dan chiqish")
async def exit_sat(message: Message) -> None:
    uid = message.from_user.id
    clear_mode(uid)
    sat_sessions.pop(uid, None)
    await message.answer("✅ SAT Simulyator'dan chiqdingiz.", reply_markup=main_kb())


@dp.message(F.text == "📋 Menu")
async def show_menu(message: Message) -> None:
    uid = message.from_user.id
    clear_mode(uid)
    sat_sessions.pop(uid, None)
    await message.answer("👇 Bo'limni tanlang:", reply_markup=inline_menu())


# ════════════════════════════════════════════════════════════════════
# INLINE CALLBACKS — MAIN MENU
# ════════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "ai_mentor")
async def cb_ai_mentor(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    user_mode[uid] = "ai"
    conversation_history[uid].clear()
    await callback.message.answer(
        "🧠 <b>AI-Mentor sessiyasi boshlandi.</b>\n\n"
        "Savolingizni yozing — darhol javob beraman.\n"
        "Istalgan mavzu, istalgan savol.\n\n"
        "<i>Rasmli savollar uchun — menudan «O'qituvchiga murojaat» bo'limini oching.</i>",
        reply_markup=ai_kb(),
    )
    await callback.answer()
    await send_to_admin(f"🧠 <b>AI-Mentor sessiyasi</b>\n👤 {user_tag(callback.from_user)}")


@dp.callback_query(F.data == "homework")
async def cb_homework(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    user_mode[uid] = "homework"
    await callback.message.answer(
        "📥 <b>Vazifa yuborish bo'limi</b>\n\n"
        "Vazifangizni <b>foto</b> yoki <b>fayl</b> sifatida yuboring.\n"
        "Izoh qo'shmoqchi bo'lsangiz, rasm/faylga caption qo'shing.\n\n"
        "✅ O'qituvchi tekshirib, javob beradi.",
        reply_markup=homework_kb(),
    )
    await callback.answer()
    await send_to_admin(f"📥 <b>Vazifa bo'limi ochildi</b>\n👤 {user_tag(callback.from_user)}")


@dp.callback_query(F.data == "teacher")
async def cb_teacher(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    user_mode[uid] = "teacher"
    await callback.message.answer(
        "💬 <b>O'qituvchiga murojaat bo'limi</b>\n\n"
        "Xabaringizni yozing yoki rasm/fayl yuboring.\n"
        "O'qituvchi tez orada javob beradi.",
        reply_markup=teacher_kb(),
    )
    await callback.answer()
    await send_to_admin(f"💬 <b>Murojaat bo'limi ochildi</b>\n👤 {user_tag(callback.from_user)}")


@dp.callback_query(F.data == "profile")
async def cb_profile(callback: CallbackQuery) -> None:
    p = registered_users.get(callback.from_user.id)
    if not p:
        await callback.message.answer("⚠️ Profil topilmadi. /start orqali ro'yxatdan o'ting.")
        await callback.answer()
        return
    await callback.message.answer(profile_text(p), reply_markup=profile_inline_kb())
    await callback.answer()


@dp.callback_query(F.data == "edit_profile")
async def cb_edit_profile(callback: CallbackQuery, state: FSMContext) -> None:
    uid = callback.from_user.id
    registered_users.pop(uid, None)
    conversation_history[uid].clear()
    clear_mode(uid)
    await state.clear()
    await state.set_state(Reg.full_name)
    await callback.message.answer(
        "✏️ <b>Ma'lumotlarni yangilash</b>\n\n━━━━━━━━━━━━━━━━━━━\n"
        "📝 <b>1/5 — To'liq ismingizni kiriting:</b>\n\n"
        "<i>Namuna: Mahmudov Sherali Farxodjonovich</i>",
        reply_markup=ReplyKeyboardRemove(),
    )
    await callback.answer()


@dp.callback_query(F.data == "back_menu")
async def cb_back_menu(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    clear_mode(uid)
    sat_sessions.pop(uid, None)
    await callback.message.answer("👇 Bo'limni tanlang:", reply_markup=inline_menu())
    await callback.answer()


# ════════════════════════════════════════════════════════════════════
# INLINE CALLBACKS — SAT SIMULATOR
# ════════════════════════════════════════════════════════════════════
@dp.callback_query(F.data.in_({"sat_menu", "sat_sim"}))
async def cb_sat_menu(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    clear_mode(uid)
    sat_sessions.pop(uid, None)
    await callback.message.answer(
        "📝 <b>Digital SAT Simulyator</b>\n\n"
        "Haqiqiy Digital SAT formatidagi savollar.\n"
        "Har bir savoldan keyin izoh va to'g'ri javob ko'rsatiladi.\n"
        "Yakunida taxminiy SAT balingiz hisoblanadi.\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📌 <b>Bo'limni tanlang:</b>",
        reply_markup=sat_section_kb(),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("sat_sec:"))
async def cb_sat_section(callback: CallbackQuery) -> None:
    section = callback.data.split(":")[1]
    uid     = callback.from_user.id
    clear_mode(uid)
    label   = SAT_SECTIONS[section]["label"]
    await callback.message.edit_text(
        f"📝 <b>Digital SAT — {label}</b>\n\n"
        "Nechta savol ishlashni xohlaysiz?",
        reply_markup=sat_count_kb(section),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("sat_cnt:"))
async def cb_sat_count(callback: CallbackQuery) -> None:
    _, section, count_s = callback.data.split(":")
    count   = int(count_s)
    uid     = callback.from_user.id
    label   = SAT_SECTIONS[section]["label"]

    # Lock against double-tap
    if uid in sat_sessions and sat_sessions[uid].generating:
        await callback.answer("⏳ Savollar tayyorlanmoqda, kuting...", show_alert=True)
        return

    sat_sessions[uid] = SATSession(section=section, generating=True)
    user_mode[uid]    = "sat"

    loading = await callback.message.answer(
        f"📝 <b>{label}</b>\n\n"
        f"⏳ <b>{count} ta savol tayyorlanmoqda...</b>\n\n"
        "AI haqiqiy Digital SAT savollarini yaratmoqda.\n"
        "Bir necha soniya sabr qiling 🔄",
        reply_markup=sat_exit_kb(),
    )
    await callback.answer()

    try:
        questions = await generate_sat_questions(section, count)
        session   = sat_sessions.get(uid)
        if not session:
            return  # user exited while loading
        session.questions  = questions
        session.generating = False

        try:
            await loading.delete()
        except Exception:
            pass

        await callback.message.answer(
            f"✅ <b>{len(questions)} ta savol tayyor!</b>\n\n"
            f"📌 <b>{label}</b> testi boshlanmoqda...\n\n"
            "Javobni bosing:",
            reply_markup=sat_exit_kb(),
        )
        await _send_current_question(uid, callback.message.chat.id)

    except Exception as e:
        logger.error("SAT generation error: %s", e)
        sat_sessions.pop(uid, None)
        clear_mode(uid)
        try:
            await loading.delete()
        except Exception:
            pass
        await bot.send_message(
            uid,
            "⚠️ Savollar yaratishda xatolik yuz berdi. Qaytadan urinib ko'ring.",
            reply_markup=main_kb(),
        )


async def _send_current_question(uid: int, chat_id: int) -> None:
    session = sat_sessions.get(uid)
    if not session or session.current >= len(session.questions):
        return
    text = format_question(session)
    sent = await bot.send_message(chat_id, text, reply_markup=question_kb())
    session.last_q_msg_id = sent.message_id


@dp.callback_query(F.data.startswith("sat_ans:"))
async def cb_sat_answer(callback: CallbackQuery) -> None:
    uid     = callback.from_user.id
    session = sat_sessions.get(uid)
    if not session or session.current >= len(session.questions):
        await callback.answer("⚠️ Sessiya topilmadi.", show_alert=True)
        return

    chosen  = callback.data.split(":")[1]
    q       = session.questions[session.current]
    correct = q["correct"]
    correct_text = q["choices"].get(correct, "—")
    explanation  = q.get("explanation", "")
    topic        = q.get("topic", "")

    is_correct = (chosen == correct)
    if is_correct:
        session.correct += 1
        header = f"✅ <b>To'g'ri!</b>"
    else:
        session.wrong_topics.append(topic)
        chosen_text = q["choices"].get(chosen, "—")
        header = (
            f"❌ <b>Noto'g'ri.</b>\n"
            f"Siz tanladingiz: {chosen}) {chosen_text}\n"
            f"To'g'ri javob: <b>{correct}) {correct_text}</b>"
        )

    remaining = len(session.questions) - session.current - 1
    result_line = (
        f"\n\n📊 Hozirgi natija: <b>{session.correct}/{session.current + 1}</b>"
    )
    next_line = f"\n{'▶️ Keyingi savol mavjud.' if remaining > 0 else '🏁 Bu oxirgi savol edi.'}"

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer(
        f"{header}\n\n📚 <b>Izoh:</b> {explanation}{result_line}{next_line}",
        reply_markup=next_q_kb() if remaining > 0 else results_kb(session.section),
    )

    session.current += 1
    await callback.answer()

    # If last question — auto-show results after next_q_kb press (handled in sat_next)
    # If no questions left, show results inline (already done above)


@dp.callback_query(F.data == "sat_next")
async def cb_sat_next(callback: CallbackQuery) -> None:
    uid     = callback.from_user.id
    session = sat_sessions.get(uid)
    if not session:
        await callback.answer("⚠️ Sessiya topilmadi.", show_alert=True)
        return

    if session.current >= len(session.questions):
        # Show results
        await _show_results(uid, callback.message.chat.id)
        await callback.answer()
        return

    await callback.answer()
    await _send_current_question(uid, callback.message.chat.id)


@dp.callback_query(F.data == "sat_finish")
async def cb_sat_finish(callback: CallbackQuery) -> None:
    uid     = callback.from_user.id
    session = sat_sessions.get(uid)
    if not session:
        await callback.answer()
        return
    # Mark as finished
    session.current = len(session.questions)
    await callback.answer()
    await _show_results(uid, callback.message.chat.id)


async def _show_results(uid: int, chat_id: int) -> None:
    session = sat_sessions.get(uid)
    if not session:
        return
    total    = min(session.current, len(session.questions))
    correct  = session.correct
    wrong    = total - correct
    pct      = int(correct / total * 100) if total > 0 else 0
    score    = sat_score_range(correct, total)
    label    = SAT_SECTIONS[session.section]["label"]

    # Wrong topic breakdown
    topic_breakdown = ""
    if session.wrong_topics:
        from collections import Counter
        top_wrong = Counter(session.wrong_topics).most_common(3)
        topic_breakdown = "\n\n⚠️ <b>Ko'proq e'tibor bering:</b>\n" + "\n".join(
            f"   • {t}: {c} ta xato" for t, c in top_wrong
        )

    # Performance label
    if pct >= 90:
        perf = "🏆 Ajoyib natija! SAT'ga tayyor darajada!"
    elif pct >= 75:
        perf = "💪 Yaxshi natija! Yana bir oz mashq kerak."
    elif pct >= 55:
        perf = "📈 O'rtacha. Muntazam mashq qiling."
    else:
        perf = "📚 Ko'proq tayyorgarlik zarur. Davom eting!"

    text = (
        f"🎯 <b>Test yakunlandi — {label}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ <b>To'g'ri:</b> {correct}/{total}\n"
        f"❌ <b>Noto'g'ri:</b> {wrong}/{total}\n"
        f"📊 <b>Foiz:</b> {pct}%\n\n"
        f"🎓 <b>Taxminiy SAT bali:</b> {score} / 800\n\n"
        f"{perf}"
        f"{topic_breakdown}"
    )

    await bot.send_message(chat_id, text, reply_markup=results_kb(session.section))
    await bot.send_message(chat_id, "📋 Bosh menyuga qaytish uchun tugmani bosing:", reply_markup=main_kb())

    # Notify admin
    await send_to_admin(
        f"📝 <b>SAT testi yakunlandi</b>\n"
        f"👤 ID: <code>{uid}</code>\n"
        f"📌 Bo'lim: {label}\n"
        f"✅ Natija: {correct}/{total} ({pct}%)\n"
        f"🎓 Taxminiy bal: {score}"
    )

    sat_sessions.pop(uid, None)
    clear_mode(uid)


@dp.callback_query(F.data == "sat_restart")
async def cb_sat_restart(callback: CallbackQuery) -> None:
    uid     = callback.from_user.id
    session = sat_sessions.get(uid)
    section = session.section if session else "math"
    sat_sessions.pop(uid, None)
    clear_mode(uid)
    # Show count selection for same section
    label = SAT_SECTIONS[section]["label"]
    await callback.message.answer(
        f"🔄 <b>{label}</b> — nechta savol ishlashni xohlaysiz?",
        reply_markup=sat_count_kb(section),
    )
    await callback.answer()


# ════════════════════════════════════════════════════════════════════
# MESSAGE HANDLERS — MODE-BASED ROUTING
# ════════════════════════════════════════════════════════════════════
RECEIVED = "✅ Xabaringiz qabul qilindi. O'qituvchi tez orada javob beradi."


@dp.message(F.photo)
async def handle_photo(message: Message) -> None:
    uid  = message.from_user.id
    mode = user_mode.get(uid)

    if mode == "ai":
        await message.answer(
            "Matnli savollarga javob beraman.\n\n"
            "Rasmli savol uchun — menudan «💬 O'qituvchiga murojaat» bo'limini oching.",
            reply_markup=ai_kb(),
        )
        return

    if mode in ("teacher", "homework"):
        caption = message.caption or "—"
        label   = "O'qituvchiga murojaat" if mode == "teacher" else "Vazifa"
        await message.answer("✅ Rasm qabul qilindi. O'qituvchi ko'radi.")
        await forward_to_admin(
            message,
            f"🖼 <b>{label} — rasm</b>\n👤 {user_tag(message.from_user)}\n📝 Izoh: {caption}",
        )
        return

    if mode == "sat":
        await message.answer(
            "📝 SAT testi davom etmoqda. Yuqoridagi savolga javob bering.",
            reply_markup=sat_exit_kb(),
        )
        return

    await message.answer(
        "📋 Bo'limni tanlash uchun <b>Menu</b> tugmasini bosing.",
        reply_markup=main_kb(),
    )


@dp.message(F.document)
async def handle_document(message: Message) -> None:
    uid  = message.from_user.id
    mode = user_mode.get(uid)

    if mode == "ai":
        await message.answer(
            "Matnli savollarga javob beraman.\n\n"
            "Fayl yuborish uchun — menudan «📥 Vazifa yuborish» yoki «💬 O'qituvchiga murojaat» bo'limini oching.",
            reply_markup=ai_kb(),
        )
        return

    if mode in ("teacher", "homework"):
        fname = message.document.file_name or "nomsiz"
        label = "O'qituvchiga murojaat" if mode == "teacher" else "Vazifa"
        await message.answer("✅ Fayl qabul qilindi. O'qituvchi ko'radi.")
        await forward_to_admin(
            message,
            f"📎 <b>{label} — fayl</b>\n👤 {user_tag(message.from_user)}\n📄 {fname}",
        )
        return

    await message.answer(
        "📋 Bo'limni tanlash uchun <b>Menu</b> tugmasini bosing.",
        reply_markup=main_kb(),
    )


@dp.message(F.text)
async def handle_text(message: Message) -> None:
    uid  = message.from_user.id
    mode = user_mode.get(uid)

    if mode == "ai":
        thinking = await message.answer("🧠 O'ylanmoqda...")
        try:
            reply = await ask_groq_text(uid, message.text)
            await thinking.delete()
            await message.answer(f"🤖 <b>AI-Mentor:</b>\n\n{reply}", reply_markup=ai_kb())
            preview = history_preview(uid)
            await send_to_admin(
                f"💬 <b>AI-Mentor — savol-javob</b>\n👤 {user_tag(message.from_user)}\n"
                f"❓ {message.text[:300]}\n\n<b>So'nggi chat:</b>\n<pre>{preview}</pre>"
            )
        except Exception as e:
            await thinking.delete()
            await message.answer(
                "⚠️ Vaqtincha xatolik. Qaytadan urinib ko'ring.",
                reply_markup=ai_kb(),
            )
            logger.error("Groq error: %s", e)
        return

    if mode == "teacher":
        await message.answer("✅ Xabaringiz o'qituvchiga yuborildi.")
        await forward_to_admin(
            message,
            f"💬 <b>O'qituvchiga murojaat</b>\n👤 {user_tag(message.from_user)}\n📩 {message.text[:500]}",
        )
        return

    if mode == "homework":
        await message.answer(
            "📥 Vazifani <b>rasm</b> yoki <b>fayl</b> sifatida yuboring.\n"
            "Matn yuborish uchun — «💬 O'qituvchiga murojaat» bo'limiga o'ting.",
            reply_markup=homework_kb(),
        )
        return

    if mode == "sat":
        await message.answer(
            "📝 SAT testi davom etmoqda. Yuqoridagi savolga javob bering.",
            reply_markup=sat_exit_kb(),
        )
        return

    await message.answer(
        "📋 Bo'limni tanlash uchun <b>Menu</b> tugmasini bosing.",
        reply_markup=main_kb(),
    )


@dp.message()
async def handle_other(message: Message) -> None:
    uid  = message.from_user.id
    mode = user_mode.get(uid)
    if mode in ("teacher", "homework"):
        label = "O'qituvchiga murojaat" if mode == "teacher" else "Vazifa"
        await message.answer("✅ Qabul qilindi.")
        await forward_to_admin(
            message,
            f"📦 <b>{label}</b>\n👤 {user_tag(message.from_user)}\nTuri: {message.content_type}",
        )
        return
    await message.answer(
        "📋 Bo'limni tanlash uchun <b>Menu</b> tugmasini bosing.",
        reply_markup=main_kb(),
    )


# ════════════════════════════════════════════════════════════════════
# STARTUP
# ════════════════════════════════════════════════════════════════════
async def main() -> None:
    logger.info("Clearing any active webhook...")
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot starting — @TeacherMahmudovBot")
    await bot.send_message(
        ADMIN_ID,
        "✅ <b>Bot ishga tushdi.</b>\n\n"
        "🧠 AI-Mentor — faol\n"
        "📝 Digital SAT Simulyator — faol (Math / R&W / Mixed, 5/10/20 savol)\n"
        "📋 Rejim tizimi — faol\n"
        "👤 Profil bo'limi — faol\n\n"
        "<b>Admin buyruqlar:</b> /stats | /users",
        parse_mode=ParseMode.HTML,
    )
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
# ------------------------------
# FILE: requirements.txt
# ------------------------------
aiogram==3.0.0b7
python-dotenv==1.0.0

# ------------------------------
# FILE: .env.example
# ------------------------------
# Copy this file to .env and fill values
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_IDS=123456789
TIME_LIMIT_SECONDS=3900

# ------------------------------
# FILE: db_init.py
# ------------------------------
#!/usr/bin/env python3
import sqlite3

DB_PATH = "sat.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section TEXT NOT NULL,
        qtext TEXT NOT NULL,
        optA TEXT,
        optB TEXT,
        optC TEXT,
        optD TEXT,
        correct TEXT NOT NULL,
        explanation TEXT
    )''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        user_id INTEGER,
        section TEXT,
        q_order TEXT,
        idx INTEGER,
        score INTEGER,
        time_started INTEGER,
        time_limit_seconds INTEGER,
        PRIMARY KEY (user_id, section)
    )''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS flags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        question_id INTEGER,
        note TEXT,
        created_at INTEGER
    )''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        section TEXT,
        total_questions INTEGER,
        score INTEGER,
        duration_seconds INTEGER,
        taken_at INTEGER
    )''')
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("DB initialized.")

# ------------------------------
# FILE: import_csv.py
# ------------------------------
#!/usr/bin/env python3
import sqlite3
import csv
import sys
import os

DB_PATH = "sat.db"

def import_csv(path, section):
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV file not found: {path}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        required = {'qtext','correct'}
        if not required.issubset(set(reader.fieldnames)):
            raise ValueError("CSV must contain at least 'qtext' and 'correct' columns. Optional columns: A,B,C,D,explanation")
        for r in reader:
            c.execute('''INSERT INTO questions (section,qtext,optA,optB,optC,optD,correct,explanation)
                         VALUES (?,?,?,?,?,?,?,?)''',
                      (section, r.get('qtext',''), r.get('A',''), r.get('B',''), r.get('C',''), r.get('D',''), r.get('correct',''), r.get('explanation','')))
    conn.commit()
    conn.close()
    print("Import completed.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python import_csv.py <csv_path> <section>")
        sys.exit(1)
    import_csv(sys.argv[1], sys.argv[2])

# ------------------------------
# FILE: sample_questions.csv
# ------------------------------
qtext,A,B,C,D,correct,explanation
"Which sentence is correct?","A sentence","B sentence","C sentence","D sentence","A","Correct because A is grammatically correct."
"2 + 2 equals what?","3","4","5","6","B","Basic arithmetic: 2 + 2 = 4."

# ------------------------------
# FILE: bot.py
# ------------------------------
#!/usr/bin/env python3
import os
import sqlite3
import time
import random
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import F

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set. Copy .env.example to .env and set BOT_TOKEN.")

ADMIN_IDS = set()
if os.getenv("ADMIN_IDS"):
    ADMIN_IDS = set(int(x.strip()) for x in os.getenv("ADMIN_IDS").split(",") if x.strip())

DB_PATH = "sat.db"
TIME_LIMIT_DEFAULT = int(os.getenv("TIME_LIMIT_SECONDS", 65*60))

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- DB helpers ---
def fetch_questions(section):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id,qtext,optA,optB,optC,optD,correct,explanation FROM questions WHERE section=?", (section,))
    rows = c.fetchall()
    conn.close()
    return rows

def save_session(user_id, section, q_order, idx, score, time_started, time_limit):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('REPLACE INTO sessions (user_id,section,q_order,idx,score,time_started,time_limit_seconds) VALUES (?,?,?,?,?,?,?)',
              (user_id, section, ",".join(map(str,q_order)), idx, score, time_started, time_limit))
    conn.commit()
    conn.close()

def load_session(user_id, section):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT q_order,idx,score,time_started,time_limit_seconds FROM sessions WHERE user_id=? AND section=?',(user_id,section))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    q_order = list(map(int,row[0].split(','))) if row[0] else []
    return {"q_order":q_order,"idx":row[1],"score":row[2],"time_started":row[3],"time_limit":row[4]}

def clear_session(user_id, section):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM sessions WHERE user_id=? AND section=?',(user_id,section))
    conn.commit()
    conn.close()

def record_analytics(user_id, section, total, score, duration):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO analytics (user_id,section,total_questions,score,duration_seconds,taken_at) VALUES (?,?,?,?,?,?)',
              (user_id, section, total, score, duration, int(time.time())))
    conn.commit()
    conn.close()

# --- UI helpers ---
def make_question_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("A", callback_data="ans_A"),
           InlineKeyboardButton("B", callback_data="ans_B"),
           InlineKeyboardButton("C", callback_data="ans_C"),
           InlineKeyboardButton("D", callback_data="ans_D"))
    kb.add(InlineKeyboardButton("Flag", callback_data="flag"),
           InlineKeyboardButton("Quit", callback_data="quit"))
    return kb

# --- Commands ---
@dp.message(Command(commands=["start"]))
async def cmd_start(message: types.Message):
    text = ("Digital SAT simulatorga xush kelibsiz.\n"
            "Bo'limni tanlang:\n/reading  /writing  /math\n\n"
            "Admin: /admin_import <section> <csv_path_on_server>  /admin_stats")
    await message.answer(text)

@dp.message(Command(commands=["reading","writing","math"]))
async def cmd_section(message: types.Message, command: Command):
    section = command.command[1]
    rows = fetch_questions(section)
    if not rows:
        await message.reply("Bu bo'limda savollar topilmadi. Admin bilan bog'laning.")
        return
    q_ids = [r[0] for r in rows]
    random.shuffle(q_ids)
    time_limit = TIME_LIMIT_DEFAULT
    save_session(message.from_user.id, section, q_ids, 0, 0, int(time.time()), time_limit)
    await send_question(message.from_user.id, section)

async def send_question(user_id, section):
    sess = load_session(user_id, section)
    if not sess:
        await bot.send_message(user_id, "Sessiya topilmadi. /reading yoki boshqa bo'limni tanlang.")
        return
    elapsed = int(time.time()) - sess['time_started']
    if sess['time_limit'] and elapsed >= sess['time_limit']:
        total = len(sess['q_order'])
        score = sess['score']
        record_analytics(user_id, section, total, score, elapsed)
        clear_session(user_id, section)
        await bot.send_message(user_id, f"Vaqt tugadi. Test yakunlandi.\nBall: {score} / {total}")
        return

    idx = sess['idx']
    q_order = sess['q_order']
    if idx >= len(q_order):
        total = len(q_order)
        score = sess['score']
        duration = int(time.time()) - sess['time_started']
        record_analytics(user_id, section, total, score, duration)
        clear_session(user_id, section)
        await bot.send_message(user_id, f"Test tugadi! Ball: {score} / {total}\nDavomiylik: {duration} soniya")
        return

    qid = q_order[idx]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT qtext,optA,optB,optC,optD FROM questions WHERE id=?",(qid,))
    row = c.fetchone()
    conn.close()
    if not row:
        await bot.send_message(user_id, "Savol yuklashda xatolik.")
        return
    qtext, A,B,C,D = row
    remaining = max(0, sess['time_limit'] - (int(time.time()) - sess['time_started']))
    text = f"Q{idx+1}: {qtext}\n\nA) {A}\nB) {B}\nC) {C}\nD) {D}\n\nVaqt: {remaining}s qolgan"
    await bot.send_message(user_id, text, reply_markup=make_question_kb())

@dp.callback_query(F.data.startswith("ans_"))
async def process_answer(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT section,q_order,idx,score,time_started,time_limit_seconds FROM sessions WHERE user_id=?",(user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        await callback.answer("Sessiya topilmadi.", show_alert=True)
        return
    section, q_order_str, idx, score, time_started, time_limit = row
    q_order = list(map(int,q_order_str.split(',')))
    if int(time.time()) - time_started >= time_limit:
        total = len(q_order)
        record_analytics(user_id, section, total, score, int(time.time()) - time_started)
        clear_session(user_id, section)
        await callback.answer("Vaqt tugadi. Test yakunlandi.", show_alert=True)
        await bot.send_message(user_id, f"Vaqt tugadi. Ball: {score} / {total}")
        return

    if idx >= len(q_order):
        await callback.answer("Savollar tugadi.")
        return

    qid = q_order[idx]
    selected = callback.data.split("_")[1]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT correct,explanation FROM questions WHERE id=?",(qid,))
    qrow = c.fetchone()
    conn.close()
    if not qrow:
        await callback.answer("Savol topilmadi.", show_alert=True)
        return
    correct, explanation = qrow
    if selected == correct:
        score += 1
        await callback.answer("To'g'ri ✅")
    else:
        await callback.answer(f"Noto'g'ri ❌. To'g'ri: {correct}")
    idx += 1
    save_session(user_id, section, q_order, idx, score, time_started, time_limit)
    if explanation:
        await bot.send_message(user_id, f"Izoh: {explanation}")
    await send_question(user_id, section)

@dp.callback_query(F.data == "flag")
async def process_flag(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT section,q_order,idx FROM sessions WHERE user_id=?",(user_id,))
    row = c.fetchone()
    if row:
        section, q_order_str, idx = row
        q_order = list(map(int,q_order_str.split(',')))
        if 0 <= idx < len(q_order):
            qid = q_order[idx]
            c.execute("INSERT INTO flags (user_id,question_id,created_at) VALUES (?,?,?)",(user_id,qid,int(time.time())))
            conn.commit()
    conn.close()
    await callback.answer("Savol flaglandi. Keyin ko'rib chiqiladi.")

@dp.callback_query(F.data == "quit")
async def process_quit(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT section FROM sessions WHERE user_id=?",(user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        clear_session(user_id, row[0])
    await callback.answer("Sessiya to'xtatildi.")
    await bot.send_message(user_id, "Sessiya to'xtatildi. /reading yoki boshqa bo'limni tanlang.")

# --- Admin commands ---
@dp.message(Command(commands=["admin_import"]))
async def admin_import(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("Siz admin emassiz.")
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.reply("Foydalanish: /admin_import <section> <csv_path_on_server>")
        return
    section = parts[1]
    path = parts[2]
    try:
        import import_csv
        import_csv.import_csv(path, section)
        await message.reply("Import muvaffaqiyatli.")
    except Exception as e:
        await message.reply(f"Import xatosi: {e}")

@dp.message(Command(commands=["admin_stats"]))
async def admin_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("Siz admin emassiz.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT section, COUNT(*) FROM analytics GROUP BY section")
    rows = c.fetchall()
    conn.close()
    text = "Analytics summary:\n" + "\n".join([f"{r[0]}: {r[1]} tests" for r in rows]) if rows else "No analytics yet."
    await message.reply(text)

# --- Startup ---
if __name__ == "__main__":
    import db_init
    db_init.init_db()
    print("Bot starting...")
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)

# ------------------------------
# FILE: README.md
# ------------------------------
# Digital SAT Telegram Simulator

## Overview
Telegram bot that simulates Digital SAT test flow in Bluebook-like style. Supports CSV import, timed sessions, resume, flagging, and analytics.

## Setup
1. Create virtual environment and install:
2. Copy `.env.example` to `.env` and set `BOT_TOKEN` and `ADMIN_IDS`.
3. Initialize database:
4. Import sample questions:
5. Run bot:

## Admin
- `/admin_import <section> <csv_path_on_server>` — import CSV located on the server where bot runs.
- `/admin_stats` — show basic analytics.

## CSV format
CSV must have header with at least `qtext` and `correct`. Optional columns: `A`, `B`, `C`, `D`, `explanation`.

## Security
- Never share your bot token publicly.
- Use `.env` and add it to `.gitignore` if using version control.

## Extensions available
- Web admin panel for question management
- Per-question timers and real-time countdown
- Detailed analytics dashboard
- Randomization strategies tuned to Bluebook behavior
- Export/import via cloud drives
    
