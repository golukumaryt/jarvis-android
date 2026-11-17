# Android text-to-speech with a British voice (pyjnius).
# ------------------------------------------------------------
# plyer's own TTS hardcodes Locale.US, so Jarvis would sound American.
# This module talks to Android's TextToSpeech directly and asks for
# Locale.UK, then tries to pick a male UK voice if the engine offers one.
# It is a best effort: the exact voice depends on the phone's TTS engine
# (usually Google's). It is NOT the actor's real voice from the films —
# that voice is not available anywhere.
#
# On any non-Android platform this module simply reports unavailable and
# the app falls back to plyer TTS. It must always import cleanly.

try:
    from jnius import autoclass, PythonJavaClass, java_method
    from android.runnable import run_on_ui_thread
    _HAVE_JNIUS = True
except Exception:
    _HAVE_JNIUS = False

    def run_on_ui_thread(func):
        return func


def available():
    return _HAVE_JNIUS


if _HAVE_JNIUS:
    class _InitListener(PythonJavaClass):
        __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]

        def __init__(self, callback):
            super().__init__()
            self._callback = callback

        @java_method("(I)V")
        def onInit(self, status):
            try:
                self._callback(status)
            except Exception:
                pass
else:
    class _InitListener:
        """Stub so the module imports cleanly on non-Android platforms."""

        def __init__(self, callback):
            self._callback = callback


class _AndroidTTS:
    def __init__(self):
        self._tts = None
        self._ready = False
        self._pending = None

    def _ensure(self):
        if self._tts is not None:
            return
        TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        self._tts = TextToSpeech(activity, _InitListener(self._on_init))

    def _on_init(self, status):
        # status 0 == TextToSpeech.SUCCESS
        if status != 0:
            return
        try:
            Locale = autoclass("java.util.Locale")
            self._tts.setLanguage(Locale.UK)
            self._tts.setSpeechRate(0.95)
            self._tts.setPitch(0.95)
            self._pick_male_voice()
        except Exception:
            pass
        self._ready = True
        if self._pending:
            text, self._pending = self._pending, None
            self.speak(text)

    def _pick_male_voice(self):
        """Prefer a UK male voice if the TTS engine offers one."""
        try:
            voices = self._tts.getVoices()
            if voices is None:
                return
            uk_voice = None
            it = voices.iterator()
            while it.hasNext():
                v = it.next()
                try:
                    loc = v.getLocale()
                    name = str(v.getName())
                except Exception:
                    continue
                if loc is None:
                    continue
                if str(loc.getLanguage()) != "en":
                    continue
                if "GB" not in str(loc.getCountry()):
                    continue
                low = name.lower()
                if "male" in low or "daniel" in low:
                    self._tts.setVoice(v)
                    return
                if uk_voice is None:
                    uk_voice = v
            if uk_voice is not None:
                self._tts.setVoice(uk_voice)
        except Exception:
            pass

    @run_on_ui_thread
    def _speak_on_ui(self, text):
        TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
        self._tts.speak(text, TextToSpeech.QUEUE_FLUSH, None)

    def speak(self, text):
        try:
            self._ensure()
        except Exception:
            return False
        if not self._ready:
            self._pending = text
            return True
        try:
            self._speak_on_ui(text)
        except Exception:
            return False
        return True


_ENGINE = _AndroidTTS()


def speak(text):
    return _ENGINE.speak(text)
