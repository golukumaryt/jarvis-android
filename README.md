# J.A.R.V.I.S. — Android App

A voice assistant for your Android phone, Iron-Man style: talk to it, it talks
back, answers questions with real AI, and runs tasks on your phone.

## ⚠️ Build status — v2.1

**v2.1 (Wed 2026-11-18): fixes the three problems the user reported
on v2.0 — a female voice, a dead microphone, and no always-on
listening.** The voice picker now scores every UK voice (male names,
the "male" token, Google's gbb/gbd male variants) and drops the pitch
when no male voice exists; the app requests all runtime permissions
at startup and voice input uses Android's SpeechRecognizer directly
(android_stt.py) with real error reporting; and a foreground service
(service/main.py) listens for "Jarvis" even with the app closed or
the phone locked, waking the app with a full-screen notification.
"Open phone" shows the system's face/PIN unlock screen.

**v2.0 (Tue 2026-11-17): the app was rewritten from scratch.** The v1.1
cloud builds (GitHub Actions, repo `golukumaryt/jarvis-android`) failed
4 times: twice on the Android SDK license prompt (fixed), then twice at
the build step itself — `requests` pulls in charset-normalizer, whose
newest release ships a compiled wheel the Android toolchain rejects
("is not a supported wheel on this platform"). v2.0 drops `requests`
entirely and uses only Python's built-in urllib for networking, so the
build requirements are just `python3,kivy,plyer,android,pyjnius`.
Same features, same voice, same commands — only the networking changed.
The rewritten files are being built in the cloud now; the APK will be
sent to the user when a run succeeds. v1.1 source is kept in
`backup-v1.1/` in this folder and in the repo's git history.

**No APK was produced on this machine.** The local build is blocked by
the machine itself, not the app: Java processes cannot open TCP
connections here (sandbox `other_tcp` permission off), so `sdkmanager`
and Gradle cannot download anything. The SDK/NDK (~2.3 GB) are already
downloaded at `~/.buildozer` for a retry if the permission is ever fixed.

## Install the APK (once you have it)

1. Copy `jarvis-2.1-arm64-v8a-debug.apk` (in the `bin/` folder after a
   successful build) to your phone.
2. On the phone, open the file and tap **Install**. If Android blocks it, allow
   **Install unknown apps** for the app you opened it from (Files / Chrome),
   then try again.
3. When Jarvis first opens, allow the permissions it asks for — see
   "Permissions Jarvis asks for" below. The Microphone is the only one
   needed for voice input; the rest unlock the phone powers one by one.
   (You can still type instead of speaking.)

## First run — add your Gemini key (once)

Jarvis's brain is Google Gemini. The key is yours, it is entered once inside
the app, and it is stored only on your phone — never sent anywhere else.

1. Get a free key at **Google AI Studio**: https://aistudio.google.com
   (sign in with Google → **Get API key** → **Create API key**).
2. In Jarvis, tap **Settings**, paste the key, tap **Save key**.
3. Done — Jarvis will say its brain is online.

Without a key, Jarvis can still open apps and websites, tell the time and
weather, take notes and set timers — but it cannot answer questions.

## How to talk to Jarvis

- Just say **"Jarvis"** any time — even with the app closed or the
  phone locked. Jarvis wakes up, says "Yes, sir?" and listens.
  (Uses more battery; turn it off with the **Listener** button.)
- Or tap **🎙 TAP TO SPEAK**, wait for "Listening…", then speak.
  Jarvis replies out loud and in the chat log.
- Or type in the box and tap **Send**.
- Tap **Commands** to see everything Jarvis understands.

## What Jarvis can do

- **Answer any question** — with reasons, not guesses. If it does not know,
  it says so.
- **Open apps & websites** — "Open YouTube", "Open Google", "Open YouTube Studio".
- **Time & date** — "What time is it?", "What is the date today?"
- **Weather** — "Weather" (current conditions, needs internet).
- **Web search** — "Search for …" (opens the results in your browser).
- **Notes** — "Note buy milk tomorrow"; "Show notes" to read them back.
- **Timers** — "Timer 5 minutes" (spoken alert when it rings, while the app
  is open).
- **Call a contact** — "Call Mum" (dials directly if the Phone permission
  is granted, otherwise opens the dialler with the number ready).
- **Send a text** — "Text Mum I'll be late" (sends directly if the SMS
  permission is granted, otherwise opens the messaging app pre-filled).
- **Alarms** — "Set alarm for 7 am" (opens the Clock app to confirm).
- **Flashlight** — "Flashlight on" / "Flashlight off".
- **Battery** — "Battery" (level and charging state).
- **Open any app** — "Open WhatsApp", "Open Maps" (by name).
- **Morning briefing** — "Good morning" (time, weather, today's notes,
  running timers, in one spoken summary).
- **Always-on "Jarvis"** — say "Jarvis" any time and the app wakes up,
  even from the lock screen (Listener button toggles it off).
- **Open phone** — "Open phone" shows the face / PIN unlock screen.
  No app can unlock a phone by itself; you scan your face or enter
  your PIN and the phone opens.
- **Chat** — greetings, thanks, and any other question go to the AI brain.

## Permissions Jarvis asks for — and why

Android asks at first use; you can allow or deny each one, and Jarvis
falls back gracefully when one is off:

| Permission | Why Jarvis wants it | If you deny it |
|---|---|---|
| Microphone | Voice input + always-on "Jarvis" listening | Type instead of speaking |
| Contacts | Look up who to call / text by name | Calls and texts by name won't work |
| Phone | Dial a contact directly | Opens the dialler with the number ready |
| SMS | Send a text directly | Opens the messaging app pre-filled |
| Camera | Flashlight (the torch is a camera feature) | Flashlight won't work |
| Notifications | The "Jarvis" wake notification (Android 13+) | The app won't wake from the lock screen |
| Foreground service | Keeps the always-on listener running | "Jarvis" only works while the app is open |

Jarvis never reads your contacts, messages or call history for any other
reason, and nothing leaves the phone except the question you ask Gemini
and the weather lookup.

## The voice

Jarvis speaks in a calm British male voice (English UK) — movie-style, chosen
in the app. **Settings shows the exact voice in use** (e.g. "Voice:
en-gb-x-gbb-network (male)"), so a wrong voice can be spotted at a
glance. Two honest notes:

- It is a phone text-to-speech voice, **not the actor's real voice** from the
  films. That voice is not available anywhere.
- If it still sounds female, the phone has no male UK voice installed:
  **Settings → System → Text-to-speech output → Preferred engine →
  Google Text-to-Speech → Install voice data → English (United Kingdom)**
  and download a male voice. Jarvis picks it up automatically.

Voice recognition uses your phone's Google speech recognition, so it needs
internet (or a downloaded offline language pack) and the Google app on the
phone.

## Honest limits

- **Needs internet** for voice recognition and for Gemini answers.
- **Cannot unlock the phone by itself** — "Open phone" shows the
  system's face/PIN screen; only the user's own face or PIN opens it.
- **Always-on listening uses more battery** — the microphone and the
  recognizer run continuously. Turn it off with the Listener button
  when you don't need it.
- **After a reboot**, the always-on listener starts again the next time
  the app is opened (there is no boot auto-start).
- **Cannot control other apps from the inside** — it can open YouTube, Google
  and any installed app, but it cannot, for example, press buttons inside
  another app or change system settings beyond what Android allows.
- **Timers and reminders only ring while the app is open** on screen.
- **Calls and texts use the contact's first name** (one word) — "Call Mum",
  "Text Dad I'll be late". If several contacts match, Jarvis lists them
  and asks which one you meant; it never guesses.
- **Alarms open the Clock app** to confirm — Android does not let an app
  set an alarm completely silently. If the time you name has already
  passed today, the Clock app sets it for tomorrow.
- **PC version is separate** — this APK is for your Android phone. The
  Windows app is in the `jarvis` folder (same assistant, built for PC).

## Build the APK yourself (from source)

On a Linux PC or VM with normal internet (Ubuntu/Debian shown):

```bash
# System packages
sudo apt-get install -y openjdk-17-jdk git zip unzip autoconf libtool \
  pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev

# Python tools (use a venv, or pip install --user buildozer cython)
python3 -m venv ~/.venvs/jarvis-android
~/.venvs/jarvis-android/bin/pip install buildozer cython

# Build (first run downloads the Android SDK + NDK, ~10 GB, and takes a while)
cd jarvis-android
~/.venvs/jarvis-android/bin/buildozer android debug
# APK: bin/jarvis-2.1-arm64-v8a-debug.apk
```

For a release APK you can install without the debug warning, use
`buildozer android release` and sign it with your own keystore
(`keytool -genkey -v -keystore my.keystore -alias jarvis ...`).

**If you are behind an authenticated proxy** (like this machine): buildozer
1.6.0 has a bug in its `sdkmanager` proxy handling — it splits the proxy URL
on `:` and ends up passing the proxy *password* as the proxy host, so
`sdkmanager` fails to resolve it. The fix, in the installed buildozer's
`targets/android.py` `_sdkmanager` method, is to parse the URL properly:

```python
from urllib.parse import urlparse
parsed = urlparse(os.environ.get(key) or '')
host = parsed.hostname
port = parsed.port
if host and port:
    command.extend(['--proxy=http',
                    f'--proxy_host={host}',
                    f'--proxy_port={port}'])
```

Even with that fixed, Java still needs proxy *authentication*, which
`sdkmanager` cannot be given on the command line. The workaround used here
was `proxy-relay.py` in this folder: a small local relay that listens on
127.0.0.1:3129 without authentication and adds the egress-proxy credentials
itself. Point the build at it with
`http_proxy=http://127.0.0.1:3129 https_proxy=http://127.0.0.1:3129` and
`JAVA_TOOL_OPTIONS="-Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=3129
-Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=3129"`. (That relay is a
build-environment helper only — the app itself does not need it.)

## Files

- `main.py` — the whole app (Kivy UI, voice, commands, Gemini brain).
  v2.0: rewritten 2026-11-17, networking on stdlib urllib only.
  v2.1: runtime permission requests, android_stt voice input,
  always-on listener wake handling, "open phone" command.
- `android_tts.py` — British-voice speech output via Android's own TTS.
  v2.1: scores every UK voice for maleness (names, "male" token,
  Google gbb/gbd variants) with a pitch-0.8 fallback.
- `android_stt.py` — speech recognition via Android's SpeechRecognizer
  (pyjnius), with result/error callbacks. v2.1, replaces plyer STT.
- `service/main.py` — the always-on "Jarvis" listener (foreground
  service): loops SpeechRecognizer, wakes the app on "Jarvis" with a
  full-screen-intent notification. v2.1.
- `android_phone.py` — phone powers: calls, texts, alarms, flashlight,
  battery, opening any app (pyjnius; degrades gracefully off-Android).
  v2.1: permission helpers, lock-screen / unlock-phone support.
- `buildozer.spec` — Android build settings (API 33, arm64). v2.0:
  requirements `python3,kivy,plyer,android,pyjnius` — no requests.
  Points at `p4a.local_recipes = ./p4a-recipes`.
- `p4a-recipes/kivy/` — local python-for-android recipe override: a copy
  of the stock Kivy recipe with `requests` removed from python_depends
  (plus its 3 stock patch files). This is what stops the build from
  pip-installing requests — and the charset-normalizer wheel that broke
  every cloud build. Without it, the build fails even though the app
  never imports requests.
- `backup-v1.1/` — the v1.1 source files, kept for reference.
- `proxy-relay.py` — build helper: local unauthenticated proxy relay for
  machines behind an authenticated egress proxy (see above). Not part of the
  app.
- `buildozer.log` — log of the build attempts on this machine (proxy
  credentials redacted).
- `README.md` — this file.
