#!/usr/bin/env python3
"""
MrBob Bookmark App
Email-based bookmark/resource organizer
"""

import os
import sqlite3
import json
import re
import imaplib
import email
import http.client
from datetime import datetime
from flask import Flask, request, render_template_string, jsonify

app = Flask(__name__)

DB_PATH = "/tmp/bookmarks.db"
GMAIL_EMAIL = os.environ.get("GMAIL_EMAIL", "onlineab9@gmail.com")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD", "")

def init_db():
    """Initialize SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        url TEXT,
        is_favorite INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
    )''')
    
    conn.commit()
    conn.close()

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def extract_from_url(url):
    """Extract title/meta from URL."""
    try:
        conn = http.client.HTTPSConnection("www.openrouter.ai" if "openrouter" in url else url.split('/')[2])
        headers = {'User-Agent': 'Mozilla/5.0'}
        conn.request('GET', '/', headers=headers, timeout=5)
        response = conn.getresponse()
        html = response.read().decode('utf-8', errors='ignore')
        
        # Extract title from <title> tag
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()
    except:
        pass
    return None

def check_emails():
    """Check Gmail for Save emails and process them."""
    if not GMAIL_PASSWORD:
        return 0
    
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_EMAIL, GMAIL_PASSWORD)
        mail.select("INBOX")
        
        # Search for unread emails with "Save -" in subject
        status, messages = mail.search(None, 'UNSEEN', 'SUBJECT', 'Save -')
        
        if status != 'OK':
            return 0
        
        email_ids = messages[0].split()
        processed = 0
        
        for email_id in email_ids:
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status != 'OK':
                continue
            
            msg = email.message_from_bytes(msg_data[0][1])
            subject = msg.get('Subject', '')
            
            # Parse subject: "Save - [Category]"
            match = re.match(r'Save\s*-\s*(.+)', subject, re.IGNORECASE)
            if not match:
                continue
            
            category_name = match.group(1).strip()
            body = ""
            url = None
            
            # Extract body and URL
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            
            # Extract URL from body
            url_match = re.search(r'https?://[^\s\n]+', body)
            if url_match:
                url = url_match.group(0)
            
            # Get title from URL or use first line of body
            title = None
            if url:
                title = extract_from_url(url)
            
            if not title:
                title = body.split('\n')[0][:100] if body else category_name
            
            # Save to database
            conn = get_db()
            c = conn.cursor()
            
            # Get or create category
            c.execute('SELECT id FROM categories WHERE name = ?', (category_name,))
            cat = c.fetchone()
            
            if not cat:
                c.execute('INSERT INTO categories (name) VALUES (?)', (category_name,))
                conn.commit()
                category_id = c.lastrowid
            else:
                category_id = cat['id']
            
            # Insert resource
            c.execute('''INSERT INTO resources (category_id, title, description, url)
                        VALUES (?, ?, ?, ?)''',
                     (category_id, title, body[:500], url))
            conn.commit()
            conn.close()
            
            processed += 1
            
            # Mark email as read
            mail.store(email_id, '+FLAGS', '\\Seen')
        
        mail.close()
        mail.logout()
        return processed
    
    except Exception as e:
        print(f"Email check error: {e}")
        return 0

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>MrBob Bookmark App</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f0f0f; color: #fff; }
        .container { display: flex; height: 100vh; }
        
        .sidebar { width: 250px; background: #1a1a1a; border-right: 1px solid #333; overflow-y: auto; padding: 20px; }
        .sidebar h2 { font-size: 16px; margin-bottom: 15px; color: #ff6b00; }
        .category { padding: 10px 15px; margin: 5px 0; background: #222; border-radius: 5px; cursor: pointer; }
        .category:hover { background: #333; }
        .category.active { background: #ff6b00; }
        .category-count { float: right; font-size: 12px; opacity: 0.7; }
        
        .main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
        .header { padding: 20px; background: #1a1a1a; border-bottom: 1px solid #333; }
        .header h1 { font-size: 24px; margin-bottom: 10px; }
        .filter { display: flex; gap: 10px; }
        .filter button { padding: 8px 15px; background: #333; border: none; color: #fff; border-radius: 5px; cursor: pointer; }
        .filter button.active { background: #ff6b00; }
        
        .resources { flex: 1; overflow-y: auto; padding: 20px; }
        .resource { background: #1a1a1a; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #ff6b00; }
        .resource-title { font-size: 16px; font-weight: bold; margin-bottom: 5px; }
        .resource-url { font-size: 12px; color: #888; margin-bottom: 10px; }
        .resource-desc { font-size: 14px; color: #ccc; margin-bottom: 10px; line-height: 1.4; }
        .resource-actions { display: flex; gap: 10px; }
        .resource-actions button { padding: 6px 12px; font-size: 12px; background: #333; border: none; color: #fff; border-radius: 3px; cursor: pointer; flex: 1; }
        .resource-actions button:hover { background: #444; }
        .resource-actions button.fav { background: #ff6b00; }
        .resource-actions button.delete { background: #d32f2f; }
        
        .empty { text-align: center; color: #666; padding: 40px 20px; }
        
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 1000; }
        .modal.active { display: flex; align-items: center; justify-content: center; }
        .modal-content { background: #1a1a1a; padding: 30px; border-radius: 8px; width: 90%; max-width: 500px; }
        .modal-content h2 { margin-bottom: 20px; }
        .modal-content input, .modal-content textarea { width: 100%; padding: 10px; margin: 10px 0; background: #222; border: 1px solid #333; color: #fff; border-radius: 5px; }
        .modal-content button { padding: 10px 20px; margin: 20px 10px 0 0; background: #ff6b00; border: none; color: #fff; border-radius: 5px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <h2>📚 Categories</h2>
            <div class="category active" onclick="loadCategory('all')">All Resources</div>
            <div class="category" onclick="loadCategory('favorites')">⭐ Favorites</div>
            <div id="categoryList"></div>
        </div>
        
        <div class="main">
            <div class="header">
                <h1>MrBob Bookmarks</h1>
                <div class="filter">
                    <button class="active" onclick="sortBy('recent')">Recent</button>
                    <button onclick="sortBy('title')">Title</button>
                </div>
            </div>
            
            <div class="resources" id="resourceList"></div>
        </div>
    </div>
    
    <div class="modal" id="editModal">
        <div class="modal-content">
            <h2>Edit Resource</h2>
            <input type="text" id="editTitle" placeholder="Title">
            <textarea id="editDesc" placeholder="Description" rows="4"></textarea>
            <input type="text" id="editUrl" placeholder="URL">
            <button onclick="saveEdit()">Save</button>
            <button onclick="closeModal()" style="background: #666;">Cancel</button>
        </div>
    </div>
    
    <script>
        let currentCategory = 'all';
        let editingId = null;
        
        async function loadCategory(cat) {
            currentCategory = cat;
            document.querySelectorAll('.category').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            loadResources();
        }
        
        async function loadResources() {
            const res = await fetch(`/api/resources?category=${currentCategory}`);
            const data = await res.json();
            const html = data.length ? data.map(r => `
                <div class="resource">
                    <div class="resource-title">${r.title}</div>
                    ${r.url ? `<a href="${r.url}" target="_blank" class="resource-url">${r.url}</a>` : ''}
                    <div class="resource-desc">${r.description || ''}</div>
                    <div class="resource-actions">
                        <button class="fav" onclick="toggleFav(${r.id}, ${r.is_favorite})">${r.is_favorite ? '⭐' : '☆'}</button>
                        <button onclick="editResource(${r.id}, '${r.title}', '${r.description || ''}', '${r.url || ''}')">✏️ Edit</button>
                        <button class="delete" onclick="deleteResource(${r.id})">🗑️ Delete</button>
                    </div>
                </div>
            `).join('') : '<div class="empty">No resources yet</div>';
            
            document.getElementById('resourceList').innerHTML = html;
        }
        
        async function toggleFav(id, isFav) {
            await fetch(`/api/resources/${id}`, {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({is_favorite: 1 - isFav})
            });
            loadResources();
        }
        
        function editResource(id, title, desc, url) {
            editingId = id;
            document.getElementById('editTitle').value = title;
            document.getElementById('editDesc').value = desc;
            document.getElementById('editUrl').value = url;
            document.getElementById('editModal').classList.add('active');
        }
        
        async function saveEdit() {
            await fetch(`/api/resources/${editingId}`, {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    title: document.getElementById('editTitle').value,
                    description: document.getElementById('editDesc').value,
                    url: document.getElementById('editUrl').value
                })
            });
            closeModal();
            loadResources();
        }
        
        function closeModal() {
            document.getElementById('editModal').classList.remove('active');
        }
        
        async function deleteResource(id) {
            if(confirm('Delete this resource?')) {
                await fetch(`/api/resources/${id}`, {method: 'DELETE'});
                loadResources();
            }
        }
        
        function sortBy(type) {
            event.target.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
        }
        
        // Load categories and resources on startup
        async function init() {
            const res = await fetch('/api/categories');
            const cats = await res.json();
            const html = cats.map(c => `<div class="category" onclick="loadCategory('${c.name}')">${c.name} (${c.count})</div>`).join('');
            document.getElementById('categoryList').innerHTML = html;
            loadResources();
        }
        
        init();
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML)

@app.route('/api/categories')
def get_categories():
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT categories.id, categories.name, COUNT(resources.id) as count
                 FROM categories LEFT JOIN resources ON categories.id = resources.category_id
                 GROUP BY categories.id ORDER BY categories.name''')
    categories = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(categories)

@app.route('/api/resources')
def get_resources():
    category = request.args.get('category', 'all')
    conn = get_db()
    c = conn.cursor()
    
    if category == 'all':
        c.execute('SELECT * FROM resources ORDER BY created_at DESC')
    elif category == 'favorites':
        c.execute('SELECT * FROM resources WHERE is_favorite = 1 ORDER BY created_at DESC')
    else:
        c.execute('''SELECT resources.* FROM resources 
                     JOIN categories ON resources.category_id = categories.id
                     WHERE categories.name = ? ORDER BY resources.created_at DESC''', (category,))
    
    resources = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(resources)

@app.route('/api/resources/<int:rid>', methods=['PATCH'])
def update_resource(rid):
    data = request.json
    conn = get_db()
    c = conn.cursor()
    
    if 'is_favorite' in data:
        c.execute('UPDATE resources SET is_favorite = ? WHERE id = ?', (data['is_favorite'], rid))
    if 'title' in data:
        c.execute('UPDATE resources SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (data['title'], rid))
    if 'description' in data:
        c.execute('UPDATE resources SET description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (data['description'], rid))
    if 'url' in data:
        c.execute('UPDATE resources SET url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (data['url'], rid))
    
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route('/api/resources/<int:rid>', methods=['DELETE'])
def delete_resource(rid):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM resources WHERE id = ?', (rid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route('/api/check-emails', methods=['POST'])
def check_emails_route():
    count = check_emails()
    return jsonify({"processed": count})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)