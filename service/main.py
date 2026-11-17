# J.A.R.V.I.S. always-on listener service (python-for-android service).
# ------------------------------------------------------------------------
# Runs in its own process, even when the app is closed or the phone is
# locked, and listens continuously for the word "Jarvis".
#
# How it works:
#   * It is a foreground service (declared with :foreground in
#     buildozer.spec), so Android keeps it alive; the system shows a
#     persistent "Jarvis is listening" notification for it.
#   * It loops Android SpeechRecognizer (via android_stt.SpeechInput)
#     and checks every (partial or final) transcript for "jarvis".
#   * On hearing "Jarvis" it writes wake.txt into the app-private
#     files dir and posts a high-priority notification with a
#     full-screen intent, which brings the Jarvis activity to the
#     front — even from the lock screen. The app sees wake.txt, says
#     "Yes, sir?" and listens for the command. While the app is
#     handling the command it writes pause.txt, and this service
#     stays quiet until the flag is gone, so the two never fight
#     over the microphone.
#
# Honest limits (also in the README):
#   * The service can only bring up the unlock screen — it cannot
#     unlock the phone by itself. "Open phone" shows the face/PIN
#     prompt; the user unlocks it.
#   * Always-on listening uses noticeably more battery than a
#     closed app. The app has a Listener ON/OFF toggle for that.
#   * Speech recognition needs the Google app / network (or an
#     offline language pack); without it the service waits and
#     writes listener_error.txt for the app to report.
#   * If the phone reboots, the service starts again the next time
#     the app is opened (there is no boot receiver).
#
# No Kivy here — this process has no UI. Only stdlib + pyjnius +
# android_stt (which is jnius-only when given a `post` function).

import os
import threading
import time

try:
    from jnius import autoclass
    _HAVE_JNIUS = True
except Exception:
    _HAVE_JNIUS = False

import android_stt

WAKE_WORD = "jarvis"
WAKE_FILE = "wake.txt"
PAUSE_FILE = "pause.txt"
ERROR_FILE = "listener_error.txt"
WAKE_CHANNEL_ID = "jarvis_wake"
LOG_TAG = "JarvisListener"


def _log(msg):
    try:
        Log = autoclass("android.util.Log")
        Log.i(LOG_TAG, str(msg))
    except Exception:
        pass


def _service():
    """The running PythonService instance (retries: it is set by the
    time Python starts, but be patient)."""
    for _ in range(50):
        try:
            PythonService = autoclass("org.kivy.android.PythonService")
            svc = PythonService.mService
            if svc is not None:
                return svc
        except Exception:
            pass
        time.sleep(0.1)
    return None


def _files_dir(service):
    try:
        return str(service.getFilesDir().getAbsolutePath())
    except Exception:
        return None


def _flag(files_dir, name):
    return os.path.join(files_dir, name) if files_dir else None


def _write_flag(path, text=""):
    try:
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
    except Exception:
        pass


def _flag_exists(path):
    try:
        return bool(path) and os.path.exists(path)
    except Exception:
        return False


