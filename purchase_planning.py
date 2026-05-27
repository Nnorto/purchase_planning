import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, timedelta
from statistics import mean

DB_NAME = "shop_purchases.db"


# ===========================================================================
#                              СЛОЙ ДАННЫХ
# ===========================================================================
class Database:
    """Обёртка над SQLite: схема, демо-данные, CRUD."""

    def __init__(self, db_name=DB_NAME):
        self.conn = sqlite3.connect(db_name)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_schema()
        self._seed_if_empty()

    def _create_schema(self):
        cur = self.conn.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            contact TEXT,
            lead_time_days INTEGER NOT NULL DEFAULT 3
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            unit TEXT NOT NULL DEFAULT 'шт',
            price REAL NOT NULL DEFAULT 0,
            stock INTEGER NOT NULL DEFAULT 0,
            min_stock INTEGER NOT NULL DEFAULT 5,
            supplier_id INTEGER,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            sale_date TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'черновик',
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        );
        CREATE TABLE IF NOT EXISTS purchase_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            FOREIGN KEY (order_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );
        """)
        self.conn.commit()

    def _seed_if_empty(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products")
        if cur.fetchone()[0] > 0:
            return
        cur.executemany(
            "INSERT INTO suppliers (name, contact, lead_time_days) VALUES (?, ?, ?)",
            [
                ("ООО «Молочный край»", "+7 495 111-22-33", 2),
                ("ИП Хлебников А.С.",   "+7 495 222-33-44", 1),
                ("ТД «Бакалея-Опт»",    "+7 495 333-44-55", 5),
            ],
        )
        cur.executemany(
            "INSERT INTO products (name, unit, price, stock, min_stock, supplier_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("Молоко 1 л",     "шт", 89.0,  30, 15, 1),
                ("Кефир 0,5 л",    "шт", 65.0,  20, 10, 1),
                ("Хлеб белый",     "шт", 45.0,  12, 20, 2),
                ("Батон нарезной", "шт", 55.0,   8, 15, 2),
                ("Сахар 1 кг",     "шт", 78.0,  25, 10, 3),
                ("Гречка 900 г",   "шт", 120.0, 18,  8, 3),
                ("Макароны 450 г", "шт", 95.0,  14, 10, 3),
            ],
        )
        today = datetime.now().date()
        pattern = {
            1: [4, 5, 3, 6, 4, 7, 8, 5, 4, 6, 5, 4, 5, 6],
            2: [2, 3, 2, 3, 3, 4, 5, 3, 2, 3, 4, 3, 2, 3],
            3: [3, 4, 5, 4, 3, 6, 7, 5, 4, 4, 5, 6, 4, 5],
            4: [2, 3, 2, 3, 2, 4, 5, 3, 3, 2, 3, 4, 3, 3],
            5: [2, 2, 1, 2, 3, 2, 3, 2, 2, 1, 2, 3, 2, 2],
            6: [1, 2, 1, 2, 1, 2, 3, 2, 1, 2, 1, 2, 2, 1],
            7: [2, 1, 2, 3, 2, 2, 3, 2, 1, 2, 2, 3, 2, 2],
        }
        for pid, qtys in pattern.items():
            for i, q in enumerate(qtys):
                d = today - timedelta(days=14 - i)
                cur.execute(
                    "INSERT INTO sales (product_id, qty, sale_date) VALUES (?, ?, ?)",
                    (pid, q, d.isoformat()),
                )
        self.conn.commit()

    # ---------- товары ----------
    def get_products(self):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT p.id, p.name, p.unit, p.price, p.stock, p.min_stock,
                   COALESCE(s.name, '—') AS supplier
            FROM products p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            ORDER BY p.name
        """)
        return cur.fetchall()

    def add_product(self, name, unit, price, stock, min_stock, supplier_id):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO products (name, unit, price, stock, min_stock, supplier_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, unit, price, stock, min_stock, supplier_id),
        )
        self.conn.commit()

    def update_product_stock(self, product_id, new_stock):
        cur = self.conn.cursor()
        cur.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
        self.conn.commit()

    def delete_product(self, product_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
        self.conn.commit()

    # ---------- поставщики ----------
    def get_suppliers(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, name, contact, lead_time_days FROM suppliers ORDER BY name")
        return cur.fetchall()

    def add_supplier(self, name, contact, lead_time):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO suppliers (name, contact, lead_time_days) VALUES (?, ?, ?)",
            (name, contact, lead_time),
        )
        self.conn.commit()

    # ---------- продажи ----------
    def add_sale(self, product_id, qty):
        cur = self.conn.cursor()
        cur.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError("Товар не найден")
        if row[0] < qty:
            raise ValueError("Недостаточно товара на складе")
        cur.execute(
            "INSERT INTO sales (product_id, qty, sale_date) VALUES (?, ?, ?)",
            (product_id, qty, datetime.now().date().isoformat()),
        )
        cur.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty, product_id))
        self.conn.commit()

    def get_sales_history(self, product_id, days=14):
        cur = self.conn.cursor()
        start = (datetime.now().date() - timedelta(days=days)).isoformat()
        cur.execute("""
            SELECT sale_date, SUM(qty)
            FROM sales
            WHERE product_id = ? AND sale_date >= ?
            GROUP BY sale_date
            ORDER BY sale_date
        """, (product_id, start))
        return cur.fetchall()

    def total_sales_revenue(self, days=14):
        cur = self.conn.cursor()
        start = (datetime.now().date() - timedelta(days=days)).isoformat()
        cur.execute("""
            SELECT COALESCE(SUM(s.qty * p.price), 0)
            FROM sales s JOIN products p ON p.id = s.product_id
            WHERE s.sale_date >= ?
        """, (start,))
        return cur.fetchone()[0]

    def revenue_by_day(self, days=14):
        cur = self.conn.cursor()
        start = (datetime.now().date() - timedelta(days=days - 1)).isoformat()
        cur.execute("""
            SELECT s.sale_date, COALESCE(SUM(s.qty * p.price), 0)
            FROM sales s JOIN products p ON p.id = s.product_id
            WHERE s.sale_date >= ?
            GROUP BY s.sale_date
            ORDER BY s.sale_date
        """, (start,))
        return dict(cur.fetchall())

    # ---------- заявки ----------
    def save_purchase_order(self, supplier_id, items):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO purchase_orders (supplier_id, created_at, status) "
            "VALUES (?, ?, ?)",
            (supplier_id, datetime.now().isoformat(timespec="seconds"), "черновик"),
        )
        order_id = cur.lastrowid
        cur.executemany(
            "INSERT INTO purchase_items (order_id, product_id, qty) VALUES (?, ?, ?)",
            [(order_id, pid, q) for pid, q in items],
        )
        self.conn.commit()
        return order_id

    def get_orders(self):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT po.id, s.name, po.created_at, po.status,
                   (SELECT SUM(pi.qty * p.price)
                      FROM purchase_items pi
                      JOIN products p ON p.id = pi.product_id
                     WHERE pi.order_id = po.id) AS total
            FROM purchase_orders po
            JOIN suppliers s ON s.id = po.supplier_id
            ORDER BY po.id DESC
        """)
        return cur.fetchall()

    def get_order_items(self, order_id):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT p.name, pi.qty, p.price, pi.qty * p.price AS sum_
            FROM purchase_items pi
            JOIN products p ON p.id = pi.product_id
            WHERE pi.order_id = ?
        """, (order_id,))
        return cur.fetchall()

    def mark_order_received(self, order_id):
        cur = self.conn.cursor()
        cur.execute("SELECT status FROM purchase_orders WHERE id = ?", (order_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError("Заявка не найдена")
        if row[0] == "получено":
            raise ValueError("Заявка уже принята")
        cur.execute("SELECT product_id, qty FROM purchase_items WHERE order_id = ?", (order_id,))
        for pid, qty in cur.fetchall():
            cur.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (qty, pid))
        cur.execute("UPDATE purchase_orders SET status = 'получено' WHERE id = ?", (order_id,))
        self.conn.commit()


# ===========================================================================
#                            ПЛАНИРОВЩИК
# ===========================================================================
class PurchasePlanner:
    """ROP = ADU·LT·(1+k);  Q = max(0, ROP + N·ADU − stock)."""

    SAFETY_FACTOR = 0.3
    COVER_DAYS = 7

    def __init__(self, db: Database):
        self.db = db

    def avg_daily_sales(self, product_id, days=14):
        history = self.db.get_sales_history(product_id, days=days)
        if not history:
            return 0.0
        return sum(q for _, q in history) / days

    def build_plan(self):
        plan = []
        cur = self.db.conn.cursor()
        cur.execute("""
            SELECT p.id, p.name, p.unit, p.price, p.stock, p.min_stock,
                   s.id, s.name, s.lead_time_days
            FROM products p LEFT JOIN suppliers s ON s.id = p.supplier_id
        """)
        for row in cur.fetchall():
            pid, pname, unit, price, stock, min_stock, sid, sname, lt = row
            if sid is None:
                continue
            adu = self.avg_daily_sales(pid)
            safety = adu * lt * self.SAFETY_FACTOR
            rop = adu * lt + safety
            recommended = rop + self.COVER_DAYS * adu - stock
            if (stock <= rop or stock < min_stock) and recommended > 0:
                plan.append({
                    "product_id": pid, "product": pname, "unit": unit,
                    "price": price, "stock": stock, "min_stock": min_stock,
                    "adu": round(adu, 2), "reorder_point": round(rop, 1),
                    "qty": int(round(recommended)),
                    "supplier_id": sid, "supplier": sname, "lead_time": lt,
                    "sum": int(round(recommended)) * price,
                })
        return plan


# ===========================================================================
#                              ОФОРМЛЕНИЕ
# ===========================================================================
class Theme:
    LIGHT = {
        "bg":             "#F4F6FB",
        "surface":        "#FFFFFF",
        "surface_alt":    "#F1F4F9",
        "border":         "#E2E6EE",
        "text":           "#1F2937",
        "text_muted":     "#6B7280",
        "primary":        "#3B82F6",
        "primary_hover":  "#2563EB",
        "success":        "#10B981",
        "warning":        "#F59E0B",
        "danger":         "#EF4444",
        "sidebar":        "#1E293B",
        "sidebar_text":   "#E5E7EB",
        "sidebar_muted":  "#94A3B8",
        "sidebar_hover":  "#334155",
        "sidebar_active": "#3B82F6",
    }
    DARK = {
        "bg":             "#0F172A",
        "surface":        "#1E293B",
        "surface_alt":    "#273449",
        "border":         "#334155",
        "text":           "#F1F5F9",
        "text_muted":     "#94A3B8",
        "primary":        "#60A5FA",
        "primary_hover":  "#3B82F6",
        "success":        "#34D399",
        "warning":        "#FBBF24",
        "danger":         "#F87171",
        "sidebar":        "#0B1220",
        "sidebar_text":   "#E2E8F0",
        "sidebar_muted":  "#64748B",
        "sidebar_hover":  "#1E293B",
        "sidebar_active": "#3B82F6",
    }
    FONT = "Segoe UI"


# ===========================================================================
#                              ИНТЕРФЕЙС
# ===========================================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Подсистема планирования закупок")
        self.geometry("1380x780")
        self.minsize(1100, 640)

        self.db = Database()
        self.planner = PurchasePlanner(self.db)

        self.is_dark = False
        self.palette = Theme.LIGHT
        self.current_page = None
        self._nav_buttons = {}
        self._current_plan = []

        # сетка окна: 0 — sidebar, 1 — контент
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._apply_style()
        self._build_sidebar()
        self._build_content()
        self._build_statusbar()
        self.configure(bg=self.palette["bg"])
        self.show_page("dashboard")

    # ============================== СТИЛИ =================================
    def _apply_style(self):
        p = self.palette
        s = ttk.Style(self)
        if "clam" in s.theme_names():
            s.theme_use("clam")

        self.configure(bg=p["bg"])
        s.configure(".", background=p["bg"], foreground=p["text"],
                    font=(Theme.FONT, 10))
        s.configure("TFrame", background=p["bg"])

        # кнопки
        s.configure("Primary.TButton",
                    background=p["primary"], foreground="#FFFFFF",
                    font=(Theme.FONT, 10, "bold"),
                    padding=(16, 9), borderwidth=0, relief="flat")
        s.map("Primary.TButton",
              background=[("active", p["primary_hover"]),
                          ("pressed", p["primary_hover"])])

        s.configure("Secondary.TButton",
                    background=p["surface"], foreground=p["text"],
                    font=(Theme.FONT, 10),
                    padding=(14, 8), borderwidth=1, relief="solid")
        s.map("Secondary.TButton",
              background=[("active", p["surface_alt"])],
              bordercolor=[("!active", p["border"])])

        s.configure("Danger.TButton",
                    background=p["danger"], foreground="#FFFFFF",
                    font=(Theme.FONT, 10, "bold"),
                    padding=(14, 8), borderwidth=0, relief="flat")
        s.map("Danger.TButton", background=[("active", "#DC2626")])

        s.configure("Success.TButton",
                    background=p["success"], foreground="#FFFFFF",
                    font=(Theme.FONT, 10, "bold"),
                    padding=(14, 8), borderwidth=0, relief="flat")
        s.map("Success.TButton", background=[("active", "#059669")])

        # поля
        s.configure("TEntry",
                    fieldbackground=p["surface"], foreground=p["text"],
                    bordercolor=p["border"], lightcolor=p["border"],
                    darkcolor=p["border"], padding=7, relief="flat")
        s.map("TEntry",
              bordercolor=[("focus", p["primary"])],
              lightcolor=[("focus", p["primary"])],
              darkcolor=[("focus", p["primary"])])

        s.configure("TCombobox",
                    fieldbackground=p["surface"], background=p["surface"],
                    foreground=p["text"], bordercolor=p["border"],
                    arrowcolor=p["text"], padding=5, relief="flat")
        s.map("TCombobox",
              fieldbackground=[("readonly", p["surface"])],
              foreground=[("readonly", p["text"])],
              bordercolor=[("focus", p["primary"])])

        # таблицы
        s.configure("Treeview",
                    background=p["surface"], fieldbackground=p["surface"],
                    foreground=p["text"], rowheight=32,
                    borderwidth=0, font=(Theme.FONT, 10))
        s.configure("Treeview.Heading",
                    background=p["surface_alt"], foreground=p["text"],
                    font=(Theme.FONT, 10, "bold"),
                    padding=(8, 10), relief="flat", borderwidth=0)
        s.map("Treeview.Heading", background=[("active", p["surface_alt"])])
        s.map("Treeview",
              background=[("selected", p["primary"])],
              foreground=[("selected", "#FFFFFF")])

        # скроллбары
        s.configure("Vertical.TScrollbar",
                    background=p["surface_alt"], troughcolor=p["bg"],
                    bordercolor=p["bg"], arrowcolor=p["text_muted"],
                    relief="flat")
        s.configure("Horizontal.TScrollbar",
                    background=p["surface_alt"], troughcolor=p["bg"],
                    bordercolor=p["bg"], arrowcolor=p["text_muted"],
                    relief="flat")

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        self.palette = Theme.DARK if self.is_dark else Theme.LIGHT
        # полностью пересобираем окно
        for w in self.winfo_children():
            w.destroy()
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._nav_buttons = {}
        self._apply_style()
        self._build_sidebar()
        self._build_content()
        self._build_statusbar()
        self.configure(bg=self.palette["bg"])
        self.show_page(self.current_page or "dashboard")

    # ============================== САЙДБАР ===============================
    def _build_sidebar(self):
        p = self.palette
        side = tk.Frame(self, bg=p["sidebar"], width=240)
        side.grid(row=0, column=0, sticky="nsw", rowspan=2)
        side.grid_propagate(False)

        # лого/заголовок
        logo = tk.Frame(side, bg=p["sidebar"])
        logo.pack(fill="x", pady=(24, 18))
        tk.Label(logo, text="🛒", bg=p["sidebar"],
                 fg=p["sidebar_text"], font=(Theme.FONT, 30)).pack()
        tk.Label(logo, text="Закупки",
                 bg=p["sidebar"], fg=p["sidebar_text"],
                 font=(Theme.FONT, 15, "bold")).pack(pady=(4, 0))
        tk.Label(logo, text="Подсистема планирования",
                 bg=p["sidebar"], fg=p["sidebar_muted"],
                 font=(Theme.FONT, 8)).pack()

        tk.Frame(side, bg=p["sidebar_hover"], height=1).pack(
            fill="x", padx=24, pady=18)

        nav = [
            ("dashboard", "📊", "Дашборд"),
            ("products",  "📦", "Товары"),
            ("sales",     "💰", "Продажи"),
            ("planning",  "🎯", "План закупок"),
            ("orders",    "📋", "Заявки"),
            ("suppliers", "🚚", "Поставщики"),
        ]
        for key, icon, label in nav:
            row = tk.Frame(side, bg=p["sidebar"], cursor="hand2")
            row.pack(fill="x", pady=2, padx=12)
            tk.Label(row, text=icon, bg=p["sidebar"], fg=p["sidebar_text"],
                     font=(Theme.FONT, 13)).pack(side="left", padx=(14, 12), pady=10)
            txt = tk.Label(row, text=label, bg=p["sidebar"],
                           fg=p["sidebar_text"],
                           font=(Theme.FONT, 11))
            txt.pack(side="left", pady=10)
            for w in (row, txt) + tuple(row.winfo_children()):
                w.bind("<Button-1>", lambda e, k=key: self.show_page(k))
                w.bind("<Enter>", lambda e, k=key: self._nav_hover(k, True))
                w.bind("<Leave>", lambda e, k=key: self._nav_hover(k, False))
            self._nav_buttons[key] = row

        # переключатель темы
        bottom = tk.Frame(side, bg=p["sidebar"])
        bottom.pack(side="bottom", fill="x", pady=20, padx=12)
        theme_text = "🌙   Тёмная тема" if not self.is_dark else "☀️   Светлая тема"
        tb = tk.Label(bottom, text=theme_text, bg=p["sidebar"],
                      fg=p["sidebar_muted"], anchor="w",
                      font=(Theme.FONT, 10), padx=14, pady=10,
                      cursor="hand2")
        tb.pack(fill="x")
        tb.bind("<Button-1>", lambda e: self.toggle_theme())
        tb.bind("<Enter>", lambda e: tb.configure(bg=p["sidebar_hover"]))
        tb.bind("<Leave>", lambda e: tb.configure(bg=p["sidebar"]))

    def _nav_hover(self, key, entering):
        p = self.palette
        if key == self.current_page:
            return
        row = self._nav_buttons[key]
        color = p["sidebar_hover"] if entering else p["sidebar"]
        row.configure(bg=color)
        for w in row.winfo_children():
            w.configure(bg=color)

    def _nav_set_active(self, key):
        p = self.palette
        for k, row in self._nav_buttons.items():
            if k == key:
                row.configure(bg=p["sidebar_active"])
                for w in row.winfo_children():
                    w.configure(bg=p["sidebar_active"], fg="#FFFFFF",
                                font=(Theme.FONT, 11, "bold")
                                if isinstance(w, tk.Label) and
                                w.cget("text").strip() not in ("📊", "📦", "💰",
                                                               "🎯", "📋", "🚚")
                                else (Theme.FONT, 13))
            else:
                row.configure(bg=p["sidebar"])
                for w in row.winfo_children():
                    w.configure(bg=p["sidebar"], fg=p["sidebar_text"],
                                font=(Theme.FONT, 11)
                                if isinstance(w, tk.Label) and
                                w.cget("text").strip() not in ("📊", "📦", "💰",
                                                               "🎯", "📋", "🚚")
                                else (Theme.FONT, 13))

    # ============================== КОНТЕНТ ===============================
    def _build_content(self):
        self.content = tk.Frame(self, bg=self.palette["bg"])
        self.content.grid(row=0, column=1, sticky="nsew")

    def _build_statusbar(self):
        p = self.palette
        self.status_var = tk.StringVar(value="Готово")
        bar = tk.Frame(self, bg=p["surface"], height=30)
        bar.grid(row=1, column=1, sticky="ew")
        bar.grid_propagate(False)
        tk.Frame(bar, bg=p["border"], height=1).pack(fill="x", side="top")
        tk.Label(bar, textvariable=self.status_var, bg=p["surface"],
                 fg=p["text_muted"], anchor="w",
                 font=(Theme.FONT, 9), padx=22).pack(fill="x", pady=6)

    def show_page(self, page):
        self.current_page = page
        for w in self.content.winfo_children():
            w.destroy()
        self._nav_set_active(page)
        getattr(self, f"_page_{page}")()

    # ================== ВСПОМОГАТЕЛЬНЫЕ КОМПОНЕНТЫ ========================
    def _page_header(self, parent, title, subtitle=None):
        p = self.palette
        frame = tk.Frame(parent, bg=p["bg"])
        frame.pack(fill="x", pady=(0, 22))
        tk.Label(frame, text=title, bg=p["bg"], fg=p["text"],
                 font=(Theme.FONT, 24, "bold")).pack(side="left")
        if subtitle:
            tk.Label(frame, text=f"  ·  {subtitle}",
                     bg=p["bg"], fg=p["text_muted"],
                     font=(Theme.FONT, 12)).pack(side="left", pady=(8, 0))
        return frame

    def _card(self, parent, **pack):
        p = self.palette
        c = tk.Frame(parent, bg=p["surface"],
                     highlightthickness=1, highlightbackground=p["border"])
        c.pack(**pack)
        return c

    # ============================== ДАШБОРД ===============================
    def _page_dashboard(self):
        p = self.palette
        wrap = tk.Frame(self.content, bg=p["bg"])
        wrap.pack(fill="both", expand=True, padx=32, pady=26)

        self._page_header(wrap, "Дашборд",
                          datetime.now().strftime("%d.%m.%Y"))

        # карточки-метрики
        cards = tk.Frame(wrap, bg=p["bg"])
        cards.pack(fill="x", pady=(0, 22))
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1, uniform="m")

        products = self.db.get_products()
        total_products = len(products)
        low_stock = sum(1 for r in products if r[4] < r[5])
        total_value = sum(r[3] * r[4] for r in products)
        revenue = self.db.total_sales_revenue(days=14)
        plan_count = len(self.planner.build_plan())

        self._metric(cards, 0, "📦", "Всего товаров", str(total_products), "neutral")
        self._metric(cards, 1, "⚠️", "Низкий остаток", str(low_stock),
                     "danger" if low_stock else "success")
        self._metric(cards, 2, "💰", "Стоимость склада",
                     f"{total_value:,.0f} ₽".replace(",", " "), "neutral")
        self._metric(cards, 3, "🎯", "К закупке",
                     f"{plan_count} поз.",
                     "warning" if plan_count else "success")

        # нижняя секция: график + действия
        row2 = tk.Frame(wrap, bg=p["bg"])
        row2.pack(fill="both", expand=True)
        row2.grid_columnconfigure(0, weight=2)
        row2.grid_columnconfigure(1, weight=1)
        row2.grid_rowconfigure(0, weight=1)

        left = tk.Frame(row2, bg=p["surface"],
                        highlightthickness=1, highlightbackground=p["border"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        tk.Label(left, text="Выручка за 14 дней", bg=p["surface"],
                 fg=p["text_muted"],
                 font=(Theme.FONT, 10, "bold")).pack(anchor="w", padx=22, pady=(20, 4))
        tk.Label(left, text=f"{revenue:,.2f} ₽".replace(",", " "),
                 bg=p["surface"], fg=p["success"],
                 font=(Theme.FONT, 30, "bold")).pack(anchor="w", padx=22)
        tk.Label(left, text="Динамика продаж в денежном выражении",
                 bg=p["surface"], fg=p["text_muted"],
                 font=(Theme.FONT, 9)).pack(anchor="w", padx=22, pady=(12, 4))
        self._chart(left)

        right = tk.Frame(row2, bg=p["surface"],
                         highlightthickness=1, highlightbackground=p["border"])
        right.grid(row=0, column=1, sticky="nsew")
        tk.Label(right, text="Быстрые действия", bg=p["surface"],
                 fg=p["text"],
                 font=(Theme.FONT, 12, "bold")).pack(anchor="w", padx=22, pady=(20, 14))

        for text, page in [
            ("🎯   Сформировать план", "planning"),
            ("💰   Новая продажа",      "sales"),
            ("📦   Товары и остатки",   "products"),
            ("📋   Заявки",             "orders"),
        ]:
            self._action_button(right, text, page)

        self.status_var.set("Дашборд обновлён")

    def _metric(self, parent, col, icon, title, value, kind):
        p = self.palette
        card = tk.Frame(parent, bg=p["surface"],
                        highlightthickness=1, highlightbackground=p["border"])
        card.grid(row=0, column=col, sticky="nsew", padx=7)

        head = tk.Frame(card, bg=p["surface"])
        head.pack(fill="x", padx=22, pady=(20, 0))
        tk.Label(head, text=icon, bg=p["surface"], fg=p["text"],
                 font=(Theme.FONT, 22)).pack(side="left")
        tk.Label(head, text=title, bg=p["surface"], fg=p["text_muted"],
                 font=(Theme.FONT, 10, "bold")).pack(side="left", padx=10)

        color = {"danger": p["danger"], "warning": p["warning"],
                 "success": p["success"]}.get(kind, p["text"])
        tk.Label(card, text=value, bg=p["surface"], fg=color,
                 font=(Theme.FONT, 26, "bold")).pack(
            anchor="w", padx=22, pady=(6, 20))

    def _action_button(self, parent, text, page):
        p = self.palette
        btn = tk.Label(parent, text=text, bg=p["bg"], fg=p["text"],
                       anchor="w", padx=16, pady=13,
                       font=(Theme.FONT, 10), cursor="hand2")
        btn.pack(fill="x", padx=22, pady=4)
        btn.bind("<Button-1>", lambda e: self.show_page(page))
        btn.bind("<Enter>", lambda e: btn.configure(bg=p["surface_alt"]))
        btn.bind("<Leave>", lambda e: btn.configure(bg=p["bg"]))

    def _chart(self, parent):
        p = self.palette
        rows = self.db.revenue_by_day(days=14)
        days, values = [], []
        for i in range(13, -1, -1):
            d = (datetime.now().date() - timedelta(days=i)).isoformat()
            days.append(d[-5:])
            values.append(rows.get(d, 0))

        width, height = 760, 190
        canvas = tk.Canvas(parent, width=width, height=height,
                           bg=p["surface"], highlightthickness=0)
        canvas.pack(padx=22, pady=(8, 22), fill="x")

        if not values or max(values) == 0:
            canvas.create_text(width // 2, height // 2,
                               text="Нет данных о продажах",
                               fill=p["text_muted"],
                               font=(Theme.FONT, 11))
            return

        max_v = max(values)
        # сетка
        for i in range(1, 4):
            y = 20 + i * (height - 50) / 4
            canvas.create_line(40, y, width - 10, y,
                               fill=p["border"], dash=(2, 4))
        # бары
        bar_w = (width - 60) / len(values)
        for i, v in enumerate(values):
            x0 = 45 + i * bar_w + 4
            x1 = 45 + (i + 1) * bar_w - 4
            h = (v / max_v) * (height - 60)
            y1 = height - 25
            y0 = y1 - h
            canvas.create_rectangle(x0, y0, x1, y1,
                                    fill=p["primary"], outline="")
            canvas.create_text((x0 + x1) / 2, height - 10,
                               text=days[i], fill=p["text_muted"],
                               font=(Theme.FONT, 7))
        canvas.create_text(width - 12, 12, anchor="ne",
                           text=f"макс: {max_v:,.0f} ₽".replace(",", " "),
                           fill=p["text_muted"],
                           font=(Theme.FONT, 8, "bold"))

    # ============================== ТОВАРЫ ================================
    def _page_products(self):
        p = self.palette
        wrap = tk.Frame(self.content, bg=p["bg"])
        wrap.pack(fill="both", expand=True, padx=32, pady=26)

        header = self._page_header(wrap, "Товары и остатки")
        ttk.Button(header, text="＋  Добавить",
                   style="Primary.TButton",
                   command=self._add_product_dialog).pack(side="right", padx=4)
        ttk.Button(header, text="✎  Изменить остаток",
                   style="Secondary.TButton",
                   command=self._edit_stock_dialog).pack(side="right", padx=4)
        ttk.Button(header, text="🗑  Удалить",
                   style="Danger.TButton",
                   command=self._delete_product).pack(side="right", padx=4)

        card = self._card(wrap, fill="both", expand=True)
        inner = tk.Frame(card, bg=p["surface"])
        inner.pack(fill="both", expand=True, padx=2, pady=2)

        cols = ("id", "name", "unit", "price", "stock", "min_stock", "supplier", "status")
        headers = ("№", "Наименование", "Ед.", "Цена, ₽",
                   "Остаток", "Минимум", "Поставщик", "Статус")
        self.tree_products = ttk.Treeview(inner, columns=cols,
                                          show="headings", height=20)
        widths = (50, 260, 70, 110, 110, 100, 240, 140)
        for c, h, w in zip(cols, headers, widths):
            self.tree_products.heading(c, text=h)
            anchor = "w" if c in ("name", "supplier") else "center"
            self.tree_products.column(c, width=w, anchor=anchor)

        sb = ttk.Scrollbar(inner, orient="vertical",
                           command=self.tree_products.yview)
        self.tree_products.configure(yscrollcommand=sb.set)
        self.tree_products.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._refresh_products()

    def _refresh_products(self):
        if not hasattr(self, "tree_products") or not self.tree_products.winfo_exists():
            return
        for i in self.tree_products.get_children():
            self.tree_products.delete(i)
        p = self.palette
        for idx, row in enumerate(self.db.get_products()):
            pid, name, unit, price, stock, min_stock, supplier = row
            if stock < min_stock:
                status, status_tag = "● мало", "low"
            elif stock < min_stock * 1.5:
                status, status_tag = "● норма", "mid"
            else:
                status, status_tag = "● запас", "ok"
            zebra = "even" if idx % 2 == 0 else "odd"
            self.tree_products.insert(
                "", "end",
                values=(pid, name, unit, f"{price:.2f}",
                        stock, min_stock, supplier, status),
                tags=(zebra, status_tag),
            )
        self.tree_products.tag_configure("low", foreground=p["danger"])
        self.tree_products.tag_configure("mid", foreground=p["warning"])
        self.tree_products.tag_configure("ok", foreground=p["success"])
        self.tree_products.tag_configure("odd", background=p["surface_alt"])
        self.tree_products.tag_configure("even", background=p["surface"])

    # =========================== ПРОДАЖИ ==================================
    def _page_sales(self):
        p = self.palette
        wrap = tk.Frame(self.content, bg=p["bg"])
        wrap.pack(fill="both", expand=True, padx=32, pady=26)

        self._page_header(wrap, "Регистрация продаж")

        # форма
        form = self._card(wrap, fill="x", pady=(0, 18))
        tk.Label(form, text="Новая продажа",
                 bg=p["surface"], fg=p["text"],
                 font=(Theme.FONT, 12, "bold")).pack(anchor="w", padx=22, pady=(18, 12))

        grid = tk.Frame(form, bg=p["surface"])
        grid.pack(fill="x", padx=22, pady=(0, 20))

        tk.Label(grid, text="Товар", bg=p["surface"], fg=p["text_muted"],
                 font=(Theme.FONT, 9)).grid(row=0, column=0, sticky="w")
        tk.Label(grid, text="Количество", bg=p["surface"], fg=p["text_muted"],
                 font=(Theme.FONT, 9)).grid(row=0, column=1, sticky="w", padx=14)

        self.sale_product = ttk.Combobox(grid, state="readonly", width=48)
        self.sale_product.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.sale_qty = ttk.Entry(grid, width=14)
        self.sale_qty.grid(row=1, column=1, padx=14, sticky="w", pady=(4, 0))
        ttk.Button(grid, text="💰  Провести", style="Success.TButton",
                   command=self._register_sale).grid(row=1, column=2,
                                                    padx=(20, 0), pady=(4, 0))
        grid.grid_columnconfigure(0, weight=1)

        # история
        hist = self._card(wrap, fill="both", expand=True)
        tk.Label(hist, text="История продаж за 14 дней",
                 bg=p["surface"], fg=p["text"],
                 font=(Theme.FONT, 12, "bold")).pack(anchor="w", padx=22, pady=(18, 12))

        body = tk.Frame(hist, bg=p["surface"])
        body.pack(fill="both", expand=True, padx=22, pady=(0, 22))

        left = tk.Frame(body, bg=p["surface"])
        left.pack(side="left", fill="both", expand=True)
        cols = ("date", "qty")
        self.tree_sales = ttk.Treeview(left, columns=cols,
                                       show="headings", height=12)
        self.tree_sales.heading("date", text="Дата")
        self.tree_sales.heading("qty", text="Продано, шт")
        self.tree_sales.column("date", width=220, anchor="center")
        self.tree_sales.column("qty", width=160, anchor="center")
        self.tree_sales.pack(fill="both", expand=True, side="left")
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tree_sales.yview)
        self.tree_sales.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        right = tk.Frame(body, bg=p["surface"], width=340)
        right.pack(side="right", fill="y", padx=(24, 0))
        right.pack_propagate(False)
        tk.Label(right, text="АНАЛИТИКА", bg=p["surface"], fg=p["text_muted"],
                 font=(Theme.FONT, 9, "bold")).pack(anchor="w")
        self.stats_var = tk.StringVar(value="Выберите товар для просмотра")
        tk.Label(right, textvariable=self.stats_var,
                 bg=p["surface"], fg=p["text"],
                 font=(Theme.FONT, 10), justify="left",
                 wraplength=320).pack(anchor="w", pady=12)

        self.sale_product.bind("<<ComboboxSelected>>",
                               lambda e: self._show_sales_history())
        self._refresh_sales_combobox()

    def _refresh_sales_combobox(self):
        if not hasattr(self, "sale_product") or not self.sale_product.winfo_exists():
            return
        products = self.db.get_products()
        values = [f"{p[0]}: {p[1]} (остаток {p[4]})" for p in products]
        self.sale_product["values"] = values
        if values:
            self.sale_product.current(0)
            self._show_sales_history()

    def _show_sales_history(self):
        for i in self.tree_sales.get_children():
            self.tree_sales.delete(i)
        sel = self.sale_product.get()
        if not sel:
            return
        pid = int(sel.split(":")[0])
        history = self.db.get_sales_history(pid, days=14)
        p = self.palette
        for idx, (d, q) in enumerate(history):
            zebra = "even" if idx % 2 == 0 else "odd"
            self.tree_sales.insert("", "end", values=(d, q), tags=(zebra,))
        self.tree_sales.tag_configure("odd", background=p["surface_alt"])
        self.tree_sales.tag_configure("even", background=p["surface"])

        if history:
            qtys = [q for _, q in history]
            self.stats_var.set(
                f"Всего продано:  {sum(qtys)} шт\n\n"
                f"Дней с продажами:  {len(qtys)} из 14\n"
                f"Средняя в активные дни:  {mean(qtys):.2f} шт\n\n"
                f"ADU (для планирования):\n"
                f"{self.planner.avg_daily_sales(pid):.2f} шт/день"
            )
        else:
            self.stats_var.set("Продаж за период не было")

    def _register_sale(self):
        try:
            sel = self.sale_product.get()
            if not sel:
                raise ValueError("Выберите товар")
            pid = int(sel.split(":")[0])
            qty = int(self.sale_qty.get())
            if qty <= 0:
                raise ValueError("Количество должно быть положительным")
            self.db.add_sale(pid, qty)
            self.sale_qty.delete(0, "end")
            self._refresh_sales_combobox()
            self._show_sales_history()
            self.status_var.set(f"Продажа зарегистрирована: {qty} шт")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # ========================== ПЛАНИРОВАНИЕ ==============================
    def _page_planning(self):
        p = self.palette
        wrap = tk.Frame(self.content, bg=p["bg"])
        wrap.pack(fill="both", expand=True, padx=32, pady=26)

        header = self._page_header(wrap, "План закупок")
        ttk.Button(header, text="🔄  Пересчитать",
                   style="Secondary.TButton",
                   command=self._refresh_plan).pack(side="right", padx=4)
        ttk.Button(header, text="✓  Сформировать заявки",
                   style="Success.TButton",
                   command=self._create_orders_from_plan).pack(side="right", padx=4)

        info = self._card(wrap, fill="x", pady=(0, 18))
        tk.Label(info, text="📐  Алгоритм расчёта",
                 bg=p["surface"], fg=p["text"],
                 font=(Theme.FONT, 10, "bold")).pack(anchor="w", padx=22, pady=(14, 4))
        tk.Label(info,
                 text="ROP = ADU · LT · (1 + k)        Q = ROP + N · ADU − остаток",
                 bg=p["surface"], fg=p["primary"],
                 font=("Consolas", 11, "bold")).pack(anchor="w", padx=22)
        tk.Label(info,
                 text="ADU — средняя дневная продажа за 14 дней   •   "
                      "LT — срок поставки   •   k = 0,3 (страховой запас)   •   "
                      "N = 7 дней (горизонт покрытия)",
                 bg=p["surface"], fg=p["text_muted"],
                 font=(Theme.FONT, 9), wraplength=900,
                 justify="left").pack(anchor="w", padx=22, pady=(2, 14))

        card = self._card(wrap, fill="both", expand=True)
        cols = ("product", "stock", "adu", "rop", "qty", "supplier", "lt", "sum")
        headers = ("Товар", "Остаток", "ADU", "Точка заказа",
                   "К заказу", "Поставщик", "Срок, дн.", "Сумма, ₽")
        self.tree_plan = ttk.Treeview(card, columns=cols,
                                      show="headings", height=15)
        widths = (260, 90, 80, 130, 100, 220, 100, 150)
        for c, h, w in zip(cols, headers, widths):
            self.tree_plan.heading(c, text=h)
            anchor = "w" if c in ("product", "supplier") else "center"
            self.tree_plan.column(c, width=w, anchor=anchor)
        self.tree_plan.pack(fill="both", expand=True, padx=2, pady=2)

        self.plan_summary = tk.StringVar(value="")
        summary = tk.Frame(wrap, bg=p["bg"])
        summary.pack(fill="x", pady=(12, 0))
        tk.Label(summary, textvariable=self.plan_summary,
                 bg=p["bg"], fg=p["text"],
                 font=(Theme.FONT, 11, "bold")).pack(side="right")

        self._refresh_plan()

    def _refresh_plan(self):
        if not hasattr(self, "tree_plan") or not self.tree_plan.winfo_exists():
            return
        for i in self.tree_plan.get_children():
            self.tree_plan.delete(i)
        self._current_plan = self.planner.build_plan()
        total = 0
        p = self.palette
        for idx, item in enumerate(self._current_plan):
            zebra = "even" if idx % 2 == 0 else "odd"
            self.tree_plan.insert("", "end", values=(
                item["product"], item["stock"], item["adu"],
                item["reorder_point"], item["qty"], item["supplier"],
                item["lead_time"],
                f"{item['sum']:,.2f}".replace(",", " "),
            ), tags=(zebra,))
            total += item["sum"]
        self.tree_plan.tag_configure("odd", background=p["surface_alt"])
        self.tree_plan.tag_configure("even", background=p["surface"])

        fmt = f"{total:,.2f}".replace(",", " ")
        self.plan_summary.set(
            f"Позиций к закупке: {len(self._current_plan)}     "
            f"Итого: {fmt} ₽"
        )
        self.status_var.set("План пересчитан")

    def _create_orders_from_plan(self):
        if not self._current_plan:
            messagebox.showinfo("Информация",
                                "Нет позиций для заказа — все остатки в норме")
            return
        by_sup = {}
        for it in self._current_plan:
            by_sup.setdefault(it["supplier_id"], []).append(
                (it["product_id"], it["qty"]))
        created = []
        for sid, items in by_sup.items():
            created.append(self.db.save_purchase_order(sid, items))
        messagebox.showinfo("Заявки созданы",
                            f"Создано заявок: {len(created)}\n"
                            f"Номера: {', '.join(map(str, created))}")
        self.show_page("orders")

    # ============================= ЗАЯВКИ =================================
    def _page_orders(self):
        p = self.palette
        wrap = tk.Frame(self.content, bg=p["bg"])
        wrap.pack(fill="both", expand=True, padx=32, pady=26)

        header = self._page_header(wrap, "Заявки на закупку")
        ttk.Button(header, text="✓  Принять поставку",
                   style="Success.TButton",
                   command=self._receive_order).pack(side="right", padx=4)
        ttk.Button(header, text="🔄  Обновить",
                   style="Secondary.TButton",
                   command=self._refresh_orders).pack(side="right", padx=4)

        top = self._card(wrap, fill="both", expand=True, pady=(0, 14))
        tk.Label(top, text="Список заявок",
                 bg=p["surface"], fg=p["text"],
                 font=(Theme.FONT, 11, "bold")).pack(anchor="w", padx=22, pady=(14, 8))
        cols = ("id", "supplier", "created", "status", "total")
        headers = ("№", "Поставщик", "Дата создания", "Статус", "Сумма, ₽")
        self.tree_orders = ttk.Treeview(top, columns=cols,
                                        show="headings", height=7)
        widths = (60, 280, 180, 150, 160)
        for c, h, w in zip(cols, headers, widths):
            self.tree_orders.heading(c, text=h)
            anchor = "w" if c == "supplier" else "center"
            self.tree_orders.column(c, width=w, anchor=anchor)
        self.tree_orders.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        self.tree_orders.bind("<<TreeviewSelect>>",
                              lambda e: self._show_order_items())

        bot = self._card(wrap, fill="both", expand=True)
        tk.Label(bot, text="Позиции выбранной заявки",
                 bg=p["surface"], fg=p["text"],
                 font=(Theme.FONT, 11, "bold")).pack(anchor="w", padx=22, pady=(14, 8))
        cols2 = ("product", "qty", "price", "sum")
        headers2 = ("Товар", "Кол-во", "Цена, ₽", "Сумма, ₽")
        self.tree_order_items = ttk.Treeview(bot, columns=cols2,
                                             show="headings", height=8)
        widths2 = (400, 140, 160, 180)
        for c, h, w in zip(cols2, headers2, widths2):
            self.tree_order_items.heading(c, text=h)
            anchor = "w" if c == "product" else "center"
            self.tree_order_items.column(c, width=w, anchor=anchor)
        self.tree_order_items.pack(fill="both", expand=True, padx=18, pady=(0, 16))

        self._refresh_orders()

    def _refresh_orders(self):
        if not hasattr(self, "tree_orders") or not self.tree_orders.winfo_exists():
            return
        for i in self.tree_orders.get_children():
            self.tree_orders.delete(i)
        p = self.palette
        for idx, row in enumerate(self.db.get_orders()):
            oid, supplier, created, status, total = row
            total = total or 0
            zebra = "even" if idx % 2 == 0 else "odd"
            status_tag = "received" if status == "получено" else "draft"
            mark = "✓ получено" if status == "получено" else "● черновик"
            created_short = created[:16].replace("T", " ")
            self.tree_orders.insert(
                "", "end",
                values=(oid, supplier, created_short, mark,
                        f"{total:,.2f}".replace(",", " ")),
                tags=(zebra, status_tag),
            )
        self.tree_orders.tag_configure("odd", background=p["surface_alt"])
        self.tree_orders.tag_configure("even", background=p["surface"])
        self.tree_orders.tag_configure("received", foreground=p["success"])
        self.tree_orders.tag_configure("draft", foreground=p["warning"])

        for i in self.tree_order_items.get_children():
            self.tree_order_items.delete(i)

    def _show_order_items(self):
        sel = self.tree_orders.selection()
        if not sel:
            return
        oid = self.tree_orders.item(sel[0])["values"][0]
        for i in self.tree_order_items.get_children():
            self.tree_order_items.delete(i)
        p = self.palette
        for idx, (name, qty, price, total) in enumerate(self.db.get_order_items(oid)):
            zebra = "even" if idx % 2 == 0 else "odd"
            self.tree_order_items.insert(
                "", "end",
                values=(name, qty, f"{price:.2f}",
                        f"{total:,.2f}".replace(",", " ")),
                tags=(zebra,),
            )
        self.tree_order_items.tag_configure("odd", background=p["surface_alt"])
        self.tree_order_items.tag_configure("even", background=p["surface"])

    def _receive_order(self):
        sel = self.tree_orders.selection()
        if not sel:
            messagebox.showinfo("Подсказка", "Выберите заявку")
            return
        oid = self.tree_orders.item(sel[0])["values"][0]
        try:
            self.db.mark_order_received(oid)
            self._refresh_orders()
            self.status_var.set(f"Заявка №{oid} принята, остатки пополнены")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # =========================== ПОСТАВЩИКИ ===============================
    def _page_suppliers(self):
        p = self.palette
        wrap = tk.Frame(self.content, bg=p["bg"])
        wrap.pack(fill="both", expand=True, padx=32, pady=26)

        header = self._page_header(wrap, "Поставщики")
        ttk.Button(header, text="＋  Добавить поставщика",
                   style="Primary.TButton",
                   command=self._add_supplier_dialog).pack(side="right")

        card = self._card(wrap, fill="both", expand=True)
        cols = ("id", "name", "contact", "lt")
        headers = ("№", "Наименование", "Контакт", "Срок поставки, дн.")
        self.tree_suppliers = ttk.Treeview(card, columns=cols,
                                           show="headings", height=18)
        widths = (60, 340, 260, 220)
        for c, h, w in zip(cols, headers, widths):
            self.tree_suppliers.heading(c, text=h)
            anchor = "w" if c in ("name", "contact") else "center"
            self.tree_suppliers.column(c, width=w, anchor=anchor)
        self.tree_suppliers.pack(fill="both", expand=True, padx=2, pady=2)

        self._refresh_suppliers()

    def _refresh_suppliers(self):
        if not hasattr(self, "tree_suppliers") or not self.tree_suppliers.winfo_exists():
            return
        for i in self.tree_suppliers.get_children():
            self.tree_suppliers.delete(i)
        p = self.palette
        for idx, s in enumerate(self.db.get_suppliers()):
            zebra = "even" if idx % 2 == 0 else "odd"
            self.tree_suppliers.insert("", "end", values=s, tags=(zebra,))
        self.tree_suppliers.tag_configure("odd", background=p["surface_alt"])
        self.tree_suppliers.tag_configure("even", background=p["surface"])

    # ============================== ДИАЛОГИ ===============================
    def _modal(self, title, w, h):
        p = self.palette
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.configure(bg=p["surface"])
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        return dlg

    def _add_product_dialog(self):
        p = self.palette
        dlg = self._modal("Новый товар", 420, 400)

        tk.Label(dlg, text="Новый товар", bg=p["surface"], fg=p["text"],
                 font=(Theme.FONT, 14, "bold")).pack(anchor="w",
                                                     padx=24, pady=(20, 16))

        form = tk.Frame(dlg, bg=p["surface"])
        form.pack(fill="x", padx=24)

        fields = {}
        labels = [("Наименование", "name", ""),
                  ("Единица измерения", "unit", "шт"),
                  ("Цена, ₽", "price", ""),
                  ("Текущий остаток", "stock", "0"),
                  ("Минимальный остаток", "min_stock", "5")]
        for i, (lbl, key, default) in enumerate(labels):
            tk.Label(form, text=lbl, bg=p["surface"], fg=p["text_muted"],
                     font=(Theme.FONT, 9)).grid(
                row=i * 2, column=0, sticky="w", pady=(8, 2))
            e = ttk.Entry(form, width=44)
            e.grid(row=i * 2 + 1, column=0, sticky="ew")
            e.insert(0, default)
            fields[key] = e

        tk.Label(form, text="Поставщик", bg=p["surface"], fg=p["text_muted"],
                 font=(Theme.FONT, 9)).grid(
            row=len(labels) * 2, column=0, sticky="w", pady=(8, 2))
        suppliers = self.db.get_suppliers()
        names = [f"{s[0]}: {s[1]}" for s in suppliers]
        cmb = ttk.Combobox(form, values=names, state="readonly", width=42)
        cmb.grid(row=len(labels) * 2 + 1, column=0, sticky="ew")
        if names:
            cmb.current(0)

        def save():
            try:
                name = fields["name"].get().strip()
                if not name:
                    raise ValueError("Введите наименование")
                if not cmb.get():
                    raise ValueError("Выберите поставщика")
                self.db.add_product(
                    name,
                    fields["unit"].get().strip() or "шт",
                    float(fields["price"].get().replace(",", ".")),
                    int(fields["stock"].get()),
                    int(fields["min_stock"].get()),
                    int(cmb.get().split(":")[0]),
                )
                self._refresh_products()
                self.status_var.set(f"Товар «{name}» добавлен")
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Ошибка", str(e), parent=dlg)

        btns = tk.Frame(dlg, bg=p["surface"])
        btns.pack(side="bottom", pady=20)
        ttk.Button(btns, text="Сохранить", style="Primary.TButton",
                   command=save).pack(side="left", padx=6)
        ttk.Button(btns, text="Отмена", style="Secondary.TButton",
                   command=dlg.destroy).pack(side="left", padx=6)

    def _edit_stock_dialog(self):
        sel = self.tree_products.selection()
        if not sel:
            messagebox.showinfo("Подсказка", "Выберите товар в таблице")
            return
        item = self.tree_products.item(sel[0])
        pid, name, current = item["values"][0], item["values"][1], item["values"][4]
        val = simpledialog.askinteger(
            "Изменение остатка",
            f"Новый остаток для «{name}»:",
            initialvalue=current, minvalue=0, parent=self,
        )
        if val is not None:
            self.db.update_product_stock(pid, val)
            self._refresh_products()
            self.status_var.set(f"Остаток «{name}» обновлён: {val}")

    def _delete_product(self):
        sel = self.tree_products.selection()
        if not sel:
            return
        item = self.tree_products.item(sel[0])
        pid, name = item["values"][0], item["values"][1]
        if messagebox.askyesno("Подтверждение", f"Удалить «{name}»?"):
            self.db.delete_product(pid)
            self._refresh_products()
            self.status_var.set(f"Товар «{name}» удалён")

    def _add_supplier_dialog(self):
        p = self.palette
        dlg = self._modal("Новый поставщик", 420, 290)

        tk.Label(dlg, text="Новый поставщик", bg=p["surface"], fg=p["text"],
                 font=(Theme.FONT, 14, "bold")).pack(anchor="w",
                                                     padx=24, pady=(20, 16))

        form = tk.Frame(dlg, bg=p["surface"])
        form.pack(fill="x", padx=24)

        entries = []
        for i, (lbl, default) in enumerate([("Наименование", ""),
                                            ("Контакт", ""),
                                            ("Срок поставки, дн.", "3")]):
            tk.Label(form, text=lbl, bg=p["surface"], fg=p["text_muted"],
                     font=(Theme.FONT, 9)).grid(
                row=i * 2, column=0, sticky="w", pady=(8, 2))
            e = ttk.Entry(form, width=44)
            e.grid(row=i * 2 + 1, column=0, sticky="ew")
            e.insert(0, default)
            entries.append(e)

        def save():
            try:
                name = entries[0].get().strip()
                if not name:
                    raise ValueError("Введите наименование")
                self.db.add_supplier(name, entries[1].get().strip(),
                                     int(entries[2].get()))
                self._refresh_suppliers()
                self.status_var.set(f"Поставщик «{name}» добавлен")
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Ошибка", str(e), parent=dlg)

        btns = tk.Frame(dlg, bg=p["surface"])
        btns.pack(side="bottom", pady=20)
        ttk.Button(btns, text="Сохранить", style="Primary.TButton",
                   command=save).pack(side="left", padx=6)
        ttk.Button(btns, text="Отмена", style="Secondary.TButton",
                   command=dlg.destroy).pack(side="left", padx=6)


# ===========================================================================
if __name__ == "__main__":
    app = App()
    app.mainloop()
