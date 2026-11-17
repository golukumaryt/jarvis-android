# Android speech recognition via SpeechRecognizer (pyjnius).
# ------------------------------------------------------------
# Replaces plyer STT for voice input.
#
# v2.1 — why: the app used plyer STT, which failed silently on the
# user's phone. Two causes, both fixed here and in main.py:
#   1. The app NEVER asked Android for the RECORD_AUDIO runtime
#      permission (it was only declared in the manifest). On
#      Android 6+ a declared-but-ungranted permission means the
#      recognizer cannot open the mic, so tapping the microphone did
#      nothing useful. main.py now requests it before listening.
#   2. plyer STT gives no usable error: its start() can fail without
#      raising, and its results/errors lists stay empty, so the app
#      just timed out after 12 seconds. This module reports every
#      outcome through callbacks (result / error / status), so the
#      app can say out loud what went wrong instead of going quiet.
#
# SpeechRecognizer must be created and driven on a thread with a
# Looper. In the app that is the UI thread; in the always-on listener
# service it is the service process's main thread. The caller passes
# a `post` function that runs a callable on that thread (defaults to
# android.runnable.run_on_ui_thread).
#
# Recognition language is en-IN (Indian English) — the user's accent.
#
# On any non-Android platform this module reports unavailable and the
# app falls back to plyer STT / typing. It must always import cleanly.

try:
    from jnius import autoclass, PythonJavaClass, java_method
    _HAVE_JNIUS = True
except Exception:
    _HAVE_JNIUS = False

try:
    # Safe to import in a service process too (it only touches the
    # activity when actually called); the service passes its own
    # `post` function and never uses this fallback.
    from android.runnable import run_on_ui_thread
except Exception:
    def run_on_ui_thread(func):
        return func


def available():
    return _HAVE_JNIUS


RECOGNITION_LANGUAGE = "en-IN"

ERROR_NAMES = {
    1: "network timeout",
    2: "network error",
    3: "audio error",
    4: "server error",
    5: "client error",
    6: "no speech heard",
    7: "no match",
    8: "recognizer busy",
    9: "microphone permission missing",
}


def error_name(code):
    return ERROR_NAMES.get(code, "error %d" % code)


def _log(msg):
    try:
        Log = autoclass("android.util.Log")
        Log.i("JarvisSTT", str(msg))
    except Exception:
        pass


if _HAVE_JNIUS:
    class _Runnable(PythonJavaClass):
        """A Java Runnable that calls a Python function (for
        Handler.post)."""

        __javainterfaces__ = ["java.lang.Runnable"]

        def __init__(self, fn):
            super().__init__()
            self._fn = fn

        @java_method("()V")
        def run(self):
            try:
                self._fn()
            except Exception:
                pass
else:
    class _Runnable:
        """Stub so the module imports cleanly off-Android."""

        def __init__(self, fn):
            self._fn = fn


def post_to_handler(handler, fn):
    """Post fn to an android.os.Handler (e.g. the main-looper handler)."""
    try:
        handler.post(_Runnable(fn))
        return True
    except Exception:
        return False


def main_looper_handler():
    """android.os.Handler bound to the process main looper, or None."""
    try:
        Looper = autoclass("android.os.Looper")
        Handler = autoclass("android.os.Handler")
        return Handler(Looper.getMainLooper())
    except Exception:
        return None


if _HAVE_JNIUS:
    class _Listener(PythonJavaClass):
        __javainterfaces__ = ["android.speech.RecognitionListener"]

        def __init__(self, owner):
            super().__init__()
            self._owner = owner

        def _results_list(self, results):
            try:
                SpeechRecognizer = autoclass(
                    "android.speech.SpeechRecognizer")
                arr = results.getStringArrayList(
                    SpeechRecognizer.RESULTS_RECOGNITION)
                if arr is None:
                    return []
                return [str(arr.get(i)) for i in range(arr.size())]
            except Exception:
                return []

        @java_method("(Landroid/os/Bundle;)V")
        def onResults(self, results):
            try:
                self._owner._on_results(self._results_list(results))
            except Exception:
                pass

        @java_method("(Landroid/os/Bundle;)V")
        def onPartialResults(self, results):
            try:
                self._owner._on_partial(self._results_list(results))
            except Exception:
                pass

        @java_method("(I)V")
        def onError(self, error):
            try:
                self._owner._on_error(int(error))
            except Exception:
                pass

        @java_method("()V")
        def onReadyForSpeech(self):
            try:
                self._owner._on_status("ready")
            except Exception:
                pass

        @java_method("()V")
        def onBeginningOfSpeech(self):
            try:
                self._owner._on_status("speaking")
            except Exception:
                pass

        @java_method("()V")
        def onEndOfSpeech(self):
            try:
                self._owner._on_status("done")
            except Exception:
                pass

        @java_method("(F)V")
        def onRmsChanged(self, rmsdB):
            pass

        @java_method("([B)V")
        def onBufferReceived(self, buffer):
            pass

        @java_method("(ILandroid/os/Bundle;)V")
        def onEvent(self, eventType, params):
            pass
