-- SQL code to create the comments table for Questje's ReQuestje's
-- Run this in your MariaDB database to create the required table

CREATE TABLE IF NOT EXISTS comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    song_title VARCHAR(500) NOT NULL,
    user_name VARCHAR(100) NOT NULL,
    comment_text VARCHAR(200) NOT NULL,
    profile_pic VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Create indexes for faster queries
    INDEX idx_song_title (song_title),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create likes table
CREATE TABLE IF NOT EXISTS comment_likes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    comment_id INT NOT NULL,
    user_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure one like per user per comment
    UNIQUE KEY unique_user_comment (comment_id, user_name),
    
    -- Foreign key reference
    FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE,
    
    -- Index for faster queries
    INDEX idx_comment_id (comment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Optional: Add some sample data for testing
-- INSERT INTO comments (song_title, user_name, comment_text, profile_pic) VALUES
-- ('test song', 'TestUser', 'This is a test comment!', 'https://example.com/profile.jpg');
