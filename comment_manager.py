#!/usr/bin/env python3
# -*- coding: utf-8 -*- 

"""
Comment Manager Module
Handles loading, saving, and managing comments for songs
Stores comments in MariaDB database with user, text, timestamp, and profile picture
"""
import pymysql
import os
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv
import urllib.parse

# Load environment variables
load_dotenv()

# MariaDB Database Configuration Constants
# You can use either a JDBC-style URL or individual components
DB_URL = os.getenv('DB_URL', 'jdbc:mariadb://localhost:3306/questje_charts')
DB_USER = os.getenv('DB_USER', 'questje_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'your_password')
DB_TABLE = os.getenv('DB_TABLE', 'comments')

def parse_db_url(url: str) -> Dict[str, str]:
    """Parse JDBC-style MariaDB URL into connection components"""
    # Remove jdbc: prefix if present
    if url.startswith('jdbc:'):
        url = url[5:]
    
    # Parse the URL
    parsed = urllib.parse.urlparse(url)
    
    return {
        'host': parsed.hostname,
        'port': parsed.port or 3306,
        'database': parsed.path.lstrip('/'),
        'scheme': parsed.scheme
    }

class CommentManager:
    def __init__(self):
        """Initialize comment manager with database connection"""
        self.connection = None
        self._init_connection()
    
    def _init_connection(self):
        """Initialize database connection"""
        try:
            # Parse database URL
            db_info = parse_db_url(DB_URL)
            
            self.connection = pymysql.connect(
                host=db_info['host'],
                port=int(db_info['port']),
                database=db_info['database'],
                user=DB_USER,
                password=DB_PASSWORD,
                charset='utf8mb4',
                autocommit=False
            )
            print("✅ Connected to MariaDB database")
        except Exception as e:
            print(f"⚠️  Error connecting to database: {e}")
            self.connection = None
    
    def _execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute a database query and return results"""
        if not self.connection:
            print("❌ No database connection available")
            return []
        
        try:
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(query, params)
                
                # If it's a SELECT query, fetch results
                if query.strip().upper().startswith('SELECT'):
                    return cursor.fetchall()
                else:
                    # For INSERT/UPDATE/DELETE, commit the transaction
                    self.connection.commit()
                    return []
                    
        except Exception as e:
            print(f"⚠️  Database query error: {e}")
            if self.connection:
                self.connection.rollback()
            return []
    
    def get_comments(self, song_title: str) -> List[Dict]:
        """Get all comments for a song"""
        # Normalize song title to lowercase for consistency
        song_key = song_title.lower().strip()
        
        query = f"""
        SELECT c.id, c.user_name, c.comment_text, c.created_at as timestamp, c.profile_pic,
               COUNT(cl.id) as like_count
        FROM {DB_TABLE} c
        LEFT JOIN comment_likes cl ON c.id = cl.comment_id
        WHERE LOWER(c.song_title) = %s
        GROUP BY c.id, c.user_name, c.comment_text, c.created_at, c.profile_pic
        ORDER BY c.created_at DESC
        """
        
        results = self._execute_query(query, (song_key,))
        
        # Get likes for each comment
        for result in results:
            likes_query = """
            SELECT user_name FROM comment_likes WHERE comment_id = %s
            """
            likes_results = self._execute_query(likes_query, (result['id'],))
            result['liked_by'] = [like['user_name'] for like in likes_results]
        
        # Convert datetime objects to ISO format strings for JSON serialization
        for result in results:
            if 'timestamp' in result and result['timestamp']:
                result['timestamp'] = result['timestamp'].isoformat()
            # Rename fields to match the old JSON format
            result['user'] = result.pop('user_name', result.get('user_name', ''))
            result['text'] = result.pop('comment_text', result.get('comment_text', ''))
        
        return results
    
    def add_comment(self, song_title: str, user: str, text: str, profile_pic: str = None) -> bool:
        """Add a comment to a song with optional profile picture"""
        # Normalize song title to lowercase for consistency
        song_key = song_title.lower().strip()
        
        # Limit text to 200 characters and sanitize
        text = text.strip()[:200]
        
        query = f"""
        INSERT INTO {DB_TABLE} (song_title, user_name, comment_text, profile_pic, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        
        params = (
            song_key,
            user.strip(),
            text,
            profile_pic,
            datetime.now()
        )
        
        try:
            self._execute_query(query, params)
            print(f"✅ Comment added for song '{song_title}' by user '{user}'")
            return True
        except Exception as e:
            print(f"❌ Failed to add comment: {e}")
            return False
    
    def update_comment(self, comment_id: int, new_text: str, user: str, is_admin: bool = False) -> bool:
        """Update a comment if user owns it or is admin"""
        # First check if comment exists and get owner
        check_query = f"""
        SELECT user_name FROM {DB_TABLE} WHERE id = %s
        """
        
        results = self._execute_query(check_query, (comment_id,))
        if not results:
            print(f"❌ Comment {comment_id} not found")
            return False
        
        comment_owner = results[0]['user_name']
        
        # Check permissions
        if not is_admin and user != comment_owner:
            print(f"❌ User {user} not authorized to edit comment {comment_id}")
            return False
        
        # Limit text to 200 characters and sanitize
        new_text = new_text.strip()[:200]
        
        # Update comment
        update_query = f"""
        UPDATE {DB_TABLE} 
        SET comment_text = %s 
        WHERE id = %s
        """
        
        try:
            self._execute_query(update_query, (new_text, comment_id))
            print(f"✅ Comment {comment_id} updated by user '{user}'")
            return True
        except Exception as e:
            print(f"❌ Failed to update comment {comment_id}: {e}")
            return False
    
    def delete_comment(self, comment_id: int, user: str, is_admin: bool = False) -> bool:
        """Delete a comment if user owns it or is admin"""
        # First check if comment exists and get owner
        check_query = f"""
        SELECT user_name FROM {DB_TABLE} WHERE id = %s
        """
        
        results = self._execute_query(check_query, (comment_id,))
        if not results:
            print(f"❌ Comment {comment_id} not found")
            return False
        
        comment_owner = results[0]['user_name']
        
        # Check permissions
        if not is_admin and user != comment_owner:
            print(f"❌ User {user} not authorized to delete comment {comment_id}")
            return False
        
        # Delete comment
        delete_query = f"""
        DELETE FROM {DB_TABLE} WHERE id = %s
        """
        
        try:
            self._execute_query(delete_query, (comment_id,))
            print(f"✅ Comment {comment_id} deleted by user '{user}'")
            return True
        except Exception as e:
            print(f"❌ Failed to delete comment {comment_id}: {e}")
            return False
    
    def toggle_like(self, comment_id: int, user: str) -> bool:
        """Toggle like for a comment (like if not liked, unlike if already liked)"""
        # Check if user already liked this comment
        check_query = """
        SELECT id FROM comment_likes WHERE comment_id = %s AND user_name = %s
        """
        
        results = self._execute_query(check_query, (comment_id, user))
        
        if results:
            # Unlike - remove the like
            delete_query = """
            DELETE FROM comment_likes WHERE comment_id = %s AND user_name = %s
            """
            try:
                self._execute_query(delete_query, (comment_id, user))
                print(f"✅ User '{user}' unliked comment {comment_id}")
                return True
            except Exception as e:
                print(f"❌ Failed to unlike comment {comment_id}: {e}")
                return False
        else:
            # Like - add the like
            insert_query = """
            INSERT INTO comment_likes (comment_id, user_name, created_at)
            VALUES (%s, %s, %s)
            """
            try:
                self._execute_query(insert_query, (comment_id, user, datetime.now()))
                print(f"✅ User '{user}' liked comment {comment_id}")
                return True
            except Exception as e:
                print(f"❌ Failed to like comment {comment_id}: {e}")
                return False
    
    def close_connection(self):
        """Close the database connection"""
        if self.connection:
            self.connection.close()
            print("🔌 Database connection closed")
