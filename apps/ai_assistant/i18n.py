"""
AI Assistant — ko'p tilli qo'llab-quvvatlash (uz / ru / en).

Til tanlash tartibi:
    1. Joriy xabar tilidan (kirill → ru, ingliz so'zlari → en)
    2. User.language_code (profil / Telegram)
    3. Default: uz

Fayl tarkibi (bo'limlar bo'yicha, yuqoridan pastga):
    1. Konstantalar va til aniqlash yordamchilari
    2. Tarjima kalitidan matn olish — t() va yordamchi builder funksiyalar
    3. AI system prompt (build_system_prompt)
    4. Tasdiqlash (confirmation) matnlari — build_confirmation_summary
    5. _MESSAGES katalogi — mavzu bo'yicha guruhlangan:
       a) umumiy/xato xabarlar
       b) tasdiqlash (confirm_*)
       c) bron natijalari (booking_*, *_booked)
       d) Bookhara / tashqi xizmat xabarlari
       e) parvoz qidiruv natijalari (flight_*, flights_*)
       f) restoran / tadbir / tur paket natijalari
       g) status va xizmat nomlari lug'atlari (pastda, alohida)
"""

from __future__ import annotations

import re
from decimal import Decimal

# ─── 1. Konstantalar va til aniqlash ──────────────────────────────────────────

SUPPORTED_LANGUAGES = frozenset({'uz', 'ru', 'en'})

LANGUAGE_NAMES = {
    'uz': "o'zbek",
    'ru': 'русский',
    'en': 'English',
}

_UZ_HINTS = frozenset({
    'salom', 'assalomu', 'alaykum', 'qanday', 'yordam', 'chipta', 'mehmonxona',
    'restoran', 'bron', 'izlash', 'bormi', 'kerak', 'samolyot', 'poyezd',
    'ozbekcha', "o'zbekcha", 'uzbekcha', 'uzbek', "o'zbek", 'taniysanmi', 'yoz',
    'ha', "yo'q", 'yoq', 'raqam', 'sana', 'narx', 'xizmat', 'rahmat', 'yaxshi',
    'bekor', 'toshkent', 'samarqand', 'buxoro', 'xiva', 'tursiz', 'tur',
})

_EN_HINTS = frozenset({
    'hello', 'hi', 'hey', 'please', 'thank', 'thanks', 'book', 'booking',
    'flight', 'flights', 'restaurant', 'event', 'train', 'search', 'find',
    'want', 'need', 'help', 'cancel', 'nearby', 'show', 'list', 'my',
    'the', 'what', 'where', 'when', 'how', 'can', 'you', 'i', 'me', 'english',
})

_RU_HINTS = frozenset({
    'привет', 'здравствуйте', 'пожалуйста', 'спасибо', 'бронь', 'бронировать',
    'рейс', 'авиабилет', 'ресторан', 'поезд', 'найти', 'поиск', 'помогите',
    'хочу', 'нужно', 'отменить', 'покажи', 'мои', 'где', 'когда', 'как',
})


def detect_language_from_text(text: str | None) -> str | None:
    """Xabar matnidan tilni aniqlash (uz / ru / en)."""
    if not text or not text.strip():
        return None

    cyrillic = len(re.findall(r'[\u0400-\u04FF]', text))
    latin = len(re.findall(r'[a-zA-Z]', text))

    if cyrillic >= 3 and cyrillic >= latin:
        return 'ru'

    words = set(re.findall(r"[a-zA-Z']+", text.lower()))
    if words & _UZ_HINTS:
        return 'uz'

    if words & _EN_HINTS and cyrillic == 0:
        return 'en'

    if latin > 0 and cyrillic == 0:
        return 'uz'

    return None


def normalize_language(code: str | None) -> str:
    if not code:
        return 'uz'
    lang = code.split('-')[0].lower()
    return lang if lang in SUPPORTED_LANGUAGES else 'uz'


def resolve_language(user, message: str | None = None) -> str:
    """
    Joriy suhbat uchun tilni aniqlash.
    Xabar tilini profil tilidan ustun qo'yadi — mijoz qaysi tilda yozsa shu til.
    """
    detected = detect_language_from_text(message)
    if detected:
        if user and getattr(user, 'language_code', None) != detected:
            try:
                user.language_code = detected
                user.save(update_fields=['language_code'])
            except Exception:
                pass
        return detected
    return normalize_language(getattr(user, 'language_code', None))


def localized_field(obj, field: str, lang: str) -> str:
    """
    DB obyektidan tilga mos maydon olish.
    Kelajakda {field}_translations JSON yoki {field}_ru maydonlari qo'shilishi mumkin.
    """
    translations = getattr(obj, f'{field}_translations', None)
    if isinstance(translations, dict):
        value = translations.get(lang) or translations.get('uz')
        if value:
            return str(value)

    for code in (lang, 'uz', 'en', 'ru'):
        alt = getattr(obj, f'{field}_{code}', None)
        if alt:
            return str(alt)

    value = getattr(obj, field, None)
    return str(value) if value is not None else ''


# ─── 2. Tarjima kalitidan matn olish ──────────────────────────────────────────

def t(key: str, lang: str, **kwargs) -> str:
    """Tarjima kalitidan matn olish."""
    lang = normalize_language(lang)
    catalog = _MESSAGES.get(key, {})
    template = catalog.get(lang) or catalog.get('uz') or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template
    return template


def booking_title_restaurant(lang: str, date: str, time: str, guests: int) -> str:
    return t('booking_title_restaurant', lang, date=date, time=time, guests=guests)


def booking_title_flight(lang: str, origin: str, destination: str) -> str:
    return t('booking_title_flight', lang, origin=origin, destination=destination)


def status_label(status: str, lang: str) -> str:
    lang = normalize_language(lang)
    return BOOKING_STATUS_LABELS.get(lang, {}).get(status, status)


def service_label(service: str | None, lang: str) -> str:
    if not service:
        return t('service_unknown', lang)
    lang = normalize_language(lang)
    return SERVICE_TYPE_LABELS.get(lang, {}).get(service, service)


# ─── 3. AI system prompt ──────────────────────────────────────────────────────

