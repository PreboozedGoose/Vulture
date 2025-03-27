import os
import csv
import time
import random
import configparser
import smtplib
from datetime import datetime, timedelta
from tkinter import *
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
from instagrapi import Client
from instagrapi.exceptions import (
    LoginRequired, ChallengeRequired, 
    ClientError, ClientConnectionError
)
import yagmail
import schedule
import threading
from dotenv import load_dotenv
import pytz

# Load environment variables
load_dotenv()

class InstagramAutomation:
    def __init__(self):
        self.client = None
        self.current_account = None
        self.settings = {
            'follow_delay': (30, 90),
            'unfollow_delay': (30, 90),
            'daily_follow_limit': 100,
            'daily_unfollow_limit': 100,
            'actions_per_hour': 30
        }
        self.load_config()
        
        # Email settings
        self.email_enabled = False
        if os.getenv('EMAIL_USER') and os.getenv('EMAIL_PASS'):
            self.email_enabled = True
            self.yag = yagmail.SMTP(
                os.getenv('EMAIL_USER'), 
                os.getenv('EMAIL_PASS')
            )

    def load_config(self):
        config = configparser.ConfigParser()
        if os.path.exists('config.ini'):
            config.read('config.ini')
            if 'Settings' in config:
                self.settings = {
                    'follow_delay': tuple(map(int, config['Settings'].get('follow_delay', '30,90').split(','))),
                    'unfollow_delay': tuple(map(int, config['Settings'].get('unfollow_delay', '30,90').split(','))),
                    'daily_follow_limit': int(config['Settings'].get('daily_follow_limit', '100')),
                    'daily_unfollow_limit': int(config['Settings'].get('daily_unfollow_limit', '100')),
                    'actions_per_hour': int(config['Settings'].get('actions_per_hour', '30'))
                }

    def save_config(self):
        config = configparser.ConfigParser()
        config['Settings'] = {
            'follow_delay': f"{self.settings['follow_delay'][0]},{self.settings['follow_delay'][1]}",
            'unfollow_delay': f"{self.settings['unfollow_delay'][0]},{self.settings['unfollow_delay'][1]}",
            'daily_follow_limit': str(self.settings['daily_follow_limit']),
            'daily_unfollow_limit': str(self.settings['daily_unfollow_limit']),
            'actions_per_hour': str(self.settings['actions_per_hour'])
        }
        with open('config.ini', 'w') as configfile:
            config.write(configfile)

    def login(self, username, password):
        self.client = Client()
        try:
            # Try to load session if exists
            session_file = f"accounts/{username}.session"
            if os.path.exists(session_file):
                self.client.load_settings(session_file)
            
            self.client.login(username, password)
            self.client.dump_settings(session_file)
            self.current_account = username
            return True
        except (LoginRequired, ChallengeRequired, ClientError) as e:
            self.send_error_email(f"Login failed for {username}", str(e))
            return False
        except Exception as e:
            self.send_error_email(f"Unexpected login error for {username}", str(e))
            return False

    def send_error_email(self, subject, content):
        if not self.email_enabled:
            return
            
        try:
            self.yag.send(
                to=os.getenv('EMAIL_USER'),
                subject=f"Instagram Tool Error: {subject}",
                contents=content
            )
        except Exception as e:
            print(f"Failed to send error email: {e}")

    def send_weekly_report(self):
        if not self.email_enabled:
            return
            
        # Generate report content from logs
        report_content = "Weekly Instagram Automation Report\n\n"
        # Add actual report data here
        
        try:
            self.yag.send(
                to=os.getenv('EMAIL_USER'),
                subject="Weekly Instagram Automation Report",
                contents=report_content
            )
        except Exception as e:
            print(f"Failed to send weekly report: {e}")

    def follow_users(self, usernames, progress_callback=None):
        if not self.client:
            return False
            
        followed = []
        for i, username in enumerate(usernames):
            try:
                user_id = self.client.user_id_from_username(username)
                self.client.user_follow(user_id)
                followed.append({
                    'username': username,
                    'timestamp': datetime.now(pytz.utc),
                    'action': 'follow'
                })
                
                # Random delay between actions
                delay = random.randint(*self.settings['follow_delay'])
                if progress_callback:
                    progress_callback(i+1, len(usernames), delay)
                time.sleep(delay)
                
            except Exception as e:
                error_msg = f"Failed to follow {username}: {str(e)}"
                self.log_error(error_msg)
                self.send_error_email("Follow Error", error_msg)
                
        self.log_actions(followed)
        return True

    def unfollow_users(self, usernames, progress_callback=None):
        # Similar implementation to follow_users
        pass

    def log_actions(self, actions):
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        log_file = f"logs/actions_{datetime.now().strftime('%Y-%m')}.csv"
        file_exists = os.path.isfile(log_file)
        
        with open(log_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['timestamp', 'account', 'action', 'username'])
            if not file_exists:
                writer.writeheader()
                
            for action in actions:
                writer.writerow({
                    'timestamp': action['timestamp'],
                    'account': self.current_account,
                    'action': action['action'],
                    'username': action['username']
                })

    def log_error(self, error_msg):
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        error_file = f"logs/errors_{datetime.now().strftime('%Y-%m')}.csv"
        file_exists = os.path.isfile(error_file)
        
        with open(error_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['timestamp', 'account', 'error'])
            if not file_exists:
                writer.writeheader()
                
            writer.writerow({
                'timestamp': datetime.now(pytz.utc),
                'account': self.current_account,
                'error': error_msg
            })

class AutomationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Instagram Automation Tool")
        self.root.geometry("900x650")
        self.root.minsize(800, 600)
        
        # Initialize automation engine
        self.automation = InstagramAutomation()
        
        # Load assets
        self.load_assets()
        
        # Setup UI
        self.setup_ui()
        
        # Start background scheduler
        self.start_scheduler()
        
    def load_assets(self):
        # Create assets directory if not exists
        if not os.path.exists('assets'):
            os.makedirs('assets')
            
        # Placeholder for actual assets
        self.logo_img = ImageTk.PhotoImage(Image.new('RGB', (100, 100), '#4a76a8'))
        
    def setup_ui(self):
        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        # Header
        self.header_frame = ttk.Frame(self.main_frame)
        self.header_frame.pack(fill=X, pady=(0, 10))
        
        ttk.Label(
            self.header_frame, 
            image=self.logo_img
        ).pack(side=LEFT, padx=5)
        
        ttk.Label(
            self.header_frame, 
            text="Instagram Automation Tool", 
            font=('Helvetica', 16, 'bold')
        ).pack(side=LEFT, padx=10)
        
        # Notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=BOTH, expand=True)
        
        # Account Tab
        self.account_tab = ttk.Frame(self.notebook)
        self.setup_account_tab()
        self.notebook.add(self.account_tab, text="Accounts")
        
        # Follow Tab
        self.follow_tab = ttk.Frame(self.notebook)
        self.setup_follow_tab()
        self.notebook.add(self.follow_tab, text="Follow")
        
        # Unfollow Tab
        self.unfollow_tab = ttk.Frame(self.notebook)
        self.setup_unfollow_tab()
        self.notebook.add(self.unfollow_tab, text="Unfollow")
        
        # Settings Tab
        self.settings_tab = ttk.Frame(self.notebook)
        self.setup_settings_tab()
        self.notebook.add(self.settings_tab, text="Settings")
        
        # Status Bar
        self.status_var = StringVar()
        self.status_var.set("Ready")
        ttk.Label(
            self.main_frame, 
            textvariable=self.status_var,
            relief=SUNKEN,
            anchor=W
        ).pack(fill=X, pady=(5,0))
        
    def setup_account_tab(self):
        # Account management controls
        ttk.Label(self.account_tab, text="Manage Instagram Accounts").pack(pady=5)
        
        # Account list
        self.account_listbox = Listbox(self.account_tab, height=10)
        self.account_listbox.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        # Button frame
        button_frame = ttk.Frame(self.account_tab)
        button_frame.pack(fill=X, pady=5)
        
        ttk.Button(
            button_frame, 
            text="Add Account", 
            command=self.add_account
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            button_frame, 
            text="Remove Account", 
            command=self.remove_account
        ).pack(side=LEFT, padx=5)
        
        ttk.Button(
            button_frame, 
            text="Login", 
            command=self.login_account
        ).pack(side=RIGHT, padx=5)
        
    def setup_follow_tab(self):
        # Follow controls
        ttk.Label(self.follow_tab, text="Follow Users from CSV").pack(pady=5)
        
        # CSV file selection
        file_frame = ttk.Frame(self.follow_tab)
        file_frame.pack(fill=X, pady=5)
        
        self.csv_path_var = StringVar()
        ttk.Entry(
            file_frame, 
            textvariable=self.csv_path_var,
            state='readonly'
        ).pack(side=LEFT, fill=X, expand=True, padx=5)
        
        ttk.Button(
            file_frame, 
            text="Browse", 
            command=self.browse_csv
        ).pack(side=RIGHT, padx=5)
        
        # Progress bar
        self.follow_progress = ttk.Progressbar(
            self.follow_tab, 
            orient=HORIZONTAL,
            mode='determinate'
        )
        self.follow_progress.pack(fill=X, padx=10, pady=5)
        
        self.progress_label = ttk.Label(self.follow_tab, text="")
        self.progress_label.pack()
        
        # Start button
        ttk.Button(
            self.follow_tab, 
            text="Start Following", 
            command=self.start_following
        ).pack(pady=10)
        
    def setup_unfollow_tab(self):
        # Similar to follow tab but for unfollowing
        pass
        
    def setup_settings_tab(self):
        # Settings controls
        ttk.Label(self.settings_tab, text="Automation Settings").pack(pady=5)
        
        # Follow delay
        ttk.Label(self.settings_tab, text="Follow Delay Range (seconds):").pack(anchor=W, padx=10)
        self.follow_delay_min = IntVar(value=self.automation.settings['follow_delay'][0])
        self.follow_delay_max = IntVar(value=self.automation.settings['follow_delay'][1])
        
        delay_frame = ttk.Frame(self.settings_tab)
        delay_frame.pack(fill=X, padx=10, pady=5)
        
        ttk.Entry(delay_frame, textvariable=self.follow_delay_min, width=5).pack(side=LEFT)
        ttk.Label(delay_frame, text="to").pack(side=LEFT, padx=5)
        ttk.Entry(delay_frame, textvariable=self.follow_delay_max, width=5).pack(side=LEFT)
        
        # Daily limits
        ttk.Label(self.settings_tab, text="Daily Follow Limit:").pack(anchor=W, padx=10)
        self.daily_follow_limit = IntVar(value=self.automation.settings['daily_follow_limit'])
        ttk.Entry(self.settings_tab, textvariable=self.daily_follow_limit).pack(fill=X, padx=10, pady=5)
        
        # Save button
        ttk.Button(
            self.settings_tab, 
            text="Save Settings", 
            command=self.save_settings
        ).pack(pady=10)
        
    def start_scheduler(self):
        # Schedule weekly report every Monday at 9AM
        schedule.every().monday.at("09:00").do(
            self.automation.send_weekly_report
        )
        
        # Run scheduler in background thread
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)
                
        scheduler_thread = threading.Thread(
            target=run_scheduler,
            daemon=True
        )
        scheduler_thread.start()
        
    def add_account(self):
        # Open dialog to add new account
        pass
        
    def remove_account(self):
        # Remove selected account
        pass
        
    def login_account(self):
        # Login to selected account
        pass
        
    def browse_csv(self):
        # Open file dialog to select CSV
        filepath = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV Files", "*.csv")]
        )
        if filepath:
            self.csv_path_var.set(filepath)
            
    def start_following(self):
        # Start follow process
        csv_path = self.csv_path_var.get()
        if not csv_path:
            messagebox.showerror("Error", "Please select a CSV file first")
            return
            
        try:
            with open(csv_path, 'r') as f:
                reader = csv.reader(f)
                usernames = [row[0] for row in reader if row]
                
            if not usernames:
                messagebox.showerror("Error", "No usernames found in CSV")
                return
                
            # Update progress bar
            self.follow_progress['maximum'] = len(usernames)
            
            # Run in background thread
            threading.Thread(
                target=self.run_follow_process,
                args=(usernames,),
                daemon=True
            ).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read CSV: {str(e)}")
            
    def run_follow_process(self, usernames):
        # Callback for progress updates
        def update_progress(current, total, delay):
            self.follow_progress['value'] = current
            self.progress_label.config(
                text=f"Processing {current}/{total} - Next in {delay}s"
            )
            self.root.update()
            
        # Execute follow
        success = self.automation.follow_users(
            usernames,
            progress_callback=update_progress
        )
        
        if success:
            self.status_var.set("Follow process completed")
            messagebox.showinfo("Success", "Follow process completed")
        else:
            self.status_var.set("Follow process failed")
            
    def save_settings(self):
        # Save settings to config
        self.automation.settings = {
            'follow_delay': (self.follow_delay_min.get(), self.follow_delay_max.get()),
            'unfollow_delay': (30, 90),  # You would add controls for these
            'daily_follow_limit': self.daily_follow_limit.get(),
            'daily_unfollow_limit': 100,  # You would add controls for these
            'actions_per_hour': 30        # You would add controls for these
        }
        self.automation.save_config()
        messagebox.showinfo("Success", "Settings saved successfully")

if __name__ == "__main__":
    # Create .env file if not exists
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write("# Email settings for error notifications\n")
            f.write("EMAIL_USER=your-email@gmail.com\n")
            f.write("EMAIL_PASS=your-app-password\n")
        
    root = Tk()
    app = AutomationGUI(root)
    root.mainloop()