else:
    class _Listener:
        def __init__(self, owner):
            self._owner = owner


def recognition_available(context):
    """True when the phone has a speech-recognition service."""
    if not _HAVE_JNIUS or context is None:
        return False
    try:
        SpeechRecognizer = autoclass("android.speech.SpeechRecognizer")
        return bool(SpeechRecognizer.isRecognitionAvailable(context))
    except Exception:
        return False


class SpeechInput:
    """One-shot speech recognition with result/error callbacks.

    Callbacks: on_result(text), on_error(code, name),
    on_partial(text) [optional], on_status(state) [optional].
    """

    def __init__(self, context, post=None):
        self._context = context
        self._post = post
        self._recognizer = None
        self._listener = None
        self._on_result = None
        self._on_error = None
        self._on_partial = None
        self._on_status = None
        self._active = False
        self._cancelled = False

    # ------------------------------------------------------------ public

    def start(self, on_result, on_error, on_partial=None, on_status=None):
        """Begin listening. Returns False if the recognizer could not
        be started (on_error is still called with the reason)."""
        if not _HAVE_JNIUS or self._context is None:
            if on_error:
                on_error(-1, "speech recognition is not available")
            return False
        self._on_result = on_result
        self._on_error = on_error
        self._on_partial = on_partial
        self._on_status = on_status
        self._active = True
        self._cancelled = False
        self._post_call(self._start_on_looper)
        return True

    def stop(self):
        """Stop listening (user pressed the mic button again)."""
        self._cancelled = True
        self._active = False
        self._post_call(self._cancel_on_looper)

    def destroy(self):
        self._cancelled = True
        self._active = False
        self._post_call(self._destroy_on_looper)

    # ------------------------------------------------------------ internals

    def _post_call(self, fn):
        if self._post is not None:
            try:
                self._post(fn)
                return
            except Exception:
                pass
        try:
            run_on_ui_thread(fn)()
        except Exception:
            try:
                fn()
            except Exception:
                pass

    def _start_on_looper(self):
        try:
            SpeechRecognizer = autoclass("android.speech.SpeechRecognizer")
            Intent = autoclass("android.content.Intent")
            RecognizerIntent = autoclass(
                "android.speech.RecognizerIntent")
            if self._recognizer is None:
                self._recognizer = SpeechRecognizer.createSpeechRecognizer(
                    self._context)
                self._listener = _Listener(self)
                self._recognizer.setRecognitionListener(self._listener)
            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                            RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE,
                            RECOGNITION_LANGUAGE)
            intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
            intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, True)
            intent.putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE,
                            self._context.getPackageName())
            self._recognizer.startListening(intent)
            _log("listening started")
        except Exception as exc:
            self._active = False
            if self._on_error:
                self._on_error(-1, "could not start listening: %s" % exc)

    def _cancel_on_looper(self):
        try:
            if self._recognizer is not None:
                self._recognizer.cancel()
        except Exception:
            pass

    def _destroy_on_looper(self):
        try:
            if self._recognizer is not None:
                self._recognizer.destroy()
        except Exception:
            pass
        self._recognizer = None
        self._listener = None

    # ------------------------------------------------------------ listener callbacks

    def _on_results(self, texts):
        if not self._active:
            return
        self._active = False
        _log("result: %s" % (texts[:1],))
        if self._on_result:
            self._on_result(texts[0] if texts else "")

    def _on_partial(self, texts):
        if not self._active:
            return
        if self._on_partial and texts:
            self._on_partial(texts[0])

    def _on_error(self, code):
        if not self._active:
            return
        self._active = False
        if self._cancelled and code == 5:  # ERROR_CLIENT after cancel()
            return
        _log("error: %d (%s)" % (code, error_name(code)))
        if self._on_error:
            self._on_error(code, error_name(code))

    def _on_status(self, state):
        if self._on_status:
            self._on_status(state)
