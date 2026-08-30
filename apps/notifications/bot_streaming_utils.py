"""
Telegram bot streaming chat utilities.
Mira bot kabi: emoji, typing indicator, markdown formatting.
"""

import time
import logging

logger = logging.getLogger(__name__)


class StreamingIndicators:
    """Streaming chat uchun emoji va holat indikatorlari"""

    THINKING = "🧠"
    PROCESSING = "⚙️"
    DONE = "✅"
    ERROR = "❌"
    CHAT = "💬"
    ARROW = "→"
    SPARK = "✨"
    CLOCK = "⏱️"

    # Streaming animatsiyasi
    DOTS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    @staticmethod
    def thinking_animation(step: int = 0) -> str:
        """O'ylanyapti animatsiyasi"""
        dot = StreamingIndicators.DOTS[step % len(StreamingIndicators.DOTS)]
        return f"{StreamingIndicators.THINKING} O'ylanyapman {dot}"

    @staticmethod
    def processing_indicator() -> str:
        """Jarayon ketayotganini ko'rsatish"""
        return f"{StreamingIndicators.PROCESSING} Jarayon ketayotgan..."

    @staticmethod
    def done_indicator() -> str:
        """Tamomlandi"""
        return f"{StreamingIndicators.DONE} Tamomlandi"


class MarkdownFormatter:
    """Telegram Markdown V2 formatting"""

    @staticmethod
    def bold(text: str) -> str:
        """**bold**"""
        return f"*{text}*"

    @staticmethod
    def code(text: str) -> str:
        """`code`"""
        return f"`{text}`"

    @staticmethod
    def code_block(text: str, lang: str = '') -> str:
        """```code block```"""
        return f"```{lang}\n{text}\n```"

    @staticmethod
    def italic(text: str) -> str:
        """_italic_"""
        return f"_{text}_"

    @staticmethod
    def link(text: str, url: str) -> str:
        """[text](url)"""
        return f"[{text}]({url})"

    @staticmethod
    def quote(text: str) -> str:
        """> quote"""
        return f">{text}"

    @staticmethod
    def list_item(text: str, indent: int = 0) -> str:
        """- list item"""
        prefix = "  " * indent
        return f"{prefix}• {text}"

    @staticmethod
    def numbered_item(num: int, text: str, indent: int = 0) -> str:
        """1. numbered"""
        prefix = "  " * indent
        return f"{prefix}{num}. {text}"

    @staticmethod
    def format_response_with_emoji(text: str, emoji: str = "💬") -> str:
        """Javobni emoji bilan formatlash"""
        lines = text.split('\n')
        if not lines:
            return f"{emoji} {text}"

        # Birinchi satr emoji bilan
        formatted = f"{emoji} {lines[0]}"
        # Qolgan satrlar indentatsiya bilan
        for line in lines[1:]:
            if line.strip():
                formatted += f"\n   {line}"
            else:
                formatted += "\n"
        return formatted


class TypingIndicator:
    """Telegram typing indicator - har 4-5 sekundda yuboriladi"""

    def __init__(self, bot, chat_id: int):
        self.bot = bot
        self.chat_id = chat_id
        self._last_sent = 0
        self._interval = 4.0  # 4 sekund

    def send_if_needed(self) -> bool:
        """Kerak bo'lsa typing harakati yuborish"""
        now = time.monotonic()
        if now - self._last_sent >= self._interval:
            try:
                self.bot.send_chat_action(self.chat_id, 'typing')
                self._last_sent = now
                return True
            except Exception as e:
                logger.debug(f"Typing action xatosi: {e}")
                return False
        return False


