# Android text-to-speech with a British MALE voice (pyjnius).
# ------------------------------------------------------------
# plyer's own TTS hardcodes Locale.US, so Jarvis would sound American.
# This module talks to Android's TextToSpeech directly and asks for
# Locale.UK, then picks a male UK voice if the engine offers one.
#
# v2.1 fix — the old code only matched voice names containing "male" or
# "daniel", which almost never matches: Google's TTS voices are named
# like "en-gb-x-gba-local" / "en-gb-x-gbb-network" (no gender in the
# name), so the app fell back to the first UK voice — which is female
# on most phones. The new picker scores every UK voice on several
# signals and logs the full voice list, so a wrong pick can be
# diagnosed from logcat (tag JarvisTTS).
#
# Voice-name signals (best effort — no Android API exposes gender):
#   * the word "male" anywhere in the name (Samsung, some engines)
#   * a common male first name as a whole token (Google/Samsung
#     named voices, e.g. "Daniel", "George")
#   * Google TTS on-device naming: en-gb-x-gbb-* / en-gb-x-gbd-* are
#     the male variants, en-gb-x-gba-* / en-gb-x-gbc-* the female ones
#     (matches Google Cloud TTS en-GB A=female, B=male, C=female,
#     D=male). This is a heuristic, not a guarantee.
# If no male voice can be identified at all, the picker keeps a UK
# voice but drops the pitch to 0.8 so it sounds deeper/more masculine.
#
# It is a phone text-to-speech voice, NOT the actor's real voice from
# the films — that voice is not available anywhere.
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


# Common male first names used by TTS engines for named voices.
_MALE_NAMES = frozenset("""
daniel george oliver arthur harry james charlie alfie freddie leo jack
thomas william henry alexander benjamin samuel edward nicholas alex adam
nathan liam noah ethan lucas owen luke ryan joshua matthew christopher
david michael robert john mark paul steve simon anthony kevin brian alan
martin stephen philip gordon nigel clive trevor barry keith terry dennis
guy marc eli aaron connor andrew richard peter chris tony neil ian colin
graham dave craig stuart ray wayne frederick victor albert reginald
norman ernest sidney leslie cecil percy horace wilfred oliver felix hugo
rory callum finlay archie tobias sebastian maximilian zachary isaac
elijah gabriel jonathan timothy patrick jonathan dominic marcus felix
""".split())


def _tokens(name):
    """Split a voice name into lowercase alphanumeric tokens."""
    import re
    return re.split(r"[^a-z0-9]+", name.lower())


def _score_voice_name(name):
    """Score how likely a TTS voice name is a male en-GB voice.

    Pure function (no Android calls) so it can be unit-tested.
    Returns an integer; >= 90 means a male voice was identified.
    """
    low = name.lower()
    toks = set(_tokens(name))
    score = 0
    # NOTE: token-based on purpose — "female" contains "male" as a
    # substring, so a plain substring check would score female voices
    # as male.
    if "male" in toks:
        score += 100
    if "female" in toks or "woman" in toks:
        score -= 100
    if toks & _MALE_NAMES:
        score += 100
    # Google on-device TTS naming: gbb/gbd = male, gba/gbc = female.
    if "gbb" in toks or "gbd" in toks:
        score += 90
    if "gba" in toks or "gbc" in toks:
        score -= 60
    if "local" in toks:
        score += 5  # works offline; prefer when scores tie
    return score


def _log(msg):
    try:
        Log = autoclass("android.util.Log")
        Log.i("JarvisTTS", str(msg))
    except Exception:
        pass


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
        self._voice_name = None
        self._male_found = False

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
            self._pick_male_voice()
        except Exception:
            pass
        self._ready = True
        if self._pending:
            text, self._pending = self._pending, None
            self.speak(text)

    def _pick_male_voice(self):
        """Pick the best-scoring male UK voice; fall back to a deeper
        pitch on a plain UK voice when no male voice can be found."""
        pitch = 0.95
        try:
            voices = self._tts.getVoices()
            if voices is None:
                self._tts.setPitch(0.8)
                return
            best = None
            best_score = -10 ** 9
            first_uk = None
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
                _log("voice: %s" % name)
                if first_uk is None:
                    first_uk = v
                score = _score_voice_name(name)
                if score > best_score:
                    best_score = score
                    best = v
            if best is not None and best_score >= 90:
                self._tts.setVoice(best)
                self._voice_name = str(best.getName())
                self._male_found = True
                _log("picked male voice: %s (score %d)"
                     % (self._voice_name, best_score))
            elif first_uk is not None:
                # No male voice identifiable: keep a UK voice but drop
                # the pitch so it sounds deeper / more masculine.
                self._tts.setVoice(first_uk)
                self._voice_name = str(first_uk.getName())
                self._male_found = False
                pitch = 0.8
                _log("no male voice found, using %s at pitch 0.8"
                     % self._voice_name)
        except Exception:
            pass
        try:
            self._tts.setSpeechRate(0.95)
            self._tts.setPitch(pitch)
        except Exception:
            pass

    def describe_voice(self):
        """Short human-readable description of the voice in use."""
        if not self._ready:
            return "Voice: starting…"
        if self._voice_name:
            kind = "male" if self._male_found else "UK (no male voice found)"
            return "Voice: %s (%s)" % (self._voice_name, kind)
        return "Voice: default UK voice"

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


def describe_voice():
    return _ENGINE.describe_voice()
