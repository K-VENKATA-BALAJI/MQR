// --- Data Structure for Job Details (used in details.html) ---
const jobData = {
    frontend: {
        title: "Senior Frontend Developer",
        summary: "Join our core engineering team to build scalable and highly responsive user interfaces using modern frameworks like React and TypeScript. You will be instrumental in setting architectural standards.",
        eligibility: [
            "Bachelor's degree in Computer Science or related field.",
            "Minimum 0-1 years of professional experience in frontend development.",
            "Expertise in React, Redux, and modern JavaScript (ES6+).",
            "Strong understanding of RESTful APIs and state management."
        ],
        responsibilities: [
            "Design, develop, and maintain high-quality user interfaces.",
            "Collaborate with UX/UI designers and backend engineers.",
            "Ensure cross-browser compatibility and optimize application performance.",
            "Mentor junior developers and participate in code reviews."
        ]
    },
    backend: {
        title: "Backend Engineer (Node.js)",
        summary: "We are looking for a skilled Backend Engineer to design and implement robust, high-performance APIs and microservices using Node.js and modern database technologies.",
        eligibility: [
            "Master's or Bachelor's degree in Engineering or Computer Science.",
            "0-1 years experience with Node.js and Express.",
            "Proficiency with relational (PostgreSQL) and NoSQL (MongoDB) databases.",
            "Experience with cloud services (AWS, Azure, or GCP)."
        ],
        responsibilities: [
            "Build and maintain secure, scalable RESTful APIs.",
            "Manage and optimize database schema and performance.",
            "Write comprehensive unit and integration tests.",
            "Participate in deployment and monitoring of production services."
        ]
    },
    designer: {
        title: "UX/UI Designer",
        summary: "As a UX/UI Designer, you will be responsible for defining and delivering the best online user experience, ensuring our product is intuitive and visually appealing.",
        eligibility: [
            "Proven experience as a UX/UI Designer or similar role.",
            "Strong portfolio demonstrating user-centered design principles.",
            "Proficiency in design tools (e.g., Figma, Sketch).",
            "Knowledge of HTML/CSS is a plus."
        ],
        responsibilities: [
            "Create wireframes, storyboards, user flows, and site maps.",
            "Conduct user research and evaluate user feedback.",
            "Design graphical elements, assets, and design systems.",
            "Work closely with product managers and engineers."
        ]
    },
    datascientist: {
        title: "Data Scientist",
        summary: "Lead the development and implementation of advanced statistical models and machine learning algorithms to drive business strategy and product optimization.",
        eligibility: [
            "Master's or Ph.D. in a quantitative field (Statistics, Math, CS).",
            "Minimum 0-1 years of experience building and deploying ML models.",
            "Expertise in Python (Pandas, NumPy, Scikit-learn) and SQL.",
            "Proven ability to translate complex data into actionable insights."
        ],
        responsibilities: [
            "Design and validate predictive and prescriptive models.",
            "Conduct A/B testing and interpret results to improve features.",
            "Clean, transform, and manage large, complex datasets.",
            "Present findings and recommendations to executive stakeholders."
        ]
    },
    productmanager: {
        title: "Product Manager",
        summary: "Own the vision, strategy, and roadmap for our flagship product line. You will bridge the gap between business goals, customer needs, and technical feasibility.",
        eligibility: [
            "Bachelor's degree; MBA or technical degree is a plus.",
            "5+ years experience in B2B SaaS product management.",
            "Strong analytical skills and experience with user story mapping.",
            "Demonstrated ability to manage product lifecycle from conception to launch."
        ],
        responsibilities: [
            "Define product requirements and acceptance criteria.",
            "Manage and prioritize the product backlog for the engineering team.",
            "Engage with customers and market analysts to identify opportunities.",
            "Track key performance indicators (KPIs) to measure product success."
        ]
    },
    marketing: {
        title: "Marketing Specialist",
        summary: "Develop and execute multi-channel marketing campaigns focused on demand generation and brand awareness. Focus on digital channels including SEO, SEM, and social media.",
        eligibility: [
            "Bachelor's degree in Marketing, Communications, or related field.",
            "3+ years experience managing digital marketing campaigns.",
            "Proficiency with marketing automation platforms (e.g., HubSpot, Marketo).",
            "Knowledge of Google Analytics and SEO best practices."
        ],
        responsibilities: [
            "Create and optimize content for blogs, emails, and landing pages.",
            "Monitor and report on campaign performance and ROI.",
            "Manage paid advertising budgets (Google Ads, social ads).",
            "Coordinate with sales and product teams for launch announcements."
        ]
    }
};

