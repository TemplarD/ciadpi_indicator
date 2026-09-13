"""ciadpi_profiles — система профилей настроек (v2.0.5 → v2.0.13).

⭐ user: «профили должны нас переключать между разными состояниями
со всей памятью каждого профиля по параметрам применённым и
изменённым, последним, избранным; белый список — отдельно для
каждого профиля; настройки приложения — тоже к профилю».

Профиль хранит ПОЛНЫЙ снимок состояния приложения:
  engine          — выбранный режим: byedpi|nfqws|snimod|bridge
  bridge          — DNS-мост: on|off (engine='bridge' = мост как режим)
  byedpi_params   — строка параметров byedpi
  nfqws_params    — строка параметров nfqws (формат zapret)
  snimod_hosts    — список хостов SNI case-mod
  params_recent   — «Последние» параметры (по режимам)
  params_favorites— «Избранное» (по режимам)
  whitelist       — весь белый список (whitelist.json)
  app_prefs       — настройки приложения (уведомления, автозапуск)
  lang            — язык интерфейса (ru|en)
  proxy_enabled / proxy_mode / proxy_host / proxy_port
  auto_disable_proxy, we_changed_proxy
  created_at / updated_at / note

Файлы: ~/.config/ciadpi/profiles/<имя>.json
Активный профиль: ключ в ~/.config/ciadpi/profiles/.active

Переключение (apply_profile):
  1) остановить текущие движки (кроме целевых из профиля)
  2) загрузить ВСЕ настройки в конфиги движков/трея
  3) поднять движок профиля + мост, если bridge=on
  4) вызывающий должен перечитать config.json в память трея

Синхронизация (sync_active): пока профиль активен, его «память»
(параметры/последние/избранное/белый список/настройки приложения)
обновляется автоматически при каждом изменении.
"""
import json
import re
import time
from pathlib import Path


