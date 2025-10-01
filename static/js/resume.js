async function handleResumeUpload(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    const statusDiv = document.getElementById('uploadStatus');
    
    try {
        statusDiv.innerHTML = 'Uploading and parsing resume...';
        statusDiv.className = 'alert alert-info';
        statusDiv.style.display = 'block';
        
        const response = await fetch('/api/resume/parse', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Store resume ID
            localStorage.setItem('currentResumeId', result.resume_id);
            
            // Display parsed data
            displayParsedResume(result.parsed_data);
            
            // Show success message
            statusDiv.innerHTML = 'Resume parsed successfully!';
            statusDiv.className = 'alert alert-success';
            
            // Enable optimization features
            enableOptimizationFeatures();
        } else {
            statusDiv.innerHTML = `Error: ${result.error}`;
            statusDiv.className = 'alert alert-danger';
        }
    } catch (error) {
        console.error('Upload error:', error);
        statusDiv.innerHTML = 'Failed to upload and parse resume';
        statusDiv.className = 'alert alert-danger';
    }
}

function displayParsedResume(data) {
    const container = document.getElementById('parsedResume');
    container.innerHTML = `
        <div class="card mb-4">
            <div class="card-body">
                <h3 class="card-title">${data.personal_info.full_name}</h3>
                <p class="text-muted">${data.personal_info.current_title}</p>
                
                <div class="section">
                    <h4>Professional Summary</h4>
                    <p>${data.sections.summary}</p>
                </div>
                
                <div class="section">
                    <h4>Experience</h4>
                    ${formatExperience(data.sections.experience)}
                </div>
                
                <div class="section">
                    <h4>Skills</h4>
                    ${formatSkills(data.sections.skills)}
                </div>
                
                <div class="section">
                    <h4>Education</h4>
                    ${formatEducation(data.sections.education)}
                </div>
            </div>
        </div>
    `;
    container.style.display = 'block';
}