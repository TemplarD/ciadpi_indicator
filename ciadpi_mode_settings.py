"""ciadpi_mode_settings — окно «Настройки режима» (v2.0.7).

⭐ user-проект: «систематизируем настройки каждого режима — ручная
строка, строка-дефолт, 4 последних использованных (по режиму,
вытесняют друг друга), конструктор и поиск стратегии для ВЫБРАННОГО
режима — в одном окне с вкладками; строка ввода подхватывает
выбранное/найденное из вкладок и обновляется своевременно».

Архитектура:
  * ОДНО окно (синглтон) с Gtk.Notebook: вкладки
    [Параметры] [Конструктор] [Поиск стратегии].
  * Содержимое каждой вкладки строится ПОД ВЫБРАННЫЙ РЕЖИМ
    (byedpi/nfqws/snimod/bridge): свои примеры, свой поиск,
    свои «последние».
  * История «последних параметров» — в config.json:
    params_recent.<mode> = [строка×4], LRU, дефолт не вытесняется
    (он отдельной кнопкой).
  * Строка параметров (entry) — ОБЩАЯ ДЛЯ ВСЕХ ВКЛАДОК:
    конструктор пишет в неё live, «Применить» из поиска — тоже.
  * Поиск стратегии: по кнопке, в фоне, БЕЗ set_sensitive(False)
    на всём окне (блокируются только свои кнопки), pulse — таймером,
    который чистится при закрытии. Зависание исключено by design:
    каждый колбэк в try/except, диалог закрывается response-ом.

Вызывается из меню трея → «⚙ Настройки режима…».
"""
import json
import time
from pathlib import Path

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib


MODES = ('byedpi', 'nfqws', 'snimod', 'bridge')

MODE_TITLES = {
    'byedpi': 'byedpi — SOCKS5-прокси',
    'nfqws': 'nfqws — десинки zapret',
    'snimod': 'snimod — наш SNI case-mod',
    'bridge': 'DNS-мост (DoT)',
}

# Примеры-дефолты по режимам (дефолт НЕ вытесняется из истории)
MODE_DEFAULTS = {
    'byedpi': '-T3 -A torst -o1 -o25+s -r 1+s',
    'nfqws': '--filter-tcp=80,443 --dpi-desync=disorder2 '
             '--dpi-desync-split-pos=1',
    'snimod': '',      # параметры = список хостов (вкладка хосты)
    'bridge': '',       # у моста нет параметров запуска
}

MODE_EXAMPLES = {
    'byedpi': [
        '-T3 -A torst -o1 -o25+s -r 1+s',
        '-T2 -A torst -o2 -o15+s -r 2+s',
        '-T1 -A torst -o1 -o5+s',
        '-T3 -A torst -o3 -o20+s -r 2+s',
        '-T5 -A torst -o4 -o10+s',
    ],
    'nfqws': [
        '--filter-tcp=80,443 --dpi-desync=disorder2 --dpi-desync-split-pos=1',
        '--filter-tcp=80,443 --dpi-desync=fake,split2 '
        '--dpi-desync-fake-tls=1 --dpi-desync-split-pos=2',
        '--filter-tcp=80,443 --dpi-desync=multisplit '
        '--dpi-desync-split-seqovl=5 --dpi-desync-split-pos=1',
        '--filter-tcp=80,443 --dpi-desync=disorder2 '
        '--dpi-desync-ttl=4 --dpi-desync-fooling=badsum',
        '--filter-tcp=80,443 --dpi-desync=fake,split '
        '--dpi-desync-fake-tls=1 --dpi-desync-split-pos=1 '
        '--dpi-desync-fooling=md5sig,badseq',
    ],
    'snimod': [],   # хосты редактируются списком, не строкой
    'bridge': [],
}


