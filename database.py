import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz
from config import DATABASE_URL, TIMEZONE, BACKUP_DIR, MAX_BACKUPS

class Database:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.init_database()
    
    def init_database(self):
        """Initialize database and create tables"""
        try:
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
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create backups table
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT,
                    size INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.conn.commit()
            print("Database initialized successfully")
            
        except Exception as e:
            print(f"Error initializing database: {e}")
            raise
    
    def add_user(self, user_data: Dict) -> bool:
        """Add or update user in database"""
        try:
            # Check if user exists
            self.cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_data['user_id'],))
            existing_user = self.cursor.fetchone()
            
            current_time = datetime.now(pytz.timezone(TIMEZONE))
            
            if existing_user:
                # Update existing user
                self.cursor.execute('''
                    UPDATE users 
                    SET username = ?, first_name = ?, last_name = ?, last_seen = ?
                    WHERE user_id = ?
                ''', (
                    user_data.get('username'),
                    user_data.get('first_name'),
                    user_data.get('last_name'),
                    current_time,
                    user_data['user_id']
                ))
            else:
                # Insert new user
                self.cursor.execute('''
                    INSERT INTO users 
                    (user_id, username, first_name, last_name, is_bot, language_code, join_date, last_seen)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_data['user_id'],
                    user_data.get('username'),
                    user_data.get('first_name'),
                    user_data.get('last_name'),
                    user_data.get('is_bot', False),
                    user_data.get('language_code'),
                    user_data.get('join_date', current_time),
                    current_time
                ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"Error adding user: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        try:
            self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = self.cursor.fetchone()
            
            if row:
                columns = [description[0] for description in self.cursor.description]
                user_dict = dict(zip(columns, row))
                
                # Parse JSON fields
                if user_dict.get('stickers'):
                    try:
                        user_dict['stickers'] = json.loads(user_dict['stickers'])
                    except:
                        user_dict['stickers'] = []
                
                if user_dict.get('custom_data'):
                    try:
                        user_dict['custom_data'] = json.loads(user_dict['custom_data'])
                    except:
                        user_dict['custom_data'] = {}
                
                # Convert timestamp strings to readable format
                for date_field in ['join_date', 'last_seen', 'ban_date']:
                    if user_dict.get(date_field):
                        try:
                            user_dict[date_field] = datetime.strptime(
                                user_dict[date_field], '%Y-%m-%d %H:%M:%S.%f%z'
                            ).strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            pass
                
                return user_dict
            return None
            
        except Exception as e:
            print(f"Error getting user: {e}")
            return None
    
    def update_user(self, user_id: int, updates: Dict) -> bool:
        """Update user information"""
        try:
            current_time = datetime.now(pytz.timezone(TIMEZONE))
            
            # Handle JSON fields
            if 'stickers' in updates:
                updates['stickers'] = json.dumps(updates['stickers'])
            if 'custom_data' in updates:
                updates['custom_data'] = json.dumps(updates['custom_data'])
            
            # Build SET clause
            set_clause_parts = []
            values = []
            
            for key, value in updates.items():
                set_clause_parts.append(f"{key} = ?")
                values.append(value)
            
            # Always update last_seen
            set_clause_parts.append("last_seen = ?")
            values.append(current_time)
            
            set_clause = ', '.join(set_clause_parts)
            values.append(user_id)
            
            query = f"UPDATE users SET {set_clause} WHERE user_id = ?"
            self.cursor.execute(query, values)
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"Error updating user: {e}")
            return False
    
    def get_all_users(self, include_banned: bool = False) -> List[Dict]:
        """Get all users"""
        try:
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
                    try:
                        user_dict['stickers'] = json.loads(user_dict['stickers'])
                    except:
                        user_dict['stickers'] = []
                
                users.append(user_dict)
            
            return users
            
        except Exception as e:
            print(f"Error getting all users: {e}")
            return []
    
    def ban_user(self, user_id: int, reason: str, banned_by: int) -> bool:
        """Ban a user"""
        try:
            current_time = datetime.now(pytz.timezone(TIMEZONE))
            self.cursor.execute('''
                UPDATE users 
                SET is_banned = TRUE, 
                    ban_reason = ?, 
                    banned_by = ?,
                    ban_date = ?
                WHERE user_id = ?
            ''', (reason, banned_by, current_time, user_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error banning user: {e}")
            return False
    
    def unban_user(self, user_id: int) -> bool:
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
        try:
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
        except Exception as e:
            print(f"Error getting banned users: {e}")
            return []
    
    def get_user_stats(self) -> Dict:
        """Get user statistics"""
        try:
            # Total users
            self.cursor.execute('SELECT COUNT(*) FROM users')
            total_users = self.cursor.fetchone()[0] or 0
            
            # Today's users
            today = datetime.now(pytz.timezone(TIMEZONE)).date()
            self.cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(join_date) = ?', (today,))
            today_users = self.cursor.fetchone()[0] or 0
            
            # Banned users
            self.cursor.execute('SELECT COUNT(*) FROM users WHERE is_banned = TRUE')
            banned_users = self.cursor.fetchone()[0] or 0
            
            # Last backup
            self.cursor.execute('SELECT MAX(timestamp) FROM backups')
            last_backup_result = self.cursor.fetchone()[0]
            if last_backup_result:
                last_backup = datetime.strptime(
                    last_backup_result, '%Y-%m-%d %H:%M:%S'
                ).strftime('%Y-%m-%d %H:%M')
            else:
                last_backup = 'Never'
            
            return {
                'total_users': total_users,
                'today_users': today_users,
                'banned_users': banned_users,
                'last_backup': last_backup
            }
        except Exception as e:
            print(f"Error getting user stats: {e}")
            return {
                'total_users': 0,
                'today_users': 0,
                'banned_users': 0,
                'last_backup': 'Never'
            }
    
    def add_log(self, user_id: int, action: str, details: str) -> bool:
        """Add log entry"""
        try:
            self.cursor.execute('''
                INSERT INTO logs (user_id, action, details)
                VALUES (?, ?, ?)
            ''', (user_id, action, details))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error adding log: {e}")
            return False
    
    def backup_database(self) -> Optional[str]:
        """Create database backup"""
        try:
            # Create backup directory if not exists
            os.makedirs(BACKUP_DIR, exist_ok=True)
            
            # Generate backup filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(BACKUP_DIR, f'backup_{timestamp}.db')
            
            # Create backup connection
            backup_conn = sqlite3.connect(backup_file)
            
            # Backup database
            self.conn.backup(backup_conn)
            backup_conn.close()
            
            # Log backup
            file_size = os.path.getsize(backup_file)
            self.cursor.execute('''
                INSERT INTO backups (filename, size)
                VALUES (?, ?)
            ''', (backup_file, file_size))
            self.conn.commit()
            
            # Clean old backups
            self._cleanup_old_backups()
            
            print(f"Backup created: {backup_file}")
            return backup_file
            
        except Exception as e:
            print(f"Error creating backup: {e}")
            return None
    
    def _cleanup_old_backups(self):
        """Remove old backups"""
        try:
            self.cursor.execute('SELECT id, filename FROM backups ORDER BY timestamp DESC')
            backups = self.cursor.fetchall()
            
            # Keep only MAX_BACKUPS
            if len(backups) > MAX_BACKUPS:
                for backup_id, filename in backups[MAX_BACKUPS:]:
                    # Remove file
                    if os.path.exists(filename):
                        os.remove(filename)
                    
                    # Remove from database
                    self.cursor.execute('DELETE FROM backups WHERE id = ?', (backup_id,))
                
                self.conn.commit()
                print(f"Cleaned up {len(backups) - MAX_BACKUPS} old backups")
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