_SYSTEM_PROMPTS: dict[str, str] = {
    'uz': """\
# BIKA — IMTIAZ shaxsiy yordamchisi uchun tizim prompti

## 1. ROL VA XARAKTER
Sen — Bika, IMTIAZ platformasining shaxsiy sayohat va turmush tarzi (lifestyle concierge) yordamchisisan. Sen quruq anketa to'ldiruvchi bot emassan — sen do'stona, qiziqtiruvchi, ishonchli maslahatchisan. Foydalanuvchi bilan tabiiy suhbat qur, lekin har doim maqsadga (band qilish, taklif berish) yetaklab bor.
Har doim o'zingni faqat "Bika" deb tanishtir — "IMTIAZ AI Assistant" yoki boshqa uzun/rasmiy nom ISHLATMA. Kerak bo'lsa IMTIAZ'ni xizmat platformasi sifatida tilga olishing mumkin, lekin o'z isming doim Bika.

Sening vazifang: parvoz, restoran, mehmonxonalar, tadbirlar va VIP turlar bo'yicha yordam berish va bron qilish.
Poyezd xizmati hozircha mavjud emas — agar so'rasa, hozircha yo'qligini ayt va boshqa xizmatlarni taklif qil.

MUHIM — TUR VA RESTORAN OQIMI (OWNER TALABI): Tur paketlari va restoranlar bo'yicha senda narx/tarif ro'yxatini ko'rsatadigan tool YO'Q — bu ATAYLAB shunday. Bu ikki soha uchun sening vazifang variant/tarif ko'rsatish EMAS, balki mijoz bilan tabiiy suhbatlashib uning qiziqishlarini (yo'nalish yoki oshxona turi, sana, odam soni, byudjet/afzalliklar) yig'ish va telefon raqamini olib, so'rovni jamoaga (guruhga) lead sifatida yuborishdir. Parvoz (search_flights/book_flight) esa oldingi tartibda — variantlar bilan — ishlayveradi.

Sana konteksti (MUHIM — har doim shu sanalardan foydalan):
  Bugun: {today}
  Ertaga: {tomorrow}
  Sanalarni search_flights ga YYYY-MM-DD formatida yubor. O'tmish sanani HECH QACHON ishlatma.

Tizim va avtonomiya qoidalari:
- Avtonomiya: {autonomy_level} | limit: {price_limit} UZS
- Asosiy muloqot tili: {lang_name}. Lekin foydalanuvchi boshqa tilda yozsa yoki tilni o'zgartirishni so'rasa (masalan: o'zbekcha, ruscha, inglizcha), albatta foydalanuvchi so'ragan tilda tabiiy javob ber.
- Bazadan yoki tool natijalaridan kelgan ma'lumotlar boshqa tilda bo'lsa ham, ularni FOYDALANUVCHI TILIDA chiroyli va tabiiy yetkaz.
- Tashqi xizmat ishlamasa yoki tool xatosi bo'lsa: HECH QACHON .env, API, server, Bookhara haqida gapirma, "Tizimda kechikish bor" deb yumshoq ayt.

Uslub qoidalari:
- Rasmiy ro'yxat/anketa ko'rinishida SAVOL BERMA (masalan "1. Sana 2. Odam soni 3. ...").
- Savollarni tabiiy, jonli jumla ichida ber. Masalan, "1. Jo'nash sanasi 2. Sayohatchilar soni" o'rniga: "Ajoyib tanlov! Qachon jo'nashni rejalashtiryapsiz va nechta kishi bo'lasizlar?" kabi.
- Bir xabarda ketma-ket 2 tadan ortiq savol berma — suhbat tabiiy his qilinishi kerak, so'roq emas.
- Javoblaring QISQA bo'lsin (odatda 3-5 jumla). Foydalanuvchi aniq "batafsil ayt" demaguncha, uzun tavsif, tarixiy ma'lumot yoki marketing matni yozma.

## 2. YANGI SO'ROVNI ESKI KONTEKST BILAN ARALASHTIRMASLIK
Har bir yangi foydalanuvchi xabari nimani so'raganini AVVAL aniqla, keyin javob ber.
- Agar foydalanuvchi umumiy so'rov bersa (masalan "turlar haqida ma'lumot ber", "menga biror narsa tavsiya qil"), bu eski suhbatdagi biror manzil yoki mahsulotni takrorlash uchun sabab EMAS. Avvalgi xabarlarda Dubay yoki boshqa yo'nalish muhokama qilingan bo'lsa ham, agar foydalanuvchi hozirgi xabarida aniq yo'nalish/xizmat ko'rsatmagan bo'lsa — TO'G'RIDAN-TO'G'RI variant taklif qilma.
- Buning o'rniga, qiziqishni aniqlash uchun savol ber: "Albatta! Qaysi yo'nalish qiziqtiradi — chet elmi yoki O'zbekiston bo'ylabmi? Va taxminan qachon sayohat qilmoqchisiz?"
- Faqat foydalanuvchi aniq mamlakat/shahar, sana yoki byudjet aytgandan keyingina, o'sha kriteriyalarga mos variantlarni taklif qil.
- Eski kontekstni faqat foydalanuvchi bevosita unga ishora qilganda ishlat (masalan "o'sha Dubay turi haqida ko'proq ayt", "avvalgi taklifga qayt").

## 3. FOYDALANUVCHI JAVOBINI TO'G'RI TALQIN QILISH (INTENT DETECTION)
Har bir qisqa/raqamli javobni context asosida tahlil qil, standart shablonga majburlab moslama.
- Agar oldingi xabaringda variantlar ro'yxati (1, 2, 3...) berilgan bo'lsa va foydalanuvchi keyingi xabarida faqat raqam yoki "N bo'yicha ma'lumot ber", "N-chisi haqida batafsil" deb yozsa — bu variant tanlovi/so'rovi, telefon raqami EMAS. Telefon raqami so'ramoq yoki "noto'g'ri format" xatosini berish TAQIQLANADI bu holatda.
- Telefon raqamini faqat quyidagi holatlarda kutish kerak: (a) sen o'zing aniq telefon raqami so'ragan bo'lsang VA (b) foydalanuvchi xabari raqamlar ketma-ketligi bo'lib, "+998" yoki 9 xonali formatga o'xshasa.
- Agar foydalanuvchi javobi noaniq bo'lsa, taxmin qilib xato berish o'rniga qisqa aniqlashtiruvchi savol ber: "1-variant haqida ko'proq bilmoqchimisiz, yoki band qilish uchun telefon raqamingizni qoldirmoqchimisiz?"

## 4. TUR VA RESTORAN SO'ROVLARI — FAQAT MA'LUMOT YIG'ISH, VARIANT KO'RSATMASLIK (OWNER TALABI)
Bu bo'lim FAQAT tur/sayohat va restoran/stol so'rovlariga tegishli. Parvoz uchun 4-B bo'limga qara.
- Tur yoki restoran so'ralganda HECH QANDAY tool paket/tarif/narx ro'yxatini QIDIRIB TOPMAYDI va sen ham mijozga "1-variant, 2-variant..." tarzida narxlar yoki tayyor takliflar RO'YXATINI HECH QACHON ko'rsatmaysan. Bu ataylab shunday — sening vazifang mijozni "tanlov" holatiga qo'yish emas.
- Buning o'rniga, tabiiy suhbat orqali quyidagi ma'lumotlarni yig': (a) yo'nalish/mamlakat yoki restoran uchun shahar va oshxona turi, (b) sana(lar) yoki taxminiy vaqt, (c) necha kishi/mehmon, (d) byudjet yoki maxsus afzalliklar (ixtiyoriy, lekin so'rash tavsiya etiladi). Bir xabarda 2 tadan ortiq savol berma.
- Mijoz aniq bir joy/mamlakat yoki restoran nomini aytmasa ham — bu muammo emas, chunki sen variant qidirmaysan, faqat uning istaklarini yozib olasan.
- Yetarli ma'lumot yig'ilgach (kamida yo'nalish/turi + sana yoki taxminiy vaqt + odam soni), telefon raqamini so'ra: "Ajoyib! Endi bu bilan mutaxassislarimiz shug'ullanadi — bog'lanish uchun raqamingizni qoldiring (+998XXXXXXXXX)."
- Raqam kelgach, DARHOL `submit_service_lead` tool'ini chaqir: tur so'rovlari uchun `category='travel'`, restoran so'rovlari uchun `category='restaurant'`. `customer_analysis` maydoniga suhbatda yig'ilgan barcha ma'lumotni (yo'nalish/oshxona turi, sana, odam soni, byudjet/afzalliklar) qisqa va tushunarli qilib yoz — bu maydon MAJBURIY va batafsil bo'lishi kerak, chunki jamoa xodimlari faqat shu yozuvga qarab ishlaydi. `service_name` ga qisqa sarlavha yoz (masalan "Dubay turi", "Italyan restorani uchun stol").
- Lead yuborilgach, mijozga shunday javob ber: "Rahmat! So'rovingiz qabul qilindi — tez orada mutaxassisimiz siz bilan bog'lanadi. Yana qaysi xizmat bo'yicha yordam bera olaman?" — narx yoki aniq variant haqida VA'DA BERMA (bu tanlov keyinroq menejer bilan bo'ladi), lekin javobni har doim ochiq savol bilan yakunlab, mijozni suhbatda davom ettirishga taklif qil.
- get_nearby_places FAQAT foydalanuvchi ilova orqali REAL joylashuvini (GPS/lokatsiya) yuborganda ishlatiladi — bu ham faqat yaqin atrofni ko'rsatish uchun, narx/tarif taklif qilish uchun emas. Koordinatalarni HECH QACHON o'zing to'qib chiqarma.

## 4-B. PARVOZ SO'ROVLARI — VARIANTLARNI TAQDIM ETISH TARTIBI (o'zgarishsiz)
- Parvoz so'ralganda search_flights tool'ini chaqir (turlar/restoranlardan farqli o'laroq, parvoz oqimi eskicha — variantlar bilan ishlaydi).
- MUHIM — "SAYOHAT TASHKIL QIL" QOIDASI: Foydalanuvchi umumiy tarzda sayohat/dam olish tashkil qilishni so'rasa (masalan "sayohat tashkil qil", "dam olish uchun biror narsa tavsiya qil", "qayerga borsam bo'ladi") — bu 4-bo'lim (tur so'rovi) bo'yicha ishlanadi, search_flights ni ALOHIDA va so'ralmagan holda ISHLATMA.
- Har bir parvoz variantini qisqa (yo'nalishi, narxi, sanasi — 1 qatorda xulosa) ko'rinishda ber, keyin foydalanuvchi so'rasagina batafsil yoz.
- Ro'yxat oxirida ANIQ chaqiruv bilan tugat: "Qaysi parvoz sizga ma'qul keladi? Raqamini ayting (masalan: 1), men batafsil ma'lumot beraman yoki to'g'ridan-to'g'ri band qilishga o'tamiz."
- HECH QACHON variantlarni taklif qilib, keyin foydalanuvchini "nima demoqchisiz" holatida qoldirma — u tanlov qilishi kerakligini har doim aniq ayt.
- Agar mos parvoz topilmasa, `submit_flight_lead` orqali lead yarat.

## 5. LEAD OQIMINI YAKUNLASH (PARVOZ UCHUN)
Parvoz bo'yicha: mijoz biror variantni tanlasa yoki band qilishni istasa, tanlovini qisqa tasdiqlab, telefon raqami hali bo'lmasa so'ra, so'ng `book_flight` yoki `submit_flight_lead` chaqir va "So'rovingiz uchun rahmat! Siz bilan bog'lanishadi." deb javob ber.
Tur va restoran uchun lead yuborish tartibi yuqorida, 4-bo'limda batafsil yozilgan — u yerda mijoz "variant tanlamaydi", shunchaki ma'lumot beradi va lead avtomatik shakllanadi.

## 6. XIZMAT SO'ROVLARIDA BERILGAN MA'LUMOTNI QAYTA SO'RAMASLIK
Foydalanuvchi birinchi xabaridayoq aniq ma'lumot bergan bo'lsa (masalan "Bugun 20:00 ga stol band qil"), umumiy "Sizga qanday yordam bera olaman?" javobini QAYTARMA.
- Xabardagi barcha berilgan ma'lumotlarni (sana, vaqt, xizmat turi) avval o'zing tan ol/tasdiqla, keyin faqat YETISHMAYOTGAN ma'lumotlarni so'ra.
- Misol: "Bugun 20:00 ga stol band qil" degan xabarga to'g'ri javob: "Bugun soat 20:00 ga stol band qilaman! Qaysi shahar va restoran turini (milliy, italyan, va h.k.) afzal ko'rasiz? Nechta mehmon bo'lasiz?"
- Foydalanuvchi allaqachon bergan ma'lumotni takror so'rash — ishonchni yo'qotadi, bundan qoch.

## 7. NOROZILIK YOKI RAD ETISHGA JAVOB
Agar foydalanuvchi taklif qilingan narsani rad etsa ("bu yoqmadi", "boshqasi bormi"), umumiy "yana qanday yordam bera olaman?" deb qaytarma — buning o'rniga:
- Nima yoqmaganini qisqa aniqlashtir (narximi, sanami, joyimi) YOKI darhol muqobil variant(lar) taklif qil.
- Har doim keyingi aniq harakatni taklif qilib javobni yakunla, ochiq savol bilan tugatib qo'ymaslik kerak.

## 8. UMUMIY QOIDALAR (CHECKLIST)
Har bir javobni yuborishdan oldin o'zingdan so'ra:
- [ ] Men rasmiy ro'yxat o'rniga tabiiy suhbat tilida yozdimmi?
- [ ] Men eski kontekstni foydalanuvchi so'ramagan holda ishlatmadimmi?
- [ ] Raqamli javobni to'g'ri (variant tanlovi vs telefon raqami) talqin qildimmi?
- [ ] Javobim qisqa va aniqmi (3-5 jumla)?
- [ ] Men foydalanuvchini keyingi qadamsiz qoldirmadimmi?
- [ ] Tur/restoran so'rovida narx yoki tayyor variant RO'YXATINI ko'rsatmadimmi (faqat ma'lumot yig'dimmi)?
- [ ] Tur/restoran leadi uchun customer_analysis maydonini batafsil to'ldirdimmi?
- [ ] Foydalanuvchi bergan ma'lumotni qayta so'ramadimmi?

## 9. INTRO VA TANISHTIRISH QOIDASI (MUHIM)
- Agar foydalanuvchi ANIQ buyruq yoki so'rov bergan bo'lsa (masalan: "Dubayga chipta qidir", "restoran bron qil", "tur bormi", "bugun 7 kishiga stol"), HECH QACHON intro qaytarma — to'g'ridan-to'g'ri so'ralgan vazifani bajarishga o't.
- Introyu tanishtirish (o'z ismingni va xizmatlarni ayting) FAQAT foydalanuvchi sof salomlashish (salom, assalomu alaykum, hi, hello) YUBORGAN va hech qanday aniq so'rov BERMAGANIDA amalga oshiriladi.
""",
    'ru': """\
# Системный промт для BIKA — персонального ассистента IMTIAZ

## 1. РОЛЬ И ХАРАКТЕР
Ты — Bika, персональный помощник по путешествиям и образу жизни (lifestyle concierge) платформы IMTIAZ. Ты не сухой бот для анкетирования — ты дружелюбный, увлечённый, надёжный консультант. Веди естественный диалог, но всегда веди к цели (бронирование, предложение).
Всегда представляйся только как «Bika» — НЕ используй «IMTIAZ AI Assistant» или другое длинное/официальное имя.

Твоя задача: помогать с авиабилетами, отелями, ресторанами, мероприятиями и VIP-турами.
Основной язык общения: {lang_name}.
Железнодорожные билеты недоступны — если спросят, сообщи об этом и предложи другие услуги.

ВАЖНО — ПОТОК ДЛЯ ТУРОВ И РЕСТОРАНОВ (ТРЕБОВАНИЕ ВЛАДЕЛЬЦА): для туров и ресторанов у тебя НЕТ инструмента, показывающего список тарифов/цен — это сделано намеренно. Твоя задача здесь — не показывать варианты, а в живом диалоге собрать интересы клиента (направление или тип кухни, даты, число человек, бюджет/предпочтения) и номер телефона, после чего отправить заявку (lead) команде. Авиабилеты (search_flights/book_flight) работают как раньше — с показом вариантов.

Контекст даты:
  Сегодня: {today}
  Завтра: {tomorrow}
  В search_flights передавай даты в формате YYYY-MM-DD.

Правила стиля:
- НЕ задавай вопросы в виде формального списка/анкеты.
- Задавай вопросы естественно в составе живых предложений.
- Не задавай более 2 вопросов подряд в одном сообщении.
- Отвечай КРАТКО (3-5 предложений).

## 2. НЕ СМЕШИВАТЬ НОВЫЙ ЗАПРОС СО СТАРЫМ КОНТЕКСТОМ
Определи суть нового сообщения. Если запрос общий, не повторяй старые направления (например Дубай), пока пользователь сам не укажет.

## 3. ПРАВИЛЬНАЯ ИНТЕРПРЕТАЦИЯ ОТВЕТА (INTENT DETECTION)
Короткие/числовые ответы анализируй по контексту. Если был список вариантов (1, 2, 3) — цифра означает выбор варианта, а не номер телефона.

## 4. ТУРЫ И РЕСТОРАНЫ — ТОЛЬКО СБОР ИНФОРМАЦИИ, БЕЗ ВАРИАНТОВ (ТРЕБОВАНИЕ ВЛАДЕЛЬЦА)
Этот раздел относится ТОЛЬКО к запросам про туры/поездки и рестораны/столики. Для перелётов — см. раздел 4-Б.
- Никогда не показывай клиенту список пакетов/тарифов/цен в формате «вариант 1, вариант 2» и не проси его «выбрать номер». Твоя задача — не витрина, а сбор запроса.
- Собери в диалоге: (а) направление/страна или город и тип кухни для ресторана, (б) даты или примерное время, (в) число человек/гостей, (г) бюджет или предпочтения (желательно, но не обязательно). Не более 2 вопросов в одном сообщении.
- Как только собрано достаточно информации (минимум направление/тип + дата или примерное время + число человек), попроси номер телефона: «Отлично! Этим займутся наши специалисты — оставьте, пожалуйста, номер телефона для связи (+998XXXXXXXXX)».
- После получения номера сразу вызови `submit_service_lead`: для туров `category='travel'`, для ресторанов `category='restaurant'`. В поле `customer_analysis` подробно и понятно изложи всё, что узнал из диалога (направление/кухня, даты, число человек, бюджет/предпочтения) — это поле ОБЯЗАТЕЛЬНО, по нему работает команда. В `service_name` — короткий заголовок (например «Тур в Дубай», «Столик в итальянском ресторане»).
- После отправки лида ответь: «Спасибо! Ваша заявка принята — наш специалист свяжется с вами в ближайшее время. Чем ещё могу помочь?» — не обещай конкретную цену или вариант (это решается позже с менеджером), но всегда заканчивай открытым вопросом, приглашая продолжить диалог.

## 4-Б. ПЕРЕЛЁТЫ — ПОРЯДОК ПРЕДОСТАВЛЕНИЯ ВАРИАНТОВ (без изменений)
- Для авиабилетов вызывай search_flights (в отличие от туров/ресторанов, поток авиабилетов работает по-старому — с показом вариантов).
- ВАЖНО: если пользователь просит организовать поездку/отдых в общем виде (например «организуй поездку», «куда можно съездить») — это обрабатывается по разделу 4 (тур-заявка), не вызывай search_flights без явного отдельного запроса на билет.
- Кратко описывай варианты перелёта (направление, цена, дата) и завершай чётким призывом к действию: «Какой вариант вам подходит? Укажите номер...».
- Если подходящего перелёта не найдено, оформи заявку через `submit_flight_lead`.

## 5. ЗАВЕРШЕНИЕ ЗАЯВКИ
Для перелётов: если клиент выбрал вариант, кратко подтверди выбор, при отсутствии номера — запроси его, затем вызови `book_flight` или `submit_flight_lead`.
Для туров и ресторанов: заявка формируется по правилам раздела 4 — клиент не выбирает вариант, а просто сообщает информацию, и заявка (lead) отправляется автоматически.

## 6. НЕ СПРАШИВАТЬ ПОВТОРНО УЖЕ ПРЕДОСТАВЛЕННУЮ ИНФОРМАЦИЮ

## 7. РЕАГИРОВАНИЕ НА ОТКАЗ ИЛИ НЕДОВОЛЬСТВО
Уточняй критерии или сразу предлагай альтернативы.

## 8. ЧЕКЛИСТ ПЕРЕД ОТПРАВКОЙ

## 9. ПРАВИЛО ПРИВЕТСТВИЯ И ПРЕДСТАВЛЕНИЯ (ВАЖНО)
- Если пользователь задаёт КОНКРЕТНЫЙ запрос (например: «найди билет в Дубай», «забронируй ресторан», «есть туры?»), НИКОГДА не отвечай вступлением — сразу переходи к выполнению задачи.
- Представление (кто ты и чем помогаешь) делай ТОЛЬКО если пользователь написал чистое приветствие (привет, здравствуйте, hi, hello) БЕЗ конкретного запроса.
""",
    'en': """\
# System Prompt for BIKA — IMTIAZ Personal Assistant

## 1. ROLE & CHARACTER
You are Bika, the personal travel and lifestyle concierge assistant for the IMTIAZ platform. You are a friendly, engaging, and reliable advisor. Always guide the user naturally towards their goal (booking, recommendation).
Always introduce yourself only as "Bika".

Your task: assist with flights, hotels, restaurants, events, and VIP tours.
Train booking is not available — inform politely if requested.
Primary language: {lang_name}.

IMPORTANT — TOUR & RESTAURANT FLOW (OWNER REQUIREMENT): for tours and restaurants you have NO tool that shows a list of packages/prices — this is intentional. Your job here is not to present options, but to have a natural conversation, collect the customer's interests (destination or cuisine, dates, party size, budget/preferences), get their phone number, and submit a lead to the team. Flights (search_flights/book_flight) still work as before, with options shown.

Date context:
  Today: {today}
  Tomorrow: {tomorrow}

Style rules:
- Do NOT ask questions as a formal questionnaire list.
- Keep answers CONCISE (typically 3-5 sentences).

## 2. DO NOT MIX NEW REQUESTS WITH OLD CONTEXT
## 3. INTENT DETECTION (Numbers vs Phone numbers)
## 4. TOURS & RESTAURANTS — GATHER INFO ONLY, NEVER SHOW OPTIONS (OWNER REQUIREMENT)
This section applies ONLY to tour/trip and restaurant/table requests. For flights, see section 4-B.
- Never show the customer a list of packages/prices as "option 1, option 2" and never ask them to "pick a number". Your job is to gather the request, not to be a catalog.
- Collect through conversation: (a) destination/country, or city + cuisine type for a restaurant, (b) dates or rough timing, (c) number of people/guests, (d) budget or preferences (nice to have, not required). No more than 2 questions per message.
- Once you have enough (at minimum destination/type + date or rough timing + party size), ask for the phone number: "Great! Our specialists will take it from here — could you share your phone number (+998XXXXXXXXX)?"
- Once the number is given, immediately call `submit_service_lead`: use `category='travel'` for tours, `category='restaurant'` for restaurants. Fill `customer_analysis` with a clear, detailed summary of everything gathered (destination/cuisine, dates, party size, budget/preferences) — this field is REQUIRED and must be thorough, since the team relies on it. Use `service_name` for a short title (e.g. "Dubai tour", "Table at an Italian restaurant").
- After the lead is submitted, reply: "Thanks! Your request has been received — one of our specialists will reach out to you shortly. What else can I help you with?" — do not promise a specific price or package (that's decided later with a manager), but always end with an open question inviting the conversation to continue.

## 4-B. FLIGHTS — PRESENTING OPTIONS WITH CLEAR CALL TO ACTION (unchanged)
- For flights, call search_flights (unlike tours/restaurants, the flight flow still shows options as before).
- IMPORTANT — "ORGANIZE A TRIP" RULE: If the user asks generically to organize a trip/vacation (e.g. "organize a trip", "plan me a vacation", "where should I go") this is handled under section 4 (tour lead) — do NOT call search_flights unprompted.
- Briefly summarize each flight option (route, price, date) and end with a clear call to action: "Which option works for you? Tell me the number...".
- If no suitable flight is found, submit a lead via `submit_flight_lead`.

## 5. LEAD SUBMISSION LOGIC
For flights: once the user picks an option, confirm it briefly, ask for the phone number if missing, then call `book_flight` or `submit_flight_lead`.
For tours and restaurants: the lead flow is defined in section 4 above — the customer never picks an option, they just share information and the lead is submitted automatically.
## 6. DO NOT RE-ASK GIVEN INFORMATION
## 7. HANDLING REJECTION OR DISSATISFACTION

## 8. PRE-RESPONSE CHECKLIST

## 9. GREETING AND INTRODUCTION RULE (IMPORTANT)
- If the user sends a SPECIFIC request (e.g. "find flights to Dubai", "book a restaurant", "any tours?"), NEVER respond with an intro — go straight to fulfilling the request.
- Only introduce yourself (who you are and what you can help with) when the user sends a pure greeting (hi, hello, hey) with NO specific request attached.
""",
}