class ModeSettingsWindow:
    """Синглтон-окно настроек выбранного режима с вкладками."""

    _instance = None

    def __init__(self, tray):
        self.tray = tray
        self.dialog = None
        self._pulse_timer = None
        self._search_state = {'running': False, 'searcher': None}
        # хуки конструкторов (трей вешает при открытии)
        self.param_builder_cb = None
        self.nfqws_builder_cb = None
        # vbox «последних» на вкладке Параметры (для живой перерисовки)
        self._recent_vbox = None

    # ---------------- публичное API ----------------

    def present(self):
        """Показать окно (создать или поднять существующее)."""
        if self.dialog is not None:
            try:
                self.dialog.present()
                return
            except Exception:
                self._cleanup_refs()
        self._build()

    # ---------------- конфиг-утилиты ----------------

    def _load_cfg(self):
        try:
            p = Path.home() / '.config' / 'ciadpi' / 'config.json'
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def _save_cfg(self, cfg):
        p = Path.home() / '.config' / 'ciadpi' / 'config.json'
        p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False),
                     encoding='utf-8')

    def _recent_for(self, mode):
        cfg = self._load_cfg()
        lst = (cfg.get('params_recent') or {}).get(mode) or []
        return [s for s in lst if isinstance(s, str)][:4]

    def _push_recent(self, mode, params_str):
        """LRU: новые сверху, максимум 4, дубль поднимается."""
        params_str = (params_str or '').strip()
        if not params_str or not mode or mode not in MODES:
            return
        cfg = self._load_cfg()
        rec = cfg.setdefault('params_recent', {})
        lst = [s for s in (rec.get(mode) or []) if s != params_str]
        lst.insert(0, params_str)
        rec[mode] = lst[:4]
        self._save_cfg(cfg)

    # ---------------- построение окна ----------------

    def _build(self):
        mode = self.tray._active_engine()

        dlg = Gtk.Dialog(title=f'Настройки режима — {MODE_TITLES.get(mode, mode)}',
                         flags=0)
        dlg.set_default_size(780, 580)
        self.dialog = dlg

        content = dlg.get_content_area()
        content.set_margin_top(8)
        content.set_margin_bottom(8)
        content.set_margin_start(8)
        content.set_margin_end(8)

        # режим-заголовок + строка параметров (общая для вкладок)
        head = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        mode_lbl = Gtk.Label()
        mode_lbl.set_markup(
            f'<b>Режим:</b> {MODE_TITLES.get(mode, mode)}  '
            '<small>(сменить — «Режимы обхода» в меню трея)</small>')
        mode_lbl.set_xalign(0)
        head.pack_start(mode_lbl, False, False, 0)

        self.params_entry = Gtk.Entry()
        self.params_entry.set_hexpand(True)
        self._refresh_params_entry(mode)
        entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                            spacing=6)
        entry_row.pack_start(self.params_entry, True, True, 0)
        btn_apply_params = Gtk.Button(label='Применить')
        btn_apply_params.connect('clicked',
                                 lambda b: self._on_apply_params(mode))
        entry_row.pack_start(btn_apply_params, False, False, 0)
        head.pack_start(entry_row, False, False, 0)
        content.pack_start(head, False, False, 0)

        # вкладки
        self.notebook = Gtk.Notebook()
        # ⭐ v2.0.8 (user: «фон вкладок выделить, область вкладок
        # чуть цветом — чтобы было понятно, что там вкладки»):
        # подсветка активного таба + лёгкий фон области страниц.
        try:
            css = b'''
            notebook header {
                background-color: rgba(120, 120, 140, 0.18);
                border-bottom: 1px solid rgba(120, 120, 140, 0.45);
                padding: 4px;
            }
            notebook header tab {
                padding: 6px 14px;
                border-radius: 6px 6px 0 0;
            }
            notebook header tab:checked {
                background-color: rgba(255, 255, 255, 0.22);
                font-weight: bold;
            }
            notebook > stack {
                background-color: rgba(255, 255, 255, 0.06);
            }
            '''
            prov = Gtk.CssProvider()
            prov.load_from_data(css)
            ctx = self.notebook.get_style_context()
            ctx.add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            # и на экран, где окна
            screen = dlg.get_screen() if hasattr(dlg, 'get_screen') \
                else None
            if screen is not None:
                Gtk.StyleContext.add_provider_for_screen(
                    screen, prov,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except Exception as e:
            print(f'⚠️ notebook css: {e}')
        content.pack_start(self.notebook, True, True, 4)

        self.notebook.append_page(self._page_params(mode),
                                  Gtk.Label(label='Параметры'))
        self.notebook.append_page(self._page_builder(mode),
                                  Gtk.Label(label='Конструктор'))
        self.notebook.append_page(self._page_search(mode),
                                  Gtk.Label(label='Поиск стратегии'))

        # переключение вкладок — обновляем подписи под режим
        self.notebook.connect('switch-page',
                              lambda nb, pg, idx: None)

        dlg.connect('response', self._on_response)
        dlg.connect('destroy', self._on_destroy)
        dlg.show_all()
        ModeSettingsWindow._instance = self

    def _refresh_params_entry(self, mode):
        """Текущие параметры режима → в строку ввода."""
        if mode == 'byedpi':
            cfg = self._load_cfg()
            txt = cfg.get('current_params') or cfg.get('params') \
                or MODE_DEFAULTS['byedpi']
        elif mode == 'nfqws':
            try:
                p = Path.home() / '.config' / 'ciadpi' / 'nfqws.json'
                cfg = json.loads(p.read_text(encoding='utf-8'))
                txt = cfg.get('params') or MODE_DEFAULTS['nfqws']
            except Exception:
                txt = MODE_DEFAULTS['nfqws']
        elif mode == 'snimod':
            txt = ''      # хосты живут в своей вкладке списка
        else:
            txt = ''
        self.params_entry.set_text(txt)

    # ---------------- вкладка «Параметры» ----------------

    def _page_params(self, mode):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # дефолт (не вытесняется)
        default_str = MODE_DEFAULTS.get(mode) or ''
        if default_str:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                          spacing=6)
            lbl = Gtk.Label(label='Дефолт:')
            lbl.set_xalign(0)
            ent = Gtk.Entry()
            ent.set_text(default_str)
            ent.set_editable(False)
            ent.set_can_focus(False)
            ent.set_hexpand(True)
            btn = Gtk.Button(label='→ в строку')
            btn.connect('clicked',
                        lambda b: self.params_entry.set_text(default_str))
            row.pack_start(lbl, False, False, 0)
            row.pack_start(ent, True, True, 0)
            row.pack_start(btn, False, False, 0)
            box.pack_start(row, False, False, 2)

        # примеры (кликабельные)
        examples = MODE_EXAMPLES.get(mode) or []
        if examples:
            ex_frame = Gtk.Frame(label='Примеры')
            ex_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                             spacing=3)
            ex_box.set_margin_top(4)
            ex_box.set_margin_bottom(4)
            ex_box.set_margin_start(6)
            ex_box.set_margin_end(6)
            for ex in examples:
                r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                            spacing=6)
                e = Gtk.Entry()
                e.set_text(ex)
                e.set_editable(False)
                e.set_can_focus(False)
                e.set_hexpand(True)
                b = Gtk.Button(label='→ в строку')
                b.connect('clicked',
                          lambda btn, s=ex:
                          self.params_entry.set_text(s))
                r.pack_start(e, True, True, 0)
                r.pack_start(b, False, False, 0)
                ex_box.pack_start(r, False, False, 2)
            ex_frame.add(ex_box)
            box.pack_start(ex_frame, False, False, 4)

        # 4 последних использованных (по режиму, LRU)
        recent_box_holder = {'box': None}
        recent_frame = Gtk.Frame(label='Последние использованные '
                                       '(авто, до 4)')
        recent_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                              spacing=3)
        recent_vbox.set_margin_top(4)
        recent_vbox.set_margin_start(6)
        recent_vbox.set_margin_end(6)
        recent_box_holder['box'] = recent_vbox
        self._recent_vbox = recent_vbox    # ⭐ для живой перерисовки
        recent_frame.add(recent_vbox)
        box.pack_start(recent_frame, False, False, 4)
        self._fill_recent(recent_vbox, mode)

        # для snimod — редактор списка хостов
        if mode == 'snimod':
            box.pack_start(self._snimod_hosts_widget(), True, True, 4)

        # для bridge — просто пояснение
        if mode == 'bridge':
            info = Gtk.Label()
            info.set_markup(
                '<small>У DNS-моста нет строковых параметров запуска:\n'
                'он слушает 127.0.0.1:53 и форвардит на 1.1.1.1:853 (DoT).\n'
                'Управление — «Режимы обхода»: Запустить/Остановить.</small>')
            info.set_xalign(0)
            box.pack_start(info, True, True, 4)

        return box

    def _fill_recent(self, vbox, mode):
        """Перерисовать список «последних» для режима."""
        for w in vbox.get_children():
            vbox.remove(w)
        items = self._recent_for(mode)
        if not items:
            empty = Gtk.Label()
            empty.set_markup('<small>пока пусто — после «Применить» '
                             'параметры появятся здесь</small>')
            empty.set_xalign(0)
            vbox.pack_start(empty, False, False, 2)
        else:
            for s in items:
                r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                            spacing=6)
                e = Gtk.Entry()
                e.set_text(s)
                e.set_editable(False)
                e.set_can_focus(False)
                e.set_hexpand(True)
                b = Gtk.Button(label='→ в строку')
                b.connect('clicked',
                          lambda btn, s=s: self.params_entry.set_text(s))
                r.pack_start(e, True, True, 0)
                r.pack_start(b, False, False, 0)
                vbox.pack_start(r, False, False, 2)
        vbox.show_all()

    def _snimod_hosts_widget(self):
        """Редактор хостов snimod (вместо строки параметров)."""
        frame = Gtk.Frame(label='Хосты SNI case-mod (по одному в строке)')
        sw = Gtk.ScrolledWindow()
        sw.set_vexpand(True)
        buf = Gtk.TextBuffer()
        try:
            p = Path.home() / '.config' / 'ciadpi' / 'snimod.json'
            cfg = json.loads(p.read_text(encoding='utf-8'))
            hosts = cfg.get('hosts') or []
        except Exception:
            hosts = []
        buf.set_text('\n'.join(hosts))
        tv = Gtk.TextView(buffer=buf)
        tv.set_monospace(True)
        sw.add(tv)

        btn = Gtk.Button(label='Сохранить хосты')
        btn.connect('clicked', lambda b: self._save_snimod_hosts(buf))
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        outer.pack_start(sw, True, True, 0)
        outer.pack_start(btn, False, False, 0)
        frame.add(outer)
        return frame

    def _save_snimod_hosts(self, buf):
        try:
            text = buf.get_text(buf.get_start_iter(),
                                buf.get_end_iter(), False)
            hosts = [h.strip() for h in text.splitlines()
                     if h.strip() and len(h.strip()) <= 253]
            if not hosts:
                return
            p = Path.home() / '.config' / 'ciadpi' / 'snimod.json'
            cfg = json.loads(p.read_text(encoding='utf-8')) \
                if p.exists() else {}
            cfg['hosts'] = hosts
            p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False),
                         encoding='utf-8')
            # применяем на лету, если сервис активен — перезапуск
            import ciadpi_enginectl as ec
            if ec.is_active('snimod'):
                def w():
                    ec.restart_engine('snimod')
                import threading
                threading.Thread(target=w, daemon=True).start()
        except Exception as e:
            print(f'⚠️ snimod hosts save: {e}')

    # ---------------- вкладка «Конструктор» ----------------

    def _page_builder(self, mode):
        """Конструктор параметров под режим."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        if mode == 'bridge':
            # ⭐ v2.0.8 (user: «для мостов какую-то настройку в
            # конструкторе»): upstream DoT-резолвер и TTL кэша.
            frame = Gtk.Frame(
                label='Настройки DNS-моста (upstream DoT-резолвер)')
            fbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                           spacing=6)
            fbox.set_margin_top(6)
            fbox.set_margin_bottom(6)
            fbox.set_margin_start(8)
            fbox.set_margin_end(8)

            cur = self._bridge_cfg()

            row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                           spacing=6)
            lbl1 = Gtk.Label(label='Upstream IP:')
            lbl1.set_xalign(0)
            self.bridge_upstream = Gtk.Entry()
            self.bridge_upstream.set_text(cur.get('upstream', '1.1.1.1'))
            self.bridge_upstream.set_tooltip_text(
                'DNS-over-TLS сервер: 1.1.1.1 (Cloudflare), '
                '8.8.8.8 (Google), 9.9.9.9 (Quad9)')
            self.bridge_upstream.set_hexpand(True)
            row1.pack_start(lbl1, False, False, 0)
            row1.pack_start(self.bridge_upstream, True, True, 0)
            fbox.pack_start(row1, False, False, 2)

            row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                           spacing=6)
            lbl2 = Gtk.Label(label='Имя TLS-сертификата:')
            lbl2.set_xalign(0)
            self.bridge_tlsname = Gtk.Entry()
            self.bridge_tlsname.set_text(cur.get('tls_name',
                                                 'cloudflare-dns.com'))
            self.bridge_tlsname.set_tooltip_text(
                'server_hostname для проверки сертификата upstream')
            self.bridge_tlsname.set_hexpand(True)
            row2.pack_start(lbl2, False, False, 0)
            row2.pack_start(self.bridge_tlsname, True, True, 0)
            fbox.pack_start(row2, False, False, 2)

            btn = Gtk.Button(label='Сохранить и перезапустить мост')
            btn.connect('clicked', self._on_bridge_cfg_apply)
            fbox.pack_start(btn, False, False, 2)

            hint = Gtk.Label()
            hint.set_markup(
                '<small>Upstream общается по TLS (порт 853) — пров '
                'не может подменить ответы, только заблокировать.\n'
                'Если мост не стартует с вашим upstream — попробуйте '
                '8.8.8.8/dns.google или 9.9.9.9/dns.quad9.</small>')
            hint.set_xalign(0)
            hint.set_line_wrap(True)
            fbox.pack_start(hint, False, False, 4)
            frame.add(fbox)
            box.pack_start(frame, False, False, 4)
            return box
        if mode == 'snimod':
            info = Gtk.Label(label='Параметры snimod — это список хостов '
                                   '(вкладка «Параметры»).')
            box.pack_start(info, True, True, 0)
            return box
        # byedpi/nfqws — строим из спецификации
        # ⭐ ФИКС v2.0.9: хуки живут на ЭТОМ окне (self.param_builder_cb),
        # а не на tray — раньше читали self.tray.param_builder_cb (его
        # не существует) и конструктор всегда был «недоступен».
        try:
            cb = (self.param_builder_cb if mode == 'byedpi'
                  else self.nfqws_builder_cb)
            widget = cb() if cb else None
        except Exception as e:
            widget = None
            print(f'⚠️ builder for {mode}: {e}')
        if widget is None:
            # запасной вариант: просто пояснение + строка
            info = Gtk.Label()
            info.set_markup(
                '<small>Конструктор недоступен для этого режима — '
                'используйте ручную строку и примеры.</small>')
            info.set_xalign(0)
            box.pack_start(info, True, True, 0)
        else:
            scroll = Gtk.ScrolledWindow()
            scroll.set_vexpand(True)
            scroll.add(widget)
            box.pack_start(scroll, True, True, 0)
        return box

    # ---------------- конфиг DNS-моста (конструктор) ----------------

    def _bridge_cfg_path(self):
        return Path.home() / '.config' / 'ciadpi' / 'dotbridge.json'

    def _bridge_cfg(self):
        try:
            return json.loads(
                self._bridge_cfg_path().read_text(encoding='utf-8'))
        except Exception:
            return {'upstream': '1.1.1.1', 'tls_name': 'cloudflare-dns.com'}

    def _on_bridge_cfg_apply(self, btn):
        import re as _re
        upstream = (self.bridge_upstream.get_text() or '').strip()
        tls_name = (self.bridge_tlsname.get_text() or '').strip()
        if not _re.fullmatch(r'(\d{1,3}\.){3}\d{1,3}', upstream or ''):
            self.tray.show_notification(
                'Мост', 'Upstream должен быть IPv4-адресом (напр. 1.1.1.1)')
            return
        if not tls_name:
            tls_name = 'cloudflare-dns.com'
        cfg = {'upstream': upstream, 'tls_name': tls_name}
        try:
            self._bridge_cfg_path().write_text(
                json.dumps(cfg, indent=2), encoding='utf-8')
        except Exception as e:
            self.tray.show_notification('Ошибка', str(e)[:120])
            return

        import threading

        def worker():
            try:
                import ciadpi_enginectl as ec
                # переписываем юнит с новыми аргументами и рестартуем
                unit = Path('/etc/systemd/system/ciadpi-dotbridge.service')
                bridge_py = Path.home() / '.local/bin/ciadpi_dotbridge.py'
                if not bridge_py.exists():
                    bridge_py = (Path(__file__).resolve().parent
                                 / 'ciadpi_dotbridge.py')
                content = (
                    '[Unit]\n'
                    'Description=CIADPI DoT DNS bridge '
                    '(127.0.0.1:53 -> upstream:853)\n'
                    'After=network.target\n'
                    'Wants=network.target\n\n'
                    '[Service]\n'
                    'Type=simple\n'
                    f'ExecStart=/usr/bin/python3 {bridge_py} '
                    f'--upstream {upstream} --tls-name {tls_name}\n'
                    'Restart=on-failure\n'
                    'RestartSec=3\n\n'
                    '[Install]\n'
                    'WantedBy=multi-user.target\n')
                import subprocess as _sp
                tmp = Path('/tmp/ciadpi_dotbridge.service')
                tmp.write_text(content, encoding='utf-8')
                with open(tmp, 'rb') as f_in:
                    _sp.run(['sudo', '-n', '/usr/bin/tee', str(unit)],
                            stdin=f_in, capture_output=True, timeout=30)
                _sp.run(['sudo', '-n', '/usr/bin/systemctl',
                         'daemon-reload'], capture_output=True, timeout=30)
                if ec.is_active('bridge'):
                    ec.stop_bridge()
                ok, msg = ec.start_bridge()
            except Exception as e:
                ok, msg = False, str(e)
            def done():
                self.tray.show_notification(
                    'Мост' if ok else 'Ошибка',
                    (msg or f'upstream → {upstream}')[:150])
                return False
            GLib.idle_add(done)
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- вкладка «Поиск стратегии» ----------------

    def _page_search(self, mode):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        if mode in ('bridge', 'snimod'):
            txt = ('Поиск параметров не имеет смысла для DNS-моста — '
                   'он безнастроечный.' if mode == 'bridge' else
                   'Поиск параметров для snimod не нужен: его стратегия — '
                   'только список хостов (вкладка «Параметры»).')
            info = Gtk.Label(label=txt)
            info.set_line_wrap(True)
            box.pack_start(info, True, True, 0)
            return box

        # urls
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl = Gtk.Label(label='URL проверки:')
        lbl.set_xalign(0)
        self.search_urls = Gtk.Entry()
        self.search_urls.set_text(
            'https://www.youtube.com '
            'https://www.google.com/generate_204 https://github.com')
        self.search_urls.set_hexpand(True)
        row.pack_start(lbl, False, False, 0)
        row.pack_start(self.search_urls, True, True, 0)
        box.pack_start(row, False, False, 0)

        # лимиты
        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        chk = Gtk.CheckButton(label='Без лимита (до нахождения)')
        self.search_unlimited = chk
        spin = Gtk.SpinButton.new_with_range(1, 200, 1)
        spin.set_value(20)
        self.search_maxtests = spin
        chk.connect('toggled',
                    lambda b: spin.set_sensitive(not b.get_active()))
        row2.pack_start(chk, False, False, 0)
        row2.pack_start(spin, False, False, 0)
        box.pack_start(row2, False, False, 0)

        # прогресс + кнопки
        self.search_progress = Gtk.ProgressBar()
        self.search_progress.set_show_text(True)
        box.pack_start(self.search_progress, False, False, 0)

        self.search_status = Gtk.Label(label='Готов к поиску')
        self.search_status.set_xalign(0)
        box.pack_start(self.search_status, False, False, 0)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                          spacing=6)
        b_start = Gtk.Button(label='▶ Найти оптимальные')
        b_stop = Gtk.Button(label='⏹ Стоп')
        b_stop.set_sensitive(False)
        b_use = Gtk.Button(label='→ в строку параметров')
        b_use.set_sensitive(False)
        self.search_btns = {'start': b_start, 'stop': b_stop, 'use': b_use}
        btn_row.pack_start(b_start, False, False, 0)
        btn_row.pack_start(b_stop, False, False, 0)
        btn_row.pack_start(b_use, False, False, 0)
        box.pack_start(btn_row, False, False, 0)

        # лог
        frame = Gtk.Frame(label='Журнал поиска')
        sw = Gtk.ScrolledWindow()
        sw.set_vexpand(True)
        tv = Gtk.TextView()
        tv.set_editable(False)
        tv.set_monospace(True)
        self.search_log_buf = tv.get_buffer()
        sw.add(tv)
        frame.add(sw)
        box.pack_start(frame, True, True, 0)

        b_start.connect('clicked', lambda b: self._on_search_start(mode))
        b_stop.connect('clicked', lambda b: self._on_search_stop())
        b_use.connect('clicked', lambda b: self._on_search_use())
        return box

    def _slog(self, msg):
        """Строка в журнал поиска (потокобезопасно через idle_add)."""
        def add():
            b = self.search_log_buf
            b.insert(b.get_end_iter(), msg + '\n')
            # кап буфера: держим последние ~300 строк
            if b.get_line_count() > 350:
                it = b.get_iter_at_line(b.get_line_count() - 300)
                b.delete(b.get_start_iter(), it)
            return False
        GLib.idle_add(add)

    def _on_search_start(self, mode):
        if self._search_state['running']:
            return
        urls = [u.strip() for u in self.search_urls.get_text().split()
                if u.strip()]
        if not urls:
            self._slog('укажите хотя бы один URL')
            return
        unlimited = self.search_unlimited.get_active()
        max_tests = 0 if unlimited else int(self.search_maxtests.get_value())

        # поиск под режим
        try:
            from ciadpi_strategy_search import StrategySearcher
            searcher = StrategySearcher()
            searcher.default_test_urls = urls
            self._search_state['mode'] = mode
            if mode == 'nfqws':
                # nfqws-поиск через реальный сервис
                from ciadpi_strategy_search import NfqwsStrategySearcher
                searcher = NfqwsStrategySearcher()
        except Exception as e:
            self._slog(f'модуль поиска недоступен: {e}')
            return

        self._search_state['running'] = True
        self._search_state['searcher'] = searcher
        self._search_state['best'] = None
        for b in self.search_btns.values():
            b.set_sensitive(b is self.search_btns['stop'])
        self.search_log_buf.set_text('')
        self._slog(f'▶ поиск {mode}: '
                    + ('БЕЗ ЛИМИТА' if unlimited else f'{max_tests} комб.')
                    + f', URL: {len(urls)}')

        # pulse-таймер (чистится при закрытии окна)
        def pulse():
            self.search_progress.pulse()
            return True
        self._pulse_timer = GLib.timeout_add(300, pulse)

        def on_progress(stage, data):
            try:
                if stage == 'test':
                    r = data.get('result') or {}
                    mark = '✅' if r.get('success') else '⛔' \
                        if r.get('urls_ok') else '❌'
                    self._slog(f"[{data.get('index', 0) + 1}] {mark} "
                              f"{r.get('urls_ok', '?')}/"
                              f"{r.get('urls_total', '?')} URL, "
                              f"{r.get('speed', 0):.1f}s | "
                              f"{r.get('params', '')}")
                    for url, ok, code, sec in (r.get('details') or []):
                        self._slog(f"    {'✅' if ok else '❌'} {url} "
                                    f"→ {code} ({sec}s)")
                    if r.get('success'):
                        self._search_state['best'] = r.get('params')
                elif stage == 'done':
                    best = self._search_state.get('best')
                    if best:
                        self._slog(f'\n🏆 Лучший результат: {best}')
                    else:
                        self._slog('\n😕 Рабочая комбинация не найдена')
            except Exception as e:
                self._slog(f'(ошибка вывода: {e})')

        import threading

        def worker():
            try:
                searcher.find_optimal_params(
                    max_tests, urls, on_progress)
            except Exception as e:
                self._slog(f'⚠️ поиск упал: {e}')
            finally:
                def done():
                    self._search_state['running'] = False
                    if self._pulse_timer:
                        GLib.source_remove(self._pulse_timer)
                        self._pulse_timer = None
                    self.search_progress.set_fraction(1.0)
                    self.search_progress.set_text('завершено')
                    for key, b in self.search_btns.items():
                        try:
                            b.set_sensitive(
                                key != 'stop' and
                                (key != 'use' or
                                 bool(self._search_state.get('best'))))
                        except Exception:
                            pass
                    return False
                GLib.idle_add(done)
        threading.Thread(target=worker, daemon=True).start()

    def _on_search_stop(self):
        s = self._search_state.get('searcher')
        if s and hasattr(s, 'stop_search'):
            try:
                s.stop_search()
                self._slog('⏹ остановка запрошена…')
            except Exception as e:
                self._slog(f'стоп: {e}')

    def _on_search_use(self):
        best = self._search_state.get('best')
        if best:
            self.params_entry.set_text(best)
            self._slog(f'→ параметры помещены в строку ввода — '
                       f'нажмите «Применить»')

    # ---------------- применение параметров ----------------

    def _on_apply_params(self, mode):
        params = (self.params_entry.get_text() or '').strip()
        if mode in ('bridge',):
            self.tray.show_notification('Мост', 'У DNS-моста нет параметров')
            return
        if mode == 'snimod':
            # для snimod строка = хосты через запятую/пробел
            hosts = [h for h in
                     params.replace(',', ' ').split() if h]
            if hosts:
                try:
                    p = Path.home() / '.config' / 'ciadpi' / 'snimod.json'
                    cfg = json.loads(p.read_text(encoding='utf-8')) \
                        if p.exists() else {}
                    cfg['hosts'] = hosts
                    p.write_text(json.dumps(cfg, indent=2,
                                            ensure_ascii=False),
                                 encoding='utf-8')
                    import ciadpi_enginectl as ec
                    if ec.is_active('snimod'):
                        import threading
                        threading.Thread(
                            target=lambda: ec.restart_engine('snimod'),
                            daemon=True).start()
                    self._push_recent('snimod', ' '.join(hosts))
                    self.tray.show_notification(
                        'snimod', f'Хосты применены: {len(hosts)}')
                except Exception as e:
                    self.tray.show_notification('Ошибка', str(e)[:120])
            return

        # byedpi / nfqws
        if not params:
            self.tray.show_notification('Пусто', 'Введите параметры')
            return

        def worker():
            ok, msg = False, ''
            try:
                if mode == 'byedpi':
                    # пишем в конфиг трея + перезапускаем сервис
                    cfg = self._load_cfg()
                    cfg['current_params'] = params
                    cfg['params'] = params
                    self._save_cfg(cfg)
                    import ciadpi_enginectl as ec
                    if ec.is_active('byedpi'):
                        ok, msg = ec.restart_engine('byedpi'), ''
                        ok = ok if isinstance(ok, bool) else ok[0]
                    else:
                        ok, msg = True, 'сохранено (сервис не активен)'
                elif mode == 'nfqws':
                    p = Path.home() / '.config' / 'ciadpi' / 'nfqws.json'
                    cfg = json.loads(p.read_text(encoding='utf-8')) \
                        if p.exists() else {}
                    cfg['params'] = params
                    p.write_text(json.dumps(cfg, indent=2,
                                            ensure_ascii=False),
                                 encoding='utf-8')
                    import ciadpi_enginectl as ec
                    if ec.is_active('nfqws'):
                        r = ec.restart_engine('nfqws')
                        ok = r[0] if isinstance(r, tuple) else r
                        msg = r[1] if isinstance(r, tuple) and len(r) > 1 else ''
                    else:
                        ok, msg = True, 'сохранено (сервис не активен)'
            except Exception as e:
                ok, msg = False, str(e)

            def done():
                self._push_recent(mode, params)
                self._refresh_params_entry(mode)
                # ⭐ ФИКС v2.0.9 («последние не появились»): список
                # «Последние использованные» теперь ПЕРЕРИСОВЫВАЕТСЯ
                # сразу после применения — раньше рисовался только
                # при открытии окна.
                try:
                    if self._recent_vbox is not None:
                        self._fill_recent(self._recent_vbox, mode)
                except Exception:
                    pass
                self.tray.show_notification(
                    'Применено' if ok else 'Ошибка',
                    (msg or 'параметры сохранены')[:150])
                return False
            GLib.idle_add(done)
        import threading
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- закрытие ----------------

    def _on_response(self, dlg, response):
        # остановить поиск при закрытии
        if self._search_state.get('running'):
            self._on_search_stop()
        dlg.destroy()

    def _on_destroy(self, dlg):
        if self._pulse_timer:
            GLib.source_remove(self._pulse_timer)
            self._pulse_timer = None
        self._cleanup_refs()

    def _cleanup_refs(self):
        self.dialog = None
        ModeSettingsWindow._instance = None
        try:
            self.tray._mode_settings_window = None
        except Exception:
            pass
