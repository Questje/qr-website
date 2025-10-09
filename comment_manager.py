"""
Comment Manager Module
Handles loading, saving, and managing comments for songs
Stores comments with user, text, timestamp, and profile picture
"""
import json
import os
from datetime import datetime
from typing import List, Dict

class CommentManager:
    def __init__(self, comments_file: str = "comments.json"):
        """Initialize comment manager with file path"""
        self.comments_file = comments_file
        self.comments = self._load_comments()
    
    def _load_comments(self) -> Dict:
        """Load comments from JSON file"""
        if os.path.exists(self.comments_file):
            try:
                with open(self.comments_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Error loading comments: {e}")
                return {}
        return {}
    
    def _save_comments(self):
        """Save comments to JSON file"""
        try:
            with open(self.comments_file, 'w', encoding='utf-8') as f:
                json.dump(self.comments, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Error saving comments: {e}")
    
    def get_comments(self, song_title: str) -> List[Dict]:
        """Get all comments for a song"""
        # Normalize song title to lowercase for consistency
        song_key = song_title.lower().strip()
        
        if song_key in self.comments:
            return self.comments[song_key]
        return []
    
    def add_comment(self, song_title: str, user: str, text: str, profile_pic: str = None) -> bool:
        """Add a comment to a song with optional profile picture"""
        # Normalize song title to lowercase for consistency
        song_key = song_title.lower().strip()
        
        # Initialize if needed
        if song_key not in self.comments:
            self.comments[song_key] = []
        
        # Create comment object
        comment = {
            "user": user.strip(),
            "text": text.strip(),
            "timestamp": datetime.now().isoformat(),
            "profile_pic": profile_pic
        }
        
        # Add to list
        self.comments[song_key].append(comment)
        
        # Save to file
        self._save_comments()
        
        return True