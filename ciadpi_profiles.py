"""ciadpi_profiles — система профилей настроек (v2.0.5).

⭐ user: «система профилей, где профиль можно выбрать, создать и
назвать, чтобы в нём сохранялись все текущие настройки режимов
и выбранный движок с параметрами — для переключения между
сетями/местами на ноутбуке».

Профиль хранит:
  engine          — выбранный движок: byedpi|nfqws|snimod
  bridge          — DNS-мост: on|off (самостоятельный режим)
  byedpi_params   — строка параметров byedpi
  nfqws_params    — строка параметров nfqws (формат zapret)
  snimod_hosts    — список хостов SNI case-mod
  proxy_enabled / proxy_mode / proxy_host / proxy_port
  auto_disable_proxy, we_changed_proxy
  created_at / updated_at / note

Файлы: ~/.config/ciadpi/profiles/<имя>.json
Активный профиль: ключ "active_profile" в ~/.config/ciadpi/profiles/.active

Переключение профиля (apply_profile):
  1) остановить текущие движки (кроме целевых из профиля)
  2) загрузить настройки в конфиги движков и трея
  3) поднять движок профиля + мост, если bridge=on
"""
import json
import re
import time
from pathlib import Path


class ProfileManager:
    """Создание/загрузка/применение профилей ciadpi."""

    def __init__(self):
        self.home = Path.home()
        self.profiles_dir = (self.home / '.config' / 'ciadpi' / 'profiles')
        self.active_marker = self.profiles_dir / '.active'
        self.tray_config = self.home / '.config' / 'ciadpi' / 'config.json'

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

    # ---------------- создание/сохранение ----------------

    def capture_current(self, name, note=''):
        """Снять СНИМОК текущих настроек в профиль <name>.

        Собирает: выбранный движок + параметры всех движков +
        состояние моста + настройки прокси.
        """
        name = self._safe_name(name)
        if not name:
            return False, 'имя профиля: 1-32 символа (буквы, цифры, -_)'

        engine = 'byedpi'
        params = {}
        cfg = {}
        try:
            cfg = json.loads(self.tray_config.read_text(encoding='utf-8'))
            engine = cfg.get('engine', 'byedpi')
        except Exception:
            pass

        # параметры движков — из их собственных конфигов
        try:
            nf = (self.home / '.config' / 'ciadpi' / 'nfqws.json')
            params['nfqws_params'] = json.loads(
                nf.read_text(encoding='utf-8')).get('params', '')
        except Exception:
            params['nfqws_params'] = ''
        try:
            sf = (self.home / '.config' / 'ciadpi' / 'snimod.json')
            params['snimod_hosts'] = json.loads(
                sf.read_text(encoding='utf-8')).get('hosts', [])
        except Exception:
            params['snimod_hosts'] = []

        # мост активен?
        bridge = 'off'
        try:
            from ciadpi_enginectl import is_active
            if is_active('bridge'):
                bridge = 'on'
        except Exception:
            pass

        profile = {
            'engine': engine,
            'bridge': bridge,
            'byedpi_params': (cfg or {}).get('current_params',
                                             (cfg or {}).get('params', '')),
            'proxy_enabled': (cfg or {}).get('proxy_enabled', False),
            'proxy_mode': (cfg or {}).get('proxy_mode', 'none'),
            'proxy_host': (cfg or {}).get('proxy_host', '127.0.0.1'),
            'proxy_port': (cfg or {}).get('proxy_port', '1080'),
            'auto_disable_proxy': (cfg or {}).get('auto_disable_proxy', False),
            'created_at': time.strftime('%Y-%m-%d %H:%M'),
            'updated_at': time.strftime('%Y-%m-%d %H:%M'),
            'note': (note or '')[:200],
            **params,
        }
        f = self.profiles_dir / f'{name}.json'
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(profile, indent=2, ensure_ascii=False),
                     encoding='utf-8')
        return True, f'профиль «{name}» сохранён ({engine} + мост:{bridge})'

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
        """Применить профиль: записать конфиги + поднять движок/мост.

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
            from pathlib import Path as _P
            import sys
            sys.path.insert(0, str(_P(__file__).resolve().parent))
            import ciadpi_enginectl as ec

        msgs = []
        engine = data.get('engine', 'byedpi')

        # 1) конфиг трея: движок + прокси
        try:
            cfg = json.loads(self.tray_config.read_text(encoding='utf-8'))
        except Exception:
            cfg = {}
        cfg.update({
            'engine': engine,
            'current_params': data.get('byedpi_params',
                                       cfg.get('current_params', '')),
            'params': data.get('byedpi_params', cfg.get('params', '')),
            'proxy_enabled': data.get('proxy_enabled', False),
            'proxy_mode': data.get('proxy_mode', 'none'),
            'proxy_host': data.get('proxy_host', '127.0.0.1'),
            'proxy_port': data.get('proxy_port', '1080'),
            'auto_disable_proxy': data.get('auto_disable_proxy', False),
        })
        self.tray_config.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')

        # 2) конфиги движков
        try:
            nf = (self.home / '.config' / 'ciadpi' / 'nfqws.json')
            ncfg = json.loads(nf.read_text(encoding='utf-8')) \
                if nf.exists() else {}
            ncfg['params'] = data.get('nfqws_params', '')
            nf.write_text(json.dumps(ncfg, indent=2, ensure_ascii=False),
                          encoding='utf-8')
        except Exception as e:
            msgs.append(f'nfqws.json: {e}')
        try:
            sf = (self.home / '.config' / 'ciadpi' / 'snimod.json')
            scfg = json.loads(sf.read_text(encoding='utf-8')) \
                if sf.exists() else {}
            if data.get('snimod_hosts'):
                scfg['hosts'] = data['snimod_hosts']
            sf.write_text(json.dumps(scfg, indent=2, ensure_ascii=False),
                          encoding='utf-8')
        except Exception as e:
            msgs.append(f'snimod.json: {e}')

        # 3) остановить всё, что не входит в профиль
        for eng in ('byedpi', 'nfqws', 'snimod'):
            if eng != engine:
                ec.stop_engine(eng)
        if data.get('bridge') != 'on':
            ec.stop_bridge()

        # 4) поднять мост (если профиль хочет) и движок
        if data.get('bridge') == 'on':
            ok_b, msg_b = ec.start_bridge()
            msgs.append(msg_b)
        ok_e, msg_e = ec.start_engine(engine)
        msgs.append(msg_e)

        self._set_active(name)
        final_ok = ok_e
        return final_ok, f'профиль «{name}»: ' + '; '.join(m for m in msgs if m)


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
    print('usage: ciadpi_profiles.py list | save <имя> [заметка] | '
          'apply <имя> | del <имя>')
    sys.exit(1)
