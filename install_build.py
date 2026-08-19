"""
مُركِّب أدوات تغليف FireEngineerAI 1.5.2

ضعه في C:\\Projects\\FireEngineerAI وشغّله:

    python install_build.py

ينشئ FireEngineerAI.spec و build_exe.py، ويصلح مسارات الخطوط والأيقونة
كي تعمل داخل ملف exe. آمن للتشغيل أكثر من مرة.
"""

import base64
import os
import shutil
import sys

FILES = {
    'FireEngineerAI.spec': (
        "IyAtKi0gbW9kZTogcHl0aG9uIDsgY29kaW5nOiB1dGYtOCAtKi0KIiIiCtil2LnYr9in2K8g2KrYutmE2YrZgSBGaXJl"
        "RW5naW5lZXJBSSDYpdmE2Ykg2YXZhNmBIGV4ZSDZiNin2K3Yry4KCiAgICBweWluc3RhbGxlciBGaXJlRW5naW5lZXJB"
        "SS5zcGVjIC0tY2xlYW4gLS1ub2NvbmZpcm0KCtin2YTZhtin2KrYrDogZGlzdFxcRmlyZUVuZ2luZWVyQUkuZXhlCgrZ"
        "hdmE2KfYrdi42KfYqiDZhdmC2LXZiNiv2Kk6CiAgKiBvbmVmaWxlOiDZhdmE2YEg2YjYp9it2K8g2YrZhtiz2K7ZhyDY"
        "p9mE2YXYs9iq2K7Yr9mFINij2YrZhtmF2Kcg2LTYp9ihLgogICogY29uc29sZT1GYWxzZTog2YTYpyDYqti42YfYsSDZ"
        "htin2YHYsNipINiz2YjYr9in2KEg2K7ZhNmBINin2YTZiNin2KzZh9ipLgogICog2KfZhNiu2LfZiNi3INmI2KfZhNij"
        "2YrZgtmI2YbYqSDZhdi22YXZjtmR2YbYqSDYudio2LEgZGF0YXMg4oCUINmI2KjYr9mI2YbZh9inINiq2LjZh9ixINin"
        "2YTYudix2KjZitipINmB2YogUERGCiAgICDZhdit2LHZkdmB2KnYjCDZhNij2YYgcmVwb3J0bGFiINmE2Kcg2YrZhdmE"
        "2YMg2K7Yt9mL2Kcg2LnYsdio2YrZi9inINmF2K/Zhdis2YvYpy4KICAqINin2YTYqNmK2KfZhtin2KogKNmC2KfYudiv"
        "2Kkg2KfZhNio2YrYp9mG2KfYqtiMINin2YTZhtiz2K7YjCDYp9mE2KrZgtin2LHZitixKSDYqtmP2K7YstmO2ZHZhiDZ"
        "gdmKCiAgICAlQVBQREFUQSVcXEZpcmVFbmdpbmVlckFJINiu2KfYsdisINin2YTZgCBleGXYjCDZgdmE2Kcg2KrZj9mB"
        "2YLYryDYudmG2K8g2KfZhNiq2K3Yr9mK2KsuCiIiIgoKaW1wb3J0IG9zCgpibG9ja19jaXBoZXIgPSBOb25lCgpkYXRh"
        "cyA9IFsKICAgICgiZm9udHMiLCAiZm9udHMiKSwgICAgICAgICAgICAjINin2YTYrti3INin2YTYudix2KjZiiDZiNi6"
        "2KfZhdmC2Ycg4oCUINil2YTYstin2YXZiiDZhNiq2YLYp9ix2YrYsSBQREYKICAgICgiYXBwX2ljb24uaWNvIiwgIi4i"
        "KSwKICAgICgiYXBwX2ljb24ucG5nIiwgIi4iKSwKXQoKIyDYp9iz2KrYqNi52KfYryDZhdmD2KrYqNin2Kog2KvZgtmK"
        "2YTYqSDZhNinINmK2LPYqtmI2LHYr9mH2Kcg2KfZhNio2LHZhtin2YXYrCDigJQg2KrZiNmB2ZHYsSDYudi02LHYp9iq"
        "INin2YTZhdmK2LrYp9io2KfZitiqCmV4Y2x1ZGVzID0gWwogICAgInRraW50ZXIiLCAidW5pdHRlc3QiLCAicHlkb2Nf"
        "ZGF0YSIsCiAgICAibnVtcHkiLCAicGFuZGFzIiwgIm1hdHBsb3RsaWIiLCAic2NpcHkiLAogICAgIlBJTC5JbWFnZVF0"
        "IiwgIlB5U2lkZTYuUXRXZWJFbmdpbmVDb3JlIiwgIlB5U2lkZTYuUXRXZWJFbmdpbmVXaWRnZXRzIiwKICAgICJQeVNp"
        "ZGU2LlF0M0RDb3JlIiwgIlB5U2lkZTYuUXRDaGFydHMiLCAiUHlTaWRlNi5RdERhdGFWaXN1YWxpemF0aW9uIiwKICAg"
        "ICJQeVNpZGU2LlF0TXVsdGltZWRpYSIsICJQeVNpZGU2LlF0TXVsdGltZWRpYVdpZGdldHMiLCAiUHlTaWRlNi5RdFF1"
        "aWNrIiwKICAgICJQeVNpZGU2LlF0UW1sIiwgIlB5U2lkZTYuUXQzRFJlbmRlciIsICJQeVNpZGU2LlF0TmV0d29ya0F1"
        "dGgiLAogICAgIlB5U2lkZTYuUXRCbHVldG9vdGgiLCAiUHlTaWRlNi5RdFBvc2l0aW9uaW5nIiwgIlB5U2lkZTYuUXRT"
        "ZW5zb3JzIiwKICAgICJQeVNpZGU2LlF0U2VyaWFsUG9ydCIsICJQeVNpZGU2LlF0VGVzdCIsICJQeVNpZGU2LlF0RGVz"
        "aWduZXIiLAogICAgIlB5U2lkZTYuUXRPcGVuR0wiLCAiUHlTaWRlNi5RdE9wZW5HTFdpZGdldHMiLCAiUHlTaWRlNi5R"
        "dFNxbCIsCl0KCmhpZGRlbmltcG9ydHMgPSBbCiAgICAicmVwb3J0bGFiLmdyYXBoaWNzLmJhcmNvZGUuY29kZTEyOCIs"
        "CiAgICAicmVwb3J0bGFiLnBkZmJhc2UuX2ZvbnRkYXRhX2VuY193aW5hbnNpIiwKICAgICJyZXBvcnRsYWIucGRmYmFz"
        "ZS5fZm9udGRhdGFfZW5jX21hY3JvbWFuIiwKICAgICJzcWxhbGNoZW15LmRpYWxlY3RzLnNxbGl0ZSIsCl0KCmEgPSBB"
        "bmFseXNpcygKICAgIFsiYXBwLnB5Il0sCiAgICBwYXRoZXg9W10sCiAgICBiaW5hcmllcz1bXSwKICAgIGRhdGFzPWRh"
        "dGFzLAogICAgaGlkZGVuaW1wb3J0cz1oaWRkZW5pbXBvcnRzLAogICAgaG9va3NwYXRoPVtdLAogICAgaG9va3Njb25m"
        "aWc9e30sCiAgICBydW50aW1lX2hvb2tzPVtdLAogICAgZXhjbHVkZXM9ZXhjbHVkZXMsCiAgICB3aW5fbm9fcHJlZmVy"
        "X3JlZGlyZWN0cz1GYWxzZSwKICAgIHdpbl9wcml2YXRlX2Fzc2VtYmxpZXM9RmFsc2UsCiAgICBjaXBoZXI9YmxvY2tf"
        "Y2lwaGVyLAogICAgbm9hcmNoaXZlPUZhbHNlLAopCgpweXogPSBQWVooYS5wdXJlLCBhLnppcHBlZF9kYXRhLCBjaXBo"
        "ZXI9YmxvY2tfY2lwaGVyKQoKZXhlID0gRVhFKAogICAgcHl6LAogICAgYS5zY3JpcHRzLAogICAgYS5iaW5hcmllcywK"
        "ICAgIGEuemlwZmlsZXMsCiAgICBhLmRhdGFzLAogICAgW10sCiAgICBuYW1lPSJGaXJlRW5naW5lZXJBSSIsCiAgICBk"
        "ZWJ1Zz1GYWxzZSwKICAgIGJvb3Rsb2FkZXJfaWdub3JlX3NpZ25hbHM9RmFsc2UsCiAgICBzdHJpcD1GYWxzZSwKICAg"
        "IHVweD1GYWxzZSwgICAgICAgICAgICAgICAgICAgICAjIFVQWCDZitix2YHYuSDYp9it2KrZhdin2YQg2KXZhtiw2KfY"
        "sSDZhdmD2KfZgditINin2YTZgdmK2LHZiNiz2KfYqgogICAgdXB4X2V4Y2x1ZGU9W10sCiAgICBydW50aW1lX3RtcGRp"
        "cj1Ob25lLAogICAgY29uc29sZT1GYWxzZSwgICAgICAgICAgICAgICAgICMg2KrYt9io2YrZgiDZhtin2YHYsNmKINio"
        "2YTYpyDZhtin2YHYsNipINij2YjYp9mF2LEKICAgIGRpc2FibGVfd2luZG93ZWRfdHJhY2ViYWNrPUZhbHNlLAogICAg"
        "YXJndl9lbXVsYXRpb249RmFsc2UsCiAgICB0YXJnZXRfYXJjaD1Ob25lLAogICAgY29kZXNpZ25faWRlbnRpdHk9Tm9u"
        "ZSwKICAgIGVudGl0bGVtZW50c19maWxlPU5vbmUsCiAgICBpY29uPSJhcHBfaWNvbi5pY28iLAopCg=="
    ),
    'build_exe.py': (
        "IiIiCtio2YbYp9ihINmF2YTZgSBGaXJlRW5naW5lZXJBSS5leGUKCiAgICBweXRob24gYnVpbGRfZXhlLnB5CgrZitmB"
        "2K3YtSDYp9mE2YXYqti32YTYqNin2Kog2KPZiNmE2YvYp9iMINmK2LTYutmR2YQg2KfZhNin2K7Yqtio2KfYsdin2KrY"
        "jCDYq9mFINmK2KjZhtmKLiDYp9mE2KjZhtin2KEg2YrYs9iq2LrYsdmCIDItNSDYr9mC2KfYptmCLgoiIiIKCmltcG9y"
        "dCBvcwppbXBvcnQgc2h1dGlsCmltcG9ydCBzdWJwcm9jZXNzCmltcG9ydCBzeXMKCkhFUkUgPSBvcy5wYXRoLmRpcm5h"
        "bWUob3MucGF0aC5hYnNwYXRoKF9fZmlsZV9fKSkKUkVRVUlSRUQgPSBbImFwcC5weSIsICJkYXRhYmFzZS5weSIsICJy"
        "ZXBvcnRzLnB5IiwgImFwcGxvZy5weSIsCiAgICAgICAgICAgICJ0aGVtZS5weSIsICJzZXR0aW5ncy5weSIsICJhcHBf"
        "aWNvbi5pY28iLAogICAgICAgICAgICAiRmlyZUVuZ2luZWVyQUkuc3BlYyJdCgoKZGVmIGZhaWwobXNnKToKICAgIHBy"
        "aW50KGYiXG5b2KrZiNmC2ZHZgV0ge21zZ31cbiIpCiAgICByZXR1cm4gMQoKCmRlZiBtYWluKCk6CiAgICBvcy5jaGRp"
        "cihIRVJFKQogICAgcHJpbnQoIlxuPT09INio2YbYp9ihIEZpcmVFbmdpbmVlckFJLmV4ZSA9PT1cbiIpCgogICAgIyAx"
        "KSDYp9mE2YXZhNmB2KfYqiDYp9mE2KPYs9in2LPZitipCiAgICBtaXNzaW5nID0gW2YgZm9yIGYgaW4gUkVRVUlSRUQg"
        "aWYgbm90IG9zLnBhdGguZXhpc3RzKG9zLnBhdGguam9pbihIRVJFLCBmKSldCiAgICBpZiBtaXNzaW5nOgogICAgICAg"
        "IHJldHVybiBmYWlsKCLZhdmE2YHYp9iqINmG2KfZgti12Kk6ICIgKyAi2IwgIi5qb2luKG1pc3NpbmcpKQogICAgcHJp"
        "bnQoIiAgWzEvNV0g2KfZhNmF2YTZgdin2Kog2KfZhNij2LPYp9iz2YrYqSDZhdmI2KzZiNiv2KkiKQoKICAgICMgMikg"
        "2KfZhNiu2LfZiNi3IOKAlCDYqNiv2YjZhtmH2Kcg2KrYrtix2Kwg2KfZhNi52LHYqNmK2Kkg2YXYrdix2ZHZgdipINmB"
        "2YogUERGCiAgICBmb250ID0gb3MucGF0aC5qb2luKEhFUkUsICJmb250cyIsICJBcmFiaWMudHRmIikKICAgIGlmIG5v"
        "dCBvcy5wYXRoLmV4aXN0cyhmb250KToKICAgICAgICByZXR1cm4gZmFpbCgi2YTYpyDZitmI2KzYryBmb250c1xcQXJh"
        "YmljLnR0ZiDigJQg2LPYqtiu2LHYrCDYqtmC2KfYsdmK2LEgUERGINio2LnYsdio2YrYqSDZhdit2LHZkdmB2KkuIikK"
        "ICAgIHByaW50KCIgIFsyLzVdINin2YTYrti3INin2YTYudix2KjZiiDZhdmI2KzZiNivIikKCiAgICAjIDMpIFB5SW5z"
        "dGFsbGVyCiAgICB0cnk6CiAgICAgICAgaW1wb3J0IFB5SW5zdGFsbGVyICAjIG5vcWE6IEY0MDEKICAgICAgICBwcmlu"
        "dCgiICBbMy81XSBQeUluc3RhbGxlciDZhdir2KjZjtmR2KoiKQogICAgZXhjZXB0IEltcG9ydEVycm9yOgogICAgICAg"
        "IHByaW50KCIgIFszLzVdIFB5SW5zdGFsbGVyINi62YrYsSDZhdir2KjZjtmR2Kog4oCUINis2KfYsdmNINin2YTYqtir"
        "2KjZitiqLi4uIikKICAgICAgICByID0gc3VicHJvY2Vzcy5ydW4oW3N5cy5leGVjdXRhYmxlLCAiLW0iLCAicGlwIiwg"
        "Imluc3RhbGwiLCAicHlpbnN0YWxsZXIiXSkKICAgICAgICBpZiByLnJldHVybmNvZGUgIT0gMDoKICAgICAgICAgICAg"
        "cmV0dXJuIGZhaWwoItmB2LTZhCDYqtir2KjZitiqIFB5SW5zdGFsbGVyLiIpCgogICAgIyA0KSDYp9mE2KfYrtiq2KjY"
        "p9ix2KfYqiDigJQg2YTYpyDZhti62YTZkdmBINmD2YjYr9mL2Kcg2YXZg9iz2YjYsdmL2KcKICAgIGlmIG9zLnBhdGgu"
        "aXNkaXIob3MucGF0aC5qb2luKEhFUkUsICJ0ZXN0cyIpKToKICAgICAgICBwcmludCgiICBbNC81XSDYqti02LrZitmE"
        "INin2YTYp9iu2KrYqNin2LHYp9iqLi4uIikKICAgICAgICByID0gc3VicHJvY2Vzcy5ydW4oW3N5cy5leGVjdXRhYmxl"
        "LCAiLW0iLCAicHl0ZXN0IiwgInRlc3RzIiwgIi1xIl0pCiAgICAgICAgaWYgci5yZXR1cm5jb2RlICE9IDA6CiAgICAg"
        "ICAgICAgIHJldHVybiBmYWlsKCLYp9mE2KfYrtiq2KjYp9ix2KfYqiDYs9mC2LfYqi4g2KPYtdmE2K3Zh9inINmC2KjZ"
        "hCDYp9mE2KrYutmE2YrZgS4iKQogICAgZWxzZToKICAgICAgICBwcmludCgiICBbNC81XSDZhNinINmK2YjYrNivINmF"
        "2KzZhNivIHRlc3RzIOKAlCDYqtiu2LfZjdmRIikKCiAgICAjIDUpINin2YTYqNmG2KfYoQogICAgcHJpbnQoIiAgWzUv"
        "NV0g2KfZhNio2YbYp9ihLi4uICgyLTUg2K/Zgtin2KbZgtiMINmE2Kcg2KrYutmE2YIg2KfZhNmG2KfZgdiw2KkpXG4i"
        "KQogICAgZm9yIGQgaW4gKCJidWlsZCIsICJkaXN0Iik6CiAgICAgICAgc2h1dGlsLnJtdHJlZShvcy5wYXRoLmpvaW4o"
        "SEVSRSwgZCksIGlnbm9yZV9lcnJvcnM9VHJ1ZSkKCiAgICByID0gc3VicHJvY2Vzcy5ydW4oW3N5cy5leGVjdXRhYmxl"
        "LCAiLW0iLCAiUHlJbnN0YWxsZXIiLAogICAgICAgICAgICAgICAgICAgICAgICAiRmlyZUVuZ2luZWVyQUkuc3BlYyIs"
        "ICItLWNsZWFuIiwgIi0tbm9jb25maXJtIl0pCiAgICBpZiByLnJldHVybmNvZGUgIT0gMDoKICAgICAgICByZXR1cm4g"
        "ZmFpbCgi2YHYtNmEINin2YTYqNmG2KfYoS4g2LHYp9is2Lkg2KfZhNix2LPYp9im2YQg2KPYudmE2KfZhy4iKQoKICAg"
        "IGV4ZSA9IG9zLnBhdGguam9pbihIRVJFLCAiZGlzdCIsICJGaXJlRW5naW5lZXJBSS5leGUiKQogICAgaWYgbm90IG9z"
        "LnBhdGguZXhpc3RzKGV4ZSk6CiAgICAgICAgcmV0dXJuIGZhaWwoItin2YbYqtmH2Ykg2KfZhNio2YbYp9ihINmE2YPZ"
        "hiDYp9mE2YXZhNmBINi62YrYsSDZhdmI2KzZiNivLiIpCgogICAgbWIgPSBvcy5wYXRoLmdldHNpemUoZXhlKSAvICgx"
        "MDI0ICogMTAyNCkKICAgIHByaW50KCJcbiIgKyAiPSIgKiA1NSkKICAgIHByaW50KGYiICDYqtmFOiAgZGlzdFxcRmly"
        "ZUVuZ2luZWVyQUkuZXhlICAgKHttYjouMGZ9INmF2YrYutin2KjYp9mK2KopIikKICAgIHByaW50KCI9IiAqIDU1KQog"
        "ICAgcHJpbnQoIlxu2KfZhNiu2LfZiNipINin2YTYqtin2YTZitipOiDYp9mG2YLYsSDYudmE2YrZhyDZhdix2KrZitmG"
        "INmI2KzYsdmR2Kgg2KXYtdiv2KfYsSDYqtmC2LHZitixIFBERiIpCiAgICBwcmludCgi2YTZhNiq2KPZg9ivINmF2YYg"
        "2LjZh9mI2LEg2KfZhNi52LHYqNmK2Kkg2LPZhNmK2YXYqS5cbiIpCiAgICBwcmludCgi2KrZhtio2YrZhzog2YLYryDZ"
        "iti52KrYsdi2IFdpbmRvd3MgU21hcnRTY3JlZW4g2YHZiiDYo9mI2YQg2KrYtNi62YrZhCDigJQiKQogICAgcHJpbnQo"
        "IiAgICAgICDYp9i22LrYtyBcIk1vcmUgaW5mb1wiINir2YUgXCJSdW4gYW55d2F5XCIuINin2YTYs9io2Kgg2KPZhiDY"
        "p9mE2YXZhNmBIikKICAgIHByaW50KCIgICAgICAg2LrZitixINmF2YjZgtmO2ZHYuSDYsdmC2YXZitmL2KfYjCDZiNmH"
        "2LDYpyDYt9io2YrYudmKINmE2YTYqNix2KfZhdisINin2YTYr9in2K7ZhNmK2KkuXG4iKQogICAgcmV0dXJuIDAKCgpp"
        "ZiBfX25hbWVfXyA9PSAiX19tYWluX18iOgogICAgc3lzLmV4aXQobWFpbigpKQo="
    ),
}

