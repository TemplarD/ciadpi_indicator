### CIADPI Complete Solution

![GitHub](https://img.shields.io/badge/platform-linux-blue)
![GitHub](https://img.shields.io/badge/ubuntu-20.04%2B-orange)
![GitHub](https://img.shields.io/badge/debian%2011%20%7C%2012%20%7C%2013-green)
![GitHub](https://img.shields.io/badge/arch%20linux-supported-1793D1)
![License](https://img.shields.io/badge/License-MIT-blue.svg) 

Комплексный обход DPI с системным треем. Четыре режима обхода, профили настроек, поиск стратегий — всё в одном индикаторе.

#### Режимы обхода (v2.0.6)

| Режим | Как работает | Когда выбрать |
|---|---|---|
| 🛡️ **byedpi** | Локальный SOCKS5-прокси ([hufrea/byedpi](https://github.com/hufrea/byedpi)); обходят только приложения, указывающие прокси | Точный контроль: только браузер/отдельные приложения |
| ⚡ **nfqws** | Десинки zapret (NFQUEUE): fake/split/disorder/ipfrag/multisplit/tamper — правит пакеты ВСЕХ приложений | Самый мощный: SNI- и IP-фильтры прова |
| 🔠 **snimod** | Наша разработка: поднимает РЕГИСТР SNI (`www.youtube.com` → `WWW.YOUTUBE.COM`) — фильтр прова регистрозависим, серверу нет (RFC 6066) | Пров режет по подстроке SNI в нижнем регистре |
| 🌉 **DNS-мост** | Локальный DoT-резолвер 127.0.0.1:53 → 1.1.1.1:853 + nft-перехват DNS. Чинит NXDOMAIN-подмену DNS прова | Пров подменяет/ломает DNS; работает сам по себе или ВМЕСТЕ с любым движком |

Управление: трей → «Режимы обхода» — radio-выбор режима, кнопки ▶ Запустить / ⏹ Остановить / ↻ Перезапустить действуют **на выбранный режим**. Повторный запуск активного — no-op. Запуск одного режима автоматически гасит остальные (взаимоисключаемость).

#### Профили (v2.0.6)

Трей → «🗂 Профили…» — наборы настроек для разных сетей:
- **Сохранить текущее как…** — снимок: выбранный режим + параметры byedpi/nfqws + хосты snimod + состояние моста + настройки прокси;
- **Применить** — поднимает сохранённое целиком (гасит лишнее, стартует нужное);
- профили живут в `~/.config/ciadpi/profiles/`, активный помечен.

Сценарий: настроил дома «Дом (nfqws+мост)» → в кафе одним кликом «Кофейня (только мост)».

#### Прочее

- 🧪 **Поиск стратегий** — перебор параметров (byedpi на тест-порту / nfqws через реальный сервис), «до нахождения» без лимита, gentle-паузы против hold-down прова, история 200 прогонов
- 🎛️ **Конструктор параметров** — каждый флаг byedpi со слайдером и подсказкой
- 🔔 **Уведомления** — отключаемые по категориям; 🌐 **RU/EN**
- ⬆️ **Обновление byedpi** из git без переустановки
- 🔌 **Режимы прокси** — системный / PAC / local-only (система не трогается)
- 🚀 **Автозапуск трея** — опционален; сервис сам не стартует никогда

#### Supported Systems

- Ubuntu 20.04+, Debian 11/12/13 (trixie), Linux Mint 20+
- **Arch Linux / Manjaro** — отдельный установщик
- Любой systemd-дистрибутив с nftables

## 📦 Установка

### Вариант 1: Пакеты (рекомендуется)

**Debian / Ubuntu / Mint (.deb):**

```bash
# Скачать последний релиз со страницы Releases и установить:
sudo apt install ./ciadpi-indicator_<версия>_all.deb
```

Сборка из исходников:

```bash
git clone https://github.com/TemplarD/ciadpi_indicator.git
cd ciadpi_indicator/packaging
./build_deb.sh            # → dist/ciadpi-indicator_<версия>_all.deb
sudo apt install ../dist/ciadpi-indicator_<версия>_all.deb
```

**Arch Linux / Manjaro (PKGBUILD):**

```bash
git clone https://github.com/TemplarD/ciadpi_indicator.git
cd ciadpi_indicator/packaging
makepkg -si
```

### Вариант 2: Полный скрипт (byedpi + индикатор)

```bash
git clone https://github.com/TemplarD/ciadpi_indicator.git
cd ciadpi_indicator
./install_ciadpi_complete.sh       # Debian/Ubuntu/Mint — спросит пароль ОДИН раз
./install_ciadpi_arch.sh            # Arch/Manjaro
```

Скрипт ставит byedpi (~/byedpi, собирает из git), индикатор в `~/.local/bin`, .desktop, sudoers-привилегии (безпарольные systemctl/nft/tee для ciadpi-юнитов). Третьи движки:
- **nfqws** — ставится вместе с zapret в `~/zapret` (скрипт качает/собирает);
- **snimod** — собирается из `snimod/` (`make`); установщик копирует бинарник в `~/.local/bin/snimod/bin/`;
- **DNS-мост** — чистый Python (`ciadpi_dotbridge.py`), требований нет.

### Удаление

```bash
./uninstall_ciadpi_complete.sh      # или uninstall_ciadpi_arch.sh
```

Вычищает: все 3 сервиса + мост (stop/disable/юнит-файлы), nft-таблицы `ciadpi`/`ciadpi_snimod`/`ciadpi_bridge` (иначе dns_dnat-хвост ронял DNS после удаления!), sudoers/polkit, откат resolv.conf из снапшота, восстановление системного прокси из бэкапа, скрипты из `~/.local/bin`. Конфиги `~/.config/ciadpi` и `~/byedpi` — спрашивает отдельно (y/N).

## 🧰 Диагностика

```bash
python3 ~/.local/bin/ciadpi_enginectl.py status          # состояние всех режимов
python3 ~/.local/bin/ciadpi_enginectl.py start bridge   # поднять только DNS-мост
python3 ~/.local/bin/ciadpi_profiles.py list            # профили
python3 ~/.local/bin/diagnose_ciadpi.py                 # полная диагностика
journalctl -u ciadpi-snimod -f                          # лог движка №3 (решения по SNI)
```

## ⚠️ Заметки

- **Провайдеры разные**: snimod работает там, где фильтр режет по регистрозависимой подстроке SNI. Если пров распознаёт и uppercase — используй nfqws (десинки ломают сигнатуру сильнее) или их комбинацию; DNS-мост нужен почти всегда, если пров NXDOMAIN-ит домены.
- Сетевые тесты заблокированных хостов лучше не долбить часто — провайдеры вводят hold-down на всю линию.
- Никакие пароли не хранятся; sudoers даёт только точные команды для ciadpi-юнитов.

## License

MIT
