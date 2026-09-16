# 📚 UniShare — Department Resource Sharing Platform

A full-stack academic resource sharing system built with **Python + Streamlit + SQLite**.

---

## Features

| Feature | Details |
|---|---|
| 🔐 Authentication | Signup / Login / Logout with bcrypt password hashing |
| 👥 Role System | Student · Teacher · Admin with role-based access |
| 📤 File Upload | PDF, DOCX, PPTX, XLSX, ZIP, images — up to 50 MB |
| 🔍 Search & Filter | By semester, course, category, keyword |
| ⭐ Favorites | Bookmark resources |
| ⭐ Ratings | 1–5 star ratings per resource |
| 💬 Comments | Per-resource discussion thread |
| 📊 Analytics | Download trends, storage usage, top resources |
| 🛡️ Admin Panel | Approve uploads, manage users, add courses/departments |
| 💡 Recommendations | Based on download history |
| 🌙 Dark Mode | Toggle in sidebar |

---

## Project Structure

```
dept_platform/
├── app.py                  # Entry point
├── platform.db             # SQLite database (auto-created)
├── requirements.txt
├── .streamlit/
│   └── config.toml         # Streamlit settings
├── uploads/                # Uploaded files (auto-created)
└── modules/
    ├── database.py         # All DB schema + queries
    ├── auth.py             # Auth helpers + login UI
    ├── file_manager.py     # Upload / download / validation
    ├── ui_components.py    # Sidebar, cards, search bar, CSS
    └── pages.py            # All page renderers
```

---

## Quick Start (Local)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
streamlit run app.py
```

The app auto-creates the database and seeds demo accounts on first run.

### Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@uni.edu | admin123 |
| Teacher | john.cse@teacher.just.edu.bd | teacher123 |
| Student | 220120.cse@student.just.edu.bd | student123 |

---

## Deploying to Streamlit Community Cloud

1. Push this folder to a **public GitHub repository**
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select your repo, branch `main`, and entry file `app.py`
4. Click **Deploy**

> **Note:** Streamlit Community Cloud has an ephemeral filesystem — uploaded files and the SQLite database will reset on each restart. For persistent storage, replace the SQLite backend with a cloud database (e.g., Supabase, PlanetScale) and use cloud object storage (e.g., S3) for files. See `modules/database.py` — all DB calls are in one place for easy swapping.

---

## Database Schema

```
users          ← id, name, email, password_hash, role, department_id, …
departments    ← id, name, code
courses        ← id, code, name, semester, department_id, teacher_id
resources      ← id, title, file_path, category, course_id, uploader_id, is_approved, …
downloads      ← id, resource_id, user_id, downloaded_at
comments       ← id, resource_id, user_id, content
ratings        ← id, resource_id, user_id, score (1–5)
favorites      ← id, resource_id, user_id
```

---

## Extending

- **Add a course**: Admin Panel → Courses tab
- **Add a department**: Admin Panel → Departments tab
- **Approve uploads**: Admin Panel → Pending Approval tab
- **Change file size limit**: Edit `MAX_FILE_SIZE_MB` in `modules/file_manager.py`