class ProfileManager:
    """Создание/загрузка/применение/синк профилей ciadpi."""

    def __init__(self):
        self.home = Path.home()
        self.profiles_dir = (self.home / '.config' / 'ciadpi' / 'profiles')
        self.active_marker = self.profiles_dir / '.active'
        self.tray_config = self.home / '.config' / 'ciadpi' / 'config.json'
        self.cfg_dir = self.home / '.config' / 'ciadpi'

    # ---------------- имена/списки ----------------

    @staticmethod
    def _safe_name(name):
        """Имя профиля: почти любые видимые символы, 1-32, без путевых."""
        name = (name or '').strip()
        if not name or len(name) > 32:
            return None
        # запретим только опасное для путей/CLI и невидимые символы
        if re.search(r'[/\\:*?"<>|\x00-\x1f]', name):
            return None
        if name.startswith('.'):
            return None
        return name

    def list_profiles(self):
        """Список (имя, метаданные) отсортированный по updated_at."""
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        out = []
        for f in sorted(self.profiles_dir.glob('*.json')):
            try:
                meta = json.loads(f.read_text(encoding='utf-8'))
                out.append((f.stem, meta))
            except Exception:
                out.append((f.stem, {'error': 'битый профиль'}))
        return out

    def active_profile(self):
        """Имя активного профиля или None."""
        try:
            return self.active_marker.read_text(encoding='utf-8').strip() \
                or None
        except Exception:
            return None

    def _set_active(self, name):
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        if name:
            self.active_marker.write_text(name, encoding='utf-8')
        else:
            self.active_marker.unlink(missing_ok=True)

    # ---------------- чтение состояния ----------------

    def _read_json(self, path, default):
        """Прочитать json-файл с fallback."""
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                if isinstance(default, dict):
                    merged = dict(default)
                    merged.update(data)
                    return merged
                return data
        except Exception:
            pass
        return default

    def _collect_state(self, note=None):
        """Собрать ПОЛНЫЙ снимок текущего состояния всех конфигов."""
        cfg = self._read_json(self.tray_config, {})

        engine = cfg.get('engine', 'byedpi')
        if cfg.get('bridge_mode'):
            engine = 'bridge'      # мост — самостоятельный режим

        nfqws_params = ''
        try:
            nfqws_params = self._read_json(
                self.cfg_dir / 'nfqws.json', {}).get('params', '')
        except Exception:
            pass
        snimod_hosts = []
        try:
            snimod_hosts = self._read_json(
                self.cfg_dir / 'snimod.json', {}).get('hosts', [])
        except Exception:
            pass

        # мост активен?
        bridge = 'off'
        try:
            from ciadpi_enginectl import is_active
            if is_active('bridge'):
                bridge = 'on'
        except Exception:
            pass

        # ⭐ v2.0.13: память параметров (последние + избранное)
        params_recent = cfg.get('params_recent') or {}
        params_favorites = cfg.get('params_favorites') or {}

        # ⭐ v2.0.13: белый список целиком
        whitelist = self._read_json(self.cfg_dir / 'whitelist.json', {})

        # ⭐ v2.0.13: настройки приложения
        app_prefs = self._read_json(self.cfg_dir / 'app_prefs.json', {})

        # ⭐ v2.0.13: язык интерфейса
        lang = 'ru'
        try:
            lang = (self.cfg_dir / 'ui_language').read_text(
                encoding='utf-8').strip() or 'ru'
        except Exception:
            pass

        state = {
            'engine': engine,
            'bridge': bridge,
            'byedpi_params': cfg.get('current_params',
                                     cfg.get('params', '')),
            'nfqws_params': nfqws_params,
            'snimod_hosts': snimod_hosts,
            'params_recent': params_recent,
            'params_favorites': params_favorites,
            'whitelist': whitelist,
            'app_prefs': app_prefs,
            'lang': lang,
            'proxy_enabled': cfg.get('proxy_enabled', False),
            'proxy_mode': cfg.get('proxy_mode', 'none'),
            'proxy_host': cfg.get('proxy_host', '127.0.0.1'),
            'proxy_port': cfg.get('proxy_port', '1080'),
            'auto_disable_proxy': cfg.get('auto_disable_proxy', False),
            'updated_at': time.strftime('%Y-%m-%d %H:%M'),
        }
        if note is not None:
            state['note'] = (note or '')[:200]
        return state

    def _write_profile(self, name, state):
        f = self.profiles_dir / f'{name}.json'
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(state, indent=2, ensure_ascii=False),
                     encoding='utf-8')
        return f

    # ---------------- создание/сохранение ----------------

    def capture_current(self, name, note='', make_active=True):
        """Снять СНИМОК текущих настроек в профиль <name>.

        ⭐ v2.0.13: полный снимок — режимы, параметры, недавние,
        избранное, белый список, настройки приложения, язык.
        make_active=True — сохранённый профиль сразу становится
        активным (дальше все изменения пишутся в него).
        """
        name = self._safe_name(name)
        if not name:
            return False, 'имя профиля: 1-32 символа (буквы, цифры, -_)'

        state = self._collect_state(note=note)
        # created_at: сохранить при перезаписи существующего профиля
        old_ok, old = self.load_profile(name)
        if old_ok and isinstance(old, dict) and old.get('created_at'):
            state['created_at'] = old['created_at']
        else:
            state['created_at'] = time.strftime('%Y-%m-%d %H:%M')

        self._write_profile(name, state)
        if make_active:
            self._set_active(name)
        return True, (f'профиль «{name}» сохранён и активирован '
                      f'({state["engine"]} + мост:{state["bridge"]}, '
                      f'память: недавние/избранное/белый список/'
                      f'настройки)')

    # ---------------- синк активного профиля ----------------

    def sync_active(self, fields=None):
        """⭐ v2.0.13: обновить «память» АКТИВНОГО профиля текущим
        состоянием.

        Вызывается при каждом изменении: параметры применены,
        M+/M−, белый список сохранён, настройки приложения
        изменены. fields=None — синк всего; иначе список ключей
        ('params_recent', 'params_favorites', 'whitelist',
        'app_prefs', 'lang', 'byedpi_params', 'nfqws_params',
        'snimod_hosts', 'engine', 'bridge', 'proxy_*').
        """
        name = self.active_profile()
        if not name:
            return False    # нет активного профиля — нечего синкать
        ok, data = self.load_profile(name)
        if not ok or not isinstance(data, dict):
            return False
        state = self._collect_state()
        if fields:
            for k in fields:
                if k in state:
                    data[k] = state[k]
        else:
            # всё, кроме дат создания/заметки
            for k, v in state.items():
                data[k] = v
        data['updated_at'] = time.strftime('%Y-%m-%d %H:%M')
        self._write_profile(name, data)
        return True

    # ---------------- загрузка/удаление ----------------

    def load_profile(self, name):
        """Прочитать профиль (без применения). Возвращает (ok, dict|str)."""
        name = self._safe_name(name)
        if not name:
            return False, 'недопустимое имя'
        f = self.profiles_dir / f'{name}.json'
        if not f.exists():
            return False, f'профиль «{name}» не найден'
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                return False, 'профиль бит: не словарь'
            return True, data
        except Exception as e:
            return False, f'профиль бит: {e}'

    def delete_profile(self, name):
        name = self._safe_name(name)
        if not name:
            return False, 'недопустимое имя'
        f = self.profiles_dir / f'{name}.json'
        if not f.exists():
            return False, f'профиль «{name}» не найден'
        f.unlink()
        if self.active_profile() == name:
            self._set_active(None)
        return True, f'профиль «{name}» удалён'

    # ---------------- применение ----------------

    def apply_profile(self, name):
        """Применить профиль: записать ВСЕ конфиги + поднять движок/мост.

        ⭐ v2.0.13: пишет и «память» (недавние, избранное, белый
        список, настройки приложения, язык). Вызывающий ОБЯЗАН
        после этого перечитать config.json в память трея
        (self.current_params = self.load_config()) и пересобрать
        меню — иначе выбор режима останется прежним (баг v2.0.12).
        Возвращает (ok, message). Вызывать ИЗ ФОНОВОГО ПОТОКА.
        """
        ok, data = self.load_profile(name)
        if not ok:
            return ok, data
        if not isinstance(data, dict):
            return False, 'профиль бит: не словарь'
        try:
            import ciadpi_enginectl as ec
        except ImportError:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import ciadpi_enginectl as ec

        msgs = []
        engine = data.get('engine', 'byedpi')
        if engine not in ('byedpi', 'nfqws', 'snimod', 'bridge'):
            engine = 'byedpi'

        # 1) конфиг трея: движок + прокси + память параметров
        cfg = self._read_json(self.tray_config, {})
        cfg.update({
            'engine': engine if engine != 'bridge' else 'byedpi',
            'bridge_mode': engine == 'bridge',
            'current_params': data.get('byedpi_params',
                                       cfg.get('current_params', '')),
            'params': data.get('byedpi_params', cfg.get('params', '')),
            'proxy_enabled': data.get('proxy_enabled', False),
            'proxy_mode': data.get('proxy_mode', 'none'),
            'proxy_host': data.get('proxy_host', '127.0.0.1'),
            'proxy_port': data.get('proxy_port', '1080'),
            'auto_disable_proxy': data.get('auto_disable_proxy', False),
        })
        # ⭐ память: недавние + избранное (если в профиле есть)
        if isinstance(data.get('params_recent'), dict):
            cfg['params_recent'] = data['params_recent']
        if isinstance(data.get('params_favorites'), dict):
            cfg['params_favorites'] = data['params_favorites']
        self.tray_config.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')

        # 2) конфиги движков
        try:
            nf = self.cfg_dir / 'nfqws.json'
            ncfg = self._read_json(nf, {})
            ncfg['params'] = data.get('nfqws_params', '')
            nf.write_text(json.dumps(ncfg, indent=2, ensure_ascii=False),
                          encoding='utf-8')
        except Exception as e:
            msgs.append(f'nfqws.json: {e}')
        try:
            sf = self.cfg_dir / 'snimod.json'
            scfg = self._read_json(sf, {})
            if data.get('snimod_hosts'):
                scfg['hosts'] = data['snimod_hosts']
            sf.write_text(json.dumps(scfg, indent=2, ensure_ascii=False),
                          encoding='utf-8')
        except Exception as e:
            msgs.append(f'snimod.json: {e}')

        # 3) ⭐ белый список профиля
        if isinstance(data.get('whitelist'), dict) and \
                data['whitelist']:
            try:
                wf = self.cfg_dir / 'whitelist.json'
                wl = self._read_json(wf, {})
                wl.update(data['whitelist'])
                wf.write_text(json.dumps(wl, indent=2,
                                         ensure_ascii=False),
                              encoding='utf-8')
            except Exception as e:
                msgs.append(f'whitelist.json: {e}')

        # 4) ⭐ настройки приложения профиля
        if isinstance(data.get('app_prefs'), dict) and \
                data['app_prefs']:
            try:
                pf = self.cfg_dir / 'app_prefs.json'
                pf.write_text(json.dumps(data['app_prefs'], indent=2,
                                         ensure_ascii=False),
                              encoding='utf-8')
            except Exception as e:
                msgs.append(f'app_prefs.json: {e}')

        # 5) ⭐ язык интерфейса профиля
        if data.get('lang') in ('ru', 'en'):
            try:
                (self.cfg_dir / 'ui_language').write_text(
                    data['lang'], encoding='utf-8')
            except Exception as e:
                msgs.append(f'ui_language: {e}')

        # 6) остановить всё, что не входит в профиль
        for eng in ('byedpi', 'nfqws', 'snimod'):
            if eng != engine:
                ec.stop_engine(eng)
        if data.get('bridge') != 'on' and engine != 'bridge':
            ec.stop_bridge()

        # 7) поднять мост (если профиль хочет) и движок
        if data.get('bridge') == 'on' or engine == 'bridge':
            ok_b, msg_b = ec.start_bridge()
            if msg_b:
                msgs.append(msg_b)
        if engine != 'bridge':
            ok_e, msg_e = ec.start_engine(engine)
            msgs.append(msg_e)
        else:
            ok_e = True

        self._set_active(name)
        final_ok = ok_e
        return final_ok, f'профиль «{name}»: ' + '; '.join(
            m for m in msgs if m)


