"""Native Desktop GUI for Gene.

Gene - Generative Engine for Natural Engagement
A modern desktop chat application using CustomTkinter.
Runs as a standalone window - no browser required.
Features: Chat with Gene, web search integration, business management.
"""

import customtkinter as ctk
import threading
import requests
import sys
import os
import re
import json
from datetime import datetime
from PIL import Image, ImageTk, ImageEnhance

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from core.llm.ollama import OllamaClient

# Web search
try:
    from ddgs import DDGS
    SEARCH_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        SEARCH_AVAILABLE = True
    except ImportError:
        SEARCH_AVAILABLE = False
        print("⚠️ Web search unavailable. Install with: pip install ddgs")

# Business management
try:
    from .business import BusinessDatabase, BusinessQueryHandler
    BUSINESS_AVAILABLE = True
except ImportError:
    try:
        from interfaces.desktop.business import BusinessDatabase, BusinessQueryHandler
        BUSINESS_AVAILABLE = True
    except ImportError:
        BUSINESS_AVAILABLE = False
        print("⚠️ Business module unavailable.")


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_MODEL = "qwen2.5-coder:7b"
DEFAULT_SYSTEM_PROMPT = """You are Gene, a helpful assistant running locally via Ollama.
Your name is Gene, which stands for Generative Engine for Natural Engagement.
You help with questions, research, and general information.
When asked what you are or what you're built on, you can mention you run on Ollama with local AI models.

IMPORTANT: Always structure your responses in two parts:
1. <thinking>Your internal reasoning, analysis of search results, consideration of sources</thinking>
2. Your final response to the user (clear, concise answer)

The thinking section should show your reasoning process. The final response should be the definitive answer."""

# Gene robot icon - hexagonal robot head using GENE letters
GENE_ICON = "<G>"  # Text fallback if image not found
GENE_ICON_PATH = os.path.join(os.path.dirname(__file__), "assets", "gene_icon.png")

# History storage directory
HISTORY_DIR = os.path.join(os.path.dirname(__file__), "chat_history")
os.makedirs(HISTORY_DIR, exist_ok=True)

# Appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ═══════════════════════════════════════════════════════════════════════════════
# Tooltip Helper
# ═══════════════════════════════════════════════════════════════════════════════

