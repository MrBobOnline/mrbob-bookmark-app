# MrBob Bookmark App

Email-based bookmark/resource organizer. Send emails to organize and bookmark resources!

## Features

- 📧 **Email to Bookmark:** Send email to `onlineab9@gmail.com` with subject `Save - [Category]`
- 📚 **Categories:** Auto-create from email subject
- ⭐ **Favorites:** Mark resources as favorites
- ✏️ **Inline Edit:** Edit title, description, and URL directly
- 🗑️ **Delete:** Remove bookmarks
- 🔍 **Search:** Filter by category or favorites

## How It Works

1. Send an email to `onlineab9@gmail.com` with subject: `Save - YourCategory`
2. Include a link in the email body
3. The app extracts the title from the link and saves it under `YourCategory`
4. Access the web UI to view, edit, favorite, and organize bookmarks

## Environment Variables

- `GMAIL_EMAIL`: Gmail address (default: onlineab9@gmail.com)
- `GMAIL_PASSWORD`: Gmail app password for IMAP access

## Deployment

### Local Development
```bash
pip install -r requirements.txt
python app.py
```

Visit `http://localhost:5000`

### Vercel Deployment
1. Connect GitHub repo to Vercel
2. Add environment variables:
   - `GMAIL_EMAIL`
   - `GMAIL_PASSWORD`
3. Deploy!

## Database

Uses SQLite with two tables:
- **categories:** Category names
- **resources:** Bookmarks with title, description, URL, favorite flag

## Cron Jobs

Email polling runs once daily (configure in Vercel Cron or external service).

Endpoint: `POST /api/check-emails`

## Tech Stack

- Flask (Python)
- SQLite
- Vanilla JavaScript
- Vercel (hosting)