# التعديلات مُرمَّزة base64 لتفادي أي لبس في المحارف والاقتباسات
REPORTS_OLD = base64.b64decode("X0JBU0VfRElSID0gb3MucGF0aC5kaXJuYW1lKG9zLnBhdGguYWJzcGF0aChfX2ZpbGVfXykpCkZPTlRTX0RJUiA9IG9zLnBhdGguam9pbihfQkFTRV9ESVIsICJmb250cyIp").decode("utf-8")
REPORTS_NEW = base64.b64decode("ZGVmIF9yZXNvdXJjZV9kaXIoKToKICAgICIiIgogICAg2YXYrNmE2K8g2KfZhNmF2YTZgdin2Kog2KfZhNmF2LHYp9mB2YLYqSAo2KfZhNiu2LfZiNi32Iwg2KfZhNij2YrZgtmI2YbYqSkuCgogICAg2LnZhtivINin2YTYqti02LrZitmEINmF2YYg2KfZhNmD2YjYryDYp9mE2YXYtdiv2LHZijog2YXYrNmE2K8g2YfYsNinINin2YTZhdmE2YEuCiAgICDYudmG2K8g2KfZhNiq2LTYutmK2YQg2YXZhiDZhdmE2YEgZXhlINmF2Y/YrNmF2Y7Zkdi5OiBQeUluc3RhbGxlciDZitmB2YPZkSDYp9mE2YXZhNmB2KfYqiDYpdmE2Ykg2YXYrNmE2K8g2YXYpNmC2KoKICAgINmI2YrYtti5INmF2LPYp9ix2Ycg2YHZiiBzeXMuX01FSVBBU1Mg4oCUINmIX19maWxlX18g2K3ZitmG2YfYpyDZiti02YrYsSDYpdmE2Ykg2YXYs9in2LEg2YjZh9mF2Yog2K/Yp9iu2YQKICAgINin2YTYo9ix2LTZitmB2Iwg2YHZhNinINiq2LXZhNitINmE2YTYqNit2Ksg2LnZhiDYp9mE2K7Yt9mI2LcuCiAgICAiIiIKICAgIG1laXBhc3MgPSBnZXRhdHRyKHN5cywgIl9NRUlQQVNTIiwgTm9uZSkKICAgIGlmIG1laXBhc3M6CiAgICAgICAgcmV0dXJuIG1laXBhc3MKICAgIHJldHVybiBvcy5wYXRoLmRpcm5hbWUob3MucGF0aC5hYnNwYXRoKF9fZmlsZV9fKSkKCgpfQkFTRV9ESVIgPSBfcmVzb3VyY2VfZGlyKCkKRk9OVFNfRElSID0gb3MucGF0aC5qb2luKF9CQVNFX0RJUiwgImZvbnRzIik=").decode("utf-8")
APP_OLD = base64.b64decode("ICAgIGJhc2UgPSBvcy5wYXRoLmRpcm5hbWUob3MucGF0aC5hYnNwYXRoKF9fZmlsZV9fKSkKICAgIGZvciBuYW1lIGluICgiYXBwX2ljb24uaWNvIiwgImFwcF9pY29uLnBuZyIpOg==").decode("utf-8")
APP_NEW = base64.b64decode("ICAgICMgc3lzLl9NRUlQQVNTOiDZhdis2YTYryDYp9mE2YHZg9mRINin2YTZhdik2YLYqiDYrdmK2YYg2YrYudmF2YQg2KfZhNio2LHZhtin2YXYrCDZg9mF2YTZgSBleGUg2YXZj9is2YXZjtmR2LkuCiAgICBiYXNlID0gZ2V0YXR0cihzeXMsICJfTUVJUEFTUyIsIE5vbmUpIG9yIG9zLnBhdGguZGlybmFtZShvcy5wYXRoLmFic3BhdGgoX19maWxlX18pKQogICAgZm9yIG5hbWUgaW4gKCJhcHBfaWNvbi5pY28iLCAiYXBwX2ljb24ucG5nIik6").decode("utf-8")