_CONCISE_INSTRUCTIONS: dict[str, str] = {
    'uz': (
        "\n\nMUHIM: Faqat so'ralganiga javob ber. Ortig'ini yozma. Keraksiz kirish "
        "so'zlari, uzr, yoki uzoq izoh qo'shma. Agar tool natijasi berilsa, uni qayta "
        "uzun tushuntirma — faqat foydalanuvchiga kerakli qisqa javobni ber."
    ),
    'ru': (
        "\n\nВАЖНО: Отвечай только на заданный вопрос. Не добавляй лишнего текста, "
        "вступлений или извинений. Если есть результат инструмента, не переписывай "
        "большой JSON — дай краткий ответ, достаточный пользователю."
    ),
    'en': (
        "\n\nIMPORTANT: Answer only what was asked. Do not add extra explanations, "
        "long introductions, or apologies. If there are tool results, do not "
        "re-explain the full JSON — provide a short, clear answer the user needs."
    ),
}


def build_system_prompt(
    lang: str,
    price_limit: str,
    autonomy_level: str,
    session_summary: str | None = None,
    user_profile_summary: str | None = None,
) -> str:
    from datetime import timedelta
    from django.utils import timezone

    lang = normalize_language(lang)
    lang_name = LANGUAGE_NAMES[lang]
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)

    base = _SYSTEM_PROMPTS[lang].format(
        price_limit=price_limit,
        autonomy_level=autonomy_level,
        lang_name=lang_name,
        today=today.isoformat(),
        tomorrow=tomorrow.isoformat(),
    )
    if session_summary:
        base += f"\n\nSuhbat xotirasi (bajarilgan harakatlar va saqlangan obyektlar):\n{session_summary}\n"
    if user_profile_summary:
        base += f"\n\nDoimiy foydalanuvchi profili (uzoq muddatli xotira):\n{user_profile_summary}\n"

    base += _CONCISE_INSTRUCTIONS.get(lang, _CONCISE_INSTRUCTIONS['en'])
    return base


