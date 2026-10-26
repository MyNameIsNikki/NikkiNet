# NikkiNet Mobile (Android)

Полноценный Android VPN-клиент на базе **sing-box** (SFA).

## Почему сборка в GitHub Actions

В этом проекте нет локального Android SDK/NDK, поэтому APK собирается на
`ubuntu-latest` в GitHub Actions:

1. Клонируется `SagerNet/sing-box` версии `v1.14.4` вместе с Android-клиентом.
2. Из исходников собирается `libbox.aar` (gomobile + NDK).
3. Приложение переименовывается в **NikkiNet** (`mobile/brand.py`):
   - `applicationId` → `com.nikkinet.mobile`;
   - название → `NikkiNet`;
   - версия → `1.0.0`.
4. Собирается подписанный release APK.
5. APK публикуется в GitHub Release `mobile-v1.0.0` и в артефактах workflow.

## Запуск сборки

GitHub → Actions → **Build Android APK** → Run workflow.

Готовый файл: `NikkiNet-Mobile-1.0.0.apk`.

## Что внутри

- полноценный VPN через `VpnService` и sing-box;
- поддержка vless / vmess / trojan / shadowsocks / hysteria2 / tuic;
- импорт конфигурации и подписок;
- тёмная тема (стандартная тема SFA; кастомный киберпанк-UI — следующий этап).

## Лицензия

Клиент основан на SFA (GPL-3.0-or-later). Исходники sing-box/SFA доступны
на GitHub; изменения NikkiNet находятся в этом репозитории.