# ---------------- CLI ----------------

if __name__ == '__main__':
    import sys
    pm = ProfileManager()
    if len(sys.argv) >= 2 and sys.argv[1] == 'list':
        active = pm.active_profile()
        for name, meta in pm.list_profiles():
            mark = ' ← активный' if name == active else ''
            print(f"{name}{mark}  "
                  f"[{meta.get('engine', '?')} + мост:{meta.get('bridge', '?')}]"
                  f"  {meta.get('note', '')}")
        sys.exit(0)
    if len(sys.argv) >= 3 and sys.argv[1] == 'save':
        note = ' '.join(sys.argv[3:]) or ''
        ok, msg = pm.capture_current(sys.argv[2], note)
        print(('OK ' if ok else 'FAIL ') + str(msg))
        sys.exit(0 if ok else 1)
    if len(sys.argv) >= 3 and sys.argv[1] == 'apply':
        ok, msg = pm.apply_profile(sys.argv[2])
        print(('OK ' if ok else 'FAIL ') + msg)
        sys.exit(0 if ok else 1)
    if len(sys.argv) >= 3 and sys.argv[1] == 'del':
        ok, msg = pm.delete_profile(sys.argv[2])
        print(('OK ' if ok else 'FAIL ') + msg)
        sys.exit(0 if ok else 1)
    if len(sys.argv) >= 2 and sys.argv[1] == 'sync':
        ok = pm.sync_active()
        print('OK синк активного профиля' if ok
              else 'FAIL нет активного профиля')
        sys.exit(0 if ok else 1)
    print('usage: ciadpi_profiles.py list | save <имя> [заметка] | '
          'apply <имя> | del <имя> | sync')
    sys.exit(1)
