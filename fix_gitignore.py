"""
تحديث .gitignore قبل الرفع - FireEngineerAI

    python fix_gitignore.py

يصلح مشكلتين تمنعان رفعًا سليمًا:
  1) السطر "*.spec" كان يستبعد FireEngineerAI.spec بصمت.
  2) الملف مكتوب بترميز تالف (cp1256) فالأسطر العربية غير مقروءة.

النسخة القديمة تُحفظ في .gitignore.bak
"""

import base64
import os
import shutil
import sys

CONTENT = base64.b64decode(
    "IyDZhdmE2YHYp9iqINio2KfZitir2YjZhiDYp9mE2YXYpNmC2KrYqSAo2YPYp9mG2Kog2YXYsdmB2YjYudipINi52YTZ"
    "iSBHaXRIdWIg2KjYp9mE2K7Yt9ijKQpfX3B5Y2FjaGVfXy8KKi5weVtjb2RdCioucHlvCioucHlkCgojINin2YTYqNmK"
    "2KbYp9iqINin2YTYp9mB2KrYsdin2LbZitipCi52ZW52Lwp2ZW52LwplbnYvCgojINmC2YjYp9i52K8g2KfZhNio2YrY"
    "p9mG2KfYqiDZiNin2YTZhtiz2K4g2KfZhNin2K3YqtmK2KfYt9mK2Kkg2KfZhNmF2K3ZhNmK2KkKKi5zcWxpdGUzCiou"
    "ZGIKZGJfbGVnYWN5X2JhY2t1cF8qLnNxbGl0ZTMKCiMg2YXYrtix2KzYp9iqINin2YTYqNix2YbYp9mF2KwKcmVwb3J0"
    "cy8KYmFja3Vwcy8Kc3RvcmFnZS8KKl9leHBvcnQuY3N2CgojINmF2YTZgdin2Kog2KfZhNmG2LjYp9mFCi5EU19TdG9y"
    "ZQpUaHVtYnMuZGIKZGVza3RvcC5pbmkKCiMg2KXYudiv2KfYr9in2Kog2KfZhNmF2K3Ysdix2KfYqgoudnNjb2RlLwou"
    "aWRlYS8KKi5zd3AKCiMg2YXYrtix2KzYp9iqINin2YTYqti62YTZitmBICjYqtmP2LnYp9ivINiq2YjZhNmK2K/Zh9in"
    "INio2YAgYnVpbGRfZXhlLnB5KQpidWlsZC8KZGlzdC8KKi5leGUKKi5zcGVjCiFGaXJlRW5naW5lZXJBSS5zcGVjCgoj"
    "INmG2LPYriDYp9it2KrZitin2LfZitipINmK2YjZhNmR2K/Zh9inINin2YTZhdmP2LHZg9mQ2ZHYqNmI2YYKKi5iYWsK"
    "CiMg2YPYp9i0INin2YTYp9iu2KrYqNin2LHYp9iqCi5weXRlc3RfY2FjaGUvCi5jb3ZlcmFnZQpodG1sY292LwoKIyDY"
    "o9iv2YjYp9iqINiq2LTYrtmK2LUg2YXYpNmC2KrYqQrYqti02K7Ziti1LnB5CtmB2K3YtV/Yp9mE2YXYs9in2LEucHkK"
    "CiMg2KjZgtin2YrYpyDYrdiy2YXYqSBHb29nbGUgRm9udHMKc3RhdGljLwpOb3RvTmFza2hBcmFiaWMtKi50dGYKUkVB"
    "RE1FLnR4dAoKIyDZhdis2YTYr9in2Kog2YbYs9iuINin2K3YqtmK2KfYt9mK2Kkg2YLYr9mK2YXYqQpiYWNrdXBfYmVm"
    "b3JlXyovCg=="
)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(os.path.join(here, "app.py")):
        print("\n[خطأ] لا يوجد app.py هنا.")
        print("      ضع الملف في C:\\Projects\\FireEngineerAI.\n")
        return 1

    path = os.path.join(here, ".gitignore")
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")
        print("\n  [نسخة] .gitignore.bak")

    with open(path, "wb") as fh:
        fh.write(CONTENT)
    print("  [تحديث] .gitignore  (%d بايت، UTF-8)" % len(CONTENT))

    print("\n  الآن FireEngineerAI.spec سيُرفع،")
    print("  وملفات .bak و dist و build لن تُرفع.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
