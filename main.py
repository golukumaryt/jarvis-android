# J.A.R.V.I.S. — Android voice assistant (Kivy) — v2.1, 2026-11-18
# ---------------------------------------------------------------------------
# Talk by voice, it talks back, answers questions with the Google Gemini
# API and runs tasks on the phone.
#
# v2.1 fixes three user-reported problems:
#   1. GIRL VOICE — android_tts now scores every UK voice (male names,
#      "male" token, Google gbb/gbd male variants) and drops the pitch
#      to 0.8 when no male voice can be found.
#   2. MICROPHONE DEAD — v2.0 never requested the RECORD_AUDIO runtime
#      permission (declared in the manifest only), so the mic silently
#      did nothing. The app now requests all runtime permissions at
#      startup and before listening. Voice input now uses android_stt
#      (SpeechRecognizer via pyjnius) with real error reporting,
#      falling back to plyer STT only if it is unavailable.
#   3. ALWAYS-ON "JARVIS" — a foreground service (service/main.py)
#      listens continuously for "Jarvis", even with the app closed or
#      the phone locked, and wakes the app with a full-screen-intent
#      notification. "Open phone" shows the system's face/PIN unlock
#      screen (no app can unlock the phone by itself).
#
# v2.0 rewrite: the v1.x build kept failing in the cloud because the
# `requests` library pulls in charset-normalizer, whose newest release
# ships a compiled wheel the Android toolchain rejects. This version
# drops `requests` entirely — ALL network calls use Python's built-in
# urllib (standard library, nothing to install), so the build only needs
# python3, kivy, plyer, android and pyjnius. Same features, same voice,
# same commands — only the networking changed.
#
# Brain: Google Gemini (gemini-2.0-flash, fallback gemini-1.5-flash).
# The API key is entered once inside the app and stored only on the phone
# (app private storage). No key is ever baked into this source.
#
# Voice in:  android_stt (SpeechRecognizer via pyjnius), plyer STT fallback.
# Voice out: custom Android TTS via pyjnius (Locale.UK, male voice
#            picked by scoring; pitch 0.8 fallback) so Jarvis sounds
#            British and calm, movie-style. Falls back to plyer TTS on
#            any other platform. NOTE: the voice is a system
#            text-to-speech voice, NOT the actor's real voice from the
#            films.

import json
import math
import os
import random
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

try:
    from plyer import stt as plyer_stt
    from plyer import tts as plyer_tts
    HAVE_PLYER = True
except Exception:
    HAVE_PLYER = False
    plyer_stt = None
    plyer_tts = None

try:
    import android_tts
    HAVE_ANDROID_TTS = android_tts.available()
except Exception:
    HAVE_ANDROID_TTS = False
    android_tts = None

try:
    import android_stt
    HAVE_ANDROID_STT = android_stt.available()
except Exception:
    HAVE_ANDROID_STT = False
    android_stt = None

try:
    import android_phone
    HAVE_ANDROID_PHONE = android_phone.available()
except Exception:
    HAVE_ANDROID_PHONE = False
    android_phone = None

# ---------------------------------------------------------------- constants

APP_TITLE = "J.A.R.V.I.S."
APP_VERSION = "2.1"
BG_COLOR = (0.016, 0.027, 0.05, 1)
CYAN = (0.21, 0.88, 1.0, 1)
CYAN_DIM = (0.13, 0.55, 0.68, 1)
TEXT_COLOR = (0.88, 0.93, 0.96, 1)
MUTED_COLOR = (0.62, 0.70, 0.78, 1)
USER_AGENT = "JARVIS-Android/2.1"

SYSTEM_PROMPT = (
    "You are J.A.R.V.I.S., a calm, precise, courteous British AI assistant in the "
    "style of a movie AI butler. Address the user as 'sir'. Give short, accurate "
    "answers — no rambling, no filler. If you do not know something, say so plainly "
    "instead of guessing. Keep every reply under about 80 words unless the user "
    "asks for detail."
)

GEMINI_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash"]

COMMANDS_TEXT = (
    "Say or type any of these — or just ask me anything:\n\n"
    "• 'Open YouTube' / 'Open Google' / 'Open YouTube Studio'\n"
    "• 'What time is it?' / 'What is the date today?'\n"
    "• 'Weather' — current conditions where you are\n"
    "• 'Search for ...' — web search, opens results\n"
    "• 'Note ...' — save a note ('Show notes' to read them)\n"
    "• 'Timer 5 minutes' — spoken alert when it rings\n"
    "• 'Call Mum' — call a contact by name (opens the dialler if the\n"
    "  phone-call permission is off)\n"
    "• 'Text Mum I'll be late' — send a text to a contact\n"
    "• 'Set alarm for 7 am' — alarm in the Clock app\n"
    "• 'Flashlight on' / 'Flashlight off'\n"
    "• 'Battery' — battery level and charging state\n"
    "• 'Open WhatsApp' — open any installed app by name\n"
    "• 'Open phone' — shows the face / PIN unlock screen\n"
    "• 'Good morning' — briefing: time, weather, today's notes, timers\n"
    "• Anything else — I answer with my AI brain\n\n"
    "Always-on: just say 'Jarvis' any time — even with the app closed\n"
    "or the phone locked — and I wake up and listen. (Uses more\n"
    "battery; turn it off with the Listener button below.)\n\n"
    "Tip: tap the microphone and speak, or type below."
)