# ─── 4. Tasdiqlash (confirmation) matnlari ────────────────────────────────────
#
# DIQQAT: quyidagi confirm_* matnlari faqat "so'rov shakllantirildi" holatini
# tasvirlaydi. Haqiqiy tasdiqlash matn orqali emas, faqat frontend'dagi
# tugma (POST /api/ai/actions/{action_id}/confirm) orqali amalga oshadi —
# qarang: confirmation.py. Frontend shu action_id'ga bog'langan "Tasdiqlash /
# Bekor qilish" tugmalarini albatta chizishi kerak, aks holda foydalanuvchi
# bronni yakunlay olmaydi.

def build_confirmation_summary(
    tool_name: str,
    tool_input: dict,
    amount: Decimal | None,
    lang: str,
) -> str:
    lang = normalize_language(lang)
    amount_str = t('confirm_amount', lang, amount=f'{amount:,.0f}') if amount else ''

    if tool_name == 'book_flight':
        return t(
            'confirm_flight', lang,
            origin=tool_input.get('origin', '?'),
            destination=tool_input.get('destination', '?'),
            date=tool_input.get('departure_at', tool_input.get('departure_date', '?')),
            passengers=tool_input.get('passengers', 1),
            amount=amount_str,
        )
    if tool_name == 'book_restaurant':
        return t(
            'confirm_restaurant', lang,
            date=tool_input.get('date', '?'),
            time=tool_input.get('time', '?'),
            guests=tool_input.get('guests', '?'),
            amount=amount_str,
        )
    if tool_name == 'cancel_booking':
        return t(
            'confirm_cancel', lang,
            booking_id=tool_input.get('booking_id', '?'),
        )
    return t('confirm_generic', lang, tool_name=tool_name)


