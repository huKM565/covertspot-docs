import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
import psutil
import subprocess
import json

# Константы
CONFIG_FILE = "deployer_config.json"
MIN_BLOCK_WIDTH = 200
BLOCK_PADX = 5
BLOCK_PADY = 5
INNER_PAD = 5
DEFAULT_WIDTH = 900
DEFAULT_HEIGHT = 600
DEFAULT_X = 100
DEFAULT_Y = 100

class AutoWidthBlock:
    def __init__(self, parent, title):
        self.frame = ttk.LabelFrame(parent, text=title, width=MIN_BLOCK_WIDTH)
        self.frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=BLOCK_PADX, pady=BLOCK_PADY)
        self.content = ttk.Frame(self.frame)
        self.content.pack(fill=tk.BOTH, expand=True, padx=INNER_PAD, pady=INNER_PAD)

    def add_entry(self, textvariable):
        entry = ttk.Entry(self.content, textvariable=textvariable)
        entry.pack(fill=tk.X, pady=2)
        return entry

    def add_button(self, text, command):
        btn = ttk.Button(self.content, text=text, command=command)
        btn.pack(fill=tk.X, pady=2)
        return btn

    def add_label(self, text):
        lbl = ttk.Label(self.content, text=text)
        lbl.pack(fill=tk.X, pady=2)
        return lbl

class PluginDeployerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Spigot Plugin Auto-Deployer")
        
        # Инициализация переменных
        self.project_dir = tk.StringVar()
        self.server_dir = tk.StringVar()
        self.process_name = tk.StringVar(value="java.exe")
        self.is_running = False
        self.observer = None
        self.target_dir = ""
        self.plugins_dir = ""
        self.bat_file = ""
        
        # Параметры окна
        self.window_width = DEFAULT_WIDTH
        self.window_height = DEFAULT_HEIGHT
        self.window_x = DEFAULT_X
        self.window_y = DEFAULT_Y
        
        # Загружаем конфиг
        self.load_config()
        
        # Устанавливаем геометрию ПОСЛЕ загрузки конфига
        self.root.geometry(f"{self.window_width}x{self.window_height}+{self.window_x}+{self.window_y}")
        
        # Главный контейнер
        main_frame = ttk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Создание интерфейса
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X)
        self.create_interface(top_frame)
        
        # Блок логов
        log_frame = ttk.LabelFrame(main_frame, text="Лог выполнения")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(
            log_frame,
            height=15,
            state="disabled",
            yscrollcommand=scrollbar.set,
            wrap=tk.WORD
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        # Обработчик изменения размера и положения
        self.root.bind('<Configure>', self.on_window_change)

    def on_window_change(self, event):
        """Сохраняем параметры окна при изменении"""
        if event.widget == self.root:
            # Обновляем только если окно не минимизировано
            if not self.root.state() == 'iconic':
                self.window_width = self.root.winfo_width()
                self.window_height = self.root.winfo_height()
                self.window_x = self.root.winfo_x()
                self.window_y = self.root.winfo_y()
                self.save_config()

    def create_interface(self, parent):
        """Создание интерфейса"""
        # Блок проекта
        project_block = AutoWidthBlock(parent, "Папка проекта")
        project_block.add_entry(self.project_dir)
        project_block.add_button("Выбрать папку", self.select_project_dir)

        # Блок сервера
        server_block = AutoWidthBlock(parent, "Папка сервера")
        server_block.add_entry(self.server_dir)
        server_block.add_button("Выбрать папку", self.select_server_dir)

        # Блок процесса
        process_block = AutoWidthBlock(parent, "Настройки сервера")
        process_block.add_entry(self.process_name)
        process_block.add_label("Имя процесса (java.exe)")

        # Блок управления
        control_block = AutoWidthBlock(parent, "Управление")
        self.start_btn = ttk.Button(
            control_block.content, 
            text="Запуск мониторинга", 
            command=self.start_monitoring
        )
        self.start_btn.pack(fill=tk.X, pady=2)
        
        ttk.Button(
            control_block.content,
            text="Остановить",
            command=self.stop_monitoring
        ).pack(fill=tk.X, pady=2)

    def load_config(self):
        """Загрузка конфигурации"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    
                    # Загружаем параметры окна
                    self.window_width = config.get("window_width", DEFAULT_WIDTH)
                    self.window_height = config.get("window_height", DEFAULT_HEIGHT)
                    self.window_x = config.get("window_x", DEFAULT_X)
                    self.window_y = config.get("window_y", DEFAULT_Y)
                    
                    # Проверяем, чтобы окно не выходило за пределы экрана
                    screen_width = self.root.winfo_screenwidth()
                    screen_height = self.root.winfo_screenheight()
                    
                    if self.window_x < 0 or self.window_x > screen_width - 100:
                        self.window_x = DEFAULT_X
                    if self.window_y < 0 or self.window_y > screen_height - 100:
                        self.window_y = DEFAULT_Y
                    
                    # Загружаем остальные параметры
                    if "project_dir" in config:
                        self.project_dir.set(config["project_dir"])
                    if "server_dir" in config:
                        self.server_dir.set(config["server_dir"])
                    if "process_name" in config:
                        self.process_name.set(config["process_name"])
                    
                    # Обновляем пути
                    if self.project_dir.get():
                        self.target_dir = os.path.join(self.project_dir.get(), "target")
                    if self.server_dir.get():
                        self.plugins_dir = os.path.join(self.server_dir.get(), "plugins")
                        self.bat_file = os.path.join(self.server_dir.get(), "start.bat")
                        
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить конфиг:\n{str(e)}")

    def save_config(self):
        """Сохранение конфигурации"""
        config = {
            "window_width": self.window_width,
            "window_height": self.window_height,
            "window_x": self.window_x,
            "window_y": self.window_y,
            "project_dir": self.project_dir.get(),
            "server_dir": self.server_dir.get(),
            "process_name": self.process_name.get()
        }
        
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить конфиг:\n{str(e)}")

    def select_project_dir(self):
        dir_path = filedialog.askdirectory(title="Выберите папку проекта плагина")
        if dir_path:
            self.project_dir.set(dir_path)
            self.target_dir = os.path.join(dir_path, "target")
            self.save_config()

    def select_server_dir(self):
        dir_path = filedialog.askdirectory(title="Выберите папку сервера")
        if dir_path:
            self.server_dir.set(dir_path)
            self.plugins_dir = os.path.join(dir_path, "plugins")
            self.bat_file = os.path.join(dir_path, "start.bat")
            self.save_config()

    def log_message(self, message):
        time_str = datetime.now().strftime("[%H:%M:%S]")
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"{time_str} {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def update_paths(self):
        project_path = self.project_dir.get()
        server_path = self.server_dir.get()
        
        if not project_path:
            self.log_message("⚠ Не указана папка проекта")
            return False
            
        self.target_dir = os.path.join(project_path, "target")
        if not os.path.exists(self.target_dir):
            self.log_message(f"⚠ Папка 'target' не найдена в проекте")
            return False
            
        if not server_path:
            self.log_message("⚠ Не указана папка сервера")
            return False
            
        self.plugins_dir = os.path.join(server_path, "plugins")
        self.bat_file = os.path.join(server_path, "start.bat")
        
        if not os.path.exists(self.plugins_dir):
            self.log_message(f"⚠ Папка 'plugins' не найдена в сервере")
            return False
            
        if not os.path.exists(self.bat_file):
            self.log_message(f"⚠ Файл 'start.bat' не найден в сервере")
            return False
            
        return True

    def start_monitoring(self):
        if not self.update_paths():
            messagebox.showerror("Ошибка", "Проверьте папки проекта и сервера!")
            return
            
        self.is_running = True
        self.start_btn.config(state="disabled")
        self.log_message(f"Мониторинг запущен:\n- Проект: {self.project_dir.get()}\n- Сервер: {self.server_dir.get()}")
        
        event_handler = PluginHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.target_dir, recursive=False)
        self.observer.start()

    def stop_monitoring(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.is_running = False
        self.start_btn.config(state="normal")
        self.log_message("Мониторинг остановлен")

    def kill_process(self):
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] == self.process_name.get():
                    proc.kill()
                    self.log_message(f"Процесс {self.process_name.get()} завершён")
                    return True
            self.log_message(f"Процесс {self.process_name.get()} не найден")
            return False
        except Exception as e:
            self.log_message(f"Ошибка: {str(e)}")
            return False

    def run_bat(self):
        try:
            subprocess.Popen(
                [self.bat_file],
                cwd=self.server_dir.get(),
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            self.log_message(f"Сервер запущен: {self.bat_file}")
        except Exception as e:
            self.log_message(f"Ошибка запуска: {str(e)}")

    def on_close(self):
        self.stop_monitoring()
        self.save_config()
        self.root.destroy()

class PluginHandler(FileSystemEventHandler):
    def __init__(self, app):
        self.app = app
    
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".jar"):
            filename = os.path.basename(event.src_path)
            
            if "original" not in filename.lower() and "shaded" not in filename.lower():
                src = event.src_path
                dst = os.path.join(self.app.plugins_dir, filename)
                
                self.app.log_message(f"Обнаружен плагин: {filename}")
                
                try:
                    if os.path.exists(dst):
                        os.remove(dst)
                        self.app.log_message(f"Удалена старая версия: {filename}")
                    
                    shutil.move(src, dst)
                    self.app.log_message(f"Плагин перемещён в: {dst}")
                    
                    if self.app.kill_process():
                        self.app.run_bat()
                        
                except Exception as e:
                    self.app.log_message(f"Ошибка: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = PluginDeployerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()