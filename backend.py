import os
import json
import smtplib
import socket
import sqlite3
import random 
import re
from email.mime.text import MIMEText
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS, cross_origin
from dotenv import load_dotenv
import pandas as pd
import io

# PDF extraction libraries
PDF_EXTRACTION_AVAILABLE = False
PDF_LIBRARY = None
try:
    import pdfplumber
    PDF_EXTRACTION_AVAILABLE = True
    PDF_LIBRARY = 'pdfplumber'
except ImportError:
    try:
        import PyPDF2
        PDF_EXTRACTION_AVAILABLE = True
        PDF_LIBRARY = 'PyPDF2'
    except ImportError:
        PDF_EXTRACTION_AVAILABLE = False
        PDF_LIBRARY = None
        print("WARNING: No PDF extraction library found. Install pdfplumber or PyPDF2 for resume highlighting.")
        print("Install with: pip install pdfplumber") 

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
# Initialize CORS globally
CORS(app) 

# Serve HTML pages
@app.route('/')
def root():
    return send_file('consent.html')

@app.route('/consent.html')
def consent_page():
    return send_file('consent.html')

@app.route('/details.html')
def details_page():
    return send_file('details.html')

@app.route('/upload.html')
def upload_page():
    return send_file('upload.html')

@app.route('/thankyou.html')
def thankyou_page():
    return send_file('thankyou.html')

@app.route('/recruiter_dashboard.html')
def recruiter_dashboard_page():
    return send_file('recruiter_dashboard.html')

@app.route('/recruiter_schedule.html')
def recruiter_schedule_page():
    return send_file('recruiter_schedule.html')

@app.route('/resume_viewer.html')
def resume_viewer_page():
    return send_file('resume_viewer.html')

# --- CONFIGURATION ---
UPLOAD_FOLDER = 'resumes'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg'}
DATABASE = 'applications.db'
EXCEL_FILE = 'All_Applications_Export.xlsx' 
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'http://127.0.0.1:5000')

# NEW: Load Recruiter Authentication Key
RECRUITER_KEY = os.getenv("RECRUITER_API_KEY") 
if not RECRUITER_KEY:
    print("WARNING: RECRUITER_API_KEY is not set in .env. Recruiter endpoint will be unsecured or disabled.")


# --- DATABASE UTILITIES ---

def init_db():
    """Initializes the SQLite database structure."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            app_id TEXT PRIMARY KEY,
            job_title TEXT NOT NULL,
            applicant_data TEXT NOT NULL
        )
    ''')
    # New table to track interview invites/schedule
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invites (
            app_id TEXT PRIMARY KEY,
            recruiter TEXT,
            interviewer TEXT,
            job_title TEXT,
            source TEXT,
            resume_status TEXT,
            phone_status TEXT,
            inperson_status TEXT,
            invited_at TEXT,
            application_status TEXT
        )
    ''')
    # Best-effort migration to add application_status if missing
    try:
        cursor.execute("ALTER TABLE invites ADD COLUMN application_status TEXT")
    except Exception:
        pass
    # Add RSVP columns if missing
    try:
        cursor.execute("ALTER TABLE invites ADD COLUMN rsvp_token TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE invites ADD COLUMN rsvp_status TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE invites ADD COLUMN rsvp_response_at TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()
    print(f"Database initialized: {DATABASE}")

def get_db_connection():
    """Returns a connection object to the database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row 
    return conn

# Initialize the database on startup
with app.app_context():
    init_db()

