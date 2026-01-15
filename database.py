import sqlite3
import json
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Optional, Any
import os
from config import DATABASE_URL, TIMEZONE, BACKUP_DIR

class Database:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.init_database()
    
    def init_database(self):
        """Initialize database and create tables"""
        self.conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Create users table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_bot BOOLEAN,
                language_code TEXT,
                join_date TIMESTAMP,
                last_seen TIMESTAMP,
                stickers TEXT DEFAULT '[]',
                is_banned BOOLEAN DEFAULT FALSE,
                ban_reason TEXT,
                banned_by INTEGER,
                ban_date TIMESTAMP,
                custom_data TEXT DEFAULT '{}'
            )
        ''')
        
        # Create logs table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                timestamp TIMESTAMP
            )
        ''')
        
        # Create backups table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                size INTEGER,
                timestamp TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def add_user(self, user_data: Dict):
        """Add or update user in database"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, last_name, is_bot, language_code, join_date, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_data['user_id'],
                user_data.get('username'),
                user_data.get('first_name'),
                user_data.get('last_name'),
                user_data.get('is_bot', False),
                user_data.get('language_code'),
                user_data.get('join_date', datetime.now(pytz.timezone(TIMEZONE))),
                datetime.now(pytz.timezone(TIMEZONE))
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error adding user: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = self.cursor.fetchone()
        
        if row:
            columns = [description[0] for description in self.cursor.description]
            user_dict = dict(zip(columns, row))
            
            # Parse JSON fields
            if user_dict.get('stickers'):
                user_dict['stickers'] = json.loads(user_dict['stickers'])
            if user_dict.get('custom_data'):
                user_dict['custom_data'] = json.loads(user_dict['custom_data'])
            
            return user_dict
        return None
    
    def update_user(self, user_id: int, updates: Dict):
        """Update user information"""
        try:
            # Handle JSON fields
            if 'stickers' in updates:
                updates['stickers'] = json.dumps(updates['stickers'])
            if 'custom_data' in updates:
                updates['custom_data'] = json.dumps(updates['custom_data'])
            
            set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
            values = list(updates.values())
            values.append(user_id)
            
            query = f"UPDATE users SET {set_clause}, last_seen = ? WHERE user_id = ?"
            values.append(datetime.now(pytz.timezone(TIMEZONE)))
            
            self.cursor.execute(query, values)
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error updating user: {e}")
            return False
    
    def get_all_users(self, include_banned: bool = False) -> List[Dict]:
        """Get all users"""
        if include_banned:
            self.cursor.execute('SELECT * FROM users')
        else:
            self.cursor.execute('SELECT * FROM users WHERE is_banned = FALSE')
        
        rows = self.cursor.fetchall()
        columns = [description[0] for description in self.cursor.description]
        
        users = []
        for row in rows:
            user_dict = dict(zip(columns, row))
            
            # Parse JSON fields
            if user_dict.get('stickers'):
                user_dict['stickers'] = json.loads(user_dict['stickers'])
            if user_dict.get('custom_data'):
                user_dict['custom_data'] = json.loads(user_dict['custom_data'])
            
            users.append(user_dict)
        
        return users
    
    def ban_user(self, user_id: int, reason: str, banned_by: int):
        """Ban a user"""
        try:
            self.cursor.execute('''
                UPDATE users 
                SET is_banned = TRUE, 
                    ban_reason = ?, 
                    banned_by = ?,
                    ban_date = ?
                WHERE user_id = ?
            ''', (reason, banned_by, datetime.now(pytz.timezone(TIMEZONE)), user_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error banning user: {e}")
            return False
    
    def unban_user(self, user_id: int):
        """Unban a user"""
        try:
            self.cursor.execute('''
                UPDATE users 
                SET is_banned = FALSE, 
                    ban_reason = NULL, 
                    banned_by = NULL,
                    ban_date = NULL
                WHERE user_id = ?
            ''', (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error unbanning user: {e}")
            return False
    
    def get_banned_users(self) -> List[Dict]:
        """Get all banned users"""
        self.cursor.execute('''
            SELECT user_id, username, first_name, ban_reason, ban_date, banned_by 
            FROM users 
            WHERE is_banned = TRUE
        ''')
        
        rows = self.cursor.fetchall()
        columns = ['user_id', 'username', 'first_name', 'ban_reason', 'ban_date', 'banned_by']
        
        banned_users = []
        for row in rows:
            banned_users.append(dict(zip(columns, row)))
        
        return banned_users
    
    def get_user_stats(self) -> Dict:
        """Get user statistics"""
        # Total users
        self.cursor.execute('SELECT COUNT(*) FROM users')
        total_users = self.cursor.fetchone()[0]
        
        # Today's users
        today = datetime.now(pytz.timezone(TIMEZONE)).date()
        self.cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(join_date) = ?', (today,))
        today_users = self.cursor.fetchone()[0]
        
        # Banned users
        self.cursor.execute('SELECT COUNT(*) FROM users WHERE is_banned = TRUE')
        banned_users = self.cursor.fetchone()[0]
        
        # Last backup
        self.cursor.execute('SELECT MAX(timestamp) FROM backups')
        last_backup = self.cursor.fetchone()[0] or 'Never'
        
        return {
            'total_users': total_users,
            'today_users': today_users,
            'banned_users': banned_users,
            'last_backup': last_backup
        }
    
    def add_log(self, user_id: int, action: str, details: str):
        """Add log entry"""
        try:
            self.cursor.execute('''
                INSERT INTO logs (user_id, action, details, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (user_id, action, details, datetime.now(pytz.timezone(TIMEZONE))))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error adding log: {e}")
            return False
    
    def get_recent_logs(self, limit: int = 50) -> List[Dict]:
        """Get recent logs"""
        self.cursor.execute('''
            SELECT * FROM logs 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = self.cursor.fetchall()
        columns = [description[0] for description in self.cursor.description]
        
        logs = []
        for row in rows:
            logs.append(dict(zip(columns, row)))
        
        return logs
    
    def backup_database(self) -> Optional[str]:
        """Create database backup"""
        try:
            # Create backup directory if not exists
            os.makedirs(BACKUP_DIR, exist_ok=True)
            
            # Generate backup filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(BACKUP_DIR, f'backup_{timestamp}.db')
            
            # Create backup
            backup_conn = sqlite3.connect(backup_file)
            self.conn.backup(backup_conn)
            backup_conn.close()
            
            # Log backup
            file_size = os.path.getsize(backup_file)
            self.cursor.execute('''
                INSERT INTO backups (filename, size, timestamp)
                VALUES (?, ?, ?)
            ''', (backup_file, file_size, datetime.now(pytz.timezone(TIMEZONE))))
            self.conn.commit()
            
            # Clean old backups
            self.cleanup_old_backups()
            
            return backup_file
        except Exception as e:
            print(f"Error creating backup: {e}")
            return None
    
    def cleanup_old_backups(self):
        """Remove old backups"""
        try:
            self.cursor.execute('SELECT id, filename FROM backups ORDER BY timestamp DESC')
            backups = self.cursor.fetchall()
            
            # Keep only MAX_BACKUPS
            if len(backups) > 10:  # MAX_BACKUPS from config
                for backup_id, filename in backups[10:]:
                    # Remove file
                    if os.path.exists(filename):
                        os.remove(filename)
                    
                    # Remove from database
                    self.cursor.execute('DELETE FROM backups WHERE id = ?', (backup_id,))
                
                self.conn.commit()
        except Exception as e:
            print(f"Error cleaning up backups: {e}")

# Singleton instance
db_instance = None

def get_db():
    """Get database instance"""
    global db_instance
    if db_instance is None:
        db_instance = Database()
    return db_instance

# Convenience functions
def init_db():
    """Initialize database"""
    return get_db()

def add_user(user_data):
    """Add user to database"""
    return get_db().add_user(user_data)

def get_user(user_id):
    """Get user by ID"""
    return get_db().get_user(user_id)

def update_user(user_id, updates):
    """Update user information"""
    return get_db().update_user(user_id, updates)

def get_all_users(include_banned=False):
    """Get all users"""
    return get_db().get_all_users(include_banned)

def ban_user(user_id, reason, banned_by):
    """Ban a user"""
    return get_db().ban_user(user_id, reason, banned_by)

def unban_user(user_id):
    """Unban a user"""
    return get_db().unban_user(user_id)

def get_banned_users():
    """Get all banned users"""
    return get_db().get_banned_users()

def get_user_stats():
    """Get user statistics"""
    return get_db().get_user_stats()

def add_log(user_id, action, details):
    """Add log entry"""
    return get_db().add_log(user_id, action, details)

def backup_database():
    """Create database backup"""
    return get_db().backup_database()