class StreamingMessage:
    """Real-time streaming message buffer va updater"""

    def __init__(self, bot, chat_id: int, initial_text: str = ""):
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = None
        self.full_text = initial_text
        self._last_update = 0
        self._update_interval = 0.5  # 500ms - yangilash intervali
        self._char_buffer = ""

    def send_initial_message(self) -> int:
        """Birinchi xabarni yuborish"""
        text = f"{StreamingIndicators.THINKING} O'ylanyapman..."
        msg = self.bot.send_message(self.chat_id, text)
        self.message_id = msg.message_id
        return msg.message_id

    def buffer_chunk(self, chunk: str) -> bool:
        """Chunk-ni bufferga qo'shish, kerak bo'lsa update qilish"""
        self.full_text += chunk
        self._char_buffer += chunk

        # 100 belgidan ko'p yoki vaqt tugaganda update qilish
        now = time.monotonic()
        if len(self._char_buffer) >= 100 or (now - self._last_update >= self._update_interval):
            self.update_message()
            return True
        return False

    def update_message(self) -> None:
        """Telegram xabarini yangilash"""
        if not self.message_id:
            return

        try:
            display_text = self.full_text or f"{StreamingIndicators.THINKING} O'ylanyapman..."
            self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message_id,
                text=display_text,
                parse_mode='HTML'
            )
            self._char_buffer = ""
            self._last_update = time.monotonic()
        except Exception as e:
            logger.debug(f"Message update xatosi: {e}")

    def finalize(self) -> None:
        """Oxirgi update va formatlash"""
        if self._char_buffer:  # Qolgan charlarni yuborish
            self.update_message()

        # Emoji qo'shish
        if self.full_text.strip():
            formatted = f"{StreamingIndicators.CHAT} {self.full_text}"
            try:
                self.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    text=formatted,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.debug(f"Finalize xatosi: {e}")


class ErrorHandler:
    """Xatoliklarni Mira bot kabi formatlash"""

    @staticmethod
    def format_error(error_msg: str, lang: str = 'uz') -> str:
        """Xatolikni user-friendly qilish"""
        if lang == 'ru':
            return f"{StreamingIndicators.ERROR} *Ошибка:* {error_msg}\n\n_Повторите попытку позже или обратитесь в поддержку._"
        elif lang == 'en':
            return f"{StreamingIndicators.ERROR} *Error:* {error_msg}\n\n_Please try again later or contact support._"
        else:  # uz
            return f"{StreamingIndicators.ERROR} *Xatolik:* {error_msg}\n\n_Iltimos, bir ozdan so'ng qayta urinib ko'ring yoki qo'llab-quvvatlag'a murojaat qiling._"

    @staticmethod
    def format_timeout(lang: str = 'uz') -> str:
        """Timeout xatosi"""
        if lang == 'ru':
            return f"{StreamingIndicators.CLOCK} Запрос занял слишком много времени. Пожалуйста, попробуйте еще раз."
        elif lang == 'en':
            return f"{StreamingIndicators.CLOCK} The request took too long. Please try again."
        else:  # uz
            return f"{StreamingIndicators.CLOCK} So'rov juda ko'p vaqt oldi. Iltimos, qayta urinib ko'ring."


class TypewriterEffect:
    """
    Character-by-character text reveal (sekin-sekin ochlash).
    Text matn ko'rinadi bir-bir belgisi bilan, Mira bot kabi.
    """

    def __init__(self, speed_ms: int = 30, batch_size: int = 1):
        """
        speed_ms: Har character orasidagi delay (millisekund)
        batch_size: Qancha character-dan keyin buffer qilish
        """
        self.speed_ms = speed_ms
        self.batch_size = batch_size

    def get_reveal_sequence(self, text: str):
        """
        Text-ni character-by-character reveal qiling.
        Generator - har bir step uchun partly revealed text qaytaradi.
        """
        revealed = ""
        for char in text:
            revealed += char
            yield revealed
            time.sleep(self.speed_ms / 1000.0)


