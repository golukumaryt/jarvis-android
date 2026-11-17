# Android-native phone powers for J.A.R.V.I.S. (pyjnius).
# ------------------------------------------------------------
# Calls, texts, alarms, flashlight, battery and opening any installed
# app — the things that need real Android APIs rather than plyer.
#
# Every public function here returns a plain reply string for Jarvis to
# speak, and every one degrades gracefully: on any non-Android platform
# (or if pyjnius is missing) it simply reports that the feature needs
# the phone. Nothing in this module ever crashes the app.
#
# Permissions (declared in buildozer.spec, granted by the user on the
# phone — Android asks at first use):
#   READ_CONTACTS — look up who to call / text.
#   CALL_PHONE    — dial directly; without it Jarvis opens the dialler
#                   with the number ready instead.
#   SEND_SMS      — send a text directly; without it Jarvis opens the
#                   messaging app with the text pre-filled instead.
#   CAMERA        — the flashlight (torch) is a camera feature.
#   Alarms need no permission — they go through the Clock app.

try:
    from jnius import autoclass
    _HAVE_JNIUS = True
except Exception:
    _HAVE_JNIUS = False

try:
    from android.permissions import check_permission, request_permissions, Permission
    _HAVE_PERMS = True
except Exception:
    _HAVE_PERMS = False
    check_permission = None
    request_permissions = None
    Permission = None

_NOT_ANDROID = ("That needs your Android phone, sir — it is not available "
                "on this device.")
_torch_on = False


def available():
    """True only when running on Android with pyjnius available."""
    return _HAVE_JNIUS


def activity():
    """The running PythonActivity, or None off-Android."""
    if not _HAVE_JNIUS:
        return None
    try:
        return _activity()
    except Exception:
        return None


def _activity():
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    return PythonActivity.mActivity


def _perm(name):
    """A permission as the constant p4a expects, or the raw string.

    p4a's Permission class does not define every newer permission
    (e.g. POST_NOTIFICATIONS); request/check_permissions also accept
    the raw "android.permission.*" string, so fall back to that.
    """
    if _HAVE_PERMS:
        try:
            return getattr(Permission, name)
        except Exception:
            pass
    return "android.permission." + name


def has_permission(perm_name):
    """Public: True if the runtime permission is already granted."""
    return _has_permission(perm_name)


def request_permission(perm_name):
    """Public: fire the runtime permission prompt (async)."""
    _ask_permission(perm_name)


def request_all_permissions():
    """Ask for every runtime permission Jarvis needs, in one go.

    Android only prompts for the ones not already granted. Call this
    once at startup — v2.0 never asked at all, which is why the
    microphone (and other powers) silently did nothing.
    """
    if not _HAVE_PERMS:
        return
    try:
        request_permissions([
            _perm("RECORD_AUDIO"),
            _perm("READ_CONTACTS"),
            _perm("CALL_PHONE"),
            _perm("SEND_SMS"),
            _perm("CAMERA"),
            _perm("POST_NOTIFICATIONS"),
        ])
    except Exception:
        pass


def _has_permission(perm_name):
    """True if the runtime permission is already granted."""
    if not _HAVE_PERMS:
        return True  # cannot check — try anyway, Android will refuse if denied
    try:
        return bool(check_permission(_perm(perm_name)))
    except Exception:
        return True


def _ask_permission(perm_name):
    """Fire the runtime permission prompt (async). Returns False: the
    caller should tell the user to allow it and ask again."""
    if _HAVE_PERMS:
        try:
            request_permissions([_perm(perm_name)])
        except Exception:
            pass
    return False


def _permission_or_error(exc, action):
    msg = str(exc)
    if "permission" in msg.lower() or "SecurityException" in msg:
        return ("I don't have the permission to %s, sir — please allow it "
                "in the phone's Settings, under Apps → J.A.R.V.I.S. → "
                "Permissions." % action)
    return "I couldn't %s just now, sir." % action


# ---------------------------------------------------------------- contacts

def find_contacts(name):
    """Search the phone's contacts by name.

    Returns a list of (display_name, number) — empty if nobody matches —
    or None when not running on Android.
    """
    if not _HAVE_JNIUS:
        return None
    activity = _activity()
    ContactsContract = autoclass("android.provider.ContactsContract")
    Phone = ContactsContract.CommonDataKinds.Phone
    resolver = activity.getContentResolver()
    cursor = resolver.query(
        Phone.CONTENT_URI, None,
        Phone.DISPLAY_NAME + " LIKE ?",
        ["%" + name + "%"],
        Phone.DISPLAY_NAME + " ASC")
    results = []
    try:
        if cursor is None:
            return []
        name_idx = cursor.getColumnIndex(Phone.DISPLAY_NAME)
        num_idx = cursor.getColumnIndex(Phone.NUMBER)
        seen = set()
        while cursor.moveToNext():
            n = str(cursor.getString(name_idx)) if name_idx >= 0 else ""
            num = str(cursor.getString(num_idx)) if num_idx >= 0 else ""
            if not n or not num:
                continue
            key = (n, num)
            if key not in seen:
                seen.add(key)
                results.append((n, num))
    finally:
        try:
            cursor.close()
        except Exception:
            pass
    return results