def _remove_flag(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _create_wake_channel(service):
    """High-importance channel for the wake notification."""
    try:
        Context = autoclass("android.content.Context")
        NotificationManager = autoclass("android.app.NotificationManager")
        NotificationChannel = autoclass("android.app.NotificationChannel")
        nm = service.getSystemService(Context.NOTIFICATION_SERVICE)
        chan = NotificationChannel(
            WAKE_CHANNEL_ID, "Jarvis wake",
            NotificationManager.IMPORTANCE_HIGH)
        chan.setDescription("Brings Jarvis to the front when you say "
                            "'Jarvis'.")
        nm.createNotificationChannel(chan)
    except Exception as exc:
        _log("wake channel failed: %s" % exc)


def _post_wake_notification(service):
    """Full-screen-intent notification: brings the Jarvis activity to
    the front, even from the lock screen or background. (Directly
    starting an activity from the background is blocked on Android
    10+; a full-screen intent is the sanctioned way alarms and
    incoming calls do it.)"""
    try:
        Context = autoclass("android.content.Context")
        Intent = autoclass("android.content.Intent")
        PendingIntent = autoclass("android.app.PendingIntent")
        Notification = autoclass("android.app.Notification")
        NotificationBuilder = autoclass("android.app.Notification$Builder")
        NotificationManager = autoclass("android.app.NotificationManager")
        nm = service.getSystemService(Context.NOTIFICATION_SERVICE)
        pm = service.getPackageManager()
        launch = pm.getLaunchIntentForPackage(service.getPackageName())
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK
                        | Intent.FLAG_ACTIVITY_SINGLE_TOP
                        | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
        pi = PendingIntent.getActivity(
            service, 0, launch,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE)
        builder = NotificationBuilder(service, WAKE_CHANNEL_ID)
        builder.setContentTitle("Jarvis")
        builder.setContentText("Yes, sir? I'm listening.")
        try:
            builder.setSmallIcon(service.getApplicationInfo().icon)
        except Exception:
            pass
        builder.setContentIntent(pi)
        builder.setFullScreenIntent(pi, True)
        builder.setCategory(Notification.CATEGORY_ALARM)
        builder.setPriority(Notification.PRIORITY_HIGH)
        builder.setVisibility(Notification.VISIBILITY_PUBLIC)
        builder.setAutoCancel(True)
        nm.notify(2, builder.build())
        _log("wake notification posted")
    except Exception as exc:
        _log("wake notification failed: %s" % exc)


def main():
    if not _HAVE_JNIUS:
        return
    service = _service()
    if service is None:
        return
    try:
        PythonService = autoclass("org.kivy.android.PythonService")
        PythonService.mService.setAutoRestartService(True)
    except Exception:
        pass
    _create_wake_channel(service)
    files_dir = _files_dir(service)
    wake_path = _flag(files_dir, WAKE_FILE)
    pause_path = _flag(files_dir, PAUSE_FILE)
    error_path = _flag(files_dir, ERROR_FILE)
    _log("listener service started, files dir: %s" % files_dir)

    handler = android_stt.main_looper_handler()
    if handler is None:
        _log("no main looper handler — cannot listen")
        return

    def post(fn):
        android_stt.post_to_handler(handler, fn)

    stt = android_stt.SpeechInput(service, post=post)
    heard = threading.Event()
    heard_text = {"text": ""}
    last_wake_time = [0.0]

    def on_result(text):
        heard_text["text"] = text or ""
        heard.set()

    def on_error(code, name):
        heard_text["text"] = ""
        heard_text["error"] = code
        heard.set()

    def on_partial(text):
        if text and WAKE_WORD in text.lower():
            heard_text["text"] = text
            heard_text["partial"] = True
            heard.set()

    _log("waiting for microphone permission / recognizer")
    while True:
        try:
            # The app pauses us while it handles a command.
            if _flag_exists(pause_path):
                time.sleep(1.0)
                continue
            # A wake the app has not consumed yet — wait for it.
            if _flag_exists(wake_path):
                time.sleep(0.5)
                continue
            if not android_stt.recognition_available(service):
                _write_flag(error_path,
                            "Speech recognition is not available on this "
                            "phone, sir.")
                _log("recognition unavailable, waiting 60s")
                time.sleep(60)
                continue
            _remove_flag(error_path)
            heard.clear()
            heard_text.clear()
            stt.start(on_result, on_error, on_partial=on_partial)
            heard.wait(timeout=15)
            stt.stop()
            text = (heard_text.get("text") or "").lower()
            if WAKE_WORD in text:
                # Cooldown: ignore the word for a while after a wake, so
                # Jarvis's own spoken reply cannot wake it again.
                if time.time() - last_wake_time[0] < 25:
                    _log("wake word in cooldown, ignoring")
                    time.sleep(0.3)
                    continue
                last_wake_time[0] = time.time()
                _log("heard wake word: %r" % heard_text.get("text"))
                _write_flag(wake_path, str(time.time()))
                _post_wake_notification(service)
                # Wait until the app consumes the wake flag (or give
                # up after 25s) before listening again.
                for _ in range(50):
                    if not _flag_exists(wake_path):
                        break
                    time.sleep(0.5)
                continue
            err = heard_text.get("error")
            if err == 9:  # ERROR_INSUFFICIENT_PERMISSIONS
                _write_flag(error_path,
                            "Jarvis needs the microphone permission for "
                            "always-on listening, sir.")
                _log("no microphone permission, waiting 30s")
                time.sleep(30)
                continue
            time.sleep(0.3)
        except Exception as exc:
            _log("loop error: %s" % exc)
            time.sleep(2.0)


if __name__ == "__main__":
    main()
