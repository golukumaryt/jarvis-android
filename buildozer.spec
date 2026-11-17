# Buildozer spec - J.A.R.V.I.S. Android app v2.0
# Build with:  buildozer android debug
# The APK lands in:  bin/jarvis-2.0-arm64-v8a-debug.apk
#
# v2.0 (2026-11-17): requirements cut to the bone. v1.x failed the cloud
# build because `requests` pulls in charset-normalizer, whose newest
# release ships a compiled cp314 wheel the Android toolchain rejects
# ("is not a supported wheel on this platform"). The app now uses only
# Python's built-in urllib for networking, so requests, certifi and
# charset-normalizer are gone from the app code — BUT Kivy's own
# python-for-android recipe still pip-installs requests (it lists it in
# its python_depends), which broke runs #6 and #8 the same way.
# Pinning charset-normalizer==3.3.2 in requirements does NOT work —
# p4a drops the version when resolving that transitive dependency.
# The fix is the local recipe override in ./p4a-recipes/kivy/ (a copy
# of the stock Kivy recipe with requests removed from python_depends),
# enabled by p4a.local_recipes below. Kivy/plyer/pyjnius are otherwise
# standard p4a recipes.

[app]
title = J.A.R.V.I.S.
package.name = jarvis
package.domain = org.jarvis
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 2.0
requirements = python3,kivy,plyer,android,pyjnius
# Local p4a recipe override (./p4a-recipes/kivy/): drops `requests` from
# Kivy's python_depends — see that file's header comment for why.
p4a.local_recipes = ./p4a-recipes
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