class ToolTip:
    """Simple tooltip for CustomTkinter widgets."""
    
    def __init__(self, widget, text: str, delay: int = 500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip_window = None
        self.scheduled_id = None
        
        widget.bind("<Enter>", self._schedule_show)
        widget.bind("<Leave>", self._hide)
        widget.bind("<Button>", self._hide)
    
    def _schedule_show(self, event=None):
        """Schedule tooltip to show after delay."""
        self._hide()
        self.scheduled_id = self.widget.after(self.delay, self._show)
    
    def _show(self, event=None):
        """Show the tooltip."""
        if self.tooltip_window:
            return
        
        # Get widget position
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 5
        y = self.widget.winfo_rooty() + self.widget.winfo_height() // 2
        
        # Create tooltip window
        self.tooltip_window = tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        
        label = ctk.CTkLabel(
            tw,
            text=self.text,
            font=ctk.CTkFont(size=12),
            fg_color="#1f2937",
            corner_radius=5,
            padx=8,
            pady=4,
        )
        label.pack()
    
    def _hide(self, event=None):
        """Hide the tooltip."""
        if self.scheduled_id:
            self.widget.after_cancel(self.scheduled_id)
            self.scheduled_id = None
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


# ═══════════════════════════════════════════════════════════════════════════════
# Main Application
# ═══════════════════════════════════════════════════════════════════════════════

class LocalAIAgentApp(ctk.CTk):
    """Main desktop application window."""
    
    def __init__(self):
        super().__init__()
        
        # CRITICAL: Set Windows app ID FIRST for correct taskbar icon
        self._set_windows_app_id()
        
        # Window title
        self.title("Gene")
        
        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Start at 80% of screen, capped at maximums
        start_width = min(int(screen_width * 0.8), 1600)
        start_height = min(int(screen_height * 0.8), 1000)
        
        # Ensure minimum reasonable values
        start_width = max(start_width, 1000)
        start_height = max(start_height, 700)
        
        # Center on screen
        x_pos = (screen_width - start_width) // 2
        y_pos = (screen_height - start_height) // 2
        
        # Apply geometry
        self.geometry(f"{start_width}x{start_height}+{x_pos}+{y_pos}")
        self.minsize(800, 600)
        
        # CRITICAL: Ensure both width and height are resizable
        self.resizable(width=True, height=True)
        
        # Force window to realize before setting icon
        self.update_idletasks()
        
        # Set window icon
        self._set_window_icon()
        
        # Ollama client
        self.client = OllamaClient()
        self.current_model = DEFAULT_MODEL
        self.system_prompt = DEFAULT_SYSTEM_PROMPT
        self.conversation_history = []
        self.pending_search_query = None  # For search confirmation
        self.pending_extracted_query = None
        
        # Location settings
        self.user_location = None  # Cached location
        self.location_permission = None  # None=not asked, True=allowed, False=denied
        self.pending_location_query = None  # Query waiting for location permission
        
        # Internet toggle - when ON, auto-search without asking
        self.internet_enabled = False
        
        # Thinking panel state
        self.thinking_visible = True  # Show thinking by default
        
        # History panel state
        self.history_visible = False  # Hidden by default
        self.current_session_id = None  # Current chat session ID
        self.session_title = None  # Auto-generated from first message
        
        # Business management
        self.business_handler = None
        if BUSINESS_AVAILABLE:
            try:
                self.business_handler = BusinessQueryHandler()
            except Exception as e:
                print(f"⚠️ Business module init error: {e}")
        
        # Track recent search context for follow-up questions
        self.recent_search_topics = []  # Keywords from recent searches
        self.last_search_results = []   # Store recent search result snippets
        self.search_context_active = False  # True after a search, until topic changes
        self.pending_query_context = None  # Store context when waiting for location/info
        
        # Question starters that might indicate follow-up questions
        self.question_starters = [
            'is ', 'are ', 'was ', 'were ', 'did ', 'does ', 'do ',
            'has ', 'have ', 'had ', 'can ', 'could ', 'would ', 'will ',
            'what about ', 'how about ', 'any update', 'what happened',
            'is it ', 'is that ', 'is there ', 'are there '
        ]
        
        # Keywords that suggest user wants real-time information
        self.search_keywords = [
            # Time-sensitive
            'latest', 'recent', 'current', 'today', 'tonight', 'tomorrow',
            'this week', 'this month', 'this year', 'right now', 'happening',
            '2024', '2025', '2026',
            # News and events
            'news', 'weather', 'forecast', 'update', 'breaking', 'live',
            'who won', 'what happened', 'score', 'results', 'standings',
            # Location-based queries
            'nearest', 'nearby', 'closest', 'near me', 'where is', 'where can i',
            'located', 'location', 'directions', 'hours', 'open',
            # Real-time data
            'stock price', 'stocks', 'crypto', 'bitcoin', 'price of',
            'trending', 'viral', 'popular',
            # Planning and visits
            'planning', 'visiting', 'coming to', 'touring', 'tour dates',
            'concert', 'appearance', 'speaking', 'speech',
            # Events and scheduling
            'when is', 'when does', 'schedule', 'event', 'taking place',
            'petition', 'election', 'vote', 'voting', 'poll',
            # How to find/get
            'how to find', 'how to get', 'where to buy', 'where to find'
        ]
        
        # Check Ollama status
        self.ollama_running = self._check_ollama()
        
        # Build UI
        self._create_ui()
        
        # Focus on input
        self.input_field.focus()
    
    def _set_windows_app_id(self):
        """Set Windows AppUserModelID for proper taskbar icon grouping.
        
        MUST be called before any window content is created.
        """
        try:
            import ctypes
            # Unique app ID for Gene
            app_id = 'PlumbMonkey.Gene.DesktopApp.1.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass  # Non-Windows or failed, not critical
    
    def _set_window_icon(self):
        """Set the window icon for title bar and taskbar."""
        self.icon_loaded = False
        
        # Get absolute path to ICO file
        ico_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "installer", "gene.ico")
        )
        
        try:
            if os.path.exists(ico_path):
                # Use iconbitmap for Windows .ico files (best taskbar support)
                self.iconbitmap(default=ico_path)
                self.icon_loaded = True
                return
            
            # Fallback to PNG if ICO not found
            if os.path.exists(GENE_ICON_PATH):
                icon_image = Image.open(GENE_ICON_PATH)
                icon_image = icon_image.convert('RGBA')
                
                # Resize to standard icon size
                icon_image = icon_image.resize((64, 64), Image.Resampling.LANCZOS)
                self.icon_photo = ImageTk.PhotoImage(icon_image)
                self.iconphoto(True, self.icon_photo)
                self.icon_loaded = True
                
        except Exception as e:
            print(f"Note: Could not load icon: {e}")
    
    def _check_ollama(self) -> bool:
        """Check if Ollama is running."""
        try:
            return self.client.health_check()
        except Exception:
            return False
    
    def _get_models(self) -> list:
        """Get available models."""
        try:
            models = self.client.list_models()
            return models if models else [DEFAULT_MODEL]
        except Exception:
            return [DEFAULT_MODEL]
    
    def _create_ui(self):
        """Create the user interface."""
        
        # Configure grid - main window has header, content area, and input
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Header - fixed height
        self.grid_rowconfigure(1, weight=1)  # Content - expands
        self.grid_rowconfigure(2, weight=0)  # Input - fixed height
        
        # ─────────────────────────────────────────────────────────────────────
        # Header Frame
        # ─────────────────────────────────────────────────────────────────────
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header_frame.grid_columnconfigure(2, weight=1)  # Push status/model to right
        
        # Header icon (if available) or fallback text
        header_col = 0
        icon_shown = False
        try:
            # Always try to load the header icon
            header_icon = Image.open(GENE_ICON_PATH)
            
            # Enhance contrast to make letters pop
            enhancer = ImageEnhance.Contrast(header_icon)
            header_icon = enhancer.enhance(1.5)  # Boost contrast 50%
            
            # Enhance color saturation
            enhancer = ImageEnhance.Color(header_icon)
            header_icon = enhancer.enhance(1.3)  # Boost saturation 30%
            
            # Sharpen the image
            enhancer = ImageEnhance.Sharpness(header_icon)
            header_icon = enhancer.enhance(2.0)  # Sharpen significantly
            
            # Resize to header size - maintain square aspect ratio
            header_size = 48  # Square icon for header
            header_icon = header_icon.resize((header_size, header_size), Image.Resampling.LANCZOS)
            
            self.header_icon = ctk.CTkImage(header_icon, size=(header_size, header_size))
            icon_label = ctk.CTkLabel(header_frame, image=self.header_icon, text="")
            icon_label.grid(row=0, column=0, sticky="w", padx=(0, 10))
            header_col = 1
            icon_shown = True
        except Exception as e:
            print(f"Icon load error: {e}")
        
        # Only show text label if icon didn't load (icon already shows "GENE")
        if not icon_shown:
            title_label = ctk.CTkLabel(
                header_frame,
                text=f"{GENE_ICON} Gene",
                font=ctk.CTkFont(family="Arial", size=28, weight="bold"),
            )
            title_label.grid(row=0, column=header_col, sticky="w")
            header_col += 1
        
        # Status
        status_text = "✅ Ollama Connected" if self.ollama_running else "❌ Ollama Not Running"
        status_color = "#22c55e" if self.ollama_running else "#ef4444"
        self.status_label = ctk.CTkLabel(
            header_frame,
            text=status_text,
            text_color=status_color,
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
        )
        self.status_label.grid(row=0, column=header_col, sticky="e", padx=10)
        
        # Model selector
        models = self._get_models() if self.ollama_running else [DEFAULT_MODEL]
        self.model_var = ctk.StringVar(value=models[0] if models else DEFAULT_MODEL)
        self.model_dropdown = ctk.CTkOptionMenu(
            header_frame,
            values=models,
            variable=self.model_var,
            command=self._on_model_change,
            width=180,
        )
        self.model_dropdown.grid(row=0, column=header_col + 1, sticky="e")
        
        # ─────────────────────────────────────────────────────────────────────
        # Main Content Frame (History + Chat + Thinking Panel)
        # ─────────────────────────────────────────────────────────────────────
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        content_frame.grid_columnconfigure(0, weight=0)  # History panel (initially hidden)
        content_frame.grid_columnconfigure(1, weight=1)  # Chat gets all space
        content_frame.grid_columnconfigure(2, weight=0)  # Thinking panel (will be configured when shown)
        content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame = content_frame  # Store reference
        
        # ─────────────────────────────────────────────────────────────────────
        # History Panel (Left side - collapsible)
        # ─────────────────────────────────────────────────────────────────────
        self.history_frame = ctk.CTkFrame(content_frame, fg_color="#1a1a2e", corner_radius=10)
        self.history_frame.grid(row=0, column=0, sticky="nsew", padx=5)
        self.history_frame.grid_columnconfigure(0, weight=1)
        self.history_frame.grid_rowconfigure(1, weight=1)
        
        # History header
        history_header = ctk.CTkFrame(self.history_frame, fg_color="transparent")
        history_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        history_header.grid_columnconfigure(0, weight=1)
        
        history_title = ctk.CTkLabel(
            history_header,
            text="📜 Chat History",
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            text_color="#9ca3af",
        )
        history_title.grid(row=0, column=0, sticky="w")
        
        # New chat button
        new_chat_btn = ctk.CTkButton(
            history_header,
            text="+ New",
            width=50,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color="#166534",
            hover_color="#15803d",
            command=self._new_chat,
        )
        new_chat_btn.grid(row=0, column=1, sticky="e")
        
        # History list (scrollable)
        self.history_scroll = ctk.CTkScrollableFrame(
            self.history_frame,
            fg_color="#16162a",
            corner_radius=5,
        )
        self.history_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.history_scroll.grid_columnconfigure(0, weight=1)
        
        # Load and display history
        self._refresh_history_list()
        
        # Initially hide history panel
        self.history_frame.grid_remove()
        
        # ─────────────────────────────────────────────────────────────────────
        # Chat Display (Center)
        # ─────────────────────────────────────────────────────────────────────
        self.chat_display = ctk.CTkTextbox(
            content_frame,
            wrap="word",
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            state="disabled",
        )
        self.chat_display.grid(row=0, column=1, sticky="nsew", padx=5)
        
        # Add right-click context menu to chat display
        self._setup_context_menu(self.chat_display)
        
        # Configure tags for styling
        self.chat_display._textbox.tag_configure("user", foreground="#60a5fa")
        self.chat_display._textbox.tag_configure("assistant", foreground="#34d399")
        self.chat_display._textbox.tag_configure("system", foreground="#a78bfa")
        self.chat_display._textbox.tag_configure("error", foreground="#f87171")
        self.chat_display._textbox.tag_configure("search", foreground="#fbbf24")
        
        # ─────────────────────────────────────────────────────────────────────
        # Thinking Panel (Right side - collapsible)
        # ─────────────────────────────────────────────────────────────────────
        self.thinking_frame = ctk.CTkFrame(content_frame, fg_color="#1a1a2e", corner_radius=10)
        self.thinking_frame.grid(row=0, column=2, sticky="nsew", padx=5)
        self.thinking_frame.grid_columnconfigure(0, weight=1)
        self.thinking_frame.grid_rowconfigure(1, weight=1)
        
        # Thinking header
        thinking_header = ctk.CTkFrame(self.thinking_frame, fg_color="transparent")
        thinking_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        thinking_header.grid_columnconfigure(0, weight=1)
        
        thinking_title = ctk.CTkLabel(
            thinking_header,
            text="💭 Gene's Thinking",
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            text_color="#9ca3af",
        )
        thinking_title.grid(row=0, column=0, sticky="w")
        
        # Clear thinking button
        clear_thinking_btn = ctk.CTkButton(
            thinking_header,
            text="Clear",
            width=50,
            height=24,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            border_width=1,
            command=self._clear_thinking,
        )
        clear_thinking_btn.grid(row=0, column=1, sticky="e")
        
        # Thinking text display
        self.thinking_display = ctk.CTkTextbox(
            self.thinking_frame,
            wrap="word",
            font=ctk.CTkFont(family="Arial", size=12, slant="italic"),
            fg_color="#16162a",
            text_color="#9ca3af",
            state="disabled",
        )
        self.thinking_display.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # Add right-click context menu to thinking display
        self._setup_context_menu(self.thinking_display)
        
        # Configure thinking panel visibility
        if self.thinking_visible:
            # Thinking panel visible - give it fixed width
            self.thinking_frame.configure(width=280)
            self.thinking_frame.grid_propagate(False)
        else:
            self.thinking_frame.grid_remove()
        
        # Welcome message
        if SEARCH_AVAILABLE:
            search_hint = " Click 🌐 to enable auto internet search, or use /search <query>."
        else:
            search_hint = ""
        self._append_message("system", f"Welcome to Gene! I'm your Generative Engine for Natural Engagement. Type a message to get started.{search_hint}\\n")
        
        # ─────────────────────────────────────────────────────────────────────
        # Input Frame
        # ─────────────────────────────────────────────────────────────────────
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)
        
        # Input field
        self.input_field = ctk.CTkTextbox(
            input_frame,
            height=70,
            wrap="word",
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
        )
        self.input_field.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.input_field.bind("<Return>", self._on_enter)
        self.input_field.bind("<Shift-Return>", self._on_shift_enter)
        
        # Button frame
        button_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        button_frame.grid(row=0, column=1, sticky="ns")
        
        # Send button
        self.send_button = ctk.CTkButton(
            button_frame,
            text="Send",
            width=80,
            command=self._send_message,
        )
        self.send_button.pack(pady=(0, 5))
        ToolTip(self.send_button, "Send Message")
        
        # Internet toggle button (globe = internet)
        if SEARCH_AVAILABLE:
            self.search_button = ctk.CTkButton(
                button_frame,
                text="🌐",
                width=40,
                font=ctk.CTkFont(size=18),
                fg_color="#374151",  # Gray when OFF
                hover_color="#4b5563",
                command=self._toggle_internet,
            )
            self.search_button.pack(pady=(0, 5))
            ToolTip(self.search_button, "Toggle Internet Search")
            
            # Tooltip-like label
            self.internet_status_label = ctk.CTkLabel(
                button_frame,
                text="OFF",
                font=ctk.CTkFont(family="Arial", size=9),
                text_color="#6b7280",
            )
            self.internet_status_label.pack(pady=(0, 5))
        
        # Thinking toggle button (brain icon)
        self.thinking_button = ctk.CTkButton(
            button_frame,
            text="🧠",
            width=40,
            font=ctk.CTkFont(size=16),
            fg_color="#1e40af",  # Blue when ON (visible)
            hover_color="#2563eb",
            command=self._toggle_thinking,
        )
        self.thinking_button.pack(pady=(0, 5))
        ToolTip(self.thinking_button, "Toggle Thinking Panel")
        
        # History toggle button
        self.history_button = ctk.CTkButton(
            button_frame,
            text="H",
            width=40,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#374151",  # Gray when OFF (hidden)
            hover_color="#4b5563",
            command=self._toggle_history,
        )
        self.history_button.pack(pady=(0, 5))
        ToolTip(self.history_button, "Chat History")
        
        # Business toggle button
        self.business_button = ctk.CTkButton(
            button_frame,
            text="B",
            width=40,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#374151",  # Gray when OFF
            hover_color="#4b5563",
            command=self._show_business_dashboard,
        )
        self.business_button.pack(pady=(0, 5))
        ToolTip(self.business_button, "Business Dashboard")
        
        # Clear button
        self.clear_button = ctk.CTkButton(
            button_frame,
            text="Clear",
            width=80,
            fg_color="transparent",
            border_width=1,
            command=self._clear_chat,
        )
        self.clear_button.pack()
        ToolTip(self.clear_button, "Clear Current Chat")
        
        # ─────────────────────────────────────────────────────────────────────
        # Search Confirmation Bar (hidden by default)
        # ─────────────────────────────────────────────────────────────────────
        self.search_confirm_frame = ctk.CTkFrame(self, fg_color="#1e3a5f")
        # Initially hidden - will be shown when search is suggested
        
        self.search_confirm_label = ctk.CTkLabel(
            self.search_confirm_frame,
            text="🔍 This looks like it needs current information. Search the web?",
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
        )
        self.search_confirm_label.pack(side="left", padx=10, pady=8)
        
        self.search_yes_btn = ctk.CTkButton(
            self.search_confirm_frame,
            text="✅ Yes, Search",
            width=100,
            fg_color="#166534",
            hover_color="#15803d",
            command=self._confirm_search,
        )
        self.search_yes_btn.pack(side="left", padx=5, pady=8)
        
        self.search_no_btn = ctk.CTkButton(
            self.search_confirm_frame,
            text="❌ No, Ask AI",
            width=100,
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            command=self._decline_search,
        )
        self.search_no_btn.pack(side="left", padx=5, pady=8)
        
        # ─────────────────────────────────────────────────────────────────────
        # Location Permission Bar (hidden by default)
        # ─────────────────────────────────────────────────────────────────────
        self.location_confirm_frame = ctk.CTkFrame(self, fg_color="#3d1f5c")
        # Initially hidden - will be shown when location is needed
        
        self.location_confirm_label = ctk.CTkLabel(
            self.location_confirm_frame,
            text="📍 Detect your location for local results? (uses IP geolocation)",
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
        )
        self.location_confirm_label.pack(side="left", padx=10, pady=8)
        
        self.location_yes_btn = ctk.CTkButton(
            self.location_confirm_frame,
            text="✅ Yes, Detect",
            width=100,
            fg_color="#166534",
            hover_color="#15803d",
            command=self._allow_location,
        )
        self.location_yes_btn.pack(side="left", padx=5, pady=8)
        
        self.location_no_btn = ctk.CTkButton(
            self.location_confirm_frame,
            text="❌ No Thanks",
            width=100,
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            command=self._deny_location,
        )
        self.location_no_btn.pack(side="left", padx=5, pady=8)
        
        # ─────────────────────────────────────────────────────────────────────
        # Footer
        # ─────────────────────────────────────────────────────────────────────
        footer_label = ctk.CTkLabel(
            self,
            text="💻 Running locally via Ollama | 🔒 Your data stays on your machine",
            font=ctk.CTkFont(family="Arial", size=12),
            text_color="gray",
        )
        footer_label.grid(row=3, column=0, pady=(0, 10))
    
    def _append_message(self, role: str, content: str):
        """Append a message to the chat display."""
        self.chat_display.configure(state="normal")
        
        if role == "user":
            self.chat_display.insert("end", "You: ", "user")
            self.chat_display.insert("end", f"{content}\n\n")
        elif role == "assistant":
            self.chat_display.insert("end", "Gene: ", "assistant")
            self.chat_display.insert("end", f"{content}\n\n")
        elif role == "system":
            self.chat_display.insert("end", f"💡 {content}\n", "system")
        elif role == "error":
            self.chat_display.insert("end", f"❌ {content}\n\n", "error")
        elif role == "search":
            self.chat_display.insert("end", "🔍 ", "search")
            self.chat_display.insert("end", f"{content}\n\n")
        
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")
    
    def _setup_context_menu(self, textbox):
        """Setup right-click context menu for a textbox."""
        import tkinter as tk
        
        # Create context menu
        context_menu = tk.Menu(textbox, tearoff=0, bg="#2d2d3d", fg="#ffffff",
                               activebackground="#4a4a5a", activeforeground="#ffffff")
        context_menu.add_command(label="Copy", command=lambda: self._copy_selection(textbox))
        context_menu.add_command(label="Select All", command=lambda: self._select_all(textbox))
        
        def show_context_menu(event):
            """Show context menu on right-click."""
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()
        
        # Bind right-click to the internal textbox
        textbox._textbox.bind("<Button-3>", show_context_menu)
    
    def _copy_selection(self, textbox):
        """Copy selected text to clipboard."""
        try:
            # Get selected text from the internal textbox
            selected_text = textbox._textbox.selection_get()
            if selected_text:
                self.clipboard_clear()
                self.clipboard_append(selected_text)
        except Exception:
            pass  # No selection
    
    def _select_all(self, textbox):
        """Select all text in the textbox."""
        textbox._textbox.tag_add("sel", "1.0", "end")
    
    def _on_model_change(self, model: str):
        """Handle model selection change."""
        self.current_model = model
        self._append_message("system", f"Model changed to: {model}\n")
    
    def _on_enter(self, event):
        """Handle Enter key - send message."""
        self._send_message()
        return "break"  # Prevent newline
    
    def _on_shift_enter(self, event):
        """Handle Shift+Enter - add newline."""
        return  # Allow default behavior (newline)
    
    def _toggle_internet(self):
        """Toggle internet search on/off."""
        self.internet_enabled = not self.internet_enabled
        
        if self.internet_enabled:
            # ON - blue color, auto-search enabled
            self.search_button.configure(
                fg_color="#1e40af",
                hover_color="#2563eb",
            )
            self.internet_status_label.configure(text="ON", text_color="#22c55e")
            self._append_message("system", "🌐 Internet search ENABLED - queries will auto-search when relevant\\n")
            
            # Also enable location permission when internet is enabled
            if self.location_permission is None:
                self.location_permission = True
                # Try to detect location now
                thread = threading.Thread(target=self._prefetch_location)
                thread.daemon = True
                thread.start()
        else:
            # OFF - gray color, will ask each time
            self.search_button.configure(
                fg_color="#374151",
                hover_color="#4b5563",
            )
            self.internet_status_label.configure(text="OFF", text_color="#6b7280")
            self._append_message("system", "🌐 Internet search DISABLED - will ask before searching\\n")
    
    def _toggle_thinking(self):
        """Toggle showing/hiding Gene's thinking panel."""
        self.thinking_visible = not self.thinking_visible
        
        if self.thinking_visible:
            # ON - show thinking panel
            self.thinking_button.configure(
                fg_color="#1e40af",
                hover_color="#2563eb",
            )
            self.thinking_frame.configure(width=280)
            self.thinking_frame.grid_propagate(False)
            self.thinking_frame.grid()  # Show the panel
            self._append_message("system", "💭 Gene's thinking panel VISIBLE\\n")
        else:
            # OFF - hide thinking panel
            self.thinking_button.configure(
                fg_color="#374151",
                hover_color="#4b5563",
            )
            self.thinking_frame.grid_remove()  # Hide the panel
            self._append_message("system", "💭 Gene's thinking panel HIDDEN\\n")
    
    def _clear_thinking(self):
        """Clear the thinking panel."""
        self.thinking_display.configure(state="normal")
        self.thinking_display.delete("1.0", "end")
        self.thinking_display.configure(state="disabled")
    
    def _append_thinking(self, content: str):
        """Append content to the thinking panel."""
        self.thinking_display.configure(state="normal")
        self.thinking_display.insert("end", f"{content}\n\n")
        self.thinking_display.configure(state="disabled")
        self.thinking_display.see("end")
    
    # ─────────────────────────────────────────────────────────────────────────
    # History Management
    # ─────────────────────────────────────────────────────────────────────────
    
    def _toggle_history(self):
        """Toggle showing/hiding the history panel."""
        self.history_visible = not self.history_visible
        
        if self.history_visible:
            # ON - show history panel
            self.history_button.configure(
                fg_color="#1e40af",
                hover_color="#2563eb",
            )
            self._refresh_history_list()
            self.history_frame.configure(width=250)
            self.history_frame.grid_propagate(False)
            self.history_frame.grid()  # Show the panel
        else:
            # OFF - hide history panel
            self.history_button.configure(
                fg_color="#374151",
                hover_color="#4b5563",
            )
            self.history_frame.grid_remove()  # Hide the panel
    
    def _get_session_filename(self, session_id: str) -> str:
        """Get the full path for a session file."""
        return os.path.join(HISTORY_DIR, f"{session_id}.json")
    
    def _generate_session_title(self, first_message: str) -> str:
        """Generate a title from the first user message."""
        # Take first 40 chars of first message
        title = first_message[:40].strip()
        if len(first_message) > 40:
            title += "..."
        return title
    
    def _save_current_session(self):
        """Save the current chat session to disk."""
        if not self.conversation_history:
            return  # Nothing to save
        
        # Generate session ID if needed
        if not self.current_session_id:
            self.current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate title from first user message if needed
        if not self.session_title:
            for msg in self.conversation_history:
                if msg.get("role") == "user":
                    self.session_title = self._generate_session_title(msg.get("content", "Untitled"))
                    break
            if not self.session_title:
                self.session_title = "Untitled Chat"
        
        # Build session data
        session_data = {
            "id": self.current_session_id,
            "title": self.session_title,
            "created": self.current_session_id,  # Timestamp is the ID
            "updated": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "model": self.current_model,
            "messages": self.conversation_history,
        }
        
        # Save to file
        filepath = self._get_session_filename(self.current_session_id)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving session: {e}")
    
    def _load_session(self, session_id: str):
        """Load a chat session from disk."""
        filepath = self._get_session_filename(session_id)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                session_data = json.load(f)
            
            # Restore session state
            self.current_session_id = session_data.get("id")
            self.session_title = session_data.get("title")
            self.conversation_history = session_data.get("messages", [])
            
            # Restore model if available
            saved_model = session_data.get("model")
            if saved_model:
                self.current_model = saved_model
                self.model_var.set(saved_model)
            
            # Clear and rebuild chat display
            self.chat_display.configure(state="normal")
            self.chat_display.delete("1.0", "end")
            self.chat_display.configure(state="disabled")
            
            # Clear thinking panel
            self._clear_thinking()
            
            # Replay messages to display
            self._append_message("system", f"📜 Loaded chat: {self.session_title}\\n")
            for msg in self.conversation_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                self._append_message(role, content + "\\n")
            
            # Clear search context
            self.recent_search_topics = []
            self.last_search_results = []
            self.search_context_active = False
            
            return True
        except Exception as e:
            print(f"Error loading session: {e}")
            return False
    
    def _list_sessions(self) -> list:
        """List all saved chat sessions, sorted by date (newest first)."""
        sessions = []
        try:
            for filename in os.listdir(HISTORY_DIR):
                if filename.endswith(".json"):
                    filepath = os.path.join(HISTORY_DIR, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        sessions.append({
                            "id": data.get("id", filename.replace(".json", "")),
                            "title": data.get("title", "Untitled"),
                            "updated": data.get("updated", data.get("created", "")),
                            "message_count": len(data.get("messages", [])),
                        })
                    except Exception:
                        pass
            # Sort by updated date, newest first
            sessions.sort(key=lambda x: x.get("updated", ""), reverse=True)
        except Exception as e:
            print(f"Error listing sessions: {e}")
        return sessions
    
    def _delete_session(self, session_id: str):
        """Delete a chat session."""
        filepath = self._get_session_filename(session_id)
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            # If we deleted the current session, start fresh
            if session_id == self.current_session_id:
                self._new_chat()
            # Refresh the list
            self._refresh_history_list()
        except Exception as e:
            print(f"Error deleting session: {e}")
    
    def _refresh_history_list(self):
        """Refresh the history list display."""
        # Clear existing items
        for widget in self.history_scroll.winfo_children():
            widget.destroy()
        
        # Get sessions
        sessions = self._list_sessions()
        
        if not sessions:
            empty_label = ctk.CTkLabel(
                self.history_scroll,
                text="No saved chats yet",
                font=ctk.CTkFont(size=12),
                text_color="#6b7280",
            )
            empty_label.pack(pady=20)
            return
        
        # Add session entries
        for session in sessions:
            self._create_history_entry(session)
    
    def _create_history_entry(self, session: dict):
        """Create a history entry widget."""
        session_id = session.get("id")
        title = session.get("title", "Untitled")
        msg_count = session.get("message_count", 0)
        updated = session.get("updated", "")
        
        # Format date
        try:
            dt = datetime.strptime(updated, "%Y%m%d_%H%M%S")
            date_str = dt.strftime("%b %d, %H:%M")
        except Exception:
            date_str = ""
        
        # Entry frame
        entry_frame = ctk.CTkFrame(
            self.history_scroll,
            fg_color="#1f2937" if session_id != self.current_session_id else "#2d4a3e",
            corner_radius=5,
        )
        entry_frame.pack(fill="x", pady=2, padx=2)
        entry_frame.grid_columnconfigure(0, weight=1)
        
        # Title button (clickable)
        title_btn = ctk.CTkButton(
            entry_frame,
            text=title[:25] + ("..." if len(title) > 25 else ""),
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            hover_color="#374151",
            anchor="w",
            command=lambda sid=session_id: self._on_history_click(sid),
        )
        title_btn.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        
        # Info row (date + message count)
        info_frame = ctk.CTkFrame(entry_frame, fg_color="transparent")
        info_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        
        info_label = ctk.CTkLabel(
            info_frame,
            text=f"{date_str} • {msg_count} msgs",
            font=ctk.CTkFont(size=10),
            text_color="#6b7280",
        )
        info_label.pack(side="left")
        
        # Delete button
        delete_btn = ctk.CTkButton(
            info_frame,
            text="🗑",
            width=24,
            height=20,
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            hover_color="#7f1d1d",
            command=lambda sid=session_id: self._delete_session(sid),
        )
        delete_btn.pack(side="right")
    
    def _on_history_click(self, session_id: str):
        """Handle clicking on a history entry."""
        # Save current session first
        if self.conversation_history and session_id != self.current_session_id:
            self._save_current_session()
        
        # Load the selected session
        if self._load_session(session_id):
            self._refresh_history_list()
    
    def _new_chat(self):
        """Start a new chat session."""
        # Save current session first
        if self.conversation_history:
            self._save_current_session()
        
        # Reset state
        self.current_session_id = None
        self.session_title = None
        self.conversation_history = []
        
        # Clear displays
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")
        self._clear_thinking()
        
        # Clear search context
        self.recent_search_topics = []
        self.last_search_results = []
        self.search_context_active = False
        
        # Welcome message
        self._append_message("system", "New chat started! What would you like to discuss?\\n")
        
        # Refresh history list
        self._refresh_history_list()
    
    def _prefetch_location(self):
        """Prefetch location when internet is enabled."""
        location = self._detect_location()
        if location:
            self.user_location = location
            city = location['city']
            region = location['region']
            location_str = f"{city}, {region}" if region else city
            self.after(0, lambda: self._append_message("system", 
                f"📍 Location detected: {location_str}\\n"))
    
    def _send_message(self):
        """Send the current message."""
        message = self.input_field.get("1.0", "end-1c").strip()
        if not message:
            return
        
        # Clear input
        self.input_field.delete("1.0", "end")
        
        # Check for /search command (always works)
        if message.lower().startswith("/search "):
            query = message[8:].strip()
            if query:
                self._append_message("user", message)
                self._do_search(query, ask_ai=True)
            return
        
        # Check if this is a location response to a pending query
        if self.pending_query_context:
            # Check if this looks like a location (city name, zip code, etc.)
            msg_clean = message.strip().lower()
            # Short response, likely providing requested info like city/location
            if len(message.split()) <= 4 and not message.endswith('?'):
                pending_context = self.pending_query_context
                self.pending_query_context = None
                
                # Build search query with the provided location
                search_query = f"{pending_context} {message}"
                self._append_message("user", message)
                self.conversation_history.append({"role": "user", "content": message})
                self._do_search(search_query, ask_ai=True)
                return
        
        # Check for business commands
        if message.lower().startswith("/biz ") or message.lower().startswith("/business "):
            cmd = message.split(" ", 1)[1] if " " in message else ""
            self._append_message("user", message)
            self._handle_business_command(cmd)
            return
        
        # Check for business-related queries
        if self.business_handler and self.business_handler.is_business_query(message):
            self._append_message("user", message)
            self._handle_business_query(message)
            return
        
        # Check if user is asking Gene to retry/try again - use pending context
        if SEARCH_AVAILABLE and self.internet_enabled and self._is_retry_request(message):
            if self.pending_query_context:
                # User is frustrated Gene didn't search - do it now with context
                self._append_message("user", message)
                self.conversation_history.append({"role": "user", "content": message})
                query = self.pending_query_context
                if self.user_location:
                    city = self.user_location['city']
                    region = self.user_location.get('region', '')
                    query = f"{query} {city} {region}".strip()
                self._append_message("system", f"🔄 Retrying search with context: {query}\\n")
                self._do_search(query, ask_ai=True)
                return
        
        # Check if message suggests need for real-time info
        if SEARCH_AVAILABLE and self._needs_search(message):
            if self.internet_enabled:
                # Internet is ON - auto-search without asking
                self._append_message("user", message)
                self.conversation_history.append({"role": "user", "content": message})
                
                # Extract and enhance query with location if available
                query = self._extract_search_query(message)
                if self._needs_location(message) and self.user_location:
                    city = self.user_location['city']
                    region = self.user_location['region']
                    location_str = f"{city}, {region}" if region else city
                    if 'local' in query.lower():
                        query = query.replace('local', location_str)
                    else:
                        query = f"{query} {location_str}"
                
                self._do_search(query, ask_ai=True)
                return
            else:
                # Internet is OFF - ask for permission
                self._show_search_confirmation(message)
                return
        
        # Regular message - no search needed
        self._append_message("user", message)
        self.conversation_history.append({"role": "user", "content": message})
        
        # Disable input while generating
        self.send_button.configure(state="disabled", text="...")
        self.input_field.configure(state="disabled")
        
        # Generate response in background thread
        thread = threading.Thread(target=self._generate_response, args=(message,))
        thread.daemon = True
        thread.start()
    
    def _needs_search(self, message: str) -> bool:
        """Check if message likely needs real-time web information."""
        message_lower = message.lower()
        
        # Direct keyword match
        if any(keyword in message_lower for keyword in self.search_keywords):
            return True
        
        # Check if this looks like a question
        is_question = message.strip().endswith('?')
        is_question = is_question or any(message_lower.startswith(q) for q in self.question_starters)
        
        # If internet is enabled and this is a question with pronouns, likely needs fresh data
        if self.internet_enabled and is_question:
            pronoun_references = ['it ', 'they ', 'that ', 'this ', 'he ', 'she ', 'him ', 'her ', 'their ']
            if any(pron in message_lower or message_lower.startswith(pron.strip()) for pron in pronoun_references):
                return True
        
        # Check if this is a follow-up question about recent search topics
        if self.search_context_active and self.recent_search_topics:
            if is_question:
                # Check if any recent search topic is mentioned
                for topic in self.recent_search_topics:
                    if topic.lower() in message_lower:
                        return True
                
                # Check for pronouns referring to recent topics
                pronoun_references = ['it ', 'they ', 'that ', 'this ', 'the ', 'he ', 'she ']
                if any(pron in message_lower for pron in pronoun_references):
                    return True
        
        return False
    
    def _is_retry_request(self, message: str) -> bool:
        """Check if user is asking Gene to retry/try again."""
        message_lower = message.lower()
        retry_phrases = [
            "you aren't able", "you aren't able to", "aren't you able",
            "can't you", "can you not", "why can't you", "why won't you",
            "try again", "please try", "search again", "look again",
            "retrieve that", "get that", "find that", "fetch that",
            "you can't", "unable to", "not able to"
        ]
        return any(phrase in message_lower for phrase in retry_phrases)
    
    def _extract_search_query(self, message: str) -> str:
        """Extract a clean search query from natural language."""
        # Remove common conversational phrases
        remove_phrases = [
            'can you ', 'could you ', 'would you ', 'please', 'can u ',
            'check ', 'find ', 'look up ', 'search for ', 'tell me about ',
            'tell me ', 'what is ', "what's ", 'show me ', 'get me ', 
            'i want to know ', 'i need ', 'help me find ', 'for me',
            'do you know ', 'give me ', 'let me know ',
            # Additional phrases for follow-up questions
            'are you able to ', 'is it possible to ', 'can we ',
            'determine if ', 'find out if ', 'figure out ',
            'do we know if ', 'is there any way to ',
        ]
        
        query = message.lower().strip()
        
        # Remove conversational phrases
        for phrase in remove_phrases:
            query = query.replace(phrase, ' ')
        
        # Clean up
        query = ' '.join(query.split())  # Remove extra spaces
        query = query.strip('.,!?')
        
        # Remove leading articles
        for article in ['the ', 'a ', 'an ']:
            if query.startswith(article):
                query = query[len(article):]
        
        # Improve specific query types
        query_lower = query.lower()
        
        # Weather queries - add location context
        if 'weather' in query_lower:
            if 'local' in query_lower:
                # Replace "local" with a suggestion to add city
                query = query.replace('local ', '').strip()
                query = f"{query} forecast today"
        
        # News queries - make more specific
        if 'news' in query_lower and 'today' not in query_lower:
            query = f"{query} today January 2026"
        
        # Political/stance queries - add specific search terms for definitive answers
        stance_indicators = ['support', 'supports', 'oppose', 'opposes', 'stance', 
                            'position', 'view', 'views', 'opinion', 'endorses', 
                            'endorsed', 'backs', 'against', 'favor', 'favors']
        if any(word in query_lower for word in stance_indicators):
            # Add terms to find definitive statements
            if 'statement' not in query_lower and 'said' not in query_lower:
                query = f"{query} official statement said"
        
        # Social media queries - add platform names
        social_indicators = ['social media', 'twitter', 'x.com', 'instagram', 'facebook', 
                            'posted', 'post', 'tweet', 'tweeted']
        if any(word in query_lower for word in social_indicators):
            if 'twitter' not in query_lower and 'x.com' not in query_lower:
                query = f"{query} twitter X instagram"
        
        # If query is too short, use original message keywords
        if len(query) < 3:
            words = message.split()
            keywords = [w for w in words if len(w) > 3 and w.lower() not in 
                       ['can', 'you', 'please', 'the', 'for', 'check', 'find', 'what', 'about']]
            query = ' '.join(keywords[:5])
        
        # For follow-up questions, add context from recent search topics
        if self.internet_enabled and self.recent_search_topics:
            # Check if query uses pronouns that need context resolution
            pronouns = ['he', 'she', 'it', 'they', 'him', 'her', 'them', 'his', 'their']
            query_words = query.lower().split()
            
            # Check if pronouns are used AND no topic is mentioned
            has_pronoun = any(p in query_words for p in pronouns)
            topic_mentioned = any(t in query.lower() for t in self.recent_search_topics)
            
            if has_pronoun and not topic_mentioned:
                # Add relevant topics to resolve the pronoun
                # Filter topics to get most relevant (proper nouns, names)
                context_topics = self.recent_search_topics[:3]
                query = f"{' '.join(context_topics)} {query}"
                query = ' '.join(query.split())  # Clean up spaces
        
        return query.strip() or message
    
    def _show_search_confirmation(self, message: str):
        """Show the search confirmation bar."""
        self.pending_search_query = message
        self.pending_extracted_query = self._extract_search_query(message)
        self._append_message("user", message)
        
        # Update label to show what will be searched
        self.search_confirm_label.configure(
            text=f"🔍 Search the web for: '{self.pending_extracted_query}'?"
        )
        
        self.search_confirm_frame.grid(row=4, column=0, padx=20, pady=(0, 5), sticky="ew")
        self.input_field.configure(state="disabled")
    
    def _confirm_search(self):
        """User confirmed to search the web."""
        query = self.pending_extracted_query  # Use the extracted query
        original_message = self.pending_search_query
        self.pending_search_query = None
        self.pending_extracted_query = None
        self.search_confirm_frame.grid_forget()
        self.input_field.configure(state="normal")
        
        if query:
            # Store original message context for AI
            self.conversation_history.append({"role": "user", "content": original_message})
            
            # Check if we need location for this query
            if self._needs_location(original_message):
                if self.location_permission is None:
                    # Haven't asked yet - ask for permission
                    self.pending_location_query = original_message
                    self.location_confirm_frame.grid(row=5, column=0, padx=20, pady=(0, 5), sticky="ew")
                    self.input_field.configure(state="disabled")
                    return
                elif self.location_permission and self.user_location:
                    # Permission granted and we have location - enhance query
                    city = self.user_location['city']
                    region = self.user_location['region']
                    location_str = f"{city}, {region}" if region else city
                    if 'local' in query.lower():
                        query = query.replace('local', location_str)
                    else:
                        query = f"{query} {location_str}"
            
            self._do_search(query, ask_ai=True)
    
    def _decline_search(self):
        """User declined search - proceed with AI only."""
        message = self.pending_search_query
        self.pending_search_query = None
        self.pending_extracted_query = None
        self.search_confirm_frame.grid_forget()
        
        # Add to conversation and generate AI response
        self.conversation_history.append({"role": "user", "content": message})
        
        self.send_button.configure(state="disabled", text="...")
        
        thread = threading.Thread(target=self._generate_response, args=(message,))
        thread.daemon = True
        thread.start()
    
    # ─────────────────────────────────────────────────────────────────────────────
    # Location Detection
    # ─────────────────────────────────────────────────────────────────────────────
    
    def _needs_location(self, message: str) -> bool:
        """Check if query needs location but doesn't have one specified."""
        message_lower = message.lower()
        
        # Keywords that suggest local information is needed
        location_keywords = ['weather', 'local', 'nearby', 'near me', 'around here', 
                            'in my area', 'my city', 'my location']
        
        # Check if needs location
        needs_location = any(kw in message_lower for kw in location_keywords)
        
        if not needs_location:
            return False
        
        # Check if location is already specified (has a city/place name)
        # Look for patterns like "in <place>" or "<place> weather"
        has_location = any(word in message_lower for word in [
            ' in ', ' at ', ' for ', 'calgary', 'toronto', 'vancouver', 'montreal',
            'new york', 'london', 'paris', 'tokyo', 'sydney', 'berlin'
            # This is a basic check - the location extraction handles the rest
        ])
        
        # If "local" or "my" is used without a specific location, we need to detect
        local_indicators = ['local', 'my area', 'my city', 'near me', 'around here']
        explicitly_local = any(kw in message_lower for kw in local_indicators)
        
        return explicitly_local or (needs_location and not has_location)
    
    def _detect_location(self) -> dict | None:
        """Detect user's location using IP geolocation."""
        try:
            # Using ip-api.com (free, no API key needed)
            response = requests.get('http://ip-api.com/json/', timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return {
                        'city': data.get('city', ''),
                        'region': data.get('regionName', ''),
                        'country': data.get('country', ''),
                        'lat': data.get('lat'),
                        'lon': data.get('lon'),
                    }
        except Exception as e:
            print(f"Location detection failed: {e}")
        return None
    
    def _show_location_permission(self, message: str):
        """Show location permission dialog."""
        self.pending_location_query = message
        self._append_message("user", message)
        self.location_confirm_frame.grid(row=5, column=0, padx=20, pady=(0, 5), sticky="ew")
        self.input_field.configure(state="disabled")
    
    def _allow_location(self):
        """User allowed location detection."""
        self.location_permission = True
        self.location_confirm_frame.grid_forget()
        self.input_field.configure(state="normal")
        
        message = self.pending_location_query
        self.pending_location_query = None
        
        # Detect location in background
        self._append_message("system", "Detecting your location...\\n")
        thread = threading.Thread(target=self._fetch_location_and_search, args=(message,))
        thread.daemon = True
        thread.start()
    
    def _fetch_location_and_search(self, message: str):
        """Fetch location and then perform search."""
        location = self._detect_location()
        
        if location:
            self.user_location = location
            city = location['city']
            region = location['region']
            location_str = f"{city}, {region}" if region else city
            
            # Update UI
            self.after(0, lambda: self._append_message("system", 
                f"📍 Location detected: {location_str}\\n"))
            
            # Enhance query with location
            query = self._extract_search_query(message)
            if 'local' in query.lower():
                query = query.replace('local', location_str)
            else:
                query = f"{query} {location_str}"
            
            # Perform search
            self.after(0, lambda: self._do_search(query, ask_ai=True))
        else:
            self.after(0, lambda: self._append_message("error", 
                "Could not detect location. Please specify a city in your query."))
            self.after(0, self._re_enable_inputs)
    
    def _deny_location(self):
        """User denied location detection."""
        self.location_permission = False
        self.location_confirm_frame.grid_forget()
        self.input_field.configure(state="normal")
        
        message = self.pending_location_query
        self.pending_location_query = None
        
        # Proceed without location
        self._append_message("system", "Location detection declined. Please specify a city for local results.\\n")
        
        # Still try to search with generic query
        query = self._extract_search_query(message)
        self._do_search(query, ask_ai=True)
    
    def _generate_response(self, message: str):
        """Generate AI response (runs in background thread)."""
        try:
            # Build prompt with context
            prompt = self._build_prompt(message)
            
            # Generate response
            response = self.client.generate(self.current_model, prompt)
            
            # Update UI from main thread
            self.after(0, lambda: self._show_response(response))
            
        except Exception as e:
            self.after(0, lambda: self._show_error(str(e)))
    
    def _build_prompt(self, message: str) -> str:
        """Build the full prompt with conversation history."""
        parts = []
        
        # System prompt
        if self.system_prompt:
            parts.append(f"System: {self.system_prompt}\n")
        
        # Conversation history (last 10 exchanges)
        for msg in self.conversation_history[-20:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                parts.append(f"User: {content}")
            else:
                parts.append(f"Assistant: {content}")
        
        parts.append("Assistant:")
        
        return "\n\n".join(parts)
    
    def _show_response(self, response: str):
        """Show the AI response, separating thinking from final answer."""
        import re
        
        # Parse thinking tags
        thinking_match = re.search(r'<thinking>(.*?)</thinking>', response, re.DOTALL)
        
        if thinking_match:
            thinking_content = thinking_match.group(1).strip()
            # Remove thinking from main response
            final_response = re.sub(r'<thinking>.*?</thinking>', '', response, flags=re.DOTALL).strip()
        else:
            thinking_content = None
            final_response = response.strip()
        
        # Display in chat
        self.chat_display.configure(state="normal")
        
        # Show thinking in side panel if present
        if thinking_content:
            self._append_thinking(thinking_content)
        
        # Show final response in main chat
        self.chat_display.insert("end", "Gene: ", "assistant")
        self.chat_display.insert("end", f"{final_response}\n\n")
        
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")
        
        # Check if Gene is asking for location - set pending context
        response_lower = final_response.lower()
        location_questions = ['city', 'zip code', 'location', 'area', 'where are you', 'which city']
        if any(q in response_lower for q in location_questions) and '?' in final_response:
            # Gene is asking for location, store context from last user message
            if self.conversation_history:
                for msg in reversed(self.conversation_history):
                    if msg.get('role') == 'user':
                        user_msg = msg.get('content', '').lower()
                        # Extract the query type (weather, temperature, news, etc.)
                        if any(kw in user_msg for kw in ['weather', 'temperature', 'forecast']):
                            self.pending_query_context = "current weather temperature"
                        elif any(kw in user_msg for kw in ['news', 'happening']):
                            self.pending_query_context = "latest news"
                        elif any(kw in user_msg for kw in ['restaurant', 'food', 'eat']):
                            self.pending_query_context = "restaurants near"
                        elif any(kw in user_msg for kw in ['store', 'shop', 'buy']):
                            self.pending_query_context = "stores near"
                        else:
                            # Generic - use the keywords from user's message
                            self.pending_query_context = user_msg[:50]
                        break
        
        # Store full response in history
        self.conversation_history.append({"role": "assistant", "content": response})
        
        # Auto-save session after each exchange
        self._save_current_session()
        
        # Re-enable input
        self._re_enable_inputs()
    
    def _show_error(self, error: str):
        """Show an error message."""
        self._append_message("error", f"Error: {error}\n\nMake sure Ollama is running: ollama serve")
        
        # Re-enable input
        self._re_enable_inputs()
    
    def _clear_chat(self):
        """Clear the chat history and start a new session."""
        # Save current session before clearing
        if self.conversation_history:
            self._save_current_session()
        
        # Reset session
        self.current_session_id = None
        self.session_title = None
        self.conversation_history = []
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")
        
        # Clear thinking panel
        self._clear_thinking()
        
        # Clear search context
        self.recent_search_topics = []
        self.last_search_results = []
        self.search_context_active = False
        
        # Show status based on internet toggle
        if SEARCH_AVAILABLE:
            if self.internet_enabled:
                status = " 🌐 Internet is ON - auto-search enabled."
            else:
                status = " 🌐 Internet is OFF - click globe to enable."
        else:
            status = ""
        self._append_message("system", f"Chat cleared. Start a new conversation!{status}\\n")
        
        # Refresh history list if visible
        if self.history_visible:
            self._refresh_history_list()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Web Search
    # ─────────────────────────────────────────────────────────────────────────
    
    def _search_web(self):
        """Trigger web search from input field content."""
        query = self.input_field.get("1.0", "end-1c").strip()
        if not query:
            self._append_message("system", "Enter a search query in the input field, then click 🔍\n")
            return
        
        self.input_field.delete("1.0", "end")
        self._append_message("user", f"🔍 Search: {query}")
        self._do_search(query, ask_ai=True)
    
    def _extract_search_topics(self, query: str, results: list):
        """Extract key topics from search query and results for follow-up detection."""
        topics = set()
        primary_topics = []  # Most important topics (names, places)
        
        # Words to always exclude
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to', 
                     'for', 'of', 'and', 'or', 'today', 'now', 'what', 'how', 'when', 'where',
                     'can', 'could', 'would', 'should', 'will', 'do', 'does', 'did'}
        
        # Event-related words to exclude (not useful for follow-ups)
        event_words = {'tickets', 'ticket', 'tour', 'dates', 'concert', 'coming', 'going',
                       'announces', 'announced', 'announcing', 'show', 'shows', 'event',
                       'events', 'live', 'performing', 'performance', 'buy', 'sale',
                       'available', 'visit', 'visiting'}
        
        # Extract from original query - prioritize these
        query_words = query.split()  # Keep original case
        for word in query_words:
            clean = word.strip('.,!?:;()[]"\'').lower()
            if len(clean) > 2 and clean not in stopwords and clean not in event_words:
                # Check if original was capitalized (likely a name)
                original_clean = word.strip('.,!?:;()[]"\'')
                if original_clean and original_clean[0].isupper():
                    primary_topics.append(clean)
                else:
                    topics.add(clean)
        
        # Extract proper nouns from result titles (names are most important)
        for r in results[:3]:
            original_title = r.get('title', '')
            words = original_title.split()
            for word in words:
                clean = word.strip('.,!?:;()[]"\'–—-')
                if len(clean) > 2 and clean[0].isupper():
                    lower = clean.lower()
                    if lower not in stopwords and lower not in event_words:
                        # Names are likely consecutive capitalized words
                        primary_topics.append(lower)
        
        # Build final topic list - primary topics first
        final_topics = []
        seen = set()
        for t in primary_topics:
            if t not in seen:
                final_topics.append(t)
                seen.add(t)
        for t in topics:
            if t not in seen:
                final_topics.append(t)
                seen.add(t)
        
        # Update tracking - keep only top 6 topics (focused)
        self.recent_search_topics = final_topics[:6]
        self.last_search_results = results[:5]
        self.search_context_active = True
    
    def _do_search(self, query: str, ask_ai: bool = False):
        """Perform web search in background thread."""
        if not SEARCH_AVAILABLE:
            self._append_message("error", "Web search not available. Install: pip install duckduckgo-search")
            return
        
        # Disable inputs
        self.send_button.configure(state="disabled", text="...")
        self.input_field.configure(state="disabled")
        if hasattr(self, 'search_button'):
            self.search_button.configure(state="disabled")
        
        self._append_message("system", f"Searching the web for: {query}...\n")
        
        # Run search in background
        thread = threading.Thread(target=self._perform_search, args=(query, ask_ai))
        thread.daemon = True
        thread.start()
    
    def _perform_search(self, query: str, ask_ai: bool):
        """Perform the actual search (runs in background thread)."""
        try:
            # New ddgs library doesn't need context manager
            ddgs = DDGS()
            results = list(ddgs.text(query, max_results=5))
            
            if not results:
                self.after(0, lambda: self._show_search_results([], query, ask_ai))
                return
            
            self.after(0, lambda: self._show_search_results(results, query, ask_ai))
            
        except Exception as e:
            self.after(0, lambda: self._search_error(str(e)))
    
    def _show_search_results(self, results: list, query: str, ask_ai: bool):
        """Display search results."""
        if not results:
            self._append_message("search", "No results found.")
            self._re_enable_inputs()
            return
        
        # Extract and store topics for follow-up question detection
        self._extract_search_topics(query, results)
        
        # Format results
        formatted = f"Search results for '{query}':\n\n"
        for i, r in enumerate(results, 1):
            title = r.get('title', 'No title')
            body = r.get('body', '')[:200]
            url = r.get('href', '')
            formatted += f"{i}. {title}\n   {body}...\n   🔗 {url}\n\n"
        
        self._append_message("search", formatted)
        
        # If ask_ai, send to AI for analysis
        if ask_ai:
            self._analyze_search_results(query, results)
        else:
            self._re_enable_inputs()
    
    def _fetch_page_content(self, url: str, max_chars: int = 4000) -> str:
        """Fetch and extract text content from a webpage."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Simple HTML to text extraction
            html = response.text
            
            # Remove script and style elements
            html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL | re.IGNORECASE)
            
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', ' ', html)
            
            # Decode HTML entities
            text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
            text = text.replace('&lt;', '<').replace('&gt;', '>')
            text = text.replace('&quot;', '"').replace('&#39;', "'")
            text = re.sub(r'&#\d+;', '', text)
            text = re.sub(r'&\w+;', '', text)
            
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Truncate to max chars
            if len(text) > max_chars:
                text = text[:max_chars] + "..."
            
            return text
        except Exception as e:
            return f"[Could not fetch page: {e}]"

    def _analyze_search_results(self, query: str, results: list):
        """Have AI analyze search results."""
        # Build context from search results
        context = f"Web search results for '{query}':\n\n"
        
        # Check if this is a query that needs real-time data (weather, prices, etc.)
        query_lower = query.lower()
        is_weather_query = any(kw in query_lower for kw in ['weather', 'temperature', 'forecast'])
        needs_page_fetch = any(kw in query_lower for kw in [
            'weather', 'temperature', 'forecast', 'price', 'stock', 
            'score', 'result', 'news', 'latest', 'current', 'today'
        ])
        
        # Sites to skip for page fetching (too generic or don't have current data)
        skip_sites = ['wikipedia.org', 'experthelp.com', 'quora.com', 'reddit.com']
        # Preferred sites for weather
        weather_sites = ['weather.gc.ca', 'theweathernetwork.com', 'weather.com', 
                        'accuweather.com', 'cbc.ca', 'ctvnews.ca', 'globalnews.ca']
        
        page_fetched = False
        best_url_to_fetch = None
        
        # Find the best URL to fetch for weather queries
        if needs_page_fetch and is_weather_query:
            # First look for preferred weather/news sites
            for r in results:
                url = r.get('href', '')
                if any(site in url for site in weather_sites):
                    best_url_to_fetch = url
                    break
            # Fallback: first non-skipped URL
            if not best_url_to_fetch:
                for r in results:
                    url = r.get('href', '')
                    if url and not any(skip in url for skip in skip_sites):
                        best_url_to_fetch = url
                        break
        
        for i, r in enumerate(results, 1):
            title = r.get('title', '')
            body = r.get('body', '')
            url = r.get('href', '')
            
            context += f"{i}. {title}\n{body}\nURL: {url}\n"
            
            # Fetch the best URL we identified (not just the first one)
            if needs_page_fetch and not page_fetched and url == best_url_to_fetch:
                self._append_message("system", f"📄 Fetching live data from {url[:60]}...\n")
                page_content = self._fetch_page_content(url)
                if page_content and not page_content.startswith("[Could not"):
                    context += f"\n--- Page Content ---\n{page_content}\n--- End Page Content ---\n"
                page_fetched = True
            
            context += "\n"
        
        # Build a more explicit prompt for the LLM
        if is_weather_query:
            instruction = (
                "Based on these search results, provide the current weather information. "
                "IMPORTANT: The search result snippets contain temperature data - extract and report it. "
                "Look for temperatures in °C or °F mentioned in the results above. "
                "Be specific - state the actual temperature numbers found in the results."
            )
        else:
            instruction = (
                "Based on these search results and page content, please answer the user's question directly. "
                "Extract specific data like temperatures, prices, scores, etc. if available in the results."
            )
        
        # Add to conversation
        self.conversation_history.append({
            "role": "user",
            "content": f"[Web Search: {query}]\n\n{context}\n\n{instruction}"
        })
        
        # Generate AI response
        thread = threading.Thread(target=self._generate_response, args=(f"Answer based on search for: {query}",))
        thread.daemon = True
        thread.start()
    
    def _search_error(self, error: str):
        """Handle search error."""
        self._append_message("error", f"Search failed: {error}")
        self._re_enable_inputs()
    
    def _re_enable_inputs(self):
        """Re-enable all input controls."""
        self.send_button.configure(state="normal", text="Send")
        self.input_field.configure(state="normal")
        if hasattr(self, 'search_button'):
            self.search_button.configure(state="normal")
        self.input_field.focus()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Business Management
    # ─────────────────────────────────────────────────────────────────────────
    
    def _handle_business_query(self, message: str):
        """Handle a business-related query."""
        if not self.business_handler:
            self._append_message("system", "Business module not available.\n")
            return
        
        # Process the query
        result = self.business_handler.process_query(message)
        
        if not result:
            # Not a business query after all, send to AI
            self.conversation_history.append({"role": "user", "content": message})
            thread = threading.Thread(target=self._generate_response, args=(message,))
            thread.daemon = True
            thread.start()
            return
        
        # Show thinking about business data
        self._append_thinking(f"📊 Business Query Detected\nCategory: {result.get('category', 'general')}\nAction: {result.get('action', 'query')}")
        
        # Show the result
        if result.get("success") and result.get("message"):
            self._append_message("assistant", result["message"] + "\n")
        elif not result.get("success"):
            self._append_message("error", result.get("message", "Error processing business query") + "\n")
        
        # If web search suggested
        if result.get("needs_web_search") and result.get("search_suggestion"):
            if self.internet_enabled and SEARCH_AVAILABLE:
                self._append_message("system", f"🔍 Searching for additional info: {result['search_suggestion']}\n")
                self._do_search(result["search_suggestion"], ask_ai=True)
                return
            elif SEARCH_AVAILABLE:
                self._append_message("system", f"💡 Tip: Enable internet (🌐) to search for: {result['search_suggestion']}\n")
        
        # If we have data, offer to analyze with AI
        if result.get("data") and message.endswith("?"):
            # Let AI provide additional insights
            context = f"Business data query result:\n{result.get('message', '')}\n\nUser asked: {message}"
            self.conversation_history.append({"role": "user", "content": context})
            thread = threading.Thread(target=self._generate_response, args=(message,))
            thread.daemon = True
            thread.start()
        else:
            self._re_enable_inputs()
    
    def _handle_business_command(self, command: str):
        """Handle explicit business commands (/biz or /business)."""
        if not self.business_handler:
            self._append_message("system", "Business module not available.\n")
            return
        
        cmd_lower = command.lower().strip()
        
        # Dashboard/Stats
        if not cmd_lower or cmd_lower in ["dashboard", "stats", "summary", "overview"]:
            stats = self.business_handler.db.get_dashboard_stats()
            self._append_message("assistant", self.business_handler._format_dashboard(stats) + "\n")
            return
        
        # Add contact
        if cmd_lower.startswith("add contact "):
            text = command[12:].strip()
            success, msg = self.business_handler.add_contact_from_text(text)
            self._append_message("assistant" if success else "error", msg + "\n")
            return
        
        # Add task
        if cmd_lower.startswith("add task "):
            text = command[9:].strip()
            success, msg = self.business_handler.add_task_from_text(text)
            self._append_message("assistant" if success else "error", msg + "\n")
            return
        
        # Add note
        if cmd_lower.startswith("add note "):
            text = command[9:].strip()
            parts = text.split(":", 1)
            title = parts[0].strip()
            content = parts[1].strip() if len(parts) > 1 else ""
            success, msg = self.business_handler.add_note_from_text(title, content)
            self._append_message("assistant" if success else "error", msg + "\n")
            return
        
        # List commands
        if cmd_lower.startswith("list ") or cmd_lower.startswith("show "):
            what = cmd_lower.split(" ", 1)[1].strip()
            result = self.business_handler.process_query(f"show all {what}")
            if result and result.get("message"):
                self._append_message("assistant", result["message"] + "\n")
            else:
                self._append_message("system", f"No data found for '{what}'\n")
            return
        
        # Help
        if cmd_lower == "help":
            help_text = """📊 **Business Commands**

**View Data:**
• `/biz` or `/biz dashboard` - Business overview
• `/biz list contacts` - List all contacts
• `/biz list clients` - List clients only
• `/biz list products` - List products/services
• `/biz list invoices` - List invoices
• `/biz list tasks` - List tasks

**Add Data:**
• `/biz add contact John Smith john@email.com` - Add contact
• `/biz add task Review quarterly report` - Add task
• `/biz add note Meeting Notes: Discussion about project` - Add note

**Natural Language:**
You can also just ask questions like:
• "How many clients do I have?"
• "Show me overdue invoices"
• "What are my urgent tasks?"
• "Find contacts at Acme Corp"
"""
            self._append_message("assistant", help_text + "\n")
            return
        
        # Unknown command - try as natural language
        self._handle_business_query(command)
    
    def _show_business_dashboard(self):
        """Show the business dashboard in chat."""
        if not self.business_handler:
            self._append_message("system", "Business module not available.\n")
            return
        
        stats = self.business_handler.db.get_dashboard_stats()
        dashboard = self.business_handler._format_dashboard(stats)
        
        self._append_message("assistant", dashboard + "\n\n💡 **Tip:** Type `/biz help` for available commands\n")


# ═══════════════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Launch the Gene desktop application."""
    print("🧬 Starting Gene - Generative Engine for Natural Engagement...")
    app = LocalAIAgentApp()
    app.mainloop()


if __name__ == "__main__":
    main()