# ---------------------------------------------------------------- storage

def data_dir():
    """Private app storage directory (works on Android and on desktop)."""
    try:
        app = App.get_running_app()
        if app is not None:
            return app.user_data_dir
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), ".jarvis")


def config_path():
    return os.path.join(data_dir(), "jarvis_config.json")


def notes_path():
    return os.path.join(data_dir(), "notes.txt")


def load_config():
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if isinstance(cfg, dict):
            return cfg
    except Exception:
        pass
    return {}


def save_config(cfg):
    try:
        os.makedirs(data_dir(), exist_ok=True)
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- networking (stdlib only — no requests)

def _http_post_json(url, payload, timeout=30):
    """POST a JSON body, return (status_code, parsed_json_or_None).

    Raises urllib.error.URLError on network failure.
    """
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8"))
        except Exception:
            data = None
        return e.code, data


def _http_get_text(url, timeout=10):
    """GET a URL, return the response text, or None on any failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read().decode("utf-8").strip()
    except Exception:
        pass
    return None


def ask_gemini(question, api_key):
    """Ask Gemini. Returns (reply_text, error_code or None).

    error_code is 'key' (bad/missing key) or 'net' (network/API failure).
    """
    prompt = SYSTEM_PROMPT + "\n\nUser: " + question + "\nJ.A.R.V.I.S.:"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 350},
    }
    for model in GEMINI_MODELS:
        try:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                + model + ":generateContent?key=" + api_key
            )
            status, data = _http_post_json(url, payload, timeout=30)
        except Exception:
            continue  # network error — try the next model, then report 'net'
        if status == 200 and data:
            try:
                parts = data["candidates"][0]["content"]["parts"]
                text = "".join(p.get("text", "") for p in parts).strip()
            except Exception:
                text = ""
            if text:
                return text, None
            return None, "net"
        if status == 404:
            continue  # model unavailable — try the next model
        if status in (400, 401, 403):
            # Our request body is fixed and valid, so a 4xx here means
            # the API key is missing, wrong or expired.
            return None, "key"
        # 429 / 5xx: transient — try the next model, then report 'net'.
    return None, "net"


def open_url(url):
    """Open a URL in the phone's browser (Android Intent if possible)."""
    try:
        from jnius import autoclass
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
        PythonActivity.mActivity.startActivity(intent)
        return True
    except Exception:
        pass
    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False


def get_weather():
    """Short current-weather line from wttr.in, or None on failure."""
    text = _http_get_text("https://wttr.in/?format=%C+%t", timeout=10)
    if text:
        return "Current weather: " + text + "."
    return None


# ---------------------------------------------------------------- HUD widgets

class Reactor(Widget):
    """Glowing arc-reactor ring with a rotating arc and a pulsing core."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.arc_angle = 0.0
        self.pulse = 0.0
        self.energy = 0.35  # 0..1, rises while listening/speaking
        with self.canvas:
            Color(0.08, 0.32, 0.48, 1)
            self.outer = Line(width=2)
            Color(0.21, 0.88, 1.0, 0.9)
            self.ring = Line(width=3)
            Color(0.21, 0.88, 1.0, 0.55)
            self.arc1 = Line(width=5)
            Color(0.21, 0.88, 1.0, 0.3)
            self.arc2 = Line(width=5)
            Color(0.45, 0.95, 1.0, 0.4)
            self.core = Ellipse()
        self.bind(pos=self._redraw, size=self._redraw)
        Clock.schedule_interval(self._tick, 0.05)

    def _tick(self, dt):
        self.arc_angle = (self.arc_angle + dt * 55) % 360
        self.pulse += dt
        self._redraw()

    def _redraw(self, *args):
        cx, cy = self.center
        r = min(self.width, self.height) * 0.44
        if r <= 0:
            return
        self.outer.circle = (cx, cy, r)
        self.ring.circle = (cx, cy, r * 0.8)
        a = self.arc_angle
        self.arc1.circle = (cx, cy, r * 0.92, a, a + 70)
        self.arc2.circle = (cx, cy, r * 0.92, a + 180, a + 235)
        glow = 1 + 0.10 * math.sin(self.pulse * 2.2) + 0.35 * self.energy
        cr = r * 0.42 * glow
        cr = min(cr, r * 0.62)
        self.core.pos = (cx - cr, cy - cr)
        self.core.size = (cr * 2, cr * 2)


class Waveform(Widget):
    """Row of bars that dance while Jarvis listens or speaks."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.level = 0.05
        self.bars = 28
        self._heights = [0.15] * self.bars
        self._phase = 0.0
        with self.canvas:
            self._color = Color(0.21, 0.88, 1.0, 0.9)
            self._rects = [Rectangle(pos=(0, 0), size=(1, 1)) for _ in range(self.bars)]
        self.bind(pos=self._redraw, size=self._redraw)
        Clock.schedule_interval(self._tick, 0.09)

    def _tick(self, dt):
        self._phase += dt
        for i in range(self.bars):
            wave = 0.5 + 0.5 * math.sin(self._phase * 6 + i * 0.7)
            target = 0.12 + self.level * (0.25 + 0.75 * wave) * random.uniform(0.7, 1.0)
            self._heights[i] += (target - self._heights[i]) * 0.45
        self._redraw()

    def _redraw(self, *args):
        w = self.width
        h = self.height
        if w <= 0 or h <= 0:
            return
        bw = w / self.bars
        for i, rect in enumerate(self._rects):
            bh = max(2, self._heights[i] * h)
            rect.pos = (self.x + i * bw + 1, self.y + (h - bh) / 2)
            rect.size = (bw - 2, bh)