def _resolve_contact(name):
    """Returns (display_name, number) for one contact, or a reply string
    explaining why the name could not be resolved."""
    if not _HAVE_JNIUS:
        return None, _NOT_ANDROID
    if not _has_permission("READ_CONTACTS"):
        _ask_permission("READ_CONTACTS")
        return None, ("I need the Contacts permission first, sir — I've "
                      "asked for it, please allow it and ask me again.")
    try:
        matches = find_contacts(name)
    except Exception as exc:
        return None, _permission_or_error(exc, "look up that contact")
    if not matches:
        return None, ("I couldn't find anyone called %s in your contacts, "
                      "sir." % name)
    if len(matches) > 1:
        listed = ", ".join("%s (%s)" % (n, num) for n, num in matches[:5])
        return None, ("I found several matches for %s, sir: %s. "
                      "Which one did you mean?" % (name, listed))
    return matches[0], None


# ---------------------------------------------------------------- calls

def call_contact(name):
    """Call a contact by name. Direct dial when CALL_PHONE is granted,
    otherwise opens the dialler with the number ready."""
    if not _HAVE_JNIUS:
        return _NOT_ANDROID
    contact, problem = _resolve_contact(name)
    if problem:
        return problem
    display, number = contact
    number = number.replace(" ", "").replace("-", "")
    try:
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        activity = _activity()
        if _has_permission("CALL_PHONE"):
            intent = Intent(Intent.ACTION_CALL, Uri.parse("tel:" + number))
            activity.startActivity(intent)
            return "Calling %s now, sir." % display
        intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + number))
        activity.startActivity(intent)
        return ("I don't have the phone-call permission, sir, so I've "
                "opened the dialler with %s's number ready — just tap "
                "call." % display)
    except Exception as exc:
        return _permission_or_error(exc, "place that call")


# ---------------------------------------------------------------- texts

def text_contact(name, message):
    """Text a contact by name. Sends directly when SEND_SMS is granted,
    otherwise opens the messaging app with the text pre-filled."""
    if not _HAVE_JNIUS:
        return _NOT_ANDROID
    contact, problem = _resolve_contact(name)
    if problem:
        return problem
    display, number = contact
    number = number.replace(" ", "").replace("-", "")
    if _has_permission("SEND_SMS"):
        try:
            SmsManager = autoclass("android.telephony.SmsManager")
            sms = SmsManager.getDefault()
            if len(message) > 160:
                parts = sms.divideMessage(message)
                sms.sendMultipartTextMessage(number, None, parts, None, None)
            else:
                sms.sendTextMessage(number, None, message, None, None)
            return "Text sent to %s, sir: '%s'." % (display, message)
        except Exception:
            pass  # fall through to the messaging-app fallback below
    try:
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        activity = _activity()
        intent = Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:" + number))
        intent.putExtra("sms_body", message)
        activity.startActivity(intent)
        return ("I've opened your messaging app with the text to %s ready, "
                "sir — just tap send." % display)
    except Exception as exc:
        return _permission_or_error(exc, "send that text")


# ---------------------------------------------------------------- alarm

def set_alarm(hour, minute):
    """Set an alarm through the Clock app (no permission needed)."""
    if not _HAVE_JNIUS:
        return _NOT_ANDROID
    try:
        Intent = autoclass("android.content.Intent")
        AlarmClock = autoclass("android.provider.AlarmClock")
        activity = _activity()
        intent = Intent(AlarmClock.ACTION_SET_ALARM)
        intent.putExtra(AlarmClock.EXTRA_HOUR, int(hour))
        intent.putExtra(AlarmClock.EXTRA_MINUTES, int(minute))
        intent.putExtra(AlarmClock.EXTRA_MESSAGE, "J.A.R.V.I.S. alarm")
        intent.putExtra(AlarmClock.EXTRA_SKIP_UI, False)
        activity.startActivity(intent)
        return "Alarm set for %02d:%02d, sir." % (int(hour), int(minute))
    except Exception as exc:
        return _permission_or_error(exc, "set that alarm")


# ---------------------------------------------------------------- flashlight

def set_flashlight(on):
    """Switch the torch on or off (CameraManager — needs CAMERA)."""
    global _torch_on
    if not _HAVE_JNIUS:
        return _NOT_ANDROID
    if not _has_permission("CAMERA"):
        _ask_permission("CAMERA")
        return ("I need the Camera permission for the flashlight, sir — "
                "I've asked for it, please allow it and ask me again.")
    try:
        Context = autoclass("android.content.Context")
        CameraManager = autoclass("android.hardware.camera2.CameraManager")
        CameraCharacteristics = autoclass(
            "android.hardware.camera2.CameraCharacteristics")
        activity = _activity()
        cm = activity.getSystemService(Context.CAMERA_SERVICE)
        for camera_id in cm.getCameraIdList():
            chars = cm.getCameraCharacteristics(camera_id)
            flash = chars.get(CameraCharacteristics.FLASH_INFO_AVAILABLE)
            try:
                has_flash = bool(flash.booleanValue())
            except Exception:
                has_flash = str(flash).lower() == "true"
            if has_flash:
                cm.setTorchMode(camera_id, bool(on))
                _torch_on = bool(on)
                return ("Flashlight on, sir." if on
                        else "Flashlight off, sir.")
        return "This phone has no flashlight, sir."
    except Exception as exc:
        return _permission_or_error(exc, "switch the flashlight")