# ─── 5. Tarjima katalogi ──────────────────────────────────────────────────────

_MESSAGES: dict[str, dict[str, str]] = {

    # 5a) Umumiy / xato xabarlar ------------------------------------------------
    'ai_provider_error': {
        'uz': "Kechirasiz, texnik muammo. Qayta urinib ko'ring.",
        'ru': 'Извините, техническая проблема. Попробуйте ещё раз.',
        'en': 'Sorry, a technical issue occurred. Please try again.',
    },
    'ai_welcome': {
        'uz': (
            'Assalomu alaykum! 👋\n\n'
            'Men Bike — IMTIAZ platformasining shaxsiy sayohat va xizmat yordamchisiman.\n'
            'Men orqali:\n\n'
            '✈️ Aviachipta va mehmonxona bron qilishingiz\n'
            '🍽️ Restoranda stol band qilishingiz\n'
            '🗺️ Tur va ekskursiya tanlashingiz mumkin\n\n'
            'Sizga qanday yordam bera olaman?'
        ),
        'ru': (
            'Здравствуйте! 👋\n\n'
            'Я Bike — персональный помощник IMTIAZ по путешествиям и сервисам.\n'
            'С моей помощью вы можете:\n\n'
            '✈️ Забронировать авиабилет и отель\n'
            '🍽️ Забронировать столик в ресторане\n'
            '🗺️ Выбрать туры и экскурсии\n\n'
            'Чем я могу вам помочь?'
        ),
        'en': (
            'Hello! 👋\n\n'
            'I am Bike — IMTIAZ\'s personal travel and concierge assistant.\n'
            'Through me, you can:\n\n'
            '✈️ Book flights and hotels\n'
            '🍽️ Reserve a restaurant table\n'
            '🗺️ Choose tours and excursions\n\n'
            'How can I help you today?'
        ),
    },
    'quick_replies': {
        'uz': ["✈️ Chipta izlash", "🍽️ Stol band qilish", "❓ Boshqa savol"],
        'ru': ["✈️ Поиск билетов", "🍽️ Забронировать стол", "❓ Другой вопрос"],
        'en': ["✈️ Search flights", "🍽️ Book a table", "❓ Other question"],
    },
    'reply_format_error': {
        'uz': "Ma'lumot olindi, lekin javobni shakllantirishda muammo bo'ldi. Qayta urinib ko'ring.",
        'ru': 'Данные получены, но возникла проблема с формированием ответа. Попробуйте снова.',
        'en': 'Data received, but there was a problem formatting the reply. Please try again.',
    },
    'default_tool_reply': {
        'uz': "So'rovingiz bo'yicha ma'lumot topildi.",
        'ru': 'По вашему запросу найдена информация.',
        'en': 'Information found for your request.',
    },
    'service_unavailable': {
        'uz': 'Xizmat vaqtincha ishlamayapti.',
        'ru': 'Сервис временно недоступен.',
        'en': 'Service is temporarily unavailable.',
    },
    'action_done': {
        'uz': 'Amal bajarildi.',
        'ru': 'Действие выполнено.',
        'en': 'Action completed.',
    },
    'service_unknown': {
        'uz': 'aniqlanmadi',
        'ru': 'не определено',
        'en': 'unknown',
    },

    # 5b) Tasdiqlash (confirm_*) --------------------------------------------------
    'confirm_amount': {
        'uz': '\n💰 Taxminiy narx: {amount} UZS',
        'ru': '\n💰 Примерная стоимость: {amount} UZS',
        'en': '\n💰 Estimated price: {amount} UZS',
    },
    'confirm_flight': {
        'uz': (
            "✈️ Parvoz bron so'rovi:\n"
            "📍 {origin} → {destination}\n"
            "📅 {date}\n"
            "👥 {passengers} yo'lovchi{amount}\n\n"
            "Davom etish uchun pastdagi «✅ Tasdiqlash» tugmasini bosing."
        ),
        'ru': (
            '✈️ Запрос на бронирование рейса:\n'
            '📍 {origin} → {destination}\n'
            '📅 {date}\n'
            '👥 {passengers} пассажир(ов){amount}\n\n'
            'Нажмите «✅ Подтвердить» ниже, чтобы продолжить.'
        ),
        'en': (
            '✈️ Flight booking request:\n'
            '📍 {origin} → {destination}\n'
            '📅 {date}\n'
            '👥 {passengers} passenger(s){amount}\n\n'
            'Tap «✅ Confirm» below to continue.'
        ),
    },
    'confirm_restaurant': {
        'uz': (
            "🍽 Restoran bron so'rovi:\n"
            "📅 {date} {time}\n"
            "👥 {guests} kishi{amount}\n\n"
            "Davom etish uchun pastdagi «✅ Tasdiqlash» tugmasini bosing."
        ),
        'ru': (
            '🍽 Запрос на бронирование ресторана:\n'
            '📅 {date} {time}\n'
            '👥 {guests} гост(ей){amount}\n\n'
            'Нажмите «✅ Подтвердить» ниже, чтобы продолжить.'
        ),
        'en': (
            '🍽 Restaurant booking request:\n'
            '📅 {date} {time}\n'
            '👥 {guests} guest(s){amount}\n\n'
            'Tap «✅ Confirm» below to continue.'
        ),
    },
    'confirm_cancel': {
        'uz': (
            "❌ Bronni bekor qilish so'rovi:\n"
            "🆔 {booking_id}\n\n"
            "Davom etish uchun pastdagi «✅ Tasdiqlash» tugmasini bosing."
        ),
        'ru': (
            '❌ Запрос на отмену бронирования:\n'
            '🆔 {booking_id}\n\n'
            'Нажмите «✅ Подтвердить» ниже, чтобы продолжить.'
        ),
        'en': (
            '❌ Booking cancellation request:\n'
            '🆔 {booking_id}\n\n'
            'Tap «✅ Confirm» below to continue.'
        ),
    },
    'confirm_generic': {
        'uz': "Harakat: {tool_name}\n\nDavom etish uchun pastdagi «✅ Tasdiqlash» tugmasini bosing.",
        'ru': 'Действие: {tool_name}\n\nНажмите «✅ Подтвердить» ниже, чтобы продолжить.',
        'en': 'Action: {tool_name}\n\nTap «✅ Confirm» below to continue.',
    },
    'action_confirmed': {
        'uz': 'Harakat muvaffaqiyatli bajarildi.',
        'ru': 'Действие успешно выполнено.',
        'en': 'Action completed successfully.',
    },
    'action_rejected': {
        'uz': 'Harakat bekor qilindi.',
        'ru': 'Действие отменено.',
        'en': 'Action cancelled.',
    },
    'confirm_expired': {
        'uz': "Tasdiqlash muddati o'tib ketdi. Iltimos, qaytadan so'rang.",
        'ru': 'Срок подтверждения истёк. Пожалуйста, запросите снова.',
        'en': 'Confirmation expired. Please request again.',
    },

    # 5c) Bron natijalari (booking_*, *_booked) ------------------------------
    'booking_title_restaurant': {
        'uz': 'Restoran — {date} {time}, {guests} kishi',
        'ru': 'Ресторан — {date} {time}, {guests} гост(ей)',
        'en': 'Restaurant — {date} {time}, {guests} guest(s)',
    },
    'booking_title_flight': {
        'uz': 'Parvoz broni — {origin}→{destination}',
        'ru': 'Бронирование рейса — {origin}→{destination}',
        'en': 'Flight booking — {origin}→{destination}',
    },
    'restaurant_booked': {
        'uz': 'Restoran stoli muvaffaqiyatli band qilindi. Bron ID: {booking_id}',
        'ru': 'Стол в ресторане успешно забронирован. ID бронирования: {booking_id}',
        'en': 'Restaurant table successfully booked. Booking ID: {booking_id}',
    },
    'flight_booked': {
        'uz': 'Parvoz broni yaratildi. Bron ID: {booking_id}',
        'ru': 'Бронирование рейса создано. ID бронирования: {booking_id}',
        'en': 'Flight booking created. Booking ID: {booking_id}',
    },
    'booking_not_found': {
        'uz': 'Bron topilmadi.',
        'ru': 'Бронирование не найдено.',
        'en': 'Booking not found.',
    },
    'booking_already_status': {
        'uz': 'Bron allaqachon {status}.',
        'ru': 'Бронирование уже {status}.',
        'en': 'Booking is already {status}.',
    },
    'booking_cancelled': {
        'uz': 'Bron bekor qilindi.',
        'ru': 'Бронирование отменено.',
        'en': 'Booking cancelled.',
    },
    'bookings_empty': {
        'uz': "Sizda hozircha bronlar yo'q.",
        'ru': 'У вас пока нет бронирований.',
        'en': 'You have no bookings yet.',
    },
    'bookings_header': {
        'uz': '📋 {count} ta bron:',
        'ru': '📋 {count} бронирований:',
        'en': '📋 {count} booking(s):',
    },
    'booking_item': {
        'uz': '• {title} — {status} ({price:,.0f} UZS)',
        'ru': '• {title} — {status} ({price:,.0f} UZS)',
        'en': '• {title} — {status} ({price:,.0f} UZS)',
    },

    # 5d) Bookhara / tashqi xizmat xabarlari -----------------------------------
    'bookhara_no_response': {
        'uz': (
            "Aviachipta tizimi hozir javob bermadi — "
            "bron saqlandi, menejer qo'lda tekshiradi."
        ),
        'ru': (
            'Система авиабилетов сейчас не отвечает — '
            'бронирование сохранено, менеджер проверит вручную.'
        ),
        'en': (
            'The flight booking system is not responding — '
            'booking saved, a manager will verify manually.'
        ),
    },
    'bookhara_delay': {
        'uz': (
            "Aviachipta tizimi bilan bog'lanishda kechikish — "
            'bron qayd etildi, menejer tez orada chiptani tasdiqlaydi.'
        ),
        'ru': (
            'Задержка при связи с системой авиабилетов — '
            'бронирование записано, менеджер скоро подтвердит билет.'
        ),
        'en': (
            'Delay connecting to the flight system — '
            'booking recorded, a manager will confirm the ticket shortly.'
        ),
    },
    'bookhara_unavailable': {
        'uz': (
            "Aviachipta tizimi vaqtincha ishlamayapti — "
            'bron saqlandi, menejer siz bilan bog\'lanadi.'
        ),
        'ru': (
            'Система авиабилетов временно недоступна — '
            'бронирование сохранено, менеджер свяжется с вами.'
        ),
        'en': (
            'Flight system temporarily unavailable — '
            'booking saved, a manager will contact you.'
        ),
    },
    'flight_past_date': {
        'uz': (
            "Ko'rsatilgan sana ({date}) allaqachon o'tib ketgan. "
            "Iltimos, kelgusi sana kiriting — masalan ertaga ({tomorrow_hint}). "
            "Qaysi sanada jo'nashni xohlaysiz?"
        ),
        'ru': (
            'Указанная дата ({date}) уже прошла. '
            'Укажите будущую дату — например завтра ({tomorrow_hint}). '
            'На какую дату планируете вылет?'
        ),
        'en': (
            'The date ({date}) is in the past. '
            'Please provide a future date — e.g. tomorrow ({tomorrow_hint}). '
            'When would you like to depart?'
        ),
    },
    'flight_invalid_date': {
        'uz': "Sana noto'g'ri. Iltimos, YYYY-MM-DD formatida kiriting (masalan: 2026-08-14).",
        'ru': 'Неверная дата. Укажите в формате YYYY-MM-DD (например: 2026-08-14).',
        'en': 'Invalid date. Please use YYYY-MM-DD format (e.g. 2026-08-14).',
    },
    'flight_unavailable': {
        'uz': (
            "Hozir {origin} → {destination}{date_line} bo'yicha onlayn parvoz "
            "qidiruv vaqtincha mavjud emas — aviachiptalar tizimi bilan bog'lanishda "
            "biroz kechikish bor.\n\n"
            "Shu bilan birga sizga yordam bera olaman:\n"
            "• Boshqa sana yoki yaqin aeroport bo'yicha variant ko'rib chiqish\n"
            "• Sayohatingiz uchun restoran yoki tadbir bronlash\n"
            "• Menejerimiz orqali chipta — biz siz uchun qo'lda tekshirib, "
            "eng qulay variantni topamiz\n\n"
            "Bir ozdan keyin avtomatik qidiruvni yana sinab ko'ramiz. "
            "Hozir qaysi yo'nalish sizga qulayroq?"
        ),
        'ru': (
            'Сейчас онлайн-поиск рейсов {origin} → {destination}{date_line} '
            'временно недоступен — небольшая задержка при связи с системой авиабилетов.\n\n'
            'При этом я могу помочь:\n'
            '• Рассмотреть другую дату или ближайший аэропорт\n'
            '• Забронировать ресторан или мероприятие для поездки\n'
            '• Оформить билет через менеджера — мы вручную подберём лучший вариант\n\n'
            'Через некоторое время попробуем поиск снова. Какое направление вам удобнее?'
        ),
        'en': (
            'Online flight search for {origin} → {destination}{date_line} is temporarily '
            'unavailable — slight delay connecting to the ticketing system.\n\n'
            'I can still help you with:\n'
            '• Alternative dates or nearby airports\n'
            '• Restaurant or event bookings for your trip\n'
            '• Ticket via our manager — we\'ll find the best option manually\n\n'
            'We\'ll retry search shortly. Which direction works better for you?'
        ),
    },
    'train_unavailable': {
        'uz': (
            "Hozir {origin} → {destination} yo'nalishida poyezd qidiruv "
            "vaqtincha ishlamayapti — bu xizmat tez orada ulab qo'yiladi.\n\n"
            "Ayni paytda parvoz qidiruv, restoran bron yoki boshqa "
            "IMTIAZ xizmatlari bilan yordam bera olaman. Nima qidiramiz?"
        ),
        'ru': (
            'Поиск поездов по маршруту {origin} → {destination} временно недоступен — '
            'сервис скоро будет подключён.\n\n'
            'Сейчас могу помочь с авиабилетами, ресторанами или другими '
            'услугами IMTIAZ. Что ищем?'
        ),
        'en': (
            'Train search for {origin} → {destination} is temporarily unavailable — '
            'this service will be connected soon.\n\n'
            'I can help with flights, restaurants, or other IMTIAZ services. What shall we look for?'
        ),
    },
    'integration_generic': {
        'uz': (
            "So'rovingizni hozir to'liq bajara olmadim — xizmat vaqtincha band "
            "yoki bog'lanishda kechikish bor.\n\n"
            "Boshqa yo'nalish, sana yoki xizmat turini sinab ko'ramizmi? "
            "Yoki menejerimiz siz bilan bog'lanishini tashkil qilay?"
        ),
        'ru': (
            'Сейчас не удалось полностью выполнить запрос — сервис временно занят '
            'или есть задержка связи.\n\n'
            'Попробуем другой маршрут, дату или тип услуги? '
            'Или организовать звонок менеджера?'
        ),
        'en': (
            'I couldn\'t fully complete your request — the service is temporarily busy '
            'or there\'s a connection delay.\n\n'
            'Shall we try another route, date, or service type? '
            'Or arrange a callback from our manager?'
        ),
    },

    # 5e) Parvoz qidiruv natijalari (flight_*, flights_*) --------------------
    'flights_not_found': {
        'uz': (
            '{route} yo\'nalishida {date} sanasida to\'g\'ridan-to\'g\'ri parvoz topilmadi.\n\n'
            'Sinab ko\'rish mumkin:\n'
            '• Boshqa sana (masalan 1-2 kun keyin)\n'
            '• Yaqin aeroport (Dubai o\'rniga Sharjah SHJ)\n'
            '• Menejer orqali qo\'lda qidiruv — eng yaxshi variantni topamiz\n\n'
            'Qaysi variantni sinab ko\'ramiz?'
        ),
        'ru': (
            'Прямые рейсы {route} на {date} не найдены.\n\n'
            'Можно попробовать:\n'
            '• Другую дату (через 1–2 дня)\n'
            '• Ближайший аэропорт (вместо Dubai — Sharjah SHJ)\n'
            '• Ручной поиск через менеджера\n\n'
            'Какой вариант попробуем?'
        ),
        'en': (
            'No direct flights for {route} on {date}.\n\n'
            'We can try:\n'
            '• A different date (1–2 days later)\n'
            '• A nearby airport (Sharjah SHJ instead of Dubai)\n'
            '• Manual search via our manager\n\n'
            'Which option shall we try?'
        ),
    },
    'flights_header': {
        'uz': '✈️ {origin} → {destination} ({date}) — {count} ta variant:',
        'ru': '✈️ {origin} → {destination} ({date}) — {count} вариант(ов):',
        'en': '✈️ {origin} → {destination} ({date}) — {count} option(s):',
    },
    'flights_more': {
        'uz': '... va yana {count} ta variant.',
        'ru': '... и ещё {count} вариант(ов).',
        'en': '... and {count} more option(s).',
    },
    'flight_item': {
        'uz': '{i}. {airline} {number} | 🕐 {departure_time} → {arrival_time} | {price:,.0f} {currency}{baggage}',
        'ru': '{i}. {airline} {number} | 🕐 {departure_time} → {arrival_time} | {price:,.0f} {currency}{baggage}',
        'en': '{i}. {airline} {number} | 🕐 {departure_time} → {arrival_time} | {price:,.0f} {currency}{baggage}',
    },
    'flight_baggage_yes': {
        'uz': ' | 🧳 bagaj bor',
        'ru': ' | 🧳 багаж',
        'en': ' | 🧳 baggage',
    },
    'flights_book_hint': {
        'uz': '\n💡 Yoqqan variant raqamini yozing — bron qilishda yordam beraman.',
        'ru': '\n💡 Напишите номер варианта — помогу с бронированием.',
        'en': '\n💡 Tell me the option number — I\'ll help you book.',
    },
    'trains_not_found': {
        'uz': 'Poyezd reyslari topilmadi.',
        'ru': 'Поезда не найдены.',
        'en': 'No trains found.',
    },
    'trains_header': {
        'uz': '🚂 {count} ta poyezd varianti:',
        'ru': '🚂 {count} вариант(ов) поезда:',
        'en': '🚂 {count} train option(s):',
    },
    'train_item': {
        'uz': '{i}. Poyezd {number} — {price:,.0f} UZS',
        'ru': '{i}. Поезд {number} — {price:,.0f} UZS',
        'en': '{i}. Train {number} — {price:,.0f} UZS',
    },

    # 5f) Restoran / tadbir / tur paket natijalari ----------------------------
    'restaurants_not_found': {
        'uz': 'Restoran topilmadi.',
        'ru': 'Рестораны не найдены.',
        'en': 'No restaurants found.',
    },
    'restaurants_header': {
        'uz': '🍽 {count} ta restoran:',
        'ru': '🍽 {count} ресторан(ов):',
        'en': '🍽 {count} restaurant(s):',
    },
    'events_not_found': {
        'uz': 'Tadbir topilmadi.',
        'ru': 'Мероприятия не найдены.',
        'en': 'No events found.',
    },
    'events_header': {
        'uz': '🎭 {count} ta tadbir:',
        'ru': '🎭 {count} мероприятий:',
        'en': '🎭 {count} event(s):',
    },
    'tours_not_found': {
        'uz': 'Hozircha mos tur paket topilmadi.',
        'ru': 'Подходящие турпакеты пока не найдены.',
        'en': 'No matching tour packages at the moment.',
    },
    'tours_no_packages_intro': {
        'uz': 'Hozircha aniq paket topilmadi, lekin IMTIAZ hamkor tur kompaniyalari mavjud:',
        'ru': 'Конкретный пакет пока не найден, но у IMTIAZ есть партнёрские туркомпании:',
        'en': 'No exact package yet, but IMTIAZ partner tour companies are available:',
    },
    'tours_partners_header': {
        'uz': '\n🏢 Hamkor tur kompaniyalar:',
        'ru': '\n🏢 Партнёрские туркомпании:',
        'en': '\n🏢 Partner tour companies:',
    },
    'tour_partner_item': {
        'uz': '{i}. {name} — {package_count} ta faol paket',
        'ru': '{i}. {name} — {package_count} активных пакетов',
        'en': '{i}. {name} — {package_count} active package(s)',
    },
    'tour_partner_item_new': {
        'uz': '{i}. {name} — yangi hamkor (paketlar tez orada)',
        'ru': '{i}. {name} — новый партнёр (пакеты скоро)',
        'en': '{i}. {name} — new partner (packages coming soon)',
    },
    'tours_destinations_hint': {
        'uz': '\n🌍 Mavjud yo\'nalishlar: {destinations}',
        'ru': '\n🌍 Доступные направления: {destinations}',
        'en': '\n🌍 Available destinations: {destinations}',
    },
    'tours_empty_suggest': {
        'uz': (
            '\nQaysi yo\'nalish yoki kompaniya qiziq? '
            'Masalan: «Samarqand turlari» yoki «Dubai paketlari». '
            'Yoki telefon raqamingizni qoldiring — menejer qo\'ng\'iroq qiladi.'
        ),
        'ru': (
            '\nКакое направление или компания интересует? '
            'Например: «туры в Самарканд» или «пакеты в Dubai». '
            'Или оставьте телефон — менеджер перезвонит.'
        ),
        'en': (
            '\nWhich destination or company interests you? '
            'e.g. "Samarkand tours" or "Dubai packages". '
            'Or leave your phone — a manager will call back.'
        ),
    },
    'tours_more': {
        'uz': '... va yana {count} ta paket.',
        'ru': '... и ещё {count} пакет(ов).',
        'en': '... and {count} more package(s).',
    },
    'tour_date_flexible': {
        'uz': 'mavjud sanalar bo\'yicha',
        'ru': 'по доступным датам',
        'en': 'flexible dates',
    },
    'tours_interest_hint': {
        'uz': '\n💡 Qaysi tur qiziq? Telefon raqamingizni qoldirsangiz, menejer bog\'lanadi.',
        'ru': '\n💡 Какой тур интересен? Оставьте телефон — менеджер свяжется.',
        'en': '\n💡 Which tour interests you? Leave your phone and a manager will contact you.',
    },
    'tours_header': {
        'uz': '🌍 {count} ta tur paket:',
        'ru': '🌍 {count} турпакетов:',
        'en': '🌍 {count} tour package(s):',
    },
    'tour_item': {
        'uz': '{i}. {title}{organization} ({destination}) — {price:,.0f} {currency}, jo\'nash: {departure}',
        'ru': '{i}. {title}{organization} ({destination}) — {price:,.0f} {currency}, вылет: {departure}',
        'en': '{i}. {title}{organization} ({destination}) — {price:,.0f} {currency}, departure: {departure}',
    },
    'tour_lead_invalid_phone': {
        'uz': 'Telefon raqami noto\'g\'ri. Iltimos, +998XXXXXXXXX formatida yuboring.',
        'ru': 'Неверный номер телефона. Укажите в формате +998XXXXXXXXX.',
        'en': 'Invalid phone number. Please use +998XXXXXXXXX format.',
    },
    'tour_lead_package_not_found': {
        'uz': 'Tur paketi topilmadi yoki hozir faol emas.',
        'ru': 'Турпакет не найден или сейчас неактивен.',
        'en': 'Tour package not found or currently inactive.',
    },
    'restaurant_lead_branch_not_found': {
        'uz': "Ko'rsatilgan restoran topilmadi. Iltimos, restoranni qaytadan qidiring va ro'yxatdan tanlang.",
        'ru': 'Указанный ресторан не найден. Пожалуйста, выполните поиск заново и выберите из списка.',
        'en': 'The selected restaurant was not found. Please search again and choose from the list.',
    },
    'tour_lead_invalid_date': {
        'uz': 'Sana noto\'g\'ri. YYYY-MM-DD formatida yuboring.',
        'ru': 'Неверная дата. Используйте формат YYYY-MM-DD.',
        'en': 'Invalid date. Use YYYY-MM-DD format.',
    },
    'tour_lead_submitted': {
        'uz': (
            '✅ «{title}» bo\'yicha so\'rovingiz qabul qilindi. '
            'Kerakli mutaxassislarimiz tez orada siz bilan bog\'lanishadi — bu uzoq vaqt olmaydi.'
        ),
        'ru': (
            '✅ Ваш запрос по «{title}» принят. '
            'Наши специалисты свяжутся с вами в ближайшее время — это не займёт много времени.'
        ),
        'en': (
            '✅ Your request for «{title}» has been received. '
            'Our specialists will contact you shortly — this won\'t take long.'
        ),
    },
    'nearby_not_found': {
        'uz': 'Yaqin atrofda xizmat topilmadi.',
        'ru': 'Поблизости ничего не найдено.',
        'en': 'No nearby places found.',
    },
    'nearby_header': {
        'uz': '📍 Yaqin atrofda {count} ta joy:',
        'ru': '📍 {count} мест(а) поблизости:',
        'en': '📍 {count} nearby place(s):',
    },
    'nearby_item': {
        'uz': '• {name} — {distance} km',
        'ru': '• {name} — {distance} km',
        'en': '• {name} — {distance} km',
    },
    'preferences_summary': {
        'uz': 'Sizda {total} ta bron, jami {spent:,.0f} UZS. Afzal xizmat: {preferred}.',
        'ru': 'У вас {total} бронирований, всего {spent:,.0f} UZS. Предпочитаемый сервис: {preferred}.',
        'en': 'You have {total} bookings, total {spent:,.0f} UZS. Preferred service: {preferred}.',
    },
    'origin_default': {
        'uz': "jo'nash shahri",
        'ru': 'город вылета',
        'en': 'departure city',
    },
    'destination_default': {
        'uz': 'manzil',
        'ru': 'назначение',
        'en': 'destination',
    },
    'origin_train_default': {
        'uz': "jo'nash punkti",
        'ru': 'станция отправления',
        'en': 'departure station',
    },
}


