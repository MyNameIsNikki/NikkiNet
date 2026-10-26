#!/usr/bin/env python3
"""Rebrand a sing-box-for-android checkout as NikkiNet Mobile.

Only the applicationId, app label and version are changed.  The Java/Kotlin
package names are intentionally left untouched: libbox.aar is generated with
the original package and renaming imports would break the build.
"""
import os
import re
import sys

root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
app = os.path.join(root, "app")
gradle = os.path.join(app, "build.gradle.kts")

if not os.path.isfile(gradle):
    sys.exit("not a sing-box-for-android checkout: %s" % root)

text = open(gradle, encoding="utf-8").read()
text = text.replace(
    'applicationId = "io.nekohasekai.sfa"',
    'applicationId = "com.nikkinet.mobile"',
)
text = text.replace(
    'base.archivesName.set("SFA-${versionName}")',
    'base.archivesName.set("NikkiNet-Mobile-${versionName}")',
)
open(gradle, "w", encoding="utf-8").write(text)

# App label in every values*/strings.xml that defines app_name.
res = os.path.join(app, "src", "main", "res")
for name in os.listdir(res):
    if not name.startswith("values"):
        continue
    strings = os.path.join(res, name, "strings.xml")
    if not os.path.isfile(strings):
        continue
    text = open(strings, encoding="utf-8").read()
    text = re.sub(
        r'(<string\s+name="app_name"[^>]*>).*?(</string>)',
        r"\1NikkiNet\2",
        text,
        flags=re.S,
    )
    open(strings, "w", encoding="utf-8").write(text)

version_file = os.path.join(root, "version.properties")
if os.path.isfile(version_file):
    text = open(version_file, encoding="utf-8").read()
    text = re.sub(r"^VERSION_CODE=.*$", "VERSION_CODE=1", text, flags=re.M)
    text = re.sub(r"^VERSION_NAME=.*$", "VERSION_NAME=1.0.0", text, flags=re.M)
    open(version_file, "w", encoding="utf-8").write(text)

print("rebranded", root)