def patch(path, old, new, marker, label):
    """يطبّق تعديلًا مرة واحدة، مع نسخة احتياطية."""
    name = os.path.basename(path)
    if not os.path.exists(path):
        print("  [تحذير] %s غير موجود - تخطي" % name)
        return
    src = open(path, encoding="utf-8").read()
    if marker in src:
        print("  [تخطي]  %s معدل مسبقا" % name)
        return
    if old not in src:
        print("  [تحذير] لم يطابق النص في %s - عدله يدويا" % name)
        return
    shutil.copy2(path, path + ".bak")
    src = src.replace(old, new, 1)
    if name == "reports.py" and "\nimport sys" not in src.split("def _resource_dir")[0]:
        src = src.replace("import os", "import os\nimport sys", 1)
    open(path, "w", encoding="utf-8").write(src)
    print("  [اصلاح] " + label)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(os.path.join(here, "app.py")):
        print("\n[خطأ] لا يوجد app.py هنا.")
        print("      ضع install_build.py في C:\\Projects\\FireEngineerAI.")
        return 1

    print("\n=== تركيب أدوات التغليف ===\n")

    for fname, blob in FILES.items():
        dest = os.path.join(here, fname)
        with open(dest, "wb") as fh:
            fh.write(base64.b64decode(blob))
        print("  [ملف]   %s  (%d بايت)" % (fname, os.path.getsize(dest)))

    print()
    patch(os.path.join(here, "reports.py"), REPORTS_OLD, REPORTS_NEW,
          "_resource_dir", "reports.py - الخطوط تعمل داخل exe")
    patch(os.path.join(here, "app.py"), APP_OLD, APP_NEW,
          "_MEIPASS", "app.py - الأيقونة تعمل داخل exe")

    if not os.path.exists(os.path.join(here, "fonts", "Arabic.ttf")):
        print("\n  [تحذير] fonts\\Arabic.ttf غير موجود - تقارير PDF ستخرج محرفة.")

    for c in (os.path.join(here, "__pycache__"),
              os.path.join(here, "tests", "__pycache__")):
        shutil.rmtree(c, ignore_errors=True)

    print("\n=== تم. للبناء شغل: ===\n")
    print("    python build_exe.py\n")
    print("يستغرق 2-5 دقائق. الناتج: dist\\FireEngineerAI.exe\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