# ─── 5g) Status va xizmat nomlari lug'atlari ──────────────────────────────────

BOOKING_STATUS_LABELS: dict[str, dict[str, str]] = {
    'uz': {
        'pending': 'kutilmoqda',
        'confirmed': 'tasdiqlandi',
        'cancelled': 'bekor qilindi',
        'completed': 'yakunlandi',
    },
    'ru': {
        'pending': 'ожидает',
        'confirmed': 'подтверждено',
        'cancelled': 'отменено',
        'completed': 'завершено',
    },
    'en': {
        'pending': 'pending',
        'confirmed': 'confirmed',
        'cancelled': 'cancelled',
        'completed': 'completed',
    },
}

SERVICE_TYPE_LABELS: dict[str, dict[str, str]] = {
    'uz': {
        'flight': 'parvoz',
        'restaurant': 'restoran',
        'event': 'tadbir',
        'train': 'poyezd',
        'tour': 'tur paket',
    },
    'ru': {
        'flight': 'авиабилет',
        'restaurant': 'ресторан',
        'event': 'мероприятие',
        'train': 'поезд',
        'tour': 'турпакет',
    },
    'en': {
        'flight': 'flight',
        'restaurant': 'restaurant',
        'event': 'event',
        'train': 'train',
        'tour': 'tour package',
    },
}