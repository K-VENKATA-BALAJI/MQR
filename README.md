# Medquest Recruitment Application

A comprehensive recruitment management system with ATS (Applicant Tracking System) scoring, interview scheduling, and automated email notifications.

## Features

- **Application Submission**: Multi-step application form with resume upload
- **ATS Scoring**: Automated resume scoring based on job requirements
- **Interview Scheduling**: Manage phone and in-person interviews
- **Status Management**: Track application status (Pending, Selected, Rejected)
- **Email Notifications**: Automated emails for application confirmations and interview invites
- **Excel Export**: Generate comprehensive Excel reports with multiple sheets
- **Recruiter Dashboard**: Secure dashboard for recruiters to manage applications

## Tech Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript
- **Database**: SQLite
- **File Processing**: PDF extraction, Excel generation
- **Email**: SMTP integration

## Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd c4
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   - Copy `env.example` to `.env`
   - Fill in your configuration:
     ```env
     PUBLIC_BASE_URL=http://127.0.0.1:5000
     RECRUITER_API_KEY=YourVerySecretRecruiterKey12345
     EMAIL_HOST=smtp.gmail.com
     EMAIL_PORT=587
     EMAIL_HOST_USER=your-email@gmail.com
     EMAIL_HOST_PASSWORD=your-app-password
     ```

5. **Run the application**
   ```bash
   python backend.py
   ```

6. **Access the application**
   - Application form: `http://127.0.0.1:5000/consent.html`
   - Recruiter dashboard: `http://127.0.0.1:5000/recruiter_dashboard.html`
   - Recruiter schedule: `http://127.0.0.1:5000/recruiter_schedule.html`

## Project Structure

```
c4/
├── backend.py              # Flask backend server
├── requirements.txt        # Python dependencies
├── Procfile               # Deployment configuration
├── .gitignore             # Git ignore rules
├── env.example            # Environment variables template
├── DEPLOYMENT.md          # Deployment guide
├── applications.db        # SQLite database (created on first run)
├── resumes/               # Uploaded resume files
├── consent.html           # Application consent page
├── details.html           # Application details form
├── upload.html            # Resume upload page
├── thankyou.html          # Thank you page
├── recruiter_dashboard.html # Recruiter dashboard
├── recruiter_schedule.html # Interview schedule page
└── app.js                 # Frontend JavaScript
```

## API Endpoints

### Public Endpoints
- `POST /api/save_details` - Save application details
- `POST /api/submit_application/<app_id>` - Submit application with resume
- `GET /rsvp/<token>` - RSVP response handler

### Protected Endpoints (Require X-Recruiter-Key header)
- `GET /api/schedule` - Get interview schedule
- `PATCH /api/schedule/<app_id>` - Update interview status
- `GET /api/view_resume/<app_id>` - View applicant resume
- `GET /api/export_to_excel` - Export applications to Excel
- `POST /api/send_status_email/<app_id>` - Send status email

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `PUBLIC_BASE_URL` | Public URL of the application | Yes |
| `RECRUITER_API_KEY` | Secret key for recruiter endpoints | Yes |
| `EMAIL_HOST` | SMTP server hostname | Yes |
| `EMAIL_PORT` | SMTP server port | Yes |
| `EMAIL_HOST_USER` | Email account username | Yes |
| `EMAIL_HOST_PASSWORD` | Email account password/app password | Yes |
| `PORT` | Server port (default: 5000) | No |
| `FLASK_DEBUG` | Enable debug mode (default: False) | No |

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions for:
- Railway
- Render
- Heroku
- DigitalOcean
- VPS

## Features in Detail

### ATS Scoring
- Analyzes resume content against job requirements
- Scores based on keywords, experience, education
- Provides detailed breakdown and suggestions

### Interview Management
- Track phone and in-person interview statuses
- Automatic status updates:
  - "No go" in either interview → Application Status: "Rejected"
  - Both interviews "Go" → Application Status: "Selected"

### Excel Export
Generates Excel file with multiple sheets:
- All Applications
- Shortlisted
- No go
- Selected
- Rejected (Final)

## Security

- Recruiter endpoints require API key authentication
- Environment variables for sensitive data
- CORS enabled for cross-origin requests
- File upload validation

## License

[Your License Here]

## Support

For issues or questions, please refer to the deployment guide or contact the development team.

