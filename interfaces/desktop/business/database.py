"""SQLite Database for Business Management.

Stores and manages business data locally.
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

# Database file location
DB_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(DB_DIR, "business_data.db")


class BusinessDatabase:
    """SQLite database for business data management."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dicts
        return conn
    
    def _init_database(self):
        """Initialize database tables."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # ─────────────────────────────────────────────────────────────────────
        # Contacts / Clients
        # ─────────────────────────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                company TEXT,
                email TEXT,
                phone TEXT,
                address TEXT,
                type TEXT DEFAULT 'contact',  -- contact, client, vendor, lead
                notes TEXT,
                tags TEXT,  -- JSON array of tags
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ─────────────────────────────────────────────────────────────────────
        # Products / Services
        # ─────────────────────────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                sku TEXT,
                price REAL,
                cost REAL,
                category TEXT,
                type TEXT DEFAULT 'product',  -- product, service
                stock_quantity INTEGER DEFAULT 0,
                unit TEXT DEFAULT 'each',
                active INTEGER DEFAULT 1,
                tags TEXT,  -- JSON array
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ─────────────────────────────────────────────────────────────────────
        # Invoices / Transactions
        # ─────────────────────────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE,
                contact_id INTEGER,
                type TEXT DEFAULT 'invoice',  -- invoice, quote, receipt
                status TEXT DEFAULT 'draft',  -- draft, sent, paid, overdue, cancelled
                subtotal REAL DEFAULT 0,
                tax_rate REAL DEFAULT 0,
                tax_amount REAL DEFAULT 0,
                total REAL DEFAULT 0,
                currency TEXT DEFAULT 'USD',
                issue_date TEXT,
                due_date TEXT,
                paid_date TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contact_id) REFERENCES contacts(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                product_id INTEGER,
                description TEXT,
                quantity REAL DEFAULT 1,
                unit_price REAL DEFAULT 0,
                total REAL DEFAULT 0,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)
        
        # ─────────────────────────────────────────────────────────────────────
        # Tasks / Projects
        # ─────────────────────────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                contact_id INTEGER,
                status TEXT DEFAULT 'active',  -- planning, active, on-hold, completed, cancelled
                start_date TEXT,
                end_date TEXT,
                budget REAL,
                tags TEXT,  -- JSON array
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contact_id) REFERENCES contacts(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                project_id INTEGER,
                contact_id INTEGER,
                status TEXT DEFAULT 'todo',  -- todo, in-progress, done, cancelled
                priority TEXT DEFAULT 'medium',  -- low, medium, high, urgent
                due_date TEXT,
                completed_at TEXT,
                tags TEXT,  -- JSON array
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (contact_id) REFERENCES contacts(id)
            )
        """)
        
        # ─────────────────────────────────────────────────────────────────────
        # Notes / Documents
        # ─────────────────────────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                category TEXT,
                contact_id INTEGER,
                project_id INTEGER,
                tags TEXT,  -- JSON array
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contact_id) REFERENCES contacts(id),
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)
        
        # ─────────────────────────────────────────────────────────────────────
        # Business Settings / Config
        # ─────────────────────────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS business_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Contact Management
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_contact(self, name: str, **kwargs) -> int:
        """Add a new contact."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        fields = ["name"]
        values = [name]
        
        for key in ["company", "email", "phone", "address", "type", "notes"]:
            if key in kwargs:
                fields.append(key)
                values.append(kwargs[key])
        
        if "tags" in kwargs:
            fields.append("tags")
            values.append(json.dumps(kwargs["tags"]))
        
        placeholders = ", ".join(["?" for _ in values])
        field_names = ", ".join(fields)
        
        cursor.execute(f"INSERT INTO contacts ({field_names}) VALUES ({placeholders})", values)
        contact_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return contact_id
    
    def get_contact(self, contact_id: int) -> Optional[Dict]:
        """Get a contact by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def search_contacts(self, query: str, contact_type: str = None) -> List[Dict]:
        """Search contacts by name, company, or email."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        sql = """
            SELECT * FROM contacts 
            WHERE (name LIKE ? OR company LIKE ? OR email LIKE ? OR notes LIKE ?)
        """
        params = [f"%{query}%"] * 4
        
        if contact_type:
            sql += " AND type = ?"
            params.append(contact_type)
        
        sql += " ORDER BY name"
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def list_contacts(self, contact_type: str = None, limit: int = 50) -> List[Dict]:
        """List all contacts."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if contact_type:
            cursor.execute(
                "SELECT * FROM contacts WHERE type = ? ORDER BY name LIMIT ?",
                (contact_type, limit)
            )
        else:
            cursor.execute("SELECT * FROM contacts ORDER BY name LIMIT ?", (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def update_contact(self, contact_id: int, **kwargs) -> bool:
        """Update a contact."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        updates = []
        values = []
        
        for key in ["name", "company", "email", "phone", "address", "type", "notes"]:
            if key in kwargs:
                updates.append(f"{key} = ?")
                values.append(kwargs[key])
        
        if "tags" in kwargs:
            updates.append("tags = ?")
            values.append(json.dumps(kwargs["tags"]))
        
        if not updates:
            conn.close()
            return False
        
        updates.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(contact_id)
        
        cursor.execute(f"UPDATE contacts SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    
    def delete_contact(self, contact_id: int) -> bool:
        """Delete a contact."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Product Management
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_product(self, name: str, **kwargs) -> int:
        """Add a new product or service."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        fields = ["name"]
        values = [name]
        
        for key in ["description", "sku", "price", "cost", "category", "type", 
                    "stock_quantity", "unit", "active"]:
            if key in kwargs:
                fields.append(key)
                values.append(kwargs[key])
        
        if "tags" in kwargs:
            fields.append("tags")
            values.append(json.dumps(kwargs["tags"]))
        
        placeholders = ", ".join(["?" for _ in values])
        field_names = ", ".join(fields)
        
        cursor.execute(f"INSERT INTO products ({field_names}) VALUES ({placeholders})", values)
        product_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return product_id
    
    def search_products(self, query: str) -> List[Dict]:
        """Search products by name, description, or SKU."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM products 
            WHERE (name LIKE ? OR description LIKE ? OR sku LIKE ? OR category LIKE ?)
            AND active = 1
            ORDER BY name
        """, (f"%{query}%",) * 4)
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def list_products(self, category: str = None, limit: int = 50) -> List[Dict]:
        """List all products."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if category:
            cursor.execute(
                "SELECT * FROM products WHERE category = ? AND active = 1 ORDER BY name LIMIT ?",
                (category, limit)
            )
        else:
            cursor.execute("SELECT * FROM products WHERE active = 1 ORDER BY name LIMIT ?", (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Invoice Management
    # ═══════════════════════════════════════════════════════════════════════════
    
    def create_invoice(self, contact_id: int = None, **kwargs) -> int:
        """Create a new invoice."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Generate invoice number
        cursor.execute("SELECT COUNT(*) FROM invoices")
        count = cursor.fetchone()[0]
        invoice_number = kwargs.get("invoice_number", f"INV-{count + 1001:05d}")
        
        fields = ["invoice_number"]
        values = [invoice_number]
        
        if contact_id:
            fields.append("contact_id")
            values.append(contact_id)
        
        for key in ["type", "status", "subtotal", "tax_rate", "tax_amount", 
                    "total", "currency", "issue_date", "due_date", "notes"]:
            if key in kwargs:
                fields.append(key)
                values.append(kwargs[key])
        
        placeholders = ", ".join(["?" for _ in values])
        field_names = ", ".join(fields)
        
        cursor.execute(f"INSERT INTO invoices ({field_names}) VALUES ({placeholders})", values)
        invoice_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return invoice_id
    
    def get_invoice(self, invoice_id: int) -> Optional[Dict]:
        """Get an invoice with items."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT i.*, c.name as contact_name, c.company as contact_company
            FROM invoices i
            LEFT JOIN contacts c ON i.contact_id = c.id
            WHERE i.id = ?
        """, (invoice_id,))
        
        invoice_row = cursor.fetchone()
        if not invoice_row:
            conn.close()
            return None
        
        invoice = dict(invoice_row)
        
        # Get items
        cursor.execute("""
            SELECT ii.*, p.name as product_name
            FROM invoice_items ii
            LEFT JOIN products p ON ii.product_id = p.id
            WHERE ii.invoice_id = ?
        """, (invoice_id,))
        
        invoice["items"] = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return invoice
    
    def list_invoices(self, status: str = None, limit: int = 50) -> List[Dict]:
        """List invoices."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        sql = """
            SELECT i.*, c.name as contact_name
            FROM invoices i
            LEFT JOIN contacts c ON i.contact_id = c.id
        """
        params = []
        
        if status:
            sql += " WHERE i.status = ?"
            params.append(status)
        
        sql += " ORDER BY i.created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_invoice_summary(self) -> Dict:
        """Get invoice summary stats."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        summary = {}
        
        # Totals by status
        cursor.execute("""
            SELECT status, COUNT(*) as count, SUM(total) as total
            FROM invoices
            GROUP BY status
        """)
        summary["by_status"] = {row["status"]: {"count": row["count"], "total": row["total"] or 0} 
                               for row in cursor.fetchall()}
        
        # Overall totals
        cursor.execute("SELECT COUNT(*) as count, SUM(total) as total FROM invoices")
        row = cursor.fetchone()
        summary["total_invoices"] = row["count"]
        summary["total_amount"] = row["total"] or 0
        
        # Paid vs unpaid
        cursor.execute("SELECT SUM(total) FROM invoices WHERE status = 'paid'")
        summary["total_paid"] = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(total) FROM invoices WHERE status IN ('sent', 'overdue')")
        summary["total_outstanding"] = cursor.fetchone()[0] or 0
        
        conn.close()
        return summary
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Task Management
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_task(self, title: str, **kwargs) -> int:
        """Add a new task."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        fields = ["title"]
        values = [title]
        
        for key in ["description", "project_id", "contact_id", "status", 
                    "priority", "due_date"]:
            if key in kwargs:
                fields.append(key)
                values.append(kwargs[key])
        
        if "tags" in kwargs:
            fields.append("tags")
            values.append(json.dumps(kwargs["tags"]))
        
        placeholders = ", ".join(["?" for _ in values])
        field_names = ", ".join(fields)
        
        cursor.execute(f"INSERT INTO tasks ({field_names}) VALUES ({placeholders})", values)
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return task_id
    
    def list_tasks(self, status: str = None, priority: str = None, limit: int = 50) -> List[Dict]:
        """List tasks."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        sql = "SELECT * FROM tasks WHERE 1=1"
        params = []
        
        if status:
            sql += " AND status = ?"
            params.append(status)
        
        if priority:
            sql += " AND priority = ?"
            params.append(priority)
        
        sql += " ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, due_date LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def complete_task(self, task_id: int) -> bool:
        """Mark a task as completed."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE tasks 
            SET status = 'done', completed_at = ?, updated_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), datetime.now().isoformat(), task_id))
        
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Notes Management
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_note(self, title: str, content: str = "", **kwargs) -> int:
        """Add a new note."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        fields = ["title", "content"]
        values = [title, content]
        
        for key in ["category", "contact_id", "project_id"]:
            if key in kwargs:
                fields.append(key)
                values.append(kwargs[key])
        
        if "tags" in kwargs:
            fields.append("tags")
            values.append(json.dumps(kwargs["tags"]))
        
        placeholders = ", ".join(["?" for _ in values])
        field_names = ", ".join(fields)
        
        cursor.execute(f"INSERT INTO notes ({field_names}) VALUES ({placeholders})", values)
        note_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return note_id
    
    def search_notes(self, query: str) -> List[Dict]:
        """Search notes by title or content."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM notes 
            WHERE title LIKE ? OR content LIKE ?
            ORDER BY updated_at DESC
        """, (f"%{query}%", f"%{query}%"))
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def list_notes(self, category: str = None, limit: int = 50) -> List[Dict]:
        """List notes."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if category:
            cursor.execute(
                "SELECT * FROM notes WHERE category = ? ORDER BY updated_at DESC LIMIT ?",
                (category, limit)
            )
        else:
            cursor.execute("SELECT * FROM notes ORDER BY updated_at DESC LIMIT ?", (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Settings
    # ═══════════════════════════════════════════════════════════════════════════
    
    def set_setting(self, key: str, value: Any):
        """Set a business setting."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        value_str = json.dumps(value) if not isinstance(value, str) else value
        
        cursor.execute("""
            INSERT OR REPLACE INTO business_settings (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value_str, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a business setting."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM business_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return default
        
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Statistics & Reports
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_dashboard_stats(self) -> Dict:
        """Get overview statistics for dashboard."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Contacts
        cursor.execute("SELECT COUNT(*) FROM contacts")
        stats["total_contacts"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM contacts WHERE type = 'client'")
        stats["total_clients"] = cursor.fetchone()[0]
        
        # Products
        cursor.execute("SELECT COUNT(*) FROM products WHERE active = 1")
        stats["total_products"] = cursor.fetchone()[0]
        
        # Invoices
        cursor.execute("SELECT SUM(total) FROM invoices WHERE status = 'paid'")
        stats["revenue_paid"] = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(total) FROM invoices WHERE status IN ('sent', 'overdue')")
        stats["revenue_outstanding"] = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM invoices WHERE status = 'overdue'")
        stats["overdue_invoices"] = cursor.fetchone()[0]
        
        # Tasks
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'todo'")
        stats["pending_tasks"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'in-progress'")
        stats["active_tasks"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE priority = 'urgent' AND status != 'done'")
        stats["urgent_tasks"] = cursor.fetchone()[0]
        
        # Projects
        cursor.execute("SELECT COUNT(*) FROM projects WHERE status = 'active'")
        stats["active_projects"] = cursor.fetchone()[0]
        
        conn.close()
        return stats
    
    def execute_query(self, sql: str, params: tuple = ()) -> List[Dict]:
        """Execute a custom SQL query (SELECT only for safety)."""
        if not sql.strip().upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