# --- EMAIL AND DATA PROCESSING UTILITIES ---

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_confirmation_email(recipient_email, applicant_name, job_title, app_id):
    """Sends a confirmation email to the applicant."""
    sender_email = os.getenv("EMAIL_HOST_USER")
    sender_password = os.getenv("EMAIL_HOST_PASSWORD")
    smtp_host = os.getenv("EMAIL_HOST")
    smtp_port = int(os.getenv("EMAIL_PORT", 587))

    # Fast-fail if SMTP creds are not configured in the environment
    if not smtp_host or not sender_email or not sender_password:
        print("Email disabled or SMTP credentials missing; skipping confirmation email.")
        return False

    subject = f"Medquest Application Confirmed: {job_title} - {applicant_name}"
    body = f"""
    Dear {applicant_name},

    Thank you for applying for the {job_title} position at Medquest.

    Your application has been successfully received and assigned the ID: {app_id}.

    We will review your details and resume, and you should hear from our HR team within the next 2-4 weeks.

    Sincerely,
    The Medquest Careers Team
    """

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email

    try:
        # Ensure we don't block the worker forever
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print(f"Confirmation email sent to {recipient_email}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
        
def send_interview_invite(recipient_email, applicant_name, job_title):
    """Sends an interview invitation email to the applicant."""
    sender_email = os.getenv("EMAIL_HOST_USER")
    sender_password = os.getenv("EMAIL_HOST_PASSWORD")
    smtp_host = os.getenv("EMAIL_HOST")
    smtp_port = int(os.getenv("EMAIL_PORT", 587))

    if not smtp_host or not sender_email or not sender_password:
        print("Email disabled or SMTP credentials missing; skipping invite email.")
        return False

    subject = f"Your Resume is Shortlisted: Interview Invitation for {job_title}"
    body = f"""
    Dear {applicant_name},

    We are pleased to inform you that your resume for the {job_title} position has been shortlisted for the next stage.

    You will be having an interview call with our HR team within the next week. Please keep your phone lines open.

    We look forward to speaking with you.

    Sincerely,
    The Medquest Careers Team
    """

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print(f"Interview invite sent to {recipient_email} for {job_title}")
        return True
    except Exception as e:
        print(f"Error sending invite email to {recipient_email}: {e}")
        return False

def send_status_email(recipient_email, applicant_name, job_title, app_id, process_status, interview_date, interview_time, additional_notes=None, rsvp_token=None):
    """Sends a status email to the applicant with interview details and confirmation request."""
    sender_email = os.getenv("EMAIL_HOST_USER")
    sender_password = os.getenv("EMAIL_HOST_PASSWORD")
    smtp_host = os.getenv("EMAIL_HOST")
    smtp_port = int(os.getenv("EMAIL_PORT", 587))

    if not smtp_host or not sender_email or not sender_password:
        print("Email disabled or SMTP credentials missing; skipping status email.")
        return False
    
    # Format date and time
    from datetime import datetime
    try:
        date_obj = datetime.strptime(interview_date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%B %d, %Y")
        time_obj = datetime.strptime(interview_time, "%H:%M")
        formatted_time = time_obj.strftime("%I:%M %p")
    except:
        formatted_date = interview_date
        formatted_time = interview_time

    subject = f"Application Update - {job_title} - {app_id}"
    
    body = f"""
Dear {applicant_name},

Thank you for your interest in the {job_title} position at Medquest.

{process_status}

Interview Details:
- Date: {formatted_date}
- Time: {formatted_time}

Please confirm your availability for the scheduled interview by choosing one of the options below:

Accept: {PUBLIC_BASE_URL}/rsvp/{rsvp_token or 'TOKEN'}?response=accept
Decline: {PUBLIC_BASE_URL}/rsvp/{rsvp_token or 'TOKEN'}?response=decline
Suggest another time: You can reply to this email with preferred slots.

{additional_notes if additional_notes else ''}

We look forward to hearing from you and potentially welcoming you to our team.

Best regards,
The Medquest Careers Team
    """

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Reply-To'] = sender_email  # Enable reply functionality

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        print(f"Status email sent to {recipient_email} for {job_title} - {app_id}")
        return True
    except Exception as e:
        print(f"Error sending status email to {recipient_email}: {e}")
        return False

def flatten_application_data(data, app_id):
    """
    Flattens the nested application data dictionary into a single-level dictionary
    for use in a DataFrame row.
    """
    flat_data = {'App_ID': app_id, 'Job_Title': data.get('jobTitle', 'N/A')}

    # 1. Flatten main sections
    for section_name in ['personal', 'communication', 'financial', 'onboarding']:
        for key, value in data.get(section_name, {}).items():
            flat_data[f"{section_name.capitalize()}_{key.capitalize()}"] = value

    # 2. Handle Education (Complex nested array)
    education_list = data.get('education', [])
    if isinstance(education_list, list) and education_list:
        edu_summary = []
        for i, entry in enumerate(education_list, 1):
            summary = (
                f"[{i}] Degree: {entry.get('degree', 'N/A')}, "
                f"Branch: {entry.get('branch', 'N/A')}, " 
                f"Institution: {entry.get('institution', 'N/A')}, "
                f"Grade: {entry.get('grade', 'N/A')}"
            )
            edu_summary.append(summary)
        flat_data['Education_Summary'] = "\n---\n".join(edu_summary)
    else:
        flat_data['Education_Summary'] = data.get('education', {}).get('status', 'N/A')


    # 3. Handle Work Experience (Complex nested array)
    work_list = data.get('work', [])
    if isinstance(work_list, list) and work_list:
        work_summary = []
        for i, entry in enumerate(work_list, 1):
            summary = (
                f"[{i}] Title: {entry.get('title', 'N/A')}, "
                f"Company: {entry.get('company', 'N/A')}, "
                f"Dates: {entry.get('startDate', 'N/A')} to {entry.get('endDate', 'Present')}"
            )
            work_summary.append(summary)
        flat_data['Work_Experience_Summary'] = "\n---\n".join(work_summary)
    else:
        flat_data['Work_Experience_Summary'] = data.get('work', {}).get('status', 'Skipped (Fresher)')

    return flat_data

# NEW: ATS Simulation Function with Detailed Breakdown
def simulate_ats_scoring(job_title, job_description, applicant_data=None, resume_file_path=None, resume_filename=None, return_details=False):
    """
    Multi-factor heuristic ATS score (0-100):
    - Seniority/role alignment
    - Keyword overlap between job description and candidate signals (work titles, education fields)
    - Work experience count
    - Education relevance to role family
    - Resume type bonus (pdf preferred)
    
    If return_details=True, returns dict with score breakdown and suggestions.
    Otherwise returns just the score.
    """
    import re

    normalized_title = (job_title or "").lower()
    normalized_desc = (job_description or "").lower()
    data = applicant_data or {}

    # Tokenize description (simple) and retain likely skill words
    tokens = set(re.findall(r"[a-zA-Z][a-zA-Z+.#/-]{1,}", normalized_desc))
    stop = {"and","or","the","to","for","of","in","with","a","an","on","is","are","will","be","our","your","we","you"}
    tokens = {t for t in tokens if t not in stop and len(t) >= 2}

    # Canonical skill keywords
    skill_keywords = {
        "react","redux","typescript","javascript","node","express","rest","api","microservices",
        "postgres","postgresql","mysql","mongodb","sql","nosql",
        "aws","azure","gcp","docker","kubernetes","ci","cd","testing","jest","pytest",
        "python","pandas","numpy","scikit-learn","sklearn","ml","machine","learning","data",
        "figma","sketch","ui","ux","design","wireframes","prototyping"
    }
    target_skills = tokens & skill_keywords

    # Candidate signals from application data
    candidate_terms = []
    work_titles = []
    work_companies = []
    education_degrees = []
    education_branches = []
    
    # Work titles and companies
    if isinstance(data.get('work'), list):
        for w in data['work']:
            title = str(w.get('title',''))
            company = str(w.get('company',''))
            work_titles.append(title)
            work_companies.append(company)
            candidate_terms.extend([title, company])
    
    # Education degrees/branches
    if isinstance(data.get('education'), list):
        for e in data['education']:
            degree = str(e.get('degree',''))
            branch = str(e.get('branch',''))
            institution = str(e.get('institution',''))
            education_degrees.append(degree)
            education_branches.append(branch)
            candidate_terms.extend([degree, branch, institution])

    candidate_blob = " ".join(candidate_terms).lower()
    candidate_tokens = set(re.findall(r"[a-zA-Z][a-zA-Z+.#/-]{1,}", candidate_blob))

    # Base score by role seniority/family
    base_score = 30
    seniority_bonus = 0
    role_family_bonus = 0
    
    if any(k in normalized_title for k in ["senior","lead","principal","manager"]):
        seniority_bonus = 15
    if any(k in normalized_title for k in ["engineer","developer","scientist","designer","product","marketing"]):
        role_family_bonus = 5
    
    score = base_score + seniority_bonus + role_family_bonus

    # Keyword overlap (heavier weight if found in candidate signals)
    overlap = target_skills & candidate_tokens
    keyword_score = min(len(overlap) * 4, 40)
    score += keyword_score

    # Work experience bonus (count entries)
    work_entries = data.get('work', [])
    work_experience_score = 0
    if isinstance(work_entries, list):
        work_experience_score = min(len(work_entries) * 3, 15)
    elif isinstance(work_entries, dict) and work_entries.get('status') == 'Skipped':
        work_experience_score = 0
    score += work_experience_score

    # Education relevance bonus: match role family vs branch/degree
    edu_bonus = 0
    edu_blob = " ".join(candidate_terms).lower()
    if any(k in normalized_title for k in ["frontend","ui","ux","designer","react","typescript","javascript"]):
        if any(k in edu_blob for k in ["computer","cs","information","it","design","ui","ux"]):
            edu_bonus = 8
    elif any(k in normalized_title for k in ["backend","node","engineer","data","scientist"]):
        if any(k in edu_blob for k in ["computer","cs","information","it","math","statistics","data"]):
            edu_bonus = 8
    elif any(k in normalized_title for k in ["product","marketing"]):
        if any(k in edu_blob for k in ["mba","business","marketing","management"]):
            edu_bonus = 8
    score += edu_bonus

    # Resume type bonus
    resume_type_score = 0
    fname = (resume_filename or (os.path.basename(resume_file_path) if resume_file_path else "")).lower()
    if fname.endswith('.pdf'):
        resume_type_score = 4
    elif fname.endswith(('.jpg', '.jpeg')):
        resume_type_score = 0

    score += resume_type_score

    # Clamp and small jitter
    score_before_jitter = max(0, min(score, 98))
    jitter = random.randint(-2, 2)
    final_score = max(0, min(score_before_jitter + jitter, 100))

    if not return_details:
        return final_score

    # Generate suggestions for improvement
    suggestions = []
    missing_keywords = target_skills - candidate_tokens
    
    if missing_keywords:
        suggestions.append(f"Add missing keywords: {', '.join(sorted(list(missing_keywords))[:10])}")
    
    if work_experience_score < 15:
        suggestions.append(f"Add more work experience entries (currently {len(work_entries) if isinstance(work_entries, list) else 0} entries)")
    
    if edu_bonus == 0:
        suggestions.append("Ensure education background matches the role requirements")
    
    if resume_type_score == 0:
        suggestions.append("Use PDF format for better compatibility")
    
    if final_score < 60:
        suggestions.append("Consider highlighting more relevant skills and experience in your resume")

    return {
        'score': final_score,
        'breakdown': {
            'base_score': base_score,
            'seniority_bonus': seniority_bonus,
            'role_family_bonus': role_family_bonus,
            'keyword_match_score': keyword_score,
            'work_experience_score': work_experience_score,
            'education_relevance_score': edu_bonus,
            'resume_type_score': resume_type_score,
            'jitter': jitter
        },
        'matched_keywords': sorted(list(overlap)),
        'missing_keywords': sorted(list(missing_keywords)),
        'target_keywords': sorted(list(target_skills)),
        'candidate_keywords': sorted(list(candidate_tokens & skill_keywords)),
        'suggestions': suggestions,
        'work_experience_count': len(work_entries) if isinstance(work_entries, list) else 0,
        'education_count': len(data.get('education', [])) if isinstance(data.get('education'), list) else 0
    }


# --- PDF EXTRACTION AND HIGHLIGHTING UTILITIES ---

def extract_text_from_pdf(file_path):
    """
    Extracts text from PDF file using available library.
    Returns extracted text or None if extraction fails.
    """
    if not PDF_EXTRACTION_AVAILABLE:
        return None
    
    try:
        if PDF_LIBRARY == 'pdfplumber':
            # Using pdfplumber (better for text extraction)
            with pdfplumber.open(file_path) as pdf:
                text_parts = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                return "\n\n".join(text_parts)
        elif PDF_LIBRARY == 'PyPDF2':
            # Using PyPDF2 (fallback)
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text_parts = []
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                return "\n\n".join(text_parts)
    except Exception as e:
        print(f"Error extracting text from PDF {file_path}: {e}")
        return None

def find_highlighted_sections(resume_text, job_title, job_description, applicant_data):
    """
    Analyzes resume text and identifies sections that contributed to ATS score.
    Returns a dictionary with highlighted keywords, skills, experience, and education sections.
    """
    if not resume_text:
        return {
            'skills': [],
            'experience': [],
            'education': [],
            'keywords': [],
            'error': 'Could not extract text from resume'
        }
    
    import re
    
    normalized_text = resume_text.lower()
    normalized_title = (job_title or "").lower()
    normalized_desc = (job_description or "").lower()
    data = applicant_data or {}
    
    # Get target keywords from job description (same logic as ATS scoring)
    tokens = set(re.findall(r"[a-zA-Z][a-zA-Z+.#/-]{1,}", normalized_desc))
    stop = {"and","or","the","to","for","of","in","with","a","an","on","is","are","will","be","our","your","we","you"}
    tokens = {t for t in tokens if t not in stop and len(t) >= 2}
    
    skill_keywords = {
        "react","redux","typescript","javascript","node","express","rest","api","microservices",
        "postgres","postgresql","mysql","mongodb","sql","nosql",
        "aws","azure","gcp","docker","kubernetes","ci","cd","testing","jest","pytest",
        "python","pandas","numpy","scikit-learn","sklearn","ml","machine","learning","data",
        "figma","sketch","ui","ux","design","wireframes","prototyping"
    }
    target_skills = tokens & skill_keywords
    
    # Find matched keywords in resume text
    found_keywords = []
    keyword_contexts = []
    
    for keyword in target_skills:
        # Use case-insensitive search with word boundaries
        pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
        matches = pattern.finditer(resume_text)
        for match in matches:
            found_keywords.append(keyword)
            # Extract context (50 chars before and after)
            start = max(0, match.start() - 50)
            end = min(len(resume_text), match.end() + 50)
            context = resume_text[start:end].replace('\n', ' ')
            keyword_contexts.append({
                'keyword': keyword,
                'context': context,
                'position': match.start()
            })
            break  # Only record first occurrence
    
    # Identify Skills Section
    skills_section = []
    skills_patterns = [
        r'skills?\s*[:]?\s*\n(.+?)(?=\n\n|\n[A-Z]|\n[0-9]|$)',
        r'technical\s+skills?\s*[:]?\s*\n(.+?)(?=\n\n|\n[A-Z]|$)',
        r'core\s+skills?\s*[:]?\s*\n(.+?)(?=\n\n|\n[A-Z]|$)',
        r'technologies?\s*[:]?\s*\n(.+?)(?=\n\n|\n[A-Z]|$)',
    ]
    
    for pattern in skills_patterns:
        match = re.search(pattern, resume_text, re.IGNORECASE | re.DOTALL)
        if match:
            skills_text = match.group(1)
            # Highlight keywords found in skills section
            highlighted_skills = []
            for keyword in found_keywords:
                if keyword.lower() in skills_text.lower():
                    highlighted_skills.append(keyword)
            if highlighted_skills:
                skills_section.append({
                    'section': skills_text[:200] + ('...' if len(skills_text) > 200 else ''),
                    'highlighted_keywords': highlighted_skills
                })
            break
    
    # Identify Experience Section
    experience_section = []
    experience_patterns = [
        r'experience\s*[:]?\s*\n(.+?)(?=\n\n[A-Z][a-z]+\s*[:]?|\n\nEducation|\n\nSkills|$)',
        r'work\s+experience\s*[:]?\s*\n(.+?)(?=\n\n[A-Z][a-z]+\s*[:]?|\n\nEducation|\n\nSkills|$)',
        r'professional\s+experience\s*[:]?\s*\n(.+?)(?=\n\n[A-Z][a-z]+\s*[:]?|\n\nEducation|\n\nSkills|$)',
    ]
    
    for pattern in experience_patterns:
        match = re.search(pattern, resume_text, re.IGNORECASE | re.DOTALL)
        if match:
            exp_text = match.group(1)
            # Check for work experience keywords
            exp_keywords = []
            for keyword in found_keywords:
                if keyword.lower() in exp_text.lower():
                    exp_keywords.append(keyword)
            
            # Extract job titles/companies mentioned
            job_title_patterns = []
            if isinstance(data.get('work'), list):
                for w in data['work']:
                    title = str(w.get('title', ''))
                    company = str(w.get('company', ''))
                    if title and title.lower() in exp_text.lower():
                        job_title_patterns.append(title)
                    if company and company.lower() in exp_text.lower():
                        job_title_patterns.append(company)
            
            if exp_keywords or job_title_patterns:
                experience_section.append({
                    'section': exp_text[:300] + ('...' if len(exp_text) > 300 else ''),
                    'highlighted_keywords': exp_keywords,
                    'job_titles': job_title_patterns
                })
            break
    
    # Identify Education Section
    education_section = []
    education_patterns = [
        r'education\s*[:]?\s*\n(.+?)(?=\n\n[A-Z][a-z]+\s*[:]?|\n\nSkills|$)',
        r'academic\s+qualification\s*[:]?\s*\n(.+?)(?=\n\n[A-Z][a-z]+\s*[:]?|\n\nSkills|$)',
    ]
    
    for pattern in education_patterns:
        match = re.search(pattern, resume_text, re.IGNORECASE | re.DOTALL)
        if match:
            edu_text = match.group(1)
            # Check for education keywords
            edu_keywords = []
            education_terms = []
            
            if isinstance(data.get('education'), list):
                for e in data['education']:
                    degree = str(e.get('degree', ''))
                    branch = str(e.get('branch', ''))
                    institution = str(e.get('institution', ''))
                    if degree and degree.lower() in edu_text.lower():
                        education_terms.append(degree)
                    if branch and branch.lower() in edu_text.lower():
                        education_terms.append(branch)
                    if institution and institution.lower() in edu_text.lower():
                        education_terms.append(institution)
            
            # Check for role-relevant education terms
            if any(k in normalized_title for k in ["frontend","ui","ux","designer","react","typescript","javascript"]):
                if any(k in edu_text.lower() for k in ["computer","cs","information","it","design","ui","ux"]):
                    edu_keywords.extend(["Computer Science", "IT", "Design"])
            elif any(k in normalized_title for k in ["backend","node","engineer","data","scientist"]):
                if any(k in edu_text.lower() for k in ["computer","cs","information","it","math","statistics","data"]):
                    edu_keywords.extend(["Computer Science", "IT", "Mathematics", "Data Science"])
            
            if edu_keywords or education_terms:
                education_section.append({
                    'section': edu_text[:200] + ('...' if len(edu_text) > 200 else ''),
                    'highlighted_keywords': edu_keywords,
                    'education_terms': education_terms
                })
            break
    
    return {
        'skills': skills_section,
        'experience': experience_section,
        'education': education_section,
        'keywords': keyword_contexts,
        'matched_keywords': sorted(list(set(found_keywords))),
        'resume_text_preview': resume_text[:500] + ('...' if len(resume_text) > 500 else '')
    }


# --- API ENDPOINTS ---

@app.route('/api/save_details', methods=['POST'])
def save_details():
    """Receives and saves structured application form data into the SQLite database."""
    try:
        data = request.json 
        app_id = f"MQ-{os.urandom(4).hex()}"
        job_title = data.get('jobTitle', 'Unknown Job')
        
        data_json = json.dumps(data)
        
        # Save to database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO applications (app_id, job_title, applicant_data) VALUES (?, ?, ?)",
            (app_id, job_title, data_json)
        )
        conn.commit()
        conn.close()
        
        print(f"Details saved to DB for Application ID: {app_id}")
        return jsonify({'status': 'success', 'application_id': app_id}), 200
    except Exception as e:
        print(f"Error saving details to DB: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/get_application/<app_id>', methods=['GET'])
def get_application(app_id):
    """Retrieves structured application data from the SQLite database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT applicant_data FROM applications WHERE app_id = ?", (app_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({'status': 'error', 'message': 'Application ID not found in database.'}), 404

    try:
        applicant_data = json.loads(row['applicant_data'])
        return jsonify({'status': 'success', 'application_data': applicant_data}), 200
    except json.JSONDecodeError:
        return jsonify({'status': 'error', 'message': 'Failed to decode stored application data.'}), 500


@app.route('/api/submit_application/<app_id>', methods=['POST'])
def submit_application(app_id):
    """Receives the final file upload and triggers the email confirmation."""
    
    # 1. Retrieve saved applicant data from DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT applicant_data FROM applications WHERE app_id = ?", (app_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({'status': 'error', 'message': 'Application ID not found.'}), 404
        
    applicant_data = json.loads(row['applicant_data'])

    # 2. Handle File Upload
    if 'resume' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part in the request.'}), 400

    file = request.files['resume']
    
    if file and allowed_file(file.filename):
        filename = f"{app_id}_{file.filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
    else:
        return jsonify({'status': 'error', 'message': 'File type not allowed.'}), 400

    # 3. Extract necessary details for the email
    applicant_email = applicant_data.get('communication', {}).get('email')
    applicant_name = applicant_data.get('personal', {}).get('firstName', 'Applicant')
    job_title = applicant_data.get('jobTitle', 'Unknown Job')
    
    # 4. Trigger Email Confirmation
    email_success = False
    if applicant_email:
        email_success = send_confirmation_email(applicant_email, applicant_name, job_title, app_id)

    # 5. Final response
    return jsonify({
        'status': 'complete', 
        'message': 'Application and resume saved successfully.',
        'email_sent': email_success,
        'application_id': app_id
    }), 200


def _generate_and_write_excel():
    """
    Internal: Regenerates the Excel workbook with multiple sheets from DB state.
    Sheets written:
      - All Applications (complete list)
      - Shortlisted (any interview status marked "Go")
      - No go (any interview status marked "No go")
      - Selected (Application_Status == "Selected")
      - Rejected (Final) (Application_Status == "Rejected")
    Returns absolute excel_path on success, raises on error.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch applications
    cursor.execute("SELECT app_id, job_title, applicant_data FROM applications")
    all_rows = cursor.fetchall()

    # Fetch invites (statuses)
    invites_map = {}
    try:
        c2 = conn.cursor()
        c2.execute("SELECT app_id, phone_status, inperson_status, recruiter, interviewer, source, application_status, invited_at, rsvp_status FROM invites")
        for r in c2.fetchall():
            invites_map[r['app_id']] = {
                'Recruiter': r['recruiter'] or '',
                'Interviewer': r['interviewer'] or '',
                'Source': r['source'] or '',
                'Phone_Status': r['phone_status'] or 'Pending',
                'Inperson_Status': r['inperson_status'] or 'Pending',
                'Application_Status': r['application_status'] or 'Open',
                'Invited_At': r['invited_at'] or '',
                'Rsvp_Status': r['rsvp_status'] or 'Pending'
            }
    except Exception:
        invites_map = {}
    finally:
        conn.close()

    if not all_rows:
        raise RuntimeError('No applications found in the database.')

    # Process data
    flattened_data_list = []
    for row in all_rows:
        app_id = row['app_id']
        applicant_data = json.loads(row['applicant_data']) if row['applicant_data'] else {}
        flat_row = flatten_application_data(applicant_data, app_id)
        # Enrich with job title and schedule/invite statuses
        flat_row['Job_Title'] = row['job_title']
        invite = invites_map.get(app_id, {})
        flat_row.update({
            'Recruiter': invite.get('Recruiter', ''),
            'Interviewer': invite.get('Interviewer', ''),
            'Source': invite.get('Source', ''),
            'Phone_Status': invite.get('Phone_Status', 'Pending'),
            'Inperson_Status': invite.get('Inperson_Status', 'Pending'),
            'Application_Status': invite.get('Application_Status', 'Open'),
            'Invited_At': invite.get('Invited_At', ''),
            'Rsvp_Status': invite.get('Rsvp_Status', 'Pending')
        })
        flattened_data_list.append(flat_row)

    # Create DataFrames
    df_all = pd.DataFrame(flattened_data_list)

    # Helpers to normalize status strings
    def _norm_stage(s):
        val = (s or '').strip().lower()
        if val in ('no go', 'nogo', 'no-go'): return 'No go'
        if val == 'go': return 'Go'
        return 'Pending'

    def _norm_final(s):
        val = (s or '').strip().lower()
        if val == 'selected': return 'Selected'
        if val == 'rejected': return 'Rejected'
        return (s or 'Open')

    # Shortlisted by stage statuses
    df_shortlisted = df_all[
        (df_all['Phone_Status'].apply(_norm_stage) == 'Go') |
        (df_all['Inperson_Status'].apply(_norm_stage) == 'Go')
    ].copy()

    # No-go by stage statuses
    df_nogo = df_all[
        (df_all['Phone_Status'].apply(_norm_stage) == 'No go') |
        (df_all['Inperson_Status'].apply(_norm_stage) == 'No go')
    ].copy()

    # Final outcomes from Application_Status
    df_selected = df_all[df_all['Application_Status'].apply(_norm_final) == 'Selected'].copy()
    df_rejected_final = df_all[df_all['Application_Status'].apply(_norm_final) == 'Rejected'].copy()

    # Write workbook
    excel_path = os.path.join(os.getcwd(), EXCEL_FILE)
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df_all.to_excel(writer, index=False, sheet_name='All Applications')
        df_shortlisted.to_excel(writer, index=False, sheet_name='Shortlisted')
        df_nogo.to_excel(writer, index=False, sheet_name='No go')
        df_selected.to_excel(writer, index=False, sheet_name='Selected')
        df_rejected_final.to_excel(writer, index=False, sheet_name='Rejected (Final)')

    return excel_path


@app.route('/api/export_to_excel', methods=['GET'])
def export_to_excel():
    """
    Regenerates and downloads the Excel file with all sheets. Always current.
    """
    try:
        excel_path = _generate_and_write_excel()
        return send_file(
            excel_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=EXCEL_FILE
        )
    except Exception as e:
        print(f"Error during Excel export: {e}")
        return jsonify({'status': 'error', 'message': f'Failed to generate Excel file: {str(e)}'}), 500


# --- NEW: Detailed ATS Score Breakdown Endpoint ---
@app.route('/api/score_details/<app_id>', methods=['GET', 'OPTIONS'])
def get_score_details(app_id):
    """Returns detailed ATS score breakdown for a specific application."""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    provided_key = request.headers.get('X-Recruiter-Key')
    if not RECRUITER_KEY or provided_key != RECRUITER_KEY:
        return jsonify({'status': 'error', 'message': 'Access Denied'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT app_id, job_title, applicant_data FROM applications WHERE app_id = ?", (app_id,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return jsonify({'status': 'error', 'message': 'Application ID not found'}), 404

        app_id_found = row['app_id']
        job_title = row['job_title']
        applicant_data = json.loads(row['applicant_data']) if row['applicant_data'] else {}
        job_description = applicant_data.get('jobDescription', '')

        target_prefix = f"{app_id}_"
        file_name = None
        for name in os.listdir(app.config['UPLOAD_FOLDER']):
            if name.startswith(target_prefix):
                file_name = name
                break

        if file_name:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
            score_details = simulate_ats_scoring(job_title, job_description, applicant_data, file_path, file_name, return_details=True)
        else:
            # No resume file - return basic details
            score_details = simulate_ats_scoring(job_title, job_description, applicant_data, None, None, return_details=True)
            score_details['has_resume'] = False

        score_details['job_title'] = job_title
        score_details['application_id'] = app_id_found
        score_details['has_resume'] = file_name is not None

        return jsonify({'status': 'success', 'score_details': score_details}), 200

    except Exception as e:
        print(f"Error getting score details for {app_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# --- NEW: Diagnostic endpoint to list all resume files ---
@app.route('/api/list_resume_files', methods=['GET', 'OPTIONS'])
def list_resume_files():
    """Lists all resume files in the upload folder for debugging."""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    provided_key = request.headers.get('X-Recruiter-Key')
    if not RECRUITER_KEY or provided_key != RECRUITER_KEY:
        return jsonify({'status': 'error', 'message': 'Access Denied'}), 401

    try:
        upload_folder = app.config['UPLOAD_FOLDER']
        if not os.path.isabs(upload_folder):
            upload_folder = os.path.join(os.getcwd(), upload_folder)
        
        if not os.path.exists(upload_folder):
            return jsonify({
                'status': 'error',
                'message': f'Upload folder does not exist: {upload_folder}',
                'current_directory': os.getcwd()
            }), 500
        
        files = [f for f in os.listdir(upload_folder) if os.path.isfile(os.path.join(upload_folder, f))]
        files.sort()
        
        # Extract Application IDs from filenames
        app_ids_from_files = set()
        for f in files:
            if f.startswith('MQ-') and '_' in f:
                app_id = f.split('_')[0]
                app_ids_from_files.add(app_id)
        
        return jsonify({
            'status': 'success',
            'upload_folder': upload_folder,
            'current_directory': os.getcwd(),
            'total_files': len(files),
            'files': files[:50],  # Limit to first 50 for response size
            'application_ids_found': sorted(list(app_ids_from_files))
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# --- NEW: Authenticated Resume View Endpoint (CORS Fix) ---
@app.route('/api/view_resume/<app_id>', methods=['GET', 'OPTIONS'])
def view_resume(app_id):
    """
    Retrieves the applicant's uploaded resume file from the server, restricted to recruiters.
    """
    # CORS FIX: Allow preflight OPTIONS request to pass without authentication
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    # 1. AUTHENTICATION CHECK
    provided_key = request.headers.get('X-Recruiter-Key')
    
    if not RECRUITER_KEY or provided_key != RECRUITER_KEY:
        return jsonify({'status': 'error', 'message': 'Access Denied: Invalid or missing recruiter credentials.'}), 401
    
    try:
        # 2. Look up application existence
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT app_id FROM applications WHERE app_id = ?", (app_id,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return jsonify({'status': 'error', 'message': f'Application ID {app_id} not found.'}), 404

        # 3. Determine the filename by prefix
        target_prefix = f"{app_id}_"
        file_name = None
        
        # Debug: List all files in the upload folder
        try:
            upload_folder = app.config['UPLOAD_FOLDER']
            # Ensure we're using absolute path
            if not os.path.isabs(upload_folder):
                upload_folder = os.path.join(os.getcwd(), upload_folder)
            
            # Verify folder exists
            if not os.path.exists(upload_folder):
                error_msg = f'Upload folder does not exist: {upload_folder}. Current working directory: {os.getcwd()}'
                print(f"ERROR: {error_msg}")
                return jsonify({'status': 'error', 'message': error_msg}), 500
            
            all_files = os.listdir(upload_folder)
            print(f"Looking for resume with prefix: {target_prefix}")
            print(f"Upload folder (absolute): {upload_folder}")
            print(f"Files in upload folder: {all_files}")
            
            for name in all_files:
                if name.startswith(target_prefix):
                    file_name = name
                    print(f"Found matching file: {file_name}")
                    break
            
            if not file_name:
                # Provide helpful error message with available files
                matching_files = [f for f in all_files if app_id.lower() in f.lower()]
                error_msg = f'Resume file not found for Application ID: {app_id}. '
                if matching_files:
                    error_msg += f'Found similar files: {matching_files}. '
                error_msg += f'Upload folder: {upload_folder}, Looking for prefix: {target_prefix}'
                print(f"ERROR: {error_msg}")
                return jsonify({'status': 'error', 'message': error_msg}), 404
        except Exception as folder_error:
            print(f"Error listing upload folder: {folder_error}")
            import traceback
            traceback.print_exc()
            return jsonify({'status': 'error', 'message': f'Cannot access upload folder: {str(folder_error)}'}), 500
            
        file_path = os.path.join(upload_folder, file_name)

        # 4. Determine mimetype and serve the file inline
        if file_name.lower().endswith('.pdf'):
            mimetype = 'application/pdf'
        elif file_name.lower().endswith(('.jpg', '.jpeg')):
            mimetype = 'image/jpeg'
        else:
            mimetype = 'application/octet-stream'

        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=False, 
            download_name=file_name
        )

    except Exception as e:
        print(f"Error viewing resume for {app_id}: {e}")
        return jsonify({'status': 'error', 'message': f'Failed to retrieve resume: {str(e)}'}), 500


# --- NEW: Resume Highlights Endpoint (Shows ATS Score Contributors) ---
@app.route('/api/resume_highlights/<app_id>', methods=['GET', 'OPTIONS'])
def get_resume_highlights(app_id):
    """
    Extracts text from resume PDF and returns highlighted sections that contributed to ATS score.
    Shows skills, experience, education, and keywords found in the resume.
    """
    # CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    # Authentication check
    provided_key = request.headers.get('X-Recruiter-Key')
    if not RECRUITER_KEY or provided_key != RECRUITER_KEY:
        return jsonify({'status': 'error', 'message': 'Access Denied: Invalid or missing recruiter credentials.'}), 401

    try:
        # Get application data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT app_id, job_title, applicant_data FROM applications WHERE app_id = ?", (app_id,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return jsonify({'status': 'error', 'message': 'Application ID not found'}), 404

        app_id_found = row['app_id']
        job_title = row['job_title']
        applicant_data = json.loads(row['applicant_data']) if row['applicant_data'] else {}
        job_description = applicant_data.get('jobDescription', '')

        # Find resume file
        target_prefix = f"{app_id}_"
        file_name = None
        upload_folder = app.config['UPLOAD_FOLDER']
        if not os.path.isabs(upload_folder):
            upload_folder = os.path.join(os.getcwd(), upload_folder)
        
        if not os.path.exists(upload_folder):
            return jsonify({'status': 'error', 'message': 'Upload folder does not exist'}), 500
        
        for name in os.listdir(upload_folder):
            if name.startswith(target_prefix):
                file_name = name
                break

        if not file_name:
            return jsonify({'status': 'error', 'message': 'Resume file not found'}), 404

        file_path = os.path.join(upload_folder, file_name)

        # Extract text from PDF
        if not file_name.lower().endswith('.pdf'):
            return jsonify({
                'status': 'error', 
                'message': 'Resume highlighting is only available for PDF files. Image files (JPG) are not supported for text extraction.'
            }), 400

        if not PDF_EXTRACTION_AVAILABLE:
            return jsonify({
                'status': 'error',
                'message': 'PDF extraction library not available. Please install pdfplumber or PyPDF2: pip install pdfplumber'
            }), 500

        resume_text = extract_text_from_pdf(file_path)

        if not resume_text:
            return jsonify({
                'status': 'error',
                'message': 'Could not extract text from PDF. The file may be image-based or corrupted.'
            }), 500

        # Find highlighted sections
        highlights = find_highlighted_sections(resume_text, job_title, job_description, applicant_data)

        # Get ATS score details for context
        score_details = simulate_ats_scoring(job_title, job_description, applicant_data, file_path, file_name, return_details=True)

        return jsonify({
            'status': 'success',
            'application_id': app_id_found,
            'job_title': job_title,
            'highlights': highlights,
            'ats_score': score_details.get('score', 0),
            'matched_keywords_count': len(highlights.get('matched_keywords', [])),
            'pdf_extraction_available': True
        }), 200

    except Exception as e:
        print(f"Error getting resume highlights for {app_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# --- NEW: Highlighted Resume HTML Endpoint ---
@app.route('/api/view_resume_highlighted/<app_id>', methods=['GET', 'OPTIONS'])
def view_resume_highlighted(app_id):
    """
    Returns an HTML version of the resume with highlighted keywords and sections
    that contributed to the ATS score.
    """
    # CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    # Authentication check
    provided_key = request.headers.get('X-Recruiter-Key')
    if not RECRUITER_KEY or provided_key != RECRUITER_KEY:
        return jsonify({'status': 'error', 'message': 'Access Denied: Invalid or missing recruiter credentials.'}), 401

    try:
        # Get application data
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT app_id, job_title, applicant_data FROM applications WHERE app_id = ?", (app_id,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return jsonify({'status': 'error', 'message': 'Application ID not found'}), 404

        app_id_found = row['app_id']
        job_title = row['job_title']
        applicant_data = json.loads(row['applicant_data']) if row['applicant_data'] else {}
        job_description = applicant_data.get('jobDescription', '')

        # Find resume file
        target_prefix = f"{app_id}_"
        file_name = None
        upload_folder = app.config['UPLOAD_FOLDER']
        if not os.path.isabs(upload_folder):
            upload_folder = os.path.join(os.getcwd(), upload_folder)
        
        if not os.path.exists(upload_folder):
            return jsonify({'status': 'error', 'message': 'Upload folder does not exist'}), 500
        
        for name in os.listdir(upload_folder):
            if name.startswith(target_prefix):
                file_name = name
                break

        if not file_name:
            return jsonify({'status': 'error', 'message': 'Resume file not found'}), 404

        file_path = os.path.join(upload_folder, file_name)

        # Extract text from PDF
        if not file_name.lower().endswith('.pdf'):
            return jsonify({
                'status': 'error', 
                'message': 'Highlighted view is only available for PDF files.'
            }), 400

        if not PDF_EXTRACTION_AVAILABLE:
            return jsonify({
                'status': 'error',
                'message': 'PDF extraction library not available.'
            }), 500

        resume_text = extract_text_from_pdf(file_path)

        if not resume_text:
            return jsonify({
                'status': 'error',
                'message': 'Could not extract text from PDF.'
            }), 500

        # Find highlighted sections and keywords
        highlights = find_highlighted_sections(resume_text, job_title, job_description, applicant_data)
        matched_keywords = highlights.get('matched_keywords', [])
        
        # Get ATS score
        score_details = simulate_ats_scoring(job_title, job_description, applicant_data, file_path, file_name, return_details=True)
        ats_score = score_details.get('score', 0)

        # Create highlighted HTML
        highlighted_text = highlight_text_in_resume(resume_text, matched_keywords, highlights, job_title)

        # Generate HTML page
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resume - {app_id_found} - Highlighted</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            color: #333;
        }}
        .header-info {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }}
        .info-item {{
            font-size: 14px;
            color: #666;
        }}
        .info-item strong {{
            color: #333;
        }}
        .score-badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            color: white;
            background-color: {'#28a745' if ats_score >= 80 else '#ffc107' if ats_score >= 70 else '#dc3545'};
        }}
        .resume-content {{
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            line-height: 1.8;
            white-space: pre-wrap;
            font-size: 14px;
        }}
        .highlight {{
            background-color: #ffff00;
            padding: 2px 4px;
            border-radius: 3px;
            font-weight: bold;
            color: #000;
        }}
        .highlight-skill {{
            background-color: #90EE90;
            color: #006400;
        }}
        .highlight-experience {{
            background-color: #87CEEB;
            color: #000080;
        }}
        .highlight-education {{
            background-color: #FFB6C1;
            color: #8B0000;
        }}
        .project-section {{
            background-color: #fffacd;
            padding: 10px;
            margin: 10px 0;
            border-left: 4px solid #ffd700;
            border-radius: 4px;
        }}
        .legend {{
            background: white;
            padding: 15px;
            margin-top: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .legend h3 {{
            margin-top: 0;
            font-size: 16px;
        }}
        .legend-item {{
            display: inline-block;
            margin: 5px 10px;
            font-size: 12px;
        }}
        .legend-color {{
            display: inline-block;
            width: 20px;
            height: 20px;
            border-radius: 3px;
            vertical-align: middle;
            margin-right: 5px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Resume - Highlighted View</h1>
        <div class="header-info">
            <div class="info-item"><strong>Application ID:</strong> {app_id_found}</div>
            <div class="info-item"><strong>Job Title:</strong> {job_title}</div>
            <div class="info-item"><strong>ATS Score:</strong> <span class="score-badge">{ats_score}%</span></div>
            <div class="info-item"><strong>Matched Keywords:</strong> {len(matched_keywords)}</div>
        </div>
    </div>
    
    <div class="resume-content">
{highlighted_text}
    </div>
    
    <div class="legend">
        <h3>📌 Highlight Legend:</h3>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #ffff00;"></span>
            <strong>Keywords:</strong> General matched keywords
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #90EE90;"></span>
            <strong>Skills:</strong> Found in skills section
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #87CEEB;"></span>
            <strong>Experience:</strong> Found in experience section
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #FFB6C1;"></span>
            <strong>Education:</strong> Found in education section
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #fffacd; border-left: 4px solid #ffd700;"></span>
            <strong>Projects:</strong> Relevant project sections
        </div>
    </div>
</body>
</html>
        """

        from flask import Response
        return Response(html_content, mimetype='text/html')

    except Exception as e:
        print(f"Error generating highlighted resume for {app_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


def highlight_text_in_resume(resume_text, matched_keywords, highlights, job_title):
    """
    Highlights keywords in resume text with different colors based on section.
    Also highlights project sections relevant to the job role.
    Returns HTML-formatted text with highlights.
    """
    import html
    
    # Escape HTML to prevent XSS
    highlighted_text = html.escape(resume_text)
    
    # Get keywords by section
    skill_keywords = set()
    exp_keywords = set()
    edu_keywords = set()
    
    if highlights.get('skills'):
        for skill in highlights['skills']:
            if skill.get('highlighted_keywords'):
                skill_keywords.update([kw.lower() for kw in skill['highlighted_keywords']])
    
    if highlights.get('experience'):
        for exp in highlights['experience']:
            if exp.get('highlighted_keywords'):
                exp_keywords.update([kw.lower() for kw in exp['highlighted_keywords']])
    
    if highlights.get('education'):
        for edu in highlights['education']:
            if edu.get('highlighted_keywords'):
                edu_keywords.update([kw.lower() for kw in edu['highlighted_keywords']])
    
    # Identify project sections based on job title (BEFORE HTML escaping)
    normalized_title = job_title.lower()
    project_keywords = []
    
    if 'data' in normalized_title or 'scientist' in normalized_title:
        project_keywords = ['python', 'machine learning', 'ml', 'data science', 'data analysis', 'pandas', 'numpy', 'scikit-learn', 'tensorflow', 'pytorch', 'project', 'model', 'dataset', 'prediction', 'algorithm']
    elif 'frontend' in normalized_title or 'react' in normalized_title:
        project_keywords = ['react', 'javascript', 'typescript', 'frontend', 'ui', 'ux', 'project', 'application', 'component', 'redux']
    elif 'backend' in normalized_title or 'node' in normalized_title:
        project_keywords = ['node', 'express', 'api', 'backend', 'server', 'database', 'project', 'microservice', 'rest', 'postgres', 'mongodb']
    elif 'designer' in normalized_title or 'ux' in normalized_title:
        project_keywords = ['design', 'ui', 'ux', 'figma', 'sketch', 'prototype', 'project', 'wireframe', 'user experience']
    
    # Find project sections in original text
    import re
    project_patterns = [
        r'(project[s]?[:]?\s*\n.*?)(?=\n\n|\n[A-Z][a-z]+|$)',
        r'(key\s+project[s]?[:]?\s*\n.*?)(?=\n\n|\n[A-Z][a-z]+|$)',
        r'(notable\s+project[s]?[:]?\s*\n.*?)(?=\n\n|\n[A-Z][a-z]+|$)',
        r'(portfolio\s+project[s]?[:]?\s*\n.*?)(?=\n\n|\n[A-Z][a-z]+|$)',
    ]
    
    project_markers = []
    for pattern in project_patterns:
        matches = list(re.finditer(pattern, resume_text, re.IGNORECASE | re.DOTALL))
        for match in matches:
            project_text = match.group(1)
            project_lower = project_text.lower()
            has_relevant_keyword = any(kw.lower() in project_lower for kw in matched_keywords + project_keywords)
            
            if has_relevant_keyword:
                project_markers.append((match.start(), match.end(), project_text))
                break
    
    # Escape HTML first
    highlighted_text = html.escape(resume_text)
    
    # Mark project sections (reverse order to preserve indices after replacement)
    for start, end, project_text in reversed(project_markers):
        escaped_project = html.escape(project_text)
        # Find the escaped version in highlighted_text
        escaped_start = highlighted_text.find(escaped_project)
        if escaped_start != -1:
            highlighted_section = f'<div class="project-section">{escaped_project}</div>'
            highlighted_text = highlighted_text[:escaped_start] + highlighted_section + highlighted_text[escaped_start + len(escaped_project):]
    
    # Highlight keywords with word boundaries (case-insensitive)
    all_keywords = [kw.lower() for kw in matched_keywords]
    
    # Sort by length (longest first) to avoid partial matches
    all_keywords.sort(key=len, reverse=True)
    
    for keyword in all_keywords:
        if not keyword or len(keyword) < 2:
            continue
            
        # Determine highlight class based on section
        highlight_class = 'highlight'
        if keyword in skill_keywords:
            highlight_class = 'highlight-skill'
        elif keyword in exp_keywords:
            highlight_class = 'highlight-experience'
        elif keyword in edu_keywords:
            highlight_class = 'highlight-education'
        
        # Case-insensitive replacement with word boundaries
        # Highlight keywords even inside project sections
        pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
        
        def replace_func(match):
            matched_text = match.group(0)
            # Check if already inside a highlight span (avoid double highlighting)
            before_match = highlighted_text[max(0, match.start()-100):match.start()]
            # If we're inside a project div but not already highlighted, still highlight
            if '<div class="project-section">' in before_match and '</span>' not in before_match[-50:]:
                return f'<span class="{highlight_class}">{matched_text}</span>'
            # If already highlighted, skip
            if '</span>' in before_match[-50:]:
                return matched_text
            return f'<span class="{highlight_class}">{matched_text}</span>'
        
        highlighted_text = pattern.sub(replace_func, highlighted_text)
    
    return highlighted_text


# --- NEW: Authenticated Filtered Scores Endpoint (CORS Fix and Bug Fix) ---
@app.route('/api/filtered_scores', methods=['GET', 'OPTIONS'])
def get_filtered_scores():
    """
    Retrieves all applications, calculates ATS scores, and filters them 
    to return only those with a score > 60, sorted by score.
    """
    # CORS FIX: Allow preflight OPTIONS request to pass without authentication
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    # 1. AUTHENTICATION CHECK
    provided_key = request.headers.get('X-Recruiter-Key')
    
    if not RECRUITER_KEY or provided_key != RECRUITER_KEY:
        return jsonify({'status': 'error', 'message': 'Access Denied: Invalid or missing recruiter credentials.'}), 401
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT app_id, job_title, applicant_data FROM applications")
        all_rows = cursor.fetchall() 
        conn.close()
        
        if not all_rows:
            return jsonify({'status': 'info', 'message': 'No applications found.'}), 200

        # --- Processing and Scoring ---
        processed_results = []
        for row in all_rows: 
            app_id = row['app_id']
            job_title = row['job_title']
            applicant_data = json.loads(row['applicant_data']) if row['applicant_data'] else {}
            job_description = applicant_data.get('jobDescription', '')
            
            target_prefix = f"{app_id}_"
            file_name = None
            
            # Using global 'app' variable to access UPLOAD_FOLDER
            for name in os.listdir(app.config['UPLOAD_FOLDER']):
                if name.startswith(target_prefix):
                    file_name = name
                    break
            
            score = 0
            
            if file_name:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
                score = simulate_ats_scoring(job_title, job_description, applicant_data, file_path, file_name)
                
            # Only include results if the score is > 60 AND a file was found
            if file_name and score > 60:
                processed_results.append({
                    'App_ID': app_id,
                    'Job_Title': job_title,
                    'Resume_File': file_name,
                    'ATS_Score': score
                })

        # Sort the results by score (descending)
        processed_results.sort(key=lambda x: x['ATS_Score'], reverse=True)
        
        return jsonify({
            'status': 'success',
            'filtered_applications': processed_results
        }), 200

    except Exception as e:
        print(f"Error during filtered scoring: {e}")
        return jsonify({'status': 'error', 'message': f'Failed to retrieve filtered data: {str(e)}'}), 500
# --- NEW: Authenticated All Scored Applications Endpoint ---
@app.route('/api/scored_applications', methods=['GET', 'OPTIONS'])
def get_all_scored_applications():
    """
    Returns ALL applications with computed ATS scores (no filtering).
    Includes entries without resumes with score 0 and Resume_File as null.
    """
    # CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    provided_key = request.headers.get('X-Recruiter-Key')
    if not RECRUITER_KEY or provided_key != RECRUITER_KEY:
        return jsonify({'status': 'error', 'message': 'Access Denied: Invalid or missing recruiter credentials.'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT app_id, job_title, applicant_data FROM applications")
        all_rows = cursor.fetchall()
        conn.close()

        results = []
        for row in all_rows:
            app_id = row['app_id']
            job_title = row['job_title']
            applicant_data = json.loads(row['applicant_data']) if row['applicant_data'] else {}
            job_description = applicant_data.get('jobDescription', '')

            target_prefix = f"{app_id}_"
            file_name = None
            for name in os.listdir(app.config['UPLOAD_FOLDER']):
                if name.startswith(target_prefix):
                    file_name = name
                    break

            if file_name:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
                score = simulate_ats_scoring(job_title, job_description, applicant_data, file_path, file_name)
            else:
                score = 0

            results.append({
                'App_ID': app_id,
                'Job_Title': job_title,
                'Resume_File': file_name,
                'ATS_Score': score
            })

        # Sort by score descending for convenience
        results.sort(key=lambda x: x['ATS_Score'], reverse=True)

        return jsonify({'status': 'success', 'applications': results}), 200

    except Exception as e:
        print(f"Error during scoring all applications: {e}")
        return jsonify({'status': 'error', 'message': f'Failed to retrieve data: {str(e)}'}), 500

# --- NEW: Authenticated Interview Invite Endpoint (Individual Invite) ---
@app.route('/api/invite_applicant/<app_id>', methods=['POST', 'OPTIONS'])
def invite_applicant(app_id):
    """Retrieves applicant details and sends the interview invite email."""
    # CORS FIX
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    # 1. AUTHENTICATION CHECK
    provided_key = request.headers.get('X-Recruiter-Key')
    if not RECRUITER_KEY or provided_key != RECRUITER_KEY:
        return jsonify({'status': 'error', 'message': 'Access Denied: Invalid credentials.'}), 401

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT applicant_data, job_title FROM applications WHERE app_id = ?", (app_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({'status': 'error', 'message': 'Application ID not found.'}), 404
    
    applicant_data = json.loads(row['applicant_data'])
    job_title = row['job_title']
    
    applicant_email = applicant_data.get('communication', {}).get('email')
    applicant_name = applicant_data.get('personal', {}).get('firstName', 'Applicant')

    if not applicant_email:
        return jsonify({'status': 'error', 'message': 'Applicant email address not found.'}), 400

    if send_interview_invite(applicant_email, applicant_name, job_title):
        # Record/Upsert into invites schedule table
        recruiter_name = request.headers.get('X-Recruiter-Name', 'Recruiter')
        source = (applicant_data.get('source') or applicant_data.get('referralSource') or '').strip()
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO invites (app_id, recruiter, interviewer, job_title, source, resume_status, phone_status, inperson_status, invited_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(app_id) DO UPDATE SET
                    recruiter=excluded.recruiter,
                    job_title=excluded.job_title
            ''', (app_id, recruiter_name, '', job_title, source, 'Go', 'Pending', 'Pending'))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Warning: failed to write invite record for {app_id}: {e}")
        return jsonify({'status': 'success', 'message': f'Invitation sent to {applicant_name}'}), 200
    else:
        return jsonify({'status': 'error', 'message': 'Failed to send email via SMTP.'}), 500


# --- NEW: Authenticated Recruiter Schedule APIs ---
@app.route('/api/schedule', methods=['GET', 'OPTIONS'])
def get_schedule():
    """Returns all invited candidates with scheduling/status info."""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    provided_key = request.headers.get('X-Recruiter-Key')
    if not RECRUITER_KEY or provided_key != RECRUITER_KEY:
        return jsonify({'status': 'error', 'message': 'Access Denied: Invalid or missing recruiter credentials.'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.app_id,
                   COALESCE(i.recruiter, '') AS recruiter,
                   COALESCE(i.interviewer, '') AS interviewer,
                   COALESCE(i.job_title, a.job_title) AS job_title,
                   COALESCE(i.source, '') AS source,
                   COALESCE(i.phone_status, 'Pending') AS phone_status,
                   COALESCE(i.inperson_status, 'Pending') AS inperson_status,
                   COALESCE(i.invited_at, '') AS invited_at,
                   COALESCE(i.application_status, 'Open') AS application_status,
                   COALESCE(i.rsvp_status, 'Pending') AS rsvp_status
            FROM applications a
            LEFT JOIN invites i ON i.app_id = a.app_id
            ORDER BY COALESCE(i.invited_at, '') DESC
        ''')
        rows = cursor.fetchall()
        # Also fetch applicant email for direct mailto links
        items = []
        for r in rows:
            email_value = ''
            try:
                c2 = conn.cursor()
                c2.execute("SELECT applicant_data FROM applications WHERE app_id = ?", (r['app_id'],))
                arow = c2.fetchone()
                if arow and arow['applicant_data']:
                    adata = json.loads(arow['applicant_data'])
                    email_value = (adata.get('communication') or {}).get('email') or ''
            except Exception as _e:
                email_value = ''

            items.append({
                'App_ID': r['app_id'],
                'Recruiter': r['recruiter'],
                'Interviewer': r['interviewer'],
                'Job_Title': r['job_title'],
                'Source': r['source'],
                'Phone_Status': r['phone_status'],
                'Inperson_Status': r['inperson_status'],
                'Invited_At': r['invited_at'],
                'Application_Status': r['application_status'],
                'Rsvp_Status': r['rsvp_status'],
                'Email': email_value
            })

        conn.close()

        return jsonify({'status': 'success', 'schedule': items}), 200
    except Exception as e:
        print(f"Error retrieving schedule: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to load schedule'}), 500


@app.route('/api/schedule/<app_id>', methods=['PATCH', 'OPTIONS'])
@cross_origin(headers=['Content-Type', 'X-Recruiter-Key'], methods=['PATCH', 'OPTIONS'])
def update_schedule(app_id):
    """Updates schedule fields like recruiter, interviewer or status columns."""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    provided_key = request.headers.get('X-Recruiter-Key')
    if not RECRUITER_KEY or provided_key != RECRUITER_KEY:
        return jsonify({'status': 'error', 'message': 'Access Denied: Invalid or missing recruiter credentials.'}), 401

    try:
        payload = request.json or {}
        fields = []
        values = []
        
        # Helper function to normalize status values
        def normalize_status(s):
            if not s:
                return None
            val = str(s).strip().lower()
            if val in ('no go', 'nogo', 'no-go'):
                return 'No go'
            if val == 'go':
                return 'Go'
            return s  # Keep original for Pending or other values
        
        # Check if phone_status or inperson_status is being set to "No go"
        # or if either is already "No go" in the database
        phone_status_value = normalize_status(payload.get('phone_status'))
        inperson_status_value = normalize_status(payload.get('inperson_status'))
        
        # Auto-update application_status based on interview statuses
        # Priority: Rejected (if either is "No go") > Selected (if both are "Go")
        should_auto_reject = False
        should_auto_select = False
        if 'application_status' not in payload:
            # Check current statuses from database to determine final state
            conn_check = get_db_connection()
            cursor_check = conn_check.cursor()
            cursor_check.execute("SELECT phone_status, inperson_status FROM invites WHERE app_id = ?", (app_id,))
            existing_row = cursor_check.fetchone()
            conn_check.close()
            
            # Determine the final statuses after update
            final_phone = phone_status_value if 'phone_status' in payload else (normalize_status(existing_row['phone_status']) if existing_row else None)
            final_inperson = inperson_status_value if 'inperson_status' in payload else (normalize_status(existing_row['inperson_status']) if existing_row else None)
            
            # Auto-reject if either final status is "No go" (highest priority)
            if final_phone == 'No go' or final_inperson == 'No go':
                should_auto_reject = True
            # Auto-select if both final statuses are "Go"
            elif final_phone == 'Go' and final_inperson == 'Go':
                should_auto_select = True
        
        for key, column in {
            'recruiter': 'recruiter',
            'interviewer': 'interviewer',
            'source': 'source',
            'phone_status': 'phone_status',
            'inperson_status': 'inperson_status',
            'application_status': 'application_status'
        }.items():
            if key in payload:
                # Normalize status values for phone_status and inperson_status
                if key in ('phone_status', 'inperson_status'):
                    normalized = normalize_status(payload[key])
                    fields.append(f"{column} = ?")
                    values.append(normalized)
                else:
                    fields.append(f"{column} = ?")
                    values.append(payload[key])
        
        # Add application_status based on auto-update logic
        # Priority: Rejected (if either is "No go") > Selected (if both are "Go")
        if should_auto_reject:
            # Only add if not already in the update list
            if 'application_status' not in payload:
                fields.append("application_status = ?")
                values.append('Rejected')
        elif should_auto_select:
            # Only add if not already in the update list
            if 'application_status' not in payload:
                fields.append("application_status = ?")
                values.append('Selected')

        if not fields:
            return jsonify({'status': 'error', 'message': 'No updatable fields provided'}), 400

        values.append(app_id)
        conn = get_db_connection()
        cursor = conn.cursor()
        # Ensure row exists for this app_id
        cursor.execute("INSERT OR IGNORE INTO invites (app_id, recruiter, interviewer, job_title, source, resume_status, phone_status, inperson_status, invited_at, application_status) VALUES (?, '', '', (SELECT job_title FROM applications WHERE app_id = ?), '', 'Pending', 'Pending', 'Pending', datetime('now'), 'Open')", (app_id, app_id))
        cursor.execute(f"UPDATE invites SET {', '.join(fields)} WHERE app_id = ?", values)
        conn.commit()
        updated = cursor.rowcount
        conn.close()
        if updated == 0:
            return jsonify({'status': 'error', 'message': 'Invite not found'}), 404
        # Best-effort: regenerate Excel workbook so Selected/Rejected sheets stay updated
        try:
            _generate_and_write_excel()
        except Exception as _e:
            print(f"Warning: failed to auto-regenerate Excel after schedule update: {_e}")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f"Error updating schedule {app_id}: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to update schedule'}), 500


# --- NEW: Send Status Email Endpoint ---
@app.route('/api/send_status_email/<app_id>', methods=['POST', 'OPTIONS'])
@cross_origin(headers=['Content-Type', 'X-Recruiter-Key'], methods=['POST', 'OPTIONS'])
def send_status_email_endpoint(app_id):
    """Sends a status email with interview details and confirmation request."""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    provided_key = request.headers.get('X-Recruiter-Key')
    if not RECRUITER_KEY or provided_key != RECRUITER_KEY:
        return jsonify({'status': 'error', 'message': 'Access Denied: Invalid or missing recruiter credentials.'}), 401

    try:
        payload = request.json or {}
        interview_date = payload.get('interview_date')
        interview_time = payload.get('interview_time')
        process_status = payload.get('process_status')
        additional_notes = payload.get('additional_notes', '')

        if not interview_date or not interview_time or not process_status:
            return jsonify({'status': 'error', 'message': 'Missing required fields: interview_date, interview_time, process_status'}), 400

        # Get applicant details
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT applicant_data, job_title FROM applications WHERE app_id = ?", (app_id,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return jsonify({'status': 'error', 'message': 'Application ID not found.'}), 404

        applicant_data = json.loads(row['applicant_data'])
        job_title = row['job_title']
        applicant_email = applicant_data.get('communication', {}).get('email')
        applicant_name = applicant_data.get('personal', {}).get('firstName', 'Applicant')

        if not applicant_email:
            return jsonify({'status': 'error', 'message': 'Applicant email address not found.'}), 400

        # Ensure RSVP token (create if missing)
        token = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            # Ensure invites row
            cursor.execute("INSERT OR IGNORE INTO invites (app_id, recruiter, interviewer, job_title, source, resume_status, phone_status, inperson_status, invited_at, application_status) VALUES (?, '', '', ?, '', 'Pending', 'Pending', 'Pending', datetime('now'), 'Open')", (app_id, job_title))
            # Try fetch token
            cursor.execute("SELECT rsvp_token FROM invites WHERE app_id = ?", (app_id,))
            row = cursor.fetchone()
            token = (row['rsvp_token'] if row else None)
            if not token:
                token = os.urandom(16).hex()
                cursor.execute("UPDATE invites SET rsvp_token = ?, invited_at = datetime('now') WHERE app_id = ?", (token, app_id))
            conn.commit()
            conn.close()
        except Exception as _e:
            print(f"Warning: failed to generate RSVP token for {app_id}: {_e}")
            token = os.urandom(16).hex()

        # Send email (inject token into body template)
        if send_status_email(applicant_email, applicant_name, job_title, app_id, process_status, interview_date, interview_time, additional_notes, rsvp_token=token):
            return jsonify({
                'status': 'success',
                'message': f'Status email sent successfully to {applicant_name}',
                'applicant_name': applicant_name
            }), 200
        else:
            return jsonify({'status': 'error', 'message': 'Failed to send email via SMTP.'}), 500

    except Exception as e:
        print(f"Error sending status email for {app_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# --- NEW: Get Applicant Email Endpoint ---
@app.route('/api/get_applicant_email/<app_id>', methods=['GET', 'OPTIONS'])
@cross_origin(headers=['X-Recruiter-Key'], methods=['GET', 'OPTIONS'])
def get_applicant_email(app_id):
    """Returns applicant email address for reply email functionality."""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    provided_key = request.headers.get('X-Recruiter-Key')
    if not RECRUITER_KEY or provided_key != RECRUITER_KEY:
        return jsonify({'status': 'error', 'message': 'Access Denied: Invalid or missing recruiter credentials.'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT applicant_data FROM applications WHERE app_id = ?", (app_id,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return jsonify({'status': 'error', 'message': 'Application ID not found.'}), 404

        applicant_data = json.loads(row['applicant_data'])
        applicant_email = applicant_data.get('communication', {}).get('email')

        if not applicant_email:
            return jsonify({'status': 'error', 'message': 'Applicant email address not found.'}), 404

        return jsonify({
            'status': 'success',
            'email': applicant_email
        }), 200

    except Exception as e:
        print(f"Error getting applicant email for {app_id}: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# --- NEW: Public RSVP endpoint for applicants ---
@app.route('/rsvp/<token>', methods=['GET'])
def handle_rsvp(token):
    """Records RSVP response and shows confirmation page."""
    response_value = (request.args.get('response') or '').strip().lower()
    if response_value not in {'accept', 'decline'}:
        response_value = 'unknown'

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT app_id FROM invites WHERE rsvp_token = ?", (token,))
        row = cursor.fetchone()
        if not row:
            return '<h3>Invalid or expired RSVP link.</h3>', 404
        app_id = row['app_id']
        # Map friendly status
        status = 'Accepted' if response_value == 'accept' else ('Declined' if response_value == 'decline' else 'Unknown')
        cursor.execute("UPDATE invites SET rsvp_status = ?, rsvp_response_at = datetime('now') WHERE app_id = ?", (status, app_id))
        conn.commit()
        conn.close()

        html = f"""
        <!DOCTYPE html>
        <html><head><meta charset='utf-8'>
        <title>Thank you</title>
        <style>body{{font-family:Arial;margin:40px}}.box{{padding:20px;border-radius:8px;background:#f5f5f5;max-width:640px}}</style>
        </head><body>
        <div class='box'>
          <h2>Thank you for your response.</h2>
          <p>Application ID: {app_id}</p>
          <p>Status recorded: <strong>{status}</strong></p>
        </div>
        </body></html>
        """
        from flask import Response
        return Response(html, mimetype='text/html')
    except Exception as e:
        print(f"Error handling RSVP for token {token}: {e}")
        return '<h3>Sorry, we could not record your response at this time.</h3>', 500


if __name__ == '__main__':
    # Get port from environment variable (for deployment platforms like Heroku, Railway, etc.)
    port = int(os.getenv('PORT', 5000))
    # Only run in debug mode if explicitly set in environment
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=port)