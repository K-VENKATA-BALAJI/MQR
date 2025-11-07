# Deployment Guide

This guide will help you deploy the Medquest Recruitment Application to various platforms.

## Prerequisites

1. **Python 3.11+** installed
2. **Git** installed
3. **Environment variables** configured (see `env.example`)

## Required Environment Variables

Create a `.env` file in the project root with the following variables:

```env
PUBLIC_BASE_URL=https://your-domain.com
RECRUITER_API_KEY=your-secret-key-here
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### Gmail Setup
For Gmail, you need to:
1. Enable 2-Factor Authentication
2. Generate an "App Password" at https://myaccount.google.com/apppasswords
3. Use the app password (not your regular password) in `EMAIL_HOST_PASSWORD`

## Deployment Options

### Option 1: Railway (Recommended - Easy Setup)

1. **Sign up** at [railway.app](https://railway.app)
2. **Create a new project**
3. **Connect your GitHub repository** or deploy from local files
4. **Add environment variables** in the Railway dashboard:
   - Go to your project → Variables tab
   - Add all variables from `env.example`
5. **Deploy** - Railway will automatically detect Python and deploy

Railway will automatically:
- Install dependencies from `requirements.txt`
- Run the app using the `Procfile`
- Provide a public URL

### Option 2: Render

1. **Sign up** at [render.com](https://render.com)
2. **Create a new Web Service**
3. **Connect your GitHub repository**
4. **Configure**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn backend:app`
   - **Environment**: Python 3
5. **Add environment variables** in the Render dashboard
6. **Deploy**

### Option 3: Heroku

1. **Install Heroku CLI**: https://devcenter.heroku.com/articles/heroku-cli
2. **Login**: `heroku login`
3. **Create app**: `heroku create your-app-name`
4. **Set environment variables**:
   ```bash
   heroku config:set PUBLIC_BASE_URL=https://your-app-name.herokuapp.com
   heroku config:set RECRUITER_API_KEY=your-secret-key
   heroku config:set EMAIL_HOST=smtp.gmail.com
   heroku config:set EMAIL_PORT=587
   heroku config:set EMAIL_HOST_USER=your-email@gmail.com
   heroku config:set EMAIL_HOST_PASSWORD=your-app-password
   ```
5. **Deploy**: `git push heroku main`

### Option 4: DigitalOcean App Platform

1. **Sign up** at [digitalocean.com](https://www.digitalocean.com)
2. **Create a new App**
3. **Connect your GitHub repository**
4. **Configure**:
   - **Type**: Web Service
   - **Build Command**: `pip install -r requirements.txt`
   - **Run Command**: `gunicorn backend:app`
   - **Environment Variables**: Add all from `env.example`
5. **Deploy**

### Option 5: VPS (Ubuntu/Debian)

1. **SSH into your server**
2. **Install dependencies**:
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-venv nginx
   ```
3. **Clone repository**:
   ```bash
   git clone <your-repo-url>
   cd c4
   ```
4. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
5. **Create systemd service** (`/etc/systemd/system/medquest.service`):
   ```ini
   [Unit]
   Description=Medquest Recruitment App
   After=network.target

   [Service]
   User=www-data
   WorkingDirectory=/path/to/c4
   Environment="PATH=/path/to/c4/venv/bin"
   ExecStart=/path/to/c4/venv/bin/gunicorn --bind 0.0.0.0:5000 backend:app
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
6. **Start service**:
   ```bash
   sudo systemctl start medquest
   sudo systemctl enable medquest
   ```
7. **Configure Nginx** as reverse proxy (optional but recommended)

## Post-Deployment Steps

1. **Update frontend URLs**: 
   - Update `BASE_URL` in `recruiter_schedule.js` and `recruiter_dashboard.js` to your production URL
   - Or use environment-based configuration

2. **Test the application**:
   - Visit your deployed URL
   - Test application submission
   - Test recruiter dashboard (with API key)

3. **Set up database backups** (if using SQLite):
   - SQLite files are stored in the project directory
   - Consider migrating to PostgreSQL for production (recommended)

## Important Notes

- **Database**: The app uses SQLite by default. For production, consider PostgreSQL
- **File Storage**: Uploaded resumes are stored in the `resumes/` folder. For production, consider cloud storage (S3, etc.)
- **Security**: 
  - Never commit `.env` file to Git
  - Use strong `RECRUITER_API_KEY`
  - Enable HTTPS in production
- **Scaling**: For high traffic, consider:
  - Using a production WSGI server (Gunicorn is included)
  - Database connection pooling
  - CDN for static files

## Troubleshooting

### Application won't start
- Check environment variables are set correctly
- Verify Python version (3.11+)
- Check logs: `heroku logs --tail` (Heroku) or platform-specific logs

### Email not sending
- Verify email credentials
- Check SMTP settings
- For Gmail, ensure App Password is used (not regular password)
- Check firewall/security settings

### Database issues
- Ensure write permissions for database file
- Check disk space
- Verify database file is not corrupted

## Support

For issues, check:
1. Application logs
2. Environment variables
3. Platform-specific documentation

