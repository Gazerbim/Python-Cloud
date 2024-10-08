
# Flask Cloud Storage App

## Overview

This Flask application provides a cloud storage system where users can upload, manage, and download their files. It also includes user management with authentication and authorization, using Flask-Login and SQLAlchemy.

## Features

- **User Registration & Login**: Users can register, log in, and reset passwords.
- **File Management**: Upload, download, edit, and delete files.
- **Storage Quota**: Users have a configurable storage quota.
- **Admin User Management**: Admins can view and update user quotas.
- **Email Notifications**: Notifications and password reset links are sent via email.

## Installation

1. **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/flask-cloud-storage.git
    cd flask-cloud-storage
    ```

2. **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3. **Set up environment**:
    - Ensure you have a valid SMTP server for sending emails.
    - Configure your email credentials in the `send_email` function inside `app.py`.

4. **Initialize the database**:
    ```bash
    python -c "from app import create_db; create_db()"
    ```

5. **Run the application**:
    ```bash
    python app.py
    ```

6. **Access the application**:
    - Go to `http://localhost:15000` in your browser.

## File Structure

```
.
├── app.py               # Main Flask application
├── db.sqlite            # SQLite database
├── templates/           # HTML templates
├── static/              # Static files (CSS, JS, etc.)
├── uploads/             # Folder for user uploads
├── server.log           # Log file for server activity
├── requirements.txt     # Python dependencies
└── README.md            # This documentation file
```

## Routes

- `/` - Home page
- `/register` - Register a new account
- `/login` - Log in to an existing account
- `/upload` - Upload a file (requires login)
- `/download/<filename>` - Download a file (requires login)
- `/delete/<filename>` - Delete a file (requires login)
- `/user_management` - Admin-only route for managing users

## Usage

- **Register**: Create an account using your email.
- **Login**: Once registered, you can log in to access your personal storage.
- **Upload files**: After logging in, use the upload form to add files to your cloud storage.
- **Manage files**: Download, delete, or edit uploaded files.
- **Admin**: Admin users can view all users, update storage quotas, and manage accounts.

---

### Future Enhancements

- Implement folder management for better organization of user files.
- Enable file sharing with access permissions.