let currentSelectedJobKey = '';

// --- CUSTOM DROPDOWN LOGIC (for details.html) ---

function toggleDropdown() {
    const options = document.getElementById('custom-job-options');
    options.classList.toggle('hidden');
}

function selectJob(jobKey, element) {
    currentSelectedJobKey = jobKey;
    const display = document.getElementById('custom-job-display');
    const options = document.getElementById('custom-job-options');
    const allOptions = options.querySelectorAll('li');

    display.textContent = element.textContent;
    options.classList.add('hidden');

    allOptions.forEach(li => li.classList.remove('selected'));
    element.classList.add('selected');

    // Save job title and description to localStorage for later use in backend submission
    const job = jobData[jobKey];
    localStorage.setItem('selected_job_title', job.title);
    const description = [
        job.summary,
        ...(job.eligibility || []),
        ...(job.responsibilities || [])
    ].join(' ');
    localStorage.setItem('selected_job_description', description);
    
    updateJobDetails(jobKey);
}

function handleKeydown(event) {
    const options = document.getElementById('custom-job-options');
    if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggleDropdown();
    }
    if (event.key === 'Escape') {
        options.classList.add('hidden');
    }
}

// Close dropdown if user clicks outside
document.addEventListener('click', function(event) {
    const container = document.querySelector('.custom-select-container');
    const options = document.getElementById('custom-job-options');
    if (container && !container.contains(event.target)) {
        options.classList.add('hidden');
    }
});


// --- Logic for Page 1: Dynamic Content Update ---

function updateJobDetails(selectedJobKey) {
    const detailsDiv = document.getElementById('job-details');
    const nextBtn = document.getElementById('next-btn');

    if (!selectedJobKey) {
        detailsDiv.classList.add('hidden');
        nextBtn.classList.add('hidden');
        return;
    }

    const job = jobData[selectedJobKey];
    
    document.getElementById('job-title').textContent = job.title;
    document.getElementById('position-summary').textContent = job.summary;

    const eligibilityList = document.getElementById('eligibility-list');
    eligibilityList.innerHTML = job.eligibility.map(item => `<li>${item}</li>`).join('');

    const responsibilitiesList = document.getElementById('responsibilities-list');
    responsibilitiesList.innerHTML = job.responsibilities.map(item => `<li>${item}</li>`).join('');
    
    detailsDiv.classList.remove('hidden');
    nextBtn.classList.remove('hidden');
}


// --- Logic for Page 3 (upload.html): Resume Upload Validation (FINAL FIX WITH TIMEOUT) ---

function displayFileInfo(input) {
    const confirmationDiv = document.getElementById('file-confirmation');
    const fileNameSpan = document.getElementById('file-name');
    const submitBtn = document.getElementById('submit-btn');

    confirmationDiv.style.display = 'none';
    submitBtn.disabled = true;

    // Use a setTimeout to give the browser a moment to fully register the file data
    setTimeout(() => {
        const file = input.files[0];
        
        if (file) {
            const validMimeTypes = [
                'application/pdf', 
                'application/x-pdf', 
                'application/acrobat', 
                'image/jpeg', 
                'image/jpg',
                'image/pjpeg'
            ];
            
            const fileType = file.type.toLowerCase();
            const fileName = file.name.toLowerCase();

            // Check 1: Validate by MIME type
            let isFileValid = validMimeTypes.includes(fileType);
            
            // Check 2: FALLBACK VALIDATION by file extension
            if (!isFileValid) {
                if (fileName.endsWith('.pdf') || fileName.endsWith('.jpg') || fileName.endsWith('.jpeg')) {
                    isFileValid = true;
                }
            }

            if (isFileValid) {
                fileNameSpan.textContent = file.name;
                confirmationDiv.style.display = 'block';
                submitBtn.disabled = false;
            } else {
                alert(`Invalid file type: ${file.name}. Please upload a .pdf or .jpg file.`);
                input.value = ''; 
            }
        } 
    }, 50); // 50 milliseconds delay
}