# ---------------------------------------------------------------- popups

def text_popup(title, body, input_hint=None, on_save=None, save_label="Save"):
    """Generic popup. If input_hint is given, shows a TextInput + save button."""
    content = BoxLayout(orientation="vertical", spacing=10, padding=10)
    content.add_widget(Label(text=body, color=TEXT_COLOR, halign="left",
                             valign="top", text_size=(None, None),
                             size_hint_y=None, height=120))
    ti = None
    if input_hint is not None:
        ti = TextInput(hint_text=input_hint, multiline=False,
                       password=(input_hint.lower().find("key") >= 0),
                       size_hint_y=None, height=44,
                       background_color=(0.08, 0.12, 0.2, 1),
                       foreground_color=TEXT_COLOR)
        content.add_widget(ti)
    btns = BoxLayout(size_hint_y=None, height=48, spacing=10)
    close_btn = Button(text="Close", background_color=(0.15, 0.2, 0.3, 1))
    btns.add_widget(close_btn)
    popup = Popup(title=title, content=content, size_hint=(0.92, 0.62),
                  background_color=(0.03, 0.05, 0.09, 1))
    close_btn.bind(on_release=popup.dismiss)
    if on_save is not None and ti is not None:
        save_btn = Button(text=save_label, background_color=(0.1, 0.5, 0.65, 1))
        btns.add_widget(save_btn)

        def _save(*args):
            on_save(ti.text.strip())
            popup.dismiss()

        save_btn.bind(on_release=_save)
    content.add_widget(btns)
    popup.open()
    return popup


# ---------------------------------------------------------------- the app