class RateLimitSafeTypewriter:
    """
    Telegram rate limit-safe typewriter effect.
    Character-by-character animation, lekin:
    - Smart batching (5 char per update)
    - Min 150ms interval
    - No 429 errors!

    Qo'llash:
        typewriter = RateLimitSafeTypewriter(bot, chat_id, msg_id)
        for char in "Hello":
            typewriter.add_char(char)
        typewriter.finalize()
    """

    def __init__(
            self,
            bot,
            chat_id: int,
            msg_id: int,
            batch_size: int = 5,
            min_interval_sec: float = 0.15,
    ):
        """
        bot: Telegram bot instance
        chat_id: Chat ID
        msg_id: Message ID (edit-lash uchun)
        batch_size: Character-lar soni (batch-da)
        min_interval_sec: Min update interval (sekund)
        """
        self.bot = bot
        self.chat_id = chat_id
        self.msg_id = msg_id

        self.batch_size = batch_size
        self.min_interval = min_interval_sec

        self.revealed = ""
        self.last_update = 0.0
        self.char_count = 0

        logger.debug(
            f"Typewriter initialized: batch_size={batch_size}, "
            f"min_interval={min_interval_sec}s"
        )

    def add_char(self, char: str) -> bool:
        """
        Bir character qo'shish.
        Agar batch/interval complete bo'lsa, message update qiladi.

        Returns: True agar update yuborsa, False aks holda
        """
        self.revealed += char
        self.char_count += 1

        # Batch check - qancha character yig'ildi?
        is_batch_complete = self.char_count % self.batch_size == 0

        # Rate limit check - etarli vaqt o'tdi?
        now = time.monotonic()
        time_elapsed = now - self.last_update
        time_ok = time_elapsed >= self.min_interval

        # Agar batch + time OK → update qilish
        if is_batch_complete and time_ok:
            return self._update_message_safe()

        return False

    def _update_message_safe(self) -> bool:
        """
        Telegram message-ni safe qilib update qilish.
        Agar rate limit hit bo'lsa, skip qilish (retry kerak emas).
        """
        try:
            self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.msg_id,
                text=self.revealed,
                parse_mode='HTML'
            )
            self.last_update = time.monotonic()
            logger.debug(
                f"Message updated: {len(self.revealed)} chars, "
                f"batch_count={self.char_count // self.batch_size}"
            )
            return True

        except Exception as e:
            error_str = str(e)

            # Rate limit hit - log va skip
            if "429" in error_str or "Too Many Requests" in error_str:
                logger.warning(
                    f"Telegram rate limit hit! "
                    f"Skipping update at {len(self.revealed)} chars"
                )
                # Interval-ni increase qilish (backoff)
                self.min_interval *= 1.5
                return False

            # Boshqa error - log qilish
            logger.error(f"Typewriter update error: {e}")
            return False

    def finalize(self) -> bool:
        """
        Oxirgi qismni update qilish (force).
        Qo'llab-quvvatlash uchun chaqiring loop tugagach.
        """
        return self._update_message_safe()

    def get_stats(self) -> dict:
        """Debug uchun - typewriter stats"""
        return {
            'total_chars': len(self.revealed),
            'char_count': self.char_count,
            'batches_sent': self.char_count // self.batch_size,
            'min_interval': self.min_interval,
        }