# ---------------------------------------------------------------- battery

def battery_status():
    """Battery level and charging state from the system broadcast."""
    if not _HAVE_JNIUS:
        return _NOT_ANDROID
    try:
        Intent = autoclass("android.content.Intent")
        IntentFilter = autoclass("android.content.IntentFilter")
        BatteryManager = autoclass("android.os.BatteryManager")
        activity = _activity()
        filt = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        battery = activity.registerReceiver(None, filt)
        if battery is None:
            return "I couldn't read the battery just now, sir."
        level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
        status = battery.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
        if level < 0 or scale <= 0:
            return "I couldn't read the battery just now, sir."
        pct = int(level * 100 / scale)
        charging = status in (BatteryManager.BATTERY_STATUS_CHARGING,
                              BatteryManager.BATTERY_STATUS_FULL)
        return "Battery is at %d percent, %s, sir." % (
            pct, "charging" if charging else "not charging")
    except Exception as exc:
        return _permission_or_error(exc, "read the battery")


# ---------------------------------------------------------------- open any app

def open_app(name):
    """Launch an installed app by its display name (exact match first,
    then a single partial match; lists the options if several match)."""
    if not _HAVE_JNIUS:
        return _NOT_ANDROID
    try:
        Intent = autoclass("android.content.Intent")
        activity = _activity()
        pm = activity.getPackageManager()
        probe = Intent(Intent.ACTION_MAIN)
        probe.addCategory(Intent.CATEGORY_LAUNCHER)
        apps = pm.queryIntentActivities(probe, 0)
        query = name.strip().lower()
        exact = None
        partial = []
        for i in range(apps.size()):
            info = apps.get(i)
            try:
                label = str(info.loadLabel(pm))
            except Exception:
                continue
            low = label.lower()
            if low == query:
                exact = (label, info)
                break
            if query in low:
                partial.append((label, info))
        chosen = exact or (partial[0] if len(partial) == 1 else None)
        if chosen is None:
            if len(partial) > 1:
                listed = ", ".join(label for label, _ in partial[:5])
                return ("I found several apps matching %s, sir: %s. "
                        "Which one did you mean?" % (name, listed))
            return "I couldn't find an app called %s on this phone, sir." % name
        label, info = chosen
        pkg = info.activityInfo.packageName
        launch = pm.getLaunchIntentForPackage(pkg)
        if launch is None:
            return "I found %s, sir, but I couldn't launch it." % label
        activity.startActivity(launch)
        return "Opening %s, sir." % label
    except Exception as exc:
        return _permission_or_error(exc, "open that app")


# ---------------------------------------------------------------- files dir
# (shared with the always-on listener service, which runs in the same
# app UID — the service and the app talk through small flag files here)

def app_files_dir():
    """Absolute path of the app-private files directory, or None."""
    if not _HAVE_JNIUS:
        return None
    try:
        activity = _activity()
        return str(activity.getFilesDir().getAbsolutePath())
    except Exception:
        return None


# ---------------------------------------------------------------- lock screen

def show_over_lock_screen():
    """Let the Jarvis activity appear above the lock screen and turn
    the screen on (API 27+). Needed so a "Jarvis" wake on the lock
    screen actually shows Jarvis instead of staying hidden behind it.
    Safe to call repeatedly; no-ops off-Android."""
    if not _HAVE_JNIUS:
        return
    try:
        activity = _activity()
        activity.setShowWhenLocked(True)
        activity.setTurnScreenOn(True)
    except Exception:
        pass


def unlock_phone():
    """Bring up the phone's own unlock screen (face / fingerprint /
    PIN) so the user can open the phone.

    HONEST LIMIT: no app can unlock a phone by itself — Android only
    lets the USER unlock it. This asks the system to show the unlock
    prompt; the user scans their face (or enters their PIN) and the
    phone opens. If the phone has no lock set, it opens at once.
    """
    if not _HAVE_JNIUS:
        return _NOT_ANDROID
    try:
        Context = autoclass("android.content.Context")
        KeyguardManager = autoclass("android.app.KeyguardManager")
        activity = _activity()
        show_over_lock_screen()
        km = activity.getSystemService(Context.KEYGUARD_SERVICE)
        if not km.isKeyguardLocked():
            return "Your phone is already unlocked, sir."
        # requestDismissKeyguard shows the system unlock prompt (face /
        # fingerprint / PIN). Callback is None — we do not need the
        # result; the system handles the unlock itself.
        km.requestDismissKeyguard(activity, None)
        return ("Opening the unlock screen, sir — please scan your face "
                "or enter your PIN and the phone will open.")
    except Exception as exc:
        return _permission_or_error(exc, "open the unlock screen")
