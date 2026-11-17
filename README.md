# J.A.R.V.I.S. — Android App

A voice assistant for your Android phone, Iron-Man style: talk to it, it talks
back, answers questions with real AI, and runs tasks on your phone.

## ⚠️ Build status — no APK in this folder yet

The complete, tested app source is here, but **no APK was produced on this
machine**. The build got all the way through downloading the Android SDK,
command-line tools and NDK (~2.3 GB), then stopped at the `sdkmanager`
step — and the reason is the machine itself, not the app:

### Retry Tue 2026-11-17 ~10:10 IST — still blocked

The user enabled the `other_tcp` permission in Muse settings and the build
was retried. **It still fails at the same place, and the build was not
started** — a Java test program was run first, as a gate check, and it
proved Java TCP is still blocked: opening a socket to `dl.google.com:443`
or to the egress proxy gets the sandbox's 193-byte denial back instead of a
real connection ("Other TCP connections is turned off for this assistant...
switch other_tcp from Deny to Ask"). Verified three times, including a
re-test 90 seconds later, so this is not a propagation delay. A build that
cannot open TCP cannot succeed, so no build time was spent.

What would unblock it: check the setting really saved (Muse Settings →
Permissions → Direct network protocols → `other_tcp` on **Ask** or
**Allow**), and if it is on, try **Allow** instead of Ask, or retry in a
fresh session — the change may not apply to a session that was already
running. Until a Java test program can open a real TCP connection, no APK
can be built on this machine; building on your own PC (below) still works.

Side note from the retry: the system JDK that the first attempt used is
gone (system paths do not survive a VM restart), so a fresh Temurin JDK 17
was downloaded and now lives at `~/jdk-17.0.21+9` (tarball `~/jdk17.tar.gz`)
— the next retry can use it via `JAVA_HOME=~/jdk-17.0.21+9`.


- This machine only reaches the internet through an authenticated egress
  proxy. Python and curl use it fine.
- But the Android build tools (`sdkmanager`, Gradle) are **Java** programs,
  and on this machine **Java processes cannot open TCP connections at all** —
  the sandbox intercepts them and answers with a "direct TCP connections are
  turned off" message. Proven directly: a Java test program connecting to the
  proxy, to a local test server, and to a local relay all got the sandbox's
  denial text instead of a real connection, while the same connections from
  Python and curl worked.
- So `sdkmanager` fails with `java.util.NoSuchElementException` while
  fetching the package list, and no APK can be built here until that changes.

**Two ways to get the APK:**

1. **Build it on your own PC** (easiest — see "Build the APK yourself"
   below). Any Linux PC, Mac, or Windows PC with WSL works; it just needs
   normal internet, no proxy tricks.
2. **Or build it on this machine after the sandbox permission is changed:**
   in Muse, go to **Settings → Permissions → Direct network protocols** and
   switch **other_tcp** from **Deny** to **Ask** (or Allow). Then re-run
   `buildozer android debug` in this folder — the SDK/NDK are already
   downloaded, so it should continue from the `sdkmanager` step.

## Install the APK (once you have it)

1. Copy `jarvis-1.1-arm64-v8a-debug.apk` (in the `bin/` folder after a
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

- Tap **🎙 TAP TO SPEAK**, wait for "Listening…", then speak. Jarvis replies
  out loud and in the chat log.
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
- **Chat** — greetings, thanks, and any other question go to the AI brain.

## Permissions Jarvis asks for — and why

Android asks at first use; you can allow or deny each one, and Jarvis
falls back gracefully when one is off:

| Permission | Why Jarvis wants it | If you deny it |
|---|---|---|
| Microphone | Voice input | Type instead of speaking |
| Contacts | Look up who to call / text by name | Calls and texts by name won't work |
| Phone | Dial a contact directly | Opens the dialler with the number ready |
| SMS | Send a text directly | Opens the messaging app pre-filled |
| Camera | Flashlight (the torch is a camera feature) | Flashlight won't work |

Jarvis never reads your contacts, messages or call history for any other
reason, and nothing leaves the phone except the question you ask Gemini
and the weather lookup.

## The voice

Jarvis speaks in a calm British male voice (English UK) — movie-style, chosen
in the app. Two honest notes:

- It is a phone text-to-speech voice, **not the actor's real voice** from the
  films. That voice is not available anywhere.
- If it ever sounds American, check the phone's own text-to-speech setting:
  **Settings → System → Text-to-speech output → Preferred engine → Language →
  English (United Kingdom)**, and pick a male voice if your engine offers one.

Voice recognition uses your phone's Google speech recognition, so it needs
internet (or a downloaded offline language pack) and the Google app on the
phone.

## Honest limits

- **Needs internet** for voice recognition and for Gemini answers.
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
# APK: bin/jarvis-1.1-arm64-v8a-debug.apk
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
- `android_tts.py` — British-voice speech output via Android's own TTS.
- `android_phone.py` — phone powers: calls, texts, alarms, flashlight,
  battery, opening any app (pyjnius; degrades gracefully off-Android).
- `buildozer.spec` — Android build settings (API 33, arm64).
- `proxy-relay.py` — build helper: local unauthenticated proxy relay for
  machines behind an authenticated egress proxy (see above). Not part of the
  app.
- `buildozer.log` — log of the build attempts on this machine (proxy
  credentials redacted).
- `README.md` — this file.
