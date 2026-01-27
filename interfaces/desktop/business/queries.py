"""Business Query Handler for Gene.

Detects and handles business-related queries using local database
and web search integration.
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from .database import BusinessDatabase


class BusinessQueryHandler:
    """Handles business-related queries for Gene."""
    
    def __init__(self, database: BusinessDatabase = None):
        self.db = database or BusinessDatabase()
        
        # Business keywords for detection
        self.business_keywords = {
            # Contacts/Clients
            "contacts": ["contact", "contacts", "client", "clients", "customer", "customers", 
                        "vendor", "vendors", "lead", "leads", "supplier", "suppliers"],
            
            # Products/Services
            "products": ["product", "products", "service", "services", "item", "items",
                        "inventory", "stock", "sku", "catalog"],
            
            # Financial
            "invoices": ["invoice", "invoices", "bill", "bills", "payment", "payments",
                        "receipt", "receipts", "quote", "quotes", "estimate", "estimates",
                        "revenue", "income", "outstanding", "overdue", "paid", "unpaid"],
            
            # Tasks/Projects
            "tasks": ["task", "tasks", "todo", "to-do", "to do", "deadline", "deadlines",
                     "project", "projects", "milestone", "milestones", "assignment"],
            
            # Notes
            "notes": ["note", "notes", "memo", "memos", "document", "documents", "record"],
            
            # General business
            "general": ["business", "company", "sales", "profit", "cost", "expense",
                       "budget", "forecast", "report", "analytics", "dashboard", "summary",
                       "how many", "how much", "total", "count", "list", "show me", "find"]
        }
        
        # Action keywords
        self.action_keywords = {
            "add": ["add", "create", "new", "insert", "register", "save"],
            "find": ["find", "search", "look for", "look up", "get", "show", "list", "display"],
            "update": ["update", "edit", "modify", "change", "set"],
            "delete": ["delete", "remove", "cancel"],
            "summary": ["summary", "stats", "statistics", "overview", "dashboard", "report",
                       "how many", "how much", "total", "count"]
        }
    
    def is_business_query(self, message: str) -> bool:
        """Check if a message is business-related."""
        message_lower = message.lower()
        
        # Check for business keywords
        for category, keywords in self.business_keywords.items():
            for keyword in keywords:
                if keyword in message_lower:
                    return True
        
        return False
    
    def detect_query_type(self, message: str) -> Tuple[Optional[str], Optional[str]]:
        """Detect the category and action type of a business query.
        
        Returns: (category, action) - e.g., ("contacts", "find")
        """
        message_lower = message.lower()
        
        # Detect category
        category = None
        for cat, keywords in self.business_keywords.items():
            if cat == "general":
                continue
            for keyword in keywords:
                if keyword in message_lower:
                    category = cat
                    break
            if category:
                break
        
        # Detect action
        action = None
        for act, keywords in self.action_keywords.items():
            for keyword in keywords:
                if keyword in message_lower:
                    action = act
                    break
            if action:
                break
        
        # Default to find/summary if category detected but no action
        if category and not action:
            action = "find"
        
        return category, action
    
    def process_query(self, message: str) -> Optional[Dict[str, Any]]:
        """Process a business query and return relevant data.
        
        Returns a dict with:
        - success: bool
        - category: str
        - action: str
        - data: query results
        - message: human-readable response
        - needs_web_search: bool (if local data insufficient)
        """
        category, action = self.detect_query_type(message)
        
        if not category and not action:
            return None
        
        result = {
            "success": True,
            "category": category,
            "action": action,
            "data": None,
            "message": "",
            "needs_web_search": False,
            "search_suggestion": None
        }
        
        try:
            # Handle different categories and actions
            if action == "summary" or "dashboard" in message.lower() or "overview" in message.lower():
                result["data"] = self._get_summary(category)
                result["message"] = self._format_summary(result["data"], category)
            
            elif category == "contacts":
                result["data"], result["message"] = self._handle_contacts(message, action)
            
            elif category == "products":
                result["data"], result["message"] = self._handle_products(message, action)
            
            elif category == "invoices":
                result["data"], result["message"] = self._handle_invoices(message, action)
            
            elif category == "tasks":
                result["data"], result["message"] = self._handle_tasks(message, action)
            
            elif category == "notes":
                result["data"], result["message"] = self._handle_notes(message, action)
            
            else:
                # General business query - get dashboard
                result["data"] = self.db.get_dashboard_stats()
                result["message"] = self._format_dashboard(result["data"])
            
            # Check if data is empty and web search might help
            if not result["data"] or (isinstance(result["data"], list) and len(result["data"]) == 0):
                result["needs_web_search"] = self._should_suggest_web_search(message)
                if result["needs_web_search"]:
                    result["search_suggestion"] = self._get_search_suggestion(message, category)
        
        except Exception as e:
            result["success"] = False
            result["message"] = f"Error processing business query: {str(e)}"
        
        return result
    
    def _get_summary(self, category: str = None) -> Dict:
        """Get summary statistics."""
        if category == "contacts":
            contacts = self.db.list_contacts()
            clients = [c for c in contacts if c.get("type") == "client"]
            return {
                "total_contacts": len(contacts),
                "total_clients": len(clients),
                "contacts": contacts[:5]  # Top 5
            }
        
        elif category == "products":
            products = self.db.list_products()
            return {
                "total_products": len(products),
                "products": products[:5]
            }
        
        elif category == "invoices":
            return self.db.get_invoice_summary()
        
        elif category == "tasks":
            tasks = self.db.list_tasks()
            todo = [t for t in tasks if t.get("status") == "todo"]
            urgent = [t for t in tasks if t.get("priority") == "urgent" and t.get("status") != "done"]
            return {
                "total_tasks": len(tasks),
                "pending": len(todo),
                "urgent": len(urgent),
                "tasks": tasks[:5]
            }
        
        else:
            return self.db.get_dashboard_stats()
    
    def _format_summary(self, data: Dict, category: str) -> str:
        """Format summary data as human-readable text."""
        if not data:
            return "No data available."
        
        lines = []
        
        if category == "contacts":
            lines.append(f"📇 **Contacts Summary**")
            lines.append(f"• Total contacts: {data.get('total_contacts', 0)}")
            lines.append(f"• Total clients: {data.get('total_clients', 0)}")
        
        elif category == "products":
            lines.append(f"📦 **Products Summary**")
            lines.append(f"• Total products: {data.get('total_products', 0)}")
        
        elif category == "invoices":
            lines.append(f"💰 **Invoice Summary**")
            lines.append(f"• Total invoices: {data.get('total_invoices', 0)}")
            lines.append(f"• Total amount: ${data.get('total_amount', 0):,.2f}")
            lines.append(f"• Total paid: ${data.get('total_paid', 0):,.2f}")
            lines.append(f"• Outstanding: ${data.get('total_outstanding', 0):,.2f}")
        
        elif category == "tasks":
            lines.append(f"✅ **Tasks Summary**")
            lines.append(f"• Total tasks: {data.get('total_tasks', 0)}")
            lines.append(f"• Pending: {data.get('pending', 0)}")
            lines.append(f"• Urgent: {data.get('urgent', 0)}")
        
        else:
            lines.append(f"📊 **Business Dashboard**")
            lines.append(f"• Contacts: {data.get('total_contacts', 0)} ({data.get('total_clients', 0)} clients)")
            lines.append(f"• Products: {data.get('total_products', 0)}")
            lines.append(f"• Revenue (paid): ${data.get('revenue_paid', 0):,.2f}")
            lines.append(f"• Outstanding: ${data.get('revenue_outstanding', 0):,.2f}")
            lines.append(f"• Overdue invoices: {data.get('overdue_invoices', 0)}")
            lines.append(f"• Active tasks: {data.get('active_tasks', 0)} ({data.get('urgent_tasks', 0)} urgent)")
            lines.append(f"• Active projects: {data.get('active_projects', 0)}")
        
        return "\n".join(lines)
    
    def _format_dashboard(self, data: Dict) -> str:
        """Format dashboard stats."""
        return self._format_summary(data, None)
    
    def _handle_contacts(self, message: str, action: str) -> Tuple[Any, str]:
        """Handle contact-related queries."""
        message_lower = message.lower()
        
        if action == "add":
            # Extract name from message (simple extraction)
            # In production, you'd use NLP or structured input
            return None, "To add a contact, please provide:\n• Name\n• Email\n• Phone\n• Company (optional)"
        
        elif action in ["find", "summary"]:
            # Try to extract search term
            search_term = self._extract_search_term(message)
            
            if search_term:
                contacts = self.db.search_contacts(search_term)
                if contacts:
                    lines = [f"Found {len(contacts)} contact(s):"]
                    for c in contacts[:10]:
                        company = f" ({c['company']})" if c.get('company') else ""
                        email = f" - {c['email']}" if c.get('email') else ""
                        lines.append(f"• {c['name']}{company}{email}")
                    return contacts, "\n".join(lines)
                else:
                    return [], f"No contacts found matching '{search_term}'"
            else:
                # List all contacts
                contacts = self.db.list_contacts()
                if contacts:
                    lines = [f"📇 All contacts ({len(contacts)}):"]
                    for c in contacts[:10]:
                        company = f" ({c['company']})" if c.get('company') else ""
                        lines.append(f"• {c['name']}{company}")
                    if len(contacts) > 10:
                        lines.append(f"... and {len(contacts) - 10} more")
                    return contacts, "\n".join(lines)
                else:
                    return [], "No contacts in database yet."
        
        return None, "I can help you find, add, or manage contacts."
    
    def _handle_products(self, message: str, action: str) -> Tuple[Any, str]:
        """Handle product-related queries."""
        if action in ["find", "summary"]:
            search_term = self._extract_search_term(message)
            
            if search_term:
                products = self.db.search_products(search_term)
                if products:
                    lines = [f"Found {len(products)} product(s):"]
                    for p in products[:10]:
                        price = f" - ${p['price']:,.2f}" if p.get('price') else ""
                        lines.append(f"• {p['name']}{price}")
                    return products, "\n".join(lines)
                else:
                    return [], f"No products found matching '{search_term}'"
            else:
                products = self.db.list_products()
                if products:
                    lines = [f"📦 All products ({len(products)}):"]
                    for p in products[:10]:
                        price = f" - ${p['price']:,.2f}" if p.get('price') else ""
                        lines.append(f"• {p['name']}{price}")
                    return products, "\n".join(lines)
                else:
                    return [], "No products in database yet."
        
        return None, "I can help you find or manage products and services."
    
    def _handle_invoices(self, message: str, action: str) -> Tuple[Any, str]:
        """Handle invoice-related queries."""
        message_lower = message.lower()
        
        if action == "summary" or any(word in message_lower for word in ["total", "revenue", "outstanding", "overdue"]):
            summary = self.db.get_invoice_summary()
            return summary, self._format_summary(summary, "invoices")
        
        # Filter by status
        status = None
        if "overdue" in message_lower:
            status = "overdue"
        elif "paid" in message_lower:
            status = "paid"
        elif "unpaid" in message_lower or "outstanding" in message_lower:
            status = "sent"
        
        invoices = self.db.list_invoices(status=status)
        
        if invoices:
            lines = [f"💰 Invoices ({len(invoices)}):"]
            for inv in invoices[:10]:
                client = inv.get('contact_name', 'Unknown')
                status_icon = {"paid": "✅", "overdue": "⚠️", "sent": "📤", "draft": "📝"}.get(inv.get('status'), "📄")
                lines.append(f"{status_icon} {inv['invoice_number']} - {client} - ${inv['total']:,.2f}")
            return invoices, "\n".join(lines)
        else:
            return [], "No invoices found."
    
    def _handle_tasks(self, message: str, action: str) -> Tuple[Any, str]:
        """Handle task-related queries."""
        message_lower = message.lower()
        
        # Filter by status/priority
        status = None
        priority = None
        
        if "urgent" in message_lower:
            priority = "urgent"
        if "pending" in message_lower or "todo" in message_lower:
            status = "todo"
        elif "in progress" in message_lower or "active" in message_lower:
            status = "in-progress"
        elif "done" in message_lower or "completed" in message_lower:
            status = "done"
        
        tasks = self.db.list_tasks(status=status, priority=priority)
        
        if tasks:
            lines = [f"✅ Tasks ({len(tasks)}):"]
            for t in tasks[:10]:
                priority_icon = {"urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(t.get('priority'), "⚪")
                status_icon = {"done": "✅", "in-progress": "🔄", "todo": "⬜"}.get(t.get('status'), "⬜")
                due = f" (due: {t['due_date']})" if t.get('due_date') else ""
                lines.append(f"{status_icon} {priority_icon} {t['title']}{due}")
            return tasks, "\n".join(lines)
        else:
            return [], "No tasks found."
    
    def _handle_notes(self, message: str, action: str) -> Tuple[Any, str]:
        """Handle note-related queries."""
        search_term = self._extract_search_term(message)
        
        if search_term:
            notes = self.db.search_notes(search_term)
        else:
            notes = self.db.list_notes()
        
        if notes:
            lines = [f"📝 Notes ({len(notes)}):"]
            for n in notes[:10]:
                preview = (n.get('content', '')[:50] + '...') if len(n.get('content', '')) > 50 else n.get('content', '')
                lines.append(f"• {n['title']}: {preview}")
            return notes, "\n".join(lines)
        else:
            return [], "No notes found."
    
    def _extract_search_term(self, message: str) -> Optional[str]:
        """Extract search term from a message."""
        # Remove common query words
        stop_words = ["find", "search", "show", "list", "get", "display", "look", "for", "up",
                     "all", "my", "the", "a", "an", "me", "contacts", "clients", "products",
                     "invoices", "tasks", "notes", "please", "can", "you", "i", "want", "to", "see"]
        
        words = message.lower().split()
        filtered = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Return remaining words as search term
        if filtered:
            return " ".join(filtered)
        return None
    
    def _should_suggest_web_search(self, message: str) -> bool:
        """Check if web search would be helpful."""
        message_lower = message.lower()
        
        # Keywords suggesting external research
        research_keywords = [
            "how to", "what is", "best practice", "industry", "market", "trend",
            "competitor", "regulation", "law", "tax", "advice", "strategy",
            "template", "example", "benchmark", "average", "standard"
        ]
        
        return any(keyword in message_lower for keyword in research_keywords)
    
    def _get_search_suggestion(self, message: str, category: str) -> str:
        """Generate a web search suggestion."""
        # Create a search query based on the message and category
        base_terms = {
            "contacts": "CRM best practices",
            "products": "product management",
            "invoices": "invoicing business finance",
            "tasks": "project management productivity",
            "notes": "business documentation"
        }
        
        base = base_terms.get(category, "business management")
        
        # Extract key terms from message
        search_term = self._extract_search_term(message)
        if search_term:
            return f"{search_term} {base}"
        return base
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Data Entry Helpers (for structured input)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_contact_from_text(self, text: str) -> Tuple[bool, str]:
        """Parse and add a contact from natural language."""
        # Simple extraction - in production use NLP
        data = {}
        
        # Extract email
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        if email_match:
            data['email'] = email_match.group()
        
        # Extract phone (simple pattern)
        phone_match = re.search(r'[\d\-\(\)\s]{10,}', text)
        if phone_match:
            data['phone'] = phone_match.group().strip()
        
        # The first capitalized words are likely the name
        words = text.split()
        name_words = []
        for word in words:
            if word[0].isupper() and '@' not in word and not word.isdigit():
                name_words.append(word)
            elif name_words:
                break
        
        if name_words:
            data['name'] = ' '.join(name_words)
        
        if 'name' not in data:
            return False, "Could not extract a name. Please provide a name for the contact."
        
        try:
            contact_id = self.db.add_contact(**data)
            return True, f"✅ Added contact: {data['name']} (ID: {contact_id})"
        except Exception as e:
            return False, f"Error adding contact: {str(e)}"
    
    def add_task_from_text(self, text: str) -> Tuple[bool, str]:
        """Parse and add a task from natural language."""
        # Simple extraction
        data = {'title': text}
        
        # Check for priority keywords
        text_lower = text.lower()
        if 'urgent' in text_lower:
            data['priority'] = 'urgent'
        elif 'important' in text_lower or 'high priority' in text_lower:
            data['priority'] = 'high'
        
        # Check for date keywords (simple)
        if 'tomorrow' in text_lower:
            from datetime import datetime, timedelta
            data['due_date'] = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        elif 'today' in text_lower:
            from datetime import datetime
            data['due_date'] = datetime.now().strftime('%Y-%m-%d')
        
        try:
            task_id = self.db.add_task(**data)
            return True, f"✅ Added task: {data['title']} (ID: {task_id})"
        except Exception as e:
            return False, f"Error adding task: {str(e)}"
    
    def add_note_from_text(self, title: str, content: str = "") -> Tuple[bool, str]:
        """Add a note."""
        try:
            note_id = self.db.add_note(title=title, content=content)
            return True, f"✅ Added note: {title} (ID: {note_id})"
        except Exception as e:
            return False, f"Error adding note: {str(e)}"
    
    def _format_dashboard(self, stats: Dict[str, Any]) -> str:
        """Format dashboard statistics for display."""
        lines = ["📊 **Business Dashboard**", ""]
        
        # Contacts
        lines.append(f"👥 **Contacts**: {stats.get('total_contacts', 0)}")
        lines.append(f"   • Clients: {stats.get('clients', 0)}")
        lines.append(f"   • Vendors: {stats.get('vendors', 0)}")
        lines.append(f"   • Leads: {stats.get('leads', 0)}")
        lines.append("")
        
        # Products
        lines.append(f"📦 **Products/Services**: {stats.get('total_products', 0)}")
        lines.append("")
        
        # Invoices
        lines.append(f"📄 **Invoices**: {stats.get('total_invoices', 0)}")
        lines.append(f"   • Paid: {stats.get('paid_invoices', 0)}")
        lines.append(f"   • Pending: {stats.get('pending_invoices', 0)}")
        lines.append(f"   • Overdue: {stats.get('overdue_invoices', 0)}")
        if stats.get('outstanding_amount', 0) > 0:
            lines.append(f"   • Outstanding: ${stats.get('outstanding_amount', 0):,.2f}")
        lines.append("")
        
        # Tasks
        lines.append(f"✅ **Tasks**: {stats.get('total_tasks', 0)}")
        lines.append(f"   • Pending: {stats.get('pending_tasks', 0)}")
        lines.append(f"   • In Progress: {stats.get('in_progress_tasks', 0)}")
        lines.append(f"   • Completed: {stats.get('completed_tasks', 0)}")
        if stats.get('overdue_tasks', 0) > 0:
            lines.append(f"   • ⚠️ Overdue: {stats.get('overdue_tasks', 0)}")
        lines.append("")
        
        # Notes
        lines.append(f"📝 **Notes**: {stats.get('total_notes', 0)}")
        
        return "\n".join(lines)
