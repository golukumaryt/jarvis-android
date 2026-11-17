# Buildozer spec - J.A.R.V.I.S. Android app
# Build with:  buildozer android debug
# The APK lands in:  bin/jarvis-1.1-arm64-v8a-debug.apk

[app]
title = J.A.R.V.I.S.
package.name = jarvis
package.domain = org.jarvis
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.1
# charset-normalizer pinned to the last pure-Python release (3.3.2).
# Newer releases ship a compiled cp314 wheel for the Android target
# that pip rejects (is not a supported wheel on this platform),
# which broke the build via the requests dependency.
requirements = python3,kivy,plyer,requests,android,pyjnius,certifi,charset-normalizer==3.3.2
orientation = portrait
fullscreen = 0
# INTERNET: Gemini brain + weather. RECORD_AUDIO + MODIFY_AUDIO_SETTINGS:
# voice input. READ_CONTACTS: call/text by name. CALL_PHONE: direct dial
# (falls back to the dialler without it). SEND_SMS: direct text (falls
# back to the messaging app without it). CAMERA: flashlight (torch).
android.permissions = INTERNET, RECORD_AUDIO, MODIFY_AUDIO_SETTINGS, READ_CONTACTS, CALL_PHONE, SEND_SMS, CAMERA
android.api = 33
android.minapi = 24
android.sdk = 33
android.ndk = 25b
android.ndk_api = 24
android.archs = arm64-v8a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 0