class JarvisApp(App):
    title = APP_TITLE
    api_key = ""
    config = {}
    listening = False
    _stt_timer = None
    _stt_elapsed = 0
    _stt = None
    _stt_timeout_ev = None
    _wake_pause_path = None
    listener_btn = None
    _timers = []
    _timer_info = []

    def build(self):
        Window.clearcolor = BG_COLOR
        self.config = load_config()
        self.api_key = self.config.get("gemini_key", "")
        self.listening = False
        self._stt_timer = None
        self._stt = None
        self._stt_timeout_ev = None
        self._wake_pause_path = None
        self._timers = []
        self._timer_info = []

        # v2.1: ask for every runtime permission up front. v2.0 never
        # asked at all — the microphone (and other powers) were declared
        # in the manifest but never granted, so they silently did
        # nothing. Android only prompts for the ones not yet granted.
        if android_phone is not None:
            try:
                android_phone.request_all_permissions()
            except Exception:
                pass
            # Let Jarvis appear above the lock screen when woken by
            # the always-on listener.
            try:
                android_phone.show_over_lock_screen()
            except Exception:
                pass

        root = BoxLayout(orientation="vertical", spacing=6, padding=10)

        # status line
        self.status_label = Label(text="J.A.R.V.I.S. — Online. At your service, sir.",
                                  color=CYAN, size_hint_y=None, height=28,
                                  font_size=15)
        root.add_widget(self.status_label)

        # reactor
        self.reactor = Reactor(size_hint_y=0.42)
        root.add_widget(self.reactor)

        # waveform
        self.wave = Waveform(size_hint_y=None, height=44)
        root.add_widget(self.wave)

        # chat log
        self.chat_layout = GridLayout(cols=1, spacing=6, size_hint_y=None,
                                      padding=4)
        self.chat_layout.bind(minimum_height=self.chat_layout.setter("height"))
        scroll = ScrollView(size_hint_y=1, do_scroll_x=False)
        scroll.add_widget(self.chat_layout)
        self.chat_scroll = scroll
        root.add_widget(scroll)

        # typed input row
        input_row = BoxLayout(size_hint_y=None, height=48, spacing=8)
        self.text_input = TextInput(hint_text="Type to Jarvis…", multiline=False,
                                    background_color=(0.08, 0.12, 0.2, 1),
                                    foreground_color=TEXT_COLOR)
        self.text_input.bind(on_text_validate=self.on_send_text)
        send_btn = Button(text="Send", size_hint_x=None, width=80,
                          background_color=(0.1, 0.5, 0.65, 1))
        send_btn.bind(on_release=self.on_send_text)
        input_row.add_widget(self.text_input)
        input_row.add_widget(send_btn)
        root.add_widget(input_row)

        # mic button
        mic_btn = Button(text="🎙  TAP TO SPEAK", size_hint_y=None, height=62,
                         font_size=18, background_color=(0.08, 0.45, 0.62, 1))
        mic_btn.bind(on_release=self.on_mic)
        root.add_widget(mic_btn)

        # bottom buttons
        bottom = BoxLayout(size_hint_y=None, height=48, spacing=8)
        for label, fn in (("Commands", self.show_commands),
                          ("Notes", self.show_notes),
                          ("Settings", self.show_settings)):
            b = Button(text=label, background_color=(0.15, 0.2, 0.3, 1))
            b.bind(on_release=fn)
            bottom.add_widget(b)
        # Always-on listener toggle (v2.1): the foreground service
        # that wakes on "Jarvis". Default ON.
        self.listener_btn = Button(
            text=("Listener: ON" if self.config.get("listener_on", True)
                  else "Listener: OFF"),
            background_color=(0.15, 0.2, 0.3, 1))
        self.listener_btn.bind(on_release=self.toggle_listener)
        bottom.add_widget(self.listener_btn)
        root.add_widget(bottom)

        self.add_message("JARVIS",
                         "Good day, sir. Jarvis at your service. "
                         "Tap the microphone and speak, or type below.")
        if not self.api_key:
            Clock.schedule_once(lambda dt: self.show_settings(first_run=True), 1.0)
        # v2.1: watch for wake-ups from the always-on listener service.
        Clock.schedule_interval(self._check_wake_flag, 1.0)
        if self.config.get("listener_on", True):
            self._start_listener_service()
        return root

    # ------------------------------------------------------------ chat UI

    def set_status(self, text):
        self.status_label.text = text

    def add_message(self, who, text):
        color = "[color=33ddff]" if who == "JARVIS" else "[color=9fb3c8]"
        lbl = Label(text=color + who + ":[/color]  " + text,
                    markup=True, color=TEXT_COLOR, halign="left",
                    valign="top", text_size=(Window.width - 40, None),
                    size_hint_y=None)
        lbl.bind(texture_size=lambda inst, val: setattr(inst, "height", val[1] + 8))
        self.chat_layout.add_widget(lbl)
        Clock.schedule_once(lambda dt: self._scroll_bottom(), 0.05)

    def _scroll_bottom(self):
        try:
            self.chat_scroll.scroll_y = 0
        except Exception:
            pass

    # ------------------------------------------------------------ voice out

    def speak(self, text):
        """Show the reply and speak it aloud."""
        self.add_message("JARVIS", text)
        self.set_status("Speaking…")
        self.reactor.energy = 1.0
        self.wave.level = 0.9
        if HAVE_ANDROID_TTS and android_tts is not None:
            try:
                android_tts.speak(text)
            except Exception:
                self._plyer_speak(text)
        elif HAVE_PLYER and plyer_tts is not None:
            self._plyer_speak(text)
        secs = max(2.0, len(text) / 14.0)
        Clock.schedule_once(self._speak_done, secs)

    def _plyer_speak(self, text):
        try:
            plyer_tts.speak(text)
        except Exception:
            pass

    def _speak_done(self, dt):
        self.set_status("Ready, sir.")
        self.reactor.energy = 0.35
        self.wave.level = 0.05

    # ------------------------------------------------------------ voice in

    def on_mic(self, *args):
        if self.listening:
            self.stop_listening()
            return
        # v2.1: the runtime permission must be granted before the
        # recognizer can open the mic — v2.0 never asked, so tapping
        # the microphone silently did nothing.
        if android_phone is not None:
            try:
                if not android_phone.has_permission("RECORD_AUDIO"):
                    android_phone.request_permission("RECORD_AUDIO")
                    self.speak("I've asked for the microphone permission, "
                               "sir — please allow it, then tap the "
                               "microphone again.")
                    return
            except Exception:
                pass
        self._start_listening()

    def _start_listening(self):
        """Begin one voice input. Prefers android_stt (SpeechRecognizer
        with real error reporting); falls back to plyer STT."""
        # Pause the always-on service while the app has the mic, or
        # the two recognizers fight over it.
        self._pause_listener_service()
        self.listening = True
        self._stt_elapsed = 0
        self.set_status("Listening… speak now, sir.")
        self.reactor.energy = 0.85
        self.wave.level = 0.8
        if self._try_android_stt():
            return
        self._try_plyer_stt()

    def _try_android_stt(self):
        """Start listening via android_stt. Returns True if listening
        started (result/error arrive through the callbacks)."""
        if not HAVE_ANDROID_STT or android_stt is None:
            return False
        activity = None
        try:
            activity = android_phone.activity() if android_phone else None
        except Exception:
            activity = None
        if activity is None:
            return False
        try:
            if not android_stt.recognition_available(activity):
                return False
        except Exception:
            return False
        if self._stt is None:
            try:
                self._stt = android_stt.SpeechInput(activity)
            except Exception:
                return False
        self._stt_timeout_ev = Clock.schedule_once(self._on_stt_timeout, 12)
        try:
            started = self._stt.start(self._on_stt_result,
                                      self._on_stt_error)
        except Exception:
            started = False
        if not started:
            if self._stt_timeout_ev is not None:
                try:
                    self._stt_timeout_ev.cancel()
                except Exception:
                    pass
                self._stt_timeout_ev = None
            return False
        return True

    def _cancel_stt_timeout(self):
        if self._stt_timeout_ev is not None:
            try:
                self._stt_timeout_ev.cancel()
            except Exception:
                pass
            self._stt_timeout_ev = None

    def _on_stt_result(self, text):
        self._cancel_stt_timeout()
        heard = (text or "").strip()
        self.stop_listening()
        if heard:
            self.handle_text(heard, spoken=True)
        else:
            self.speak("I did not catch that, sir. Could you repeat it?")

    def _on_stt_error(self, code, name):
        self._cancel_stt_timeout()
        self.stop_listening()
        if code == 9:
            self.speak("I don't have the microphone permission, sir — "
                       "please allow it in the phone's Settings, under "
                       "Apps, J.A.R.V.I.S., Permissions, then try again.")
        elif code in (6, 7):
            self.speak("I could not hear you clearly, sir. "
                       "Please try again.")
        elif code == 8:
            self.speak("The microphone is busy, sir — please try again "
                       "in a moment.")
        else:
            self.speak("Speech recognition had a problem, sir (%s). "
                       "Please type your request instead." % name)

    def _on_stt_timeout(self, dt):
        if not self.listening:
            return
        self.stop_listening()
        self.speak("I did not hear anything, sir.")

    def _try_plyer_stt(self):
        """Fallback: the old plyer STT path (kept for devices where
        the native recognizer is unavailable)."""
        if not HAVE_PLYER or plyer_stt is None:
            self.listening = False
            self._release_wake_pause()
            self._speak_done(0)
            self.speak("Voice input is not available on this device, sir. "
                       "Please type your request instead.")
            return
        try:
            if not plyer_stt.exist():
                self.listening = False
                self._release_wake_pause()
                self._speak_done(0)
                self.speak("Speech recognition is not available on this "
                           "phone, sir. Please type your request instead.")
                return
        except Exception:
            pass
        try:
            plyer_stt.start()
        except Exception:
            self.listening = False
            self._release_wake_pause()
            self._speak_done(0)
            self.speak("I could not start the microphone, sir. "
                       "Please check the microphone permission and try again.")
            return
        self._stt_timer = Clock.schedule_interval(self._poll_stt, 0.3)

    def _poll_stt(self, dt):
        if not self.listening:
            return False
        results = []
        errors = []
        try:
            results = list(getattr(plyer_stt, "results", []) or [])
            errors = list(getattr(plyer_stt, "errors", []) or [])
        except Exception:
            pass
        if results:
            self.stop_listening()
            heard = results[0].strip()
            if heard:
                self.handle_text(heard, spoken=True)
            else:
                self.speak("I did not catch that, sir. Could you repeat it?")
            return False
        if errors:
            self.stop_listening()
            self.speak("I could not hear you clearly, sir. Please try again.")
            return False
        # give up after ~12 seconds of silence
        self._stt_elapsed = getattr(self, "_stt_elapsed", 0) + 0.3
        if self._stt_elapsed > 12:
            self.stop_listening()
            self.speak("I did not hear anything, sir.")
            return False
        return True

    def stop_listening(self):
        self.listening = False
        self._stt_elapsed = 0
        self._cancel_stt_timeout()
        if self._stt_timer is not None:
            try:
                self._stt_timer.cancel()
            except Exception:
                pass
            self._stt_timer = None
        try:
            if self._stt is not None:
                self._stt.stop()
        except Exception:
            pass
        try:
            if plyer_stt is not None and getattr(plyer_stt, "listening", False):
                plyer_stt.stop()
        except Exception:
            pass
        # Release the always-on listener service (it was paused while
        # the app listened for the command).
        self._release_wake_pause()
        self.reactor.energy = 0.35
        self.wave.level = 0.05

    # ------------------------------------------------------------ always-on
    # listener ("Jarvis" wake word) — v2.1

    def _listener_files(self):
        """(wake_path, pause_path, error_path) in the app files dir,
        shared with the listener service. None when not on Android."""
        if android_phone is None:
            return (None, None, None)
        try:
            d = android_phone.app_files_dir()
        except Exception:
            d = None
        if not d:
            return (None, None, None)
        return (os.path.join(d, "wake.txt"),
                os.path.join(d, "pause.txt"),
                os.path.join(d, "listener_error.txt"))

    def _check_wake_flag(self, dt):
        """Polled every second: did the listener service hear
        'Jarvis'? Also surfaces listener errors (e.g. no mic
        permission) once, as a chat line, not a repeated popup."""
        wake_path, pause_path, error_path = self._listener_files()
        if error_path:
            try:
                if os.path.exists(error_path):
                    with open(error_path, "r", encoding="utf-8") as f:
                        msg = f.read().strip()
                    os.remove(error_path)
                    if msg:
                        self.add_message("JARVIS", msg)
            except Exception:
                pass
        if not wake_path or self.listening:
            return
        try:
            if not os.path.exists(wake_path):
                return
            with open(wake_path, "r", encoding="utf-8") as f:
                ts = float((f.read().strip() or "0"))
            os.remove(wake_path)
        except Exception:
            return
        if time.time() - ts > 60:
            return  # stale wake — ignore
        # Consume the wake: pause the service, greet, then listen for
        # the command. (Listening starts after the greeting is spoken,
        # so the mic does not pick up Jarvis's own voice.)
        self._pause_listener_service()
        self.speak("Yes, sir?")
        secs = max(2.0, len("Yes, sir?") / 14.0)
        Clock.schedule_once(lambda dt: self._start_listening(), secs)

    def _pause_listener_service(self):
        """Tell the always-on service to stay off the mic while the
        app listens (manual tap or after a wake). Released by
        stop_listening() via _release_wake_pause()."""
        _, pause_path, _ = self._listener_files()
        if not pause_path:
            return
        try:
            with open(pause_path, "w", encoding="utf-8") as f:
                f.write("1")
            self._wake_pause_path = pause_path
        except Exception:
            pass

    def _release_wake_pause(self):
        if self._wake_pause_path:
            try:
                if os.path.exists(self._wake_pause_path):
                    os.remove(self._wake_pause_path)
            except Exception:
                pass
            self._wake_pause_path = None

    def _listener_service_class(self):
        """The generated service class, e.g.
        org.jarvis.jarvis.ServiceJarvislistener. Falls back to the
        base PythonService class if the generated one is not found."""
        try:
            from jnius import autoclass
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            pkg = str(activity.getPackageName())
            try:
                return autoclass(pkg + ".ServiceJarvislistener")
            except Exception:
                return autoclass("org.kivy.android.PythonService")
        except Exception:
            return None

    def _start_listener_service(self):
        try:
            service = self._listener_service_class()
            if service is None:
                return False
            from jnius import autoclass
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            service.start(activity, "ic_launcher", "Jarvis is listening",
                          "Say 'Jarvis' any time.", "")
            return True
        except Exception:
            return False

    def _stop_listener_service(self):
        try:
            service = self._listener_service_class()
            if service is None:
                return
            from jnius import autoclass
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            service.stop(activity)
        except Exception:
            pass

    def toggle_listener(self, *args):
        on = not self.config.get("listener_on", True)
        self.config["listener_on"] = on
        save_config(self.config)
        if self.listener_btn is not None:
            self.listener_btn.text = ("Listener: ON" if on
                                      else "Listener: OFF")
        if on:
            self._start_listener_service()
            self.speak("Always-on listening is on, sir — just say "
                       "'Jarvis' any time. Note that it uses more "
                       "battery while it listens.")
        else:
            self._stop_listener_service()
            self.speak("Always-on listening is off, sir. I will only "
                       "listen when you tap the microphone.")

    # ------------------------------------------------------------ input

    def on_send_text(self, *args):
        text = self.text_input.text.strip()
        if not text:
            return
        self.text_input.text = ""
        self.handle_text(text, spoken=False)

    def handle_text(self, text, spoken=False):
        self.add_message("YOU", text)
        reply = self.run_command(text)
        if reply is None:
            # Not a built-in command: ask the AI brain.
            self.set_status("Thinking…")
            self.reactor.energy = 0.7
            threading.Thread(target=self._ask_brain_thread, args=(text,),
                             daemon=True).start()
        else:
            self.speak(reply)

    def _ask_brain_thread(self, text):
        if not self.api_key:
            Clock.schedule_once(
                lambda dt: self.speak(
                    "My AI brain has no key yet, sir. Please add your Gemini "
                    "API key in Settings — it takes a minute, and it stays on "
                    "this phone only."), 0)
            Clock.schedule_once(lambda dt: self.show_settings(), 0.5)
            return
        reply, err = ask_gemini(text, self.api_key)
        if err == "key":
            Clock.schedule_once(
                lambda dt: self.speak(
                    "The Gemini key looks wrong or expired, sir. Please check "
                    "it in Settings."), 0)
            Clock.schedule_once(lambda dt: self.show_settings(), 0.5)
            return
        if err or not reply:
            Clock.schedule_once(
                lambda dt: self.speak(
                    "I could not reach my brain just now, sir. Please check "
                    "your internet connection and try again."), 0)
            return
        Clock.schedule_once(lambda dt: self.speak(reply), 0)

    # ------------------------------------------------------------ commands

    def run_command(self, text):
        """Built-in phone tasks. Returns a reply string, or None to use AI."""
        t = text.lower().strip()

        if "open youtube studio" in t or "youtube studio" in t:
            open_url("https://studio.youtube.com")
            return "Opening YouTube Studio, sir."
        if "open youtube" in t:
            open_url("https://www.youtube.com")
            return "Opening YouTube, sir."
        if "open google" in t:
            open_url("https://www.google.com")
            return "Opening Google, sir."

        if "what time" in t or t in ("time", "time please"):
            return "It is " + datetime.now().strftime("%I:%M %p") + ", sir."
        if "date" in t:
            return "Today is " + datetime.now().strftime("%A, %d %B %Y") + ", sir."

        if "weather" in t:
            w = get_weather()
            if w:
                return w
            return ("I could not fetch the weather just now, sir. "
                    "Please check your internet connection.")

        if t.startswith("search"):
            q = re.sub(r"^search( for| the web for)?", "", t).strip()
            if not q:
                return "What shall I search for, sir?"
            open_url("https://www.google.com/search?q=" + q.replace(" ", "+"))
            return "Searching the web for " + q + ", sir."

        if t.startswith("note ") or t.startswith("take a note"):
            note = re.sub(r"^(note|take a note)\s*", "", t, count=1).strip()
            if not note:
                return "What should I note down, sir?"
            try:
                os.makedirs(data_dir(), exist_ok=True)
                with open(notes_path(), "a", encoding="utf-8") as f:
                    f.write(datetime.now().strftime("%Y-%m-%d %H:%M") + " — "
                            + text.strip()[text.lower().find("note") + 4:].strip()
                            + "\n")
                return "Noted, sir."
            except Exception:
                return "I could not save that note, sir."

        if "show notes" in t or "read notes" in t or "my notes" in t:
            self.show_notes()
            return "Here are your notes, sir."

        m = re.search(r"timer (\d+)\s*(minute|minutes|second|seconds)", t)
        if m:
            amount = int(m.group(1))
            unit = m.group(2)
            secs = amount * 60 if "minute" in unit else amount
            unit_word = ("minute" if amount == 1 else "minutes") if "minute" in unit \
                else ("second" if amount == 1 else "seconds")
            label = "%d %s" % (amount, unit_word)
            info = {"label": label, "fires_at": time.time() + secs}

            def _fire(dt, _info=info):
                try:
                    self._timer_info.remove(_info)
                except ValueError:
                    pass
                self.speak("Your timer is finished, sir.")

            ev = Clock.schedule_once(_fire, secs)
            info["event"] = ev
            self._timers.append(ev)
            self._timer_info.append(info)
            return "Timer set for %s, sir." % label

        if t in ("hello", "hi", "hey jarvis", "jarvis"):
            return "At your service, sir. How may I help?"
        if "thank" in t:
            return "Always a pleasure, sir."

        # ---- phone powers (android_phone.py; degrade gracefully off-Android)
        if android_phone is not None:
            if ("open phone" in t or "unlock phone" in t
                    or "unlock my phone" in t):
                return android_phone.unlock_phone()
            if t in ("call", "phone"):
                return "Who should I call, sir?"
            if t in ("text", "message", "send sms", "send a text",
                     "send a sms"):
                return ("Who should I text, and what should it say, sir? "
                        "For example, 'Text Mum I'll be late'.")

            m = re.match(r"(?i)^(?:call|phone)\s+(.+?)\s*$", text.strip())
            if m:
                return android_phone.call_contact(m.group(1).strip())

            m = re.match(
                r"(?i)^send\s+(?:an?\s+)?(?:sms|text)\s+to\s+(\S+)"
                r"(?:\s+(.+))?$", text.strip())
            if m:
                if not m.group(2):
                    return "What should the text to %s say, sir?" % m.group(1)
                return android_phone.text_contact(m.group(1), m.group(2).strip())
            m = re.match(r"(?i)^(?:text|message)\s+(\S+)(?:\s+(.+))?$",
                         text.strip())
            if m:
                if not m.group(2):
                    return "What should the text to %s say, sir?" % m.group(1)
                return android_phone.text_contact(m.group(1), m.group(2).strip())

            m = re.search(
                r"(?i)set\s+(?:an\s+)?alarm\s+(?:for\s+)?(\d{1,2})"
                r"(?::(\d{2}))?\s*(am|pm)?", text)
            if m:
                hour = int(m.group(1))
                minute = int(m.group(2)) if m.group(2) else 0
                ampm = (m.group(3) or "").lower()
                if ampm == "pm" and hour < 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0
                if hour > 23 or minute > 59:
                    return ("That time doesn't look right, sir — try "
                            "'set alarm for 7 am' or 'set alarm for 19:30'.")
                return android_phone.set_alarm(hour, minute)
            if "set alarm" in t or "set an alarm" in t:
                return ("What time should I set the alarm for, sir? "
                        "For example, 'set alarm for 7 am'.")

            if "flashlight" in t or "torch" in t:
                if "off" in t:
                    return android_phone.set_flashlight(False)
                if "on" in t:
                    return android_phone.set_flashlight(True)
                return "Flashlight on or off, sir?"

            if "battery" in t or "system status" in t:
                return android_phone.battery_status()

            if t.startswith("good morning") or t in ("briefing",
                                                     "morning briefing"):
                return self.morning_briefing()

            m = re.match(r"(?i)^(?:open|launch)\s+(.+?)\s*$", text.strip())
            if m:
                return android_phone.open_app(m.group(1).strip())

        return None

    def morning_briefing(self):
        """One spoken summary: time, date, weather, today's notes,
        running timers."""
        now = datetime.now()
        parts = ["Good morning, sir. It is " + now.strftime("%I:%M %p")
                 + " on " + now.strftime("%A, %d %B") + "."]
        w = get_weather()
        parts.append(w if w else "I could not fetch the weather just now.")
        today = now.strftime("%Y-%m-%d")
        todays = []
        try:
            with open(notes_path(), "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith(today):
                        todays.append(line.strip().split("—", 1)[-1].strip())
        except Exception:
            pass
        if todays:
            parts.append("Your notes for today: " + "; ".join(todays) + ".")
        else:
            parts.append("No notes for today.")
        pending = [i for i in getattr(self, "_timer_info", [])
                   if i["fires_at"] > time.time()]
        if pending:
            parts.append("You have %d timer%s still running."
                         % (len(pending), "s" if len(pending) != 1 else ""))
        else:
            parts.append("No timers running.")
        return " ".join(parts)

    # ------------------------------------------------------------ popups

    def show_commands(self, *args):
        text_popup("Commands", COMMANDS_TEXT)

    def show_notes(self, *args):
        try:
            with open(notes_path(), "r", encoding="utf-8") as f:
                saved = f.read().strip()
        except Exception:
            saved = ""
        body = "Your notes:\n\n" + (saved if saved else "(No notes yet.)")
        content = BoxLayout(orientation="vertical", spacing=10, padding=10)
        content.add_widget(Label(text=body, color=TEXT_COLOR, halign="left",
                                 valign="top", size_hint_y=1))
        ti = TextInput(hint_text="Add a note…", multiline=False, size_hint_y=None,
                       height=44, background_color=(0.08, 0.12, 0.2, 1),
                       foreground_color=TEXT_COLOR)
        content.add_widget(ti)
        btns = BoxLayout(size_hint_y=None, height=48, spacing=10)
        close_btn = Button(text="Close", background_color=(0.15, 0.2, 0.3, 1))
        save_btn = Button(text="Save note", background_color=(0.1, 0.5, 0.65, 1))
        btns.add_widget(close_btn)
        btns.add_widget(save_btn)
        popup = Popup(title="Notes", content=content, size_hint=(0.92, 0.7),
                      background_color=(0.03, 0.05, 0.09, 1))
        close_btn.bind(on_release=popup.dismiss)

        def _save(*a):
            note = ti.text.strip()
            if note:
                try:
                    os.makedirs(data_dir(), exist_ok=True)
                    with open(notes_path(), "a", encoding="utf-8") as f:
                        f.write(datetime.now().strftime("%Y-%m-%d %H:%M")
                                + " — " + note + "\n")
                except Exception:
                    pass
            popup.dismiss()
            self.show_notes()

        save_btn.bind(on_release=_save)
        content.add_widget(btns)
        popup.open()

    def show_settings(self, *args, first_run=False):
        body = (
            "Gemini API key (entered once, stored only on this phone):\n"
            "Get a free key at Google AI Studio — aistudio.google.com — "
            "then paste it here.\n"
            "Without a key I can still open apps, tell the time and weather, "
            "take notes and set timers, but I cannot answer questions."
            if first_run else
            "Gemini API key (stored only on this phone):"
        )
        # v2.1: show which voice is actually in use, so a wrong (female)
        # voice can be spotted at a glance.
        try:
            if HAVE_ANDROID_TTS and android_tts is not None:
                body += "\n\n" + android_tts.describe_voice() + "."
        except Exception:
            pass

        def _save(value):
            if value:
                self.api_key = value
                self.config["gemini_key"] = value
                save_config(self.config)
                self.speak("Thank you, sir. My brain is online now.")

        text_popup("Settings", body, input_hint="Paste Gemini API key here",
                   on_save=_save, save_label="Save key")


if __name__ == "__main__":
    JarvisApp().run()