class StreamingMessageV2:
    """
    Enhanced streaming message - now with optional typewriter effect.

    Modes:
    1. Chunk streaming (default) - Mira bot-like fast
    2. Typewriter effect - Sekin-sekin ochlash
    3. Hybrid - Chunks + typewriter
    """

    CHUNK_MODE = 'chunk'
    TYPEWRITER_MODE = 'typewriter'
    HYBRID_MODE = 'hybrid'

    def __init__(
            self,
            bot,
            chat_id: int,
            mode: str = CHUNK_MODE,
            typewriter_batch_size: int = 5,
            typewriter_interval: float = 0.15,
    ):
        """
        bot: Telegram bot
        chat_id: Chat ID
        mode: 'chunk' | 'typewriter' | 'hybrid'
        """
        self.bot = bot
        self.chat_id = chat_id
        self.mode = mode
        self.message_id = None
        self.full_text = ""

        # Typewriter settings
        self.typewriter_batch_size = typewriter_batch_size
        self.typewriter_interval = typewriter_interval
        self.typewriter = None

        self._last_update = 0
        self._update_interval = 0.5
        self._char_buffer = ""

    def send_initial_message(self) -> int:
        """Birinchi xabarni yuborish"""
        text = f"{StreamingIndicators.THINKING} O'ylanyapman..."
        msg = self.bot.send_message(self.chat_id, text)
        self.message_id = msg.message_id

        # Typewriter mode - typewriter manager yaratish
        if self.mode in (self.TYPEWRITER_MODE, self.HYBRID_MODE):
            self.typewriter = RateLimitSafeTypewriter(
                self.bot,
                self.chat_id,
                self.message_id,
                batch_size=self.typewriter_batch_size,
                min_interval_sec=self.typewriter_interval,
            )

        return msg.message_id

    def buffer_chunk(self, chunk: str) -> bool:
        """Chunk-ni bufferga qo'shish"""
        self.full_text += chunk

        if self.mode == self.CHUNK_MODE:
            # Chunk mode - traditional streaming
            self._char_buffer += chunk
            now = time.monotonic()
            if len(self._char_buffer) >= 100 or (now - self._last_update >= self._update_interval):
                self.update_message()
                return True

        elif self.mode == self.TYPEWRITER_MODE:
            # Typewriter mode - character-by-character
            if self.typewriter:
                for char in chunk:
                    self.typewriter.add_char(char)
            return True

        elif self.mode == self.HYBRID_MODE:
            # Hybrid - chunks first, then typewriter
            # Birinchi 500ms -> chunks, keyin typewriter
            now = time.monotonic()
            if len(self._char_buffer) == 0:
                # Start time
                self._hybrid_start = now

            elapsed = now - self._hybrid_start if hasattr(self, '_hybrid_start') else 0

            if elapsed < 0.5:
                # Still in chunk mode
                self._char_buffer += chunk
                if len(self._char_buffer) >= 100:
                    self.update_message()
            else:
                # Switch to typewriter mode
                if self.typewriter is None:
                    self.typewriter = RateLimitSafeTypewriter(
                        self.bot, self.chat_id, self.message_id,
                        batch_size=self.typewriter_batch_size,
                    )
                for char in chunk:
                    self.typewriter.add_char(char)
            return True

        return False

    def update_message(self) -> None:
        """Telegram xabarini yangilash"""
        if not self.message_id:
            return

        try:
            display_text = self.full_text or f"{StreamingIndicators.THINKING} O'ylanyapman..."
            self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message_id,
                text=display_text,
                parse_mode='HTML'
            )
            self._char_buffer = ""
            self._last_update = time.monotonic()
        except Exception as e:
            if "429" not in str(e):
                logger.debug(f"Message update error: {e}")

    def finalize(self) -> None:
        """Oxirgi update va formatlash"""
        if self._char_buffer:
            self.update_message()

        # Typewriter mode-da finalize qilish
        if self.typewriter:
            self.typewriter.finalize()

        # Emoji qo'shish
        if self.full_text.strip():
            formatted = f"{StreamingIndicators.CHAT} {self.full_text}"
            try:
                self.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    text=formatted,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.debug(f"Finalize error: {e}")


# Quick emoji mappings
EMOJIS = {
    'thinking': '🧠',
    'done': '✅',
    'error': '❌',
    'chat': '💬',
    'bot': '🤖',
    'user': '👤',
    'loading': '⏳',
    'success': '✨',
    'warning': '⚠️',
    'info': 'ℹ️',
    'flight': '✈️',
    'restaurant': '🍽️',
    'car': '🚗',
    'medical': '⚕️',
    'money': '💰',
    'calendar': '📅',
    'clock': '🕐',
    'pin': '📍',
    'phone': '☎️',
}