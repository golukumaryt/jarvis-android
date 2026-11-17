# Buildozer spec - J.A.R.V.I.S. Android app v2.0
# Build with:  buildozer android debug
# The APK lands in:  bin/jarvis-2.0-arm64-v8a-debug.apk
#
# v2.0 (2026-11-17): requirements cut to the bone. v1.x failed the cloud
# build because `requests` pulls in charset-normalizer, whose newest
# release ships a compiled cp314 wheel the Android toolchain rejects
# ("is not a supported wheel on this platform"). The app now uses only
# Python's built-in urllib for networking, so requests, certifi and
# charset-normalizer are gone entirely — nothing left that can break
# the pip install step. Kivy/plyer/pyjnius are standard p4a recipes.

[app]
title = J.A.R.V.I.S.
package.name = jarvis
package.domain = org.jarvis
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 2.0
requirements = python3,kivy,plyer,android,pyjnius
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